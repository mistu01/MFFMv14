#!/usr/bin/env python3
# ==============================================================================
# MFFMv14 ZIP Signing Helper
# Copyright © 2026 MFFM / Mistu
# Last modified: 2026-06-18
# ==============================================================================
"""Download, cache, sign, and verify module ZIPs with ZipSignerust."""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


API_URL = "https://api.github.com/repos/MrCarb0n/zipsignerust/releases/latest"
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
    return urllib.request.Request(url, headers={"User-Agent": "MFFMv14-builder", "Accept": "application/vnd.github+json"})


def _ensure_binary(root: Path) -> Path:
    path_binary = shutil.which("zipsignerust") or shutil.which("zipsignerust.exe")
    cache = root / CACHE_NAME / "bin"
    name = _asset_name()
    binary = cache / name
    if binary.exists():
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        return binary
    try:
        with urllib.request.urlopen(_request(API_URL), timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))
        asset = next(item for item in release.get("assets", []) if item.get("name") == name)
        cache.mkdir(parents=True, exist_ok=True)
        temp = binary.with_suffix(binary.suffix + ".download")
        with urllib.request.urlopen(_request(asset["browser_download_url"]), timeout=90) as response, temp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        temp.replace(binary)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        return binary
    except Exception as exc:
        if path_binary:
            print(f"Warning: download failed; using ZipSignerust from PATH: {exc}")
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
            [openssl, "req", "-x509", "-newkey", "rsa:4096", "-sha256", "-nodes", "-days", "3650",
             "-subj", "/CN=MFFM Module Signing/", "-keyout", str(private), "-out", str(certificate)],
            text=True, capture_output=True,
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
        x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650)).sign(key, hashes.SHA256())
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
