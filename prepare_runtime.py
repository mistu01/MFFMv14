#!/usr/bin/env python3
"""Build the MFFM Runtime python.tar.xz payloads (shared Python + fontTools).

Downloads a pinned, statically-linked CPython (musl) from python-build-standalone
for each supported Android ABI, strips the binary, trims the standard library to
the subset fontTools needs, installs the pure-python fontTools wheel, and writes
runtime-template/runtime/<abi>/python.tar.xz plus the matching manifest.json SHA
pins. Run this before build_runtime.py.

Supported ABIs (musl-static runs on Android's Linux kernel without Termux):
  aarch64  (arm64-v8a)  -> aarch64-unknown-linux-musl
  x64      (x86_64)     -> x86_64-unknown-linux-musl
armv7/x86 have no musl or android build in python-build-standalone, so the
runtime falls back to the Termux pip bootstrap for those devices at flash time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = ROOT / "runtime-template" / "runtime"
MANIFEST_PATH = ROOT / "runtime-template" / "manifest.json"

# Supply-chain pins (mirrors zipsigner_auto.py's approach). Bump together.
PYTHON_RELEASE_TAG = "20260814"
PYTHON_VERSION = "3.11.16"
PYTHON_ABI_TARGET = {
    "aarch64": "aarch64-unknown-linux-musl",
    "x64": "x86_64-unknown-linux-musl",
}
PYTHON_VARIANT = "lto+static-full"
PYTHON_RELEASE_BASE = "https://github.com/astral-sh/python-build-standalone/releases/download"

# Pure-python fontTools wheel (no C accelerator, works on static musl python).
FONTTOOLS_VERSION = "4.64.0"
FONTTOOLS_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/82/f8/7188153c4b265c899cd035de6a062677d51f67118a4ba640902bd9683e90"
    "/fonttools-4.64.0-py3-none-any.whl"
)
FONTTOOLS_WHEEL_SHA256 = "4a05783ff54ce4c7a28f18e5772efdf63c219374bd9ffc55452182e1cef8be60"

# Standard-library directories safe to drop for a fontTools-only runtime.
STDLIB_REMOVE_DIRS = (
    "config-3.11-x86_64-linux-musl", "config-3.11-aarch64-linux-musl", "config-3.11",
    "test", "idlelib", "tkinter", "turtle", "ensurepip", "venv", "lib2to3",
    "distutils", "unittest", "pydoc_data",
)
STDLIB_REMOVE_PREFIXES = ("config-3.11", "config-")
SITE_PACKAGES_REMOVE = (
    "pip", "pip-*.dist-info", "setuptools", "setuptools-*.dist-info",
    "_distutils_hack", "distutils-precedence.pth",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, expected_sha: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and expected_sha and sha256_file(dest) == expected_sha:
        print(f"  [cached] {dest.name}")
        return
    print(f"  [download] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "MFFMv14-runtime-builder"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=300) as response, tmp.open("wb") as out:
        shutil.copyfileobj(response, out)
    if expected_sha:
        actual = sha256_file(tmp)
        if actual != expected_sha:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"SHA256 mismatch for {url}: expected {expected_sha}, got {actual}")
    tmp.replace(dest)


def _decompress_zst(zst: Path, out_tar: Path) -> None:
    try:
        import zstandard
        print(f"  [zstd] {zst.name} -> {out_tar.name}")
        data = zstandard.ZstdDecompressor().decompress(zst.read_bytes())
        out_tar.write_bytes(data)
    except ImportError:
        raise RuntimeError("zstandard package is required for .zst decompression. Run: pip install zstandard")


def _find_strip_binary(abi: str) -> str | None:
    if abi == "x64":
        return shutil.which("strip")
    for candidate in ("aarch64-linux-gnu-strip", "aarch64-linux-android-strip", "llvm-strip"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def _strip_binary(binary: Path, abi: str) -> None:
    stripper = _find_strip_binary(abi)
    if not stripper:
        print(f"  [warn] no cross-strip available for {abi}; shipping unstripped binary")
        return
    before = binary.stat().st_size
    proc = subprocess.run([stripper, str(binary)], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  [warn] strip failed for {abi}: {proc.stderr.strip()[:200]}")
        return
    after = binary.stat().st_size
    print(f"  [strip] {binary.name}: {before // 1024 // 1024}MB -> {after // 1024 // 1024}MB")


def _trim_stdlib(lib_dir: Path) -> None:
    removed = 0
    for entry in list(lib_dir.iterdir()):
        name = entry.name
        if name in STDLIB_REMOVE_DIRS or any(name.startswith(p) for p in STDLIB_REMOVE_PREFIXES):
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    # Remove __pycache__ dirs (regenerated at runtime)
    for pycache in lib_dir.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    sp = lib_dir / "site-packages"
    if sp.is_dir():
        for entry in list(sp.iterdir()):
            name = entry.name
            for pattern in SITE_PACKAGES_REMOVE:
                if pattern.endswith("*"):
                    if name.startswith(pattern[:-1]):
                        _rm(sp, entry)
                        break
                elif name == pattern:
                    _rm(sp, entry)
                    break
    print(f"  [trim] removed {removed} stdlib dirs + pycache + bundled pip/setuptools")


def _rm(sp: Path, entry: Path) -> None:
    if entry.is_dir():
        shutil.rmtree(entry, ignore_errors=True)
    else:
        entry.unlink(missing_ok=True)


def install_fonttools(site_packages: Path) -> None:
    import zipfile
    site_packages.mkdir(parents=True, exist_ok=True)
    wheel = site_packages.parent / "fonttools.whl"  # temp, outside site-packages
    _download(FONTTOOLS_WHEEL_URL, wheel, FONTTOOLS_WHEEL_SHA256)
    with zipfile.ZipFile(wheel) as zf:
        zf.extractall(site_packages)
    wheel.unlink(missing_ok=True)
    print(f"  [fonttools] installed {FONTTOOLS_VERSION} -> {site_packages}")


def build_abi_payload(abi: str, work: Path) -> Path:
    triple = PYTHON_ABI_TARGET[abi]
    ext = "tar.zst" if "full" in PYTHON_VARIANT or "zst" in PYTHON_VARIANT else "tar.gz"
    asset = f"cpython-{PYTHON_VERSION}+{PYTHON_RELEASE_TAG}-{triple}-{PYTHON_VARIANT}.{ext}"
    url = f"{PYTHON_RELEASE_BASE}/{PYTHON_RELEASE_TAG}/{asset.replace('+', '%2B')}"

    print(f"\n=== Building {abi} ({triple}) ===")
    archive_path = work / asset
    _download(url, archive_path)

    extract_dir = work / abi
    shutil.rmtree(extract_dir, ignore_errors=True)
    def _extract_needed(tf_obj):
        for member in tf_obj.getmembers():
            # Only extract binary and standard library; skip share/terminfo, include, etc.
            if any(member.name.startswith(p) for p in ("python/bin", "python/lib", "python/install/bin", "python/install/lib")):
                try:
                    if hasattr(tarfile, "data_filter"):
                        tf_obj.extract(member, extract_dir, filter=lambda m, path: m)
                    else:
                        tf_obj.extract(member, extract_dir)
                except Exception:
                    pass

    if ext == "tar.zst":
        tar_path = archive_path.with_suffix("")
        _decompress_zst(archive_path, tar_path)
        with tarfile.open(tar_path) as tf:
            _extract_needed(tf)
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            _extract_needed(tf)

    install_dir = extract_dir / "python"
    if not (install_dir / "bin" / "python3.11").exists():
        install_dir = extract_dir / "python" / "install"
    if not (install_dir / "bin" / "python3.11").exists():
        raise SystemExit(f"Unexpected layout in {asset}: missing python/bin/python3.11")

    # Assemble minimal runtime layout
    payload = work / f"payload-{abi}"
    shutil.rmtree(payload, ignore_errors=True)
    payload_bin = payload / "bin"
    payload_lib = payload / "lib" / "python3.11"
    payload_bin.mkdir(parents=True, exist_ok=True)
    payload_lib.mkdir(parents=True, exist_ok=True)

    # Binary
    src_bin = install_dir / "bin" / "python3.11"
    dst_bin = payload_bin / "python3.11"
    shutil.copy2(src_bin, dst_bin)
    _strip_binary(dst_bin, abi)
    try:
        dst_bin.chmod(0o755)
    except OSError:
        pass

    py3_link = payload_bin / "python3"
    shutil.copy2(dst_bin, py3_link)
    try:
        py3_link.chmod(0o755)
    except OSError:
        pass

    # Stdlib (trimmed)
    src_lib = install_dir / "lib" / "python3.11"
    shutil.copytree(src_lib, payload_lib, dirs_exist_ok=True)
    _trim_stdlib(payload_lib)

    # fontTools
    install_fonttools(payload_lib / "site-packages")

    # Smoke test (only on host Linux x86_64)
    import platform
    if abi == "x64" and sys.platform.startswith("linux") and platform.machine() in ("x86_64", "AMD64"):
        test = subprocess.run(
            [str(dst_bin), "-c", "import fontTools; from fontTools.ttLib import TTCollection; print('fontTools', fontTools.version)"],
            capture_output=True, text=True,
        )
        if test.returncode != 0:
            raise SystemExit(f"fontTools smoke test failed on {abi}:\n{test.stderr}")
        print(f"  [verify] {abi} runtime: {test.stdout.strip()}")
    elif abi == "x64":
        print(f"  [verify] skipped execution smoke test on non-Linux host ({sys.platform})")

    # Package
    out_dir = RUNTIME_DIR / abi
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tar = out_dir / "python.tar.xz"
    if out_tar.exists():
        out_tar.unlink()
    with tarfile.open(out_tar, "w:xz") as tf:
        tf.add(payload, arcname=".")
    size_mb = out_tar.stat().st_size / 1024 / 1024
    digest = sha256_file(out_tar)
    print(f"  [package] {out_tar.relative_to(ROOT)} ({size_mb:.1f}MB)")
    print(f"  [sha256] {digest}")
    return out_tar


def update_manifest(shas: dict[str, str]) -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    now = dt.datetime.now()
    data["version"] = now.strftime("%Y.%m.%d")
    data["versionCode"] = now.strftime("%y%m%d")
    data["python_version"] = PYTHON_VERSION
    data["fonttools_version"] = FONTTOOLS_VERSION
    data["python_release_tag"] = PYTHON_RELEASE_TAG
    data["python_variant"] = PYTHON_VARIANT
    data["source"] = "astral-sh/python-build-standalone"
    sha_map = data.setdefault("sha256", {})
    for abi, digest in shas.items():
        sha_map[abi] = digest
    # Keep unsupported ABIs documented but empty
    for abi in ("armv7", "x86"):
        sha_map.setdefault(abi, "")
    data["sha256"] = sha_map
    data["notes"] = (
        "aarch64/x64: static musl CPython + pure-python fontTools (runs without Termux). "
        "armv7/x86: unsupported by python-build-standalone; flash-time falls back to Termux pip."
    )
    MANIFEST_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[manifest] wrote {MANIFEST_PATH.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare MFFM Runtime python.tar.xz payloads")
    parser.add_argument("--abi", choices=("aarch64", "x64"), action="append",
                        help="ABI to build (repeatable; default: all supported)")
    parser.add_argument("--no-strip", action="store_true", help="skip binary stripping")
    parser.add_argument("--keep-work", action="store_true", help="keep intermediate work dir")
    args = parser.parse_args()

    abis = args.abi or ["aarch64", "x64"]
    work = Path(tempfile.mkdtemp(prefix="mffm-runtime-prep-"))
    shas: dict[str, str] = {}
    try:
        for abi in abis:
            out_tar = build_abi_payload(abi, work)
            shas[abi] = sha256_file(out_tar)
        update_manifest(shas)
        print("\nRuntime payloads ready. Next: python build_runtime.py")
        return 0
    finally:
        if not args.keep_work:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
