#!/usr/bin/env python3
"""Download, cache, sign, and verify module ZIPs with ZipSignerust."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SIGNER_TAG = "latest"
DOWNLOAD_URL = "https://github.com/MrCarb0n/zipsignerust/releases/download/{tag}/{name}"
# Pinned SHA-256 of every ZipSignerust asset used to sign modules. The upstream release tag is
# rolling, so these digests are the only thing tying a build to a reviewed signer binary; refresh
# them deliberately with `gh api repos/MrCarb0n/zipsignerust/releases/latest`.
SIGNER_DIGESTS = {
    "zipsignerust-android-arm64": "531ffe746bb0d76c2d2957acd6c71a12d42580ea5539a01859d1b6139f64d592",
    "zipsignerust-android-armv7": "406359208378d94dd71a5f40a8a5f1bb67c9d68ab03dc103c01dc4917dcd495c",
    "zipsignerust-linux-x64": "dc51bec0646f025a90a182f6f39cdb0a73e23dfa6bd9432bc16e870004c47ac9",
    "zipsignerust-windows-x64.exe": "d0bda8d29faf69794dba2de445f335a0d53ca72ff3b427b69fb2efe6f82d879f",
}
CACHE_NAME = ".mffm-signer"


class ZipSignerError(RuntimeError):
    pass


def _asset_name() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64", "x64"}:
        if sys.platform.startswith("win"):
            return "zipsignerust-windows-x64.exe"
        if sys.platform.startswith("linux"):
            return "zipsignerust-linux-x64"
    if sys.platform.startswith("linux") and machine in {"aarch64", "arm64"}:
        return "zipsignerust-android-arm64"
    if sys.platform.startswith("linux") and machine in {"armv7l", "armv7"}:
        return "zipsignerust-android-armv7"
    raise ZipSignerError(f"No supported ZipSignerust binary for {platform.system()} {platform.machine()}")


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": "MFFMv14-builder"})


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_binary(root: Path) -> Path:
    path_binary = shutil.which("zipsignerust") or shutil.which("zipsignerust.exe")
    name = _asset_name()
    expected = SIGNER_DIGESTS[name]
    # The digest is part of the cache path, so re-pinning the signer never reuses the old binary.
    binary = root / CACHE_NAME / "bin" / expected[:16] / name
    if binary.exists() and _digest(binary) == expected:
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        return binary

    try:
        binary.parent.mkdir(parents=True, exist_ok=True)
        temp = binary.with_suffix(binary.suffix + ".download")
        url = DOWNLOAD_URL.format(tag=SIGNER_TAG, name=name)
        with urllib.request.urlopen(_request(url), timeout=90) as response, temp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        actual = _digest(temp)
        if actual != expected:
            temp.unlink(missing_ok=True)
            raise ZipSignerError(
                f"Refusing to run {name} from {url}: expected SHA-256 {expected}, got {actual}.\n"
                "Upstream publishes new binaries under the same rolling tag. Review the release, then"
                " update SIGNER_DIGESTS in zipsigner_auto.py."
            )
        temp.replace(binary)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        return binary
    except ZipSignerError:
        raise
    except Exception as exc:
        if path_binary and _digest(Path(path_binary)) == expected:
            print(f"Warning: download failed; using the pinned ZipSignerust from PATH: {exc}")
            return Path(path_binary)
        raise ZipSignerError(f"Could not obtain ZipSignerust: {exc}") from exc


def _ensure_keys(root: Path) -> tuple[Path, Path]:
    keys = root / CACHE_NAME / "keys"
    private = keys / "mffm-signing-key.pem"
    certificate = keys / "mffm-signing-cert.pem"
    if private.exists() and certificate.exists():
        return private, certificate

    keys.mkdir(parents=True, exist_ok=True)
    openssl = shutil.which("openssl")
    if openssl:
        proc = subprocess.run(
            [
                openssl, "req", "-x509", "-newkey", "rsa:4096", "-sha256", "-nodes", "-days", "3650",
                "-subj", "/CN=MFFM Module Signing/", "-keyout", str(private), "-out", str(certificate)
            ],
            text=True,
            capture_output=True,
        )
        if proc.returncode == 0:
            return private, certificate

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as exc:
        raise ZipSignerError("Signing keys are missing. Install OpenSSL or: python -m pip install cryptography") from exc

    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MFFM Module Signing")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    if os.name != "nt":
        private.chmod(0o600)
        certificate.chmod(0o644)
    return private, certificate


def _run(command: list[str], stage: str) -> None:
    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.returncode:
        details = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
        raise ZipSignerError(f"ZipSignerust {stage} failed ({proc.returncode}):\n{details}")


def sign_zip(zip_path: Path, project_root: Path) -> Path:
    target = zip_path.resolve()
    root = project_root.resolve()
    binary = _ensure_binary(root)
    private, certificate = _ensure_keys(root)
    _run([str(binary), "sign", "--inplace", str(target), "--private-key", str(private), "--public-key", str(certificate)], "signing")
    _run([str(binary), "verify", str(target), "--public-key", str(certificate)], "verification")
    return target
