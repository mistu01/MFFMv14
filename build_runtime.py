#!/usr/bin/env python3
"""Build the MFFM Runtime module ZIP (shared Python + fontTools) — Option 1.

Packages runtime-template/ into a signed ZIP similar to build.py/package_template.py.
Embeds prebuilt python.tar.xz per ABI if present, verifies manifest.json SHA pins,
and honours SOURCE_DATE_EPOCH for reproducible output.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME_TEMPLATE = ROOT / "runtime-template"
BUILD_CONFIG_NAME = ".mffm-build.json"

try:
    from build import zip_timestamp
    from font_module import read_props, write_props
    from zipsigner_auto import ZipSignerError, sign_zip
except ImportError:
    # Fallback if build not importable
    def zip_timestamp():
        raw = os.environ.get("SOURCE_DATE_EPOCH")
        if raw:
            return time.gmtime(max(int(raw), 315532800))[:6]
        return dt.datetime.now().timetuple()[:6]
    def read_props(p): return {}
    def write_props(p, d): pass
    class ZipSignerError(RuntimeError): pass
    def sign_zip(a, b): return a

PAYLOAD_NAMES = ("module.prop", "customize.sh", "service.sh", "uninstall.sh", "post-mount.sh", "META-INF", "manifest.json", "runtime")

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build MFFM Runtime module ZIP")
    p.add_argument("--output-dir", type=Path, default=ROOT / "dist", help="output dir (default: ./dist)")
    p.add_argument("--version", help="override version (default: manifest.json version)")
    p.add_argument("--version-code", help="override versionCode")
    p.add_argument("--no-sign", action="store_true", help="skip signing")
    p.add_argument("--no-zip", action="store_true", help="prepare files without zipping")
    p.add_argument("--inspect", action="store_true", help="inspect runtime payloads and manifest without packaging")
    return p.parse_args()

def payload_files(module_dir: Path):
    for name in PAYLOAD_NAMES:
        path = module_dir / name
        if not path.exists():
            continue
        if path.is_file():
            yield path, Path(name)
        else:
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.name != ".gitkeep" and "README.txt" not in child.name:
                    # Include runtime tarballs if present, skip placeholder READMEs
                    if child.name == "README.txt" and "runtime" in child.parts:
                        continue
                    yield child, child.relative_to(module_dir)

def write_zip(module_dir: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = zip_timestamp()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in payload_files(module_dir):
            info = zipfile.ZipInfo(relative.as_posix(), timestamp)
            executable = relative.name.endswith(".sh") or relative.name == "update-binary" or relative.name in {"mffm-helper", "python3", "python"}
            info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_manifest(manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        print("  [WARN] manifest.json not found, skipping SHA verification")
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    sha_map = data.get("sha256", {})
    for abi in ("aarch64", "armv7", "x64", "x86"):
        tar_xz = RUNTIME_TEMPLATE / "runtime" / abi / "python.tar.xz"
        tar_gz = RUNTIME_TEMPLATE / "runtime" / abi / "python.tar.gz"
        tar = tar_xz if tar_xz.is_file() else tar_gz if tar_gz.is_file() else None
        expected = sha_map.get(abi, "")
        if tar and expected:
            actual = sha256_file(tar)
            if actual != expected:
                raise SystemExit(f"SHA256 mismatch for {tar.relative_to(ROOT)}: expected {expected}, got {actual}")
            print(f"  [OK] SHA verified {abi}: {actual[:16]}...")
        elif tar and not expected:
            print(f"  [WARN] No SHA pin for {abi} in manifest.json (tar exists but not pinned)")
        elif not tar and expected:
            print(f"  [WARN] SHA pin exists for {abi} but no tarball found at runtime/{abi}/")
    return data

def build_runtime(args: argparse.Namespace) -> Path | None:
    if not (RUNTIME_TEMPLATE / "customize.sh").exists():
        raise SystemExit(f"Runtime template missing: {RUNTIME_TEMPLATE}/customize.sh")

    manifest = verify_manifest(RUNTIME_TEMPLATE / "manifest.json")
    # Load version from manifest
    version = args.version or manifest.get("version", "1.0")
    version_code = args.version_code or manifest.get("versionCode", dt.datetime.now().strftime("%y%m%d"))

    import tempfile
    work_dir = Path(tempfile.mkdtemp(prefix="mffm-runtime-build-"))
    module_dir = work_dir / "module"
    try:
        # Copy template
        shutil.copytree(RUNTIME_TEMPLATE, module_dir, dirs_exist_ok=True)
        # Remove placeholder READMEs from copy (they are excluded in payload_files anyway)
        for readme in module_dir.rglob("README.txt"):
            if "runtime" in readme.parts:
                readme.unlink(missing_ok=True)

        # Update module.prop
        props = read_props(module_dir / "module.prop")
        props["version"] = version
        props["versionCode"] = version_code
        # Keep id mffm_runtime
        write_props(module_dir / "module.prop", props)

        print("=" * 60)
        print("MFFM Runtime module packaging")
        print("=" * 60)
        print(f"Version    : {version} ({version_code})")
        found_tars = []
        for abi in ("aarch64", "armv7", "x64", "x86"):
            for name in ("python.tar.xz", "python.tar.gz"):
                p = RUNTIME_TEMPLATE / "runtime" / abi / name
                if p.is_file():
                    found_tars.append((abi, name, p))
                    print(f"  - {abi}/{name} ({p.stat().st_size/1024/1024:.2f} MB, sha {sha256_file(p)[:12]}...)")
        if not found_tars:
            print("  (no embedded python tarballs found; module will install in Termux/bootstrap-fallback mode)")

        if getattr(args, "inspect", False):
            print("\nInspection complete (use without --inspect to build ZIP).")
            return None

        if args.no_zip:
            print(f"Prepared module files at: {module_dir}")
            return None

        out_dir = getattr(args, "output_dir", None)
        if out_dir is None:
            out_dir = ROOT / "dist"
        output = Path(out_dir).resolve() / f"mffm-runtime-{version}.zip"
        if output.exists():
            output.unlink()
        write_zip(module_dir, output)

        if not args.no_sign:
            try:
                sign_zip(output, ROOT)
            except ZipSignerError as exc:
                output.unlink(missing_ok=True)
                raise SystemExit(str(exc)) from exc
            print("Signature  : verified")
        else:
            print("Signature  : skipped (--no-sign)")

        print(f"Output     : {output}")
        return output
    finally:
        if not args.no_zip:
            shutil.rmtree(work_dir, ignore_errors=True)

def main() -> int:
    args = parse_args()
    build_runtime(args)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
