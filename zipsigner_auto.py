#!/usr/bin/env python3
"""Download, cache, sign, and verify module ZIPs with ZipSignerust."""

from __future__ import annotations

import hashlib
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

# Supply-chain pin: the release tag ZipSignerust publishes plus the exact
# SHA-256 of every binary we are willing to execute. The tag alone is not a
# pin (the project tags its release "latest"), so the digests are the real
# gate — if the release is re-published with different bytes, downloads fail
# until these constants are re-verified and bumped together.
ZIPSIGNERUST_TAG = "latest"
ZIPSIGNERUST_RELEASE_URL = f"https://api.github.com/repos/MrCarb0n/zipsignerust/releases/tags/{ZIPSIGNERUST_TAG}"
ZIPSIGNERUST_SHA256 = {
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
    headers = {"User-Agent": "MFFMv14-builder", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_binary(root: Path) -> Path:
    custom_bin = os.environ.get("ZIPSIGNER_BIN")
    if custom_bin and Path(custom_bin).exists():
        p = Path(custom_bin)
        try:
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        except OSError:
            pass
        return p
    path_binary = shutil.which("zipsignerust") or shutil.which("zipsignerust.exe")
    cache = root / CACHE_NAME / "bin"
    name = _asset_name()
    binary = cache / name
    expected_hash = ZIPSIGNERUST_SHA256.get(name)
    if binary.exists():
        if expected_hash is None or _sha256_file(binary) == expected_hash:
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
            return binary
        print(f"Warning: cached {name} failed SHA-256 verification; re-downloading from the pinned release")
        binary.unlink()

    try:
        with urllib.request.urlopen(_request(ZIPSIGNERUST_RELEASE_URL), timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))
        asset = next(item for item in release.get("assets", []) if item.get("name") == name)
        cache.mkdir(parents=True, exist_ok=True)
        temp = binary.with_suffix(binary.suffix + ".download")
        with urllib.request.urlopen(_request(asset["browser_download_url"]), timeout=90) as response, temp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        if expected_hash is not None:
            actual_hash = _sha256_file(temp)
            if actual_hash != expected_hash:
                temp.unlink(missing_ok=True)
                raise ZipSignerError(
                    f"Downloaded {name} SHA-256 mismatch: got {actual_hash}, expected {expected_hash}. "
                    "The pinned ZipSignerust release may have been re-published; verify the new binary "
                    "and update ZIPSIGNERUST_TAG/ZIPSIGNERUST_SHA256 in zipsigner_auto.py."
                )
        temp.replace(binary)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        return binary
    except ZipSignerError:
        raise
    except Exception as exc:
        if path_binary:
            print(f"Warning: download failed; using ZipSignerust from PATH (unpinned): {exc}")
            return Path(path_binary)
        raise ZipSignerError(f"Could not obtain ZipSignerust: {exc}") from exc


FALLBACK_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIEyDCCArCgAwIBAgIUfe0EZkGtItPbcKnHbwhuiV5wIeswDQYJKoZIhvcNAQEL
BQAwHjEcMBoGA1UEAwwTTUZGTSBNb2R1bGUgU2lnbmluZzAeFw0yNjA5MjMwMDAw
NDNaFw0zNjA5MjAwMDA1NDNaMB4xHDAaBgNVBAMME01GRk0gTW9kdWxlIFNpZ25p
YmcwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCnGGOO7vz8iSt/1ySR
8fIXf8+qfTzaBTyEugISgDeFw1wXmf1TmDpgQ/HwxuNouq0rHowVJ0gIlZ56/e0T
MUJt9udmrA8kSvOX/2+g40q7+xG78OFEUDuS3tIHaXi4j/p9BR6JLvwPLi4Ik0MV
eEWaQQNNUDVjwvpNfxSjvZg2A5pJ7hkdjYKoha6RLINTledVImQQ1r00ZVYnlCYz
v4VsbasFbW1cqnet3js6FJqqDaczr31DsMJwmiPIP4oYcoUS3Z3n/sFQbRq1cJ4S
gN8bpGef9J7fdpSBkLt9+w/2JCPFVlTdVRc3cs8TruZAJe6Xc6V+Y0K2+4f/YCln
8XkvTRILpqgqeA+YKI4VtGbNnw3aJguIGC6c9KYsP3CZx+UIyRM8bpkBbB3q5Ldr
bgdQdmPz738BQRYkeyecqymt5+AwTpTvMMUOdZ286mtpzvmueiBmV8PHTWNZYwsm
7rbw+P1DR70OSIcclThdI90mjqiJSz/hMfGvNHC/JRH8y4Q3kvwMAevt9xsIWFZi
0dBqQ2ZQirYtHyaWEJYuJHjhy1iUZ2DHlH22yReVEHxRQiNELBnzVmUAH27m3ESq
6RO5AKq54MT0rLIqCnriDwkrTSUrESfCwMSkuBhZDcjjtjfZy9mzURJ2tstreP/2
BqaHpZyx0bKKnNmlYcLx6cJBCwIDAQABMA0GCSqGSIb3DQEBCwUAA4ICAQAlG50U
Pc3hDoZQxBswTDY53K7Z63WkWVDIL/+T/bbim3FFO6v+6GX1C+2b2o4OGnItgckT
dPT6FjD7VR3j55FG2t/Bio+T89m1nNLzPTQa2C11R35jCbWKqSjfJ/zLr7gJwgm/
T39pTxLm/EX6t6y++/8ofzNZQJtGLkNuC9jvyc7Tcyp4bISQydiRTygYjqI3oxO/
xJ5CL0NFkN40+qdyPtTYYx2EDosVv8WZcfOuFl6362BdNiwuG+Zfzt6rpNz5DmXy
4PoCDXjnVRLVYCTCyySqYS9WpikNJfpukiGrBGXqIOa1jBa0KhwmKBtUfvUqBM8U
/WmNjfQXH7eMdbPXV0LDrWZDzROwtkRAltTLZUzZc4gKOt2o9vEJEiSoO7+pZCcK
ZR7Mtxjwxz90cBR1X90Rv3iK0ciKYNsY2HH+ESaZp/UibDVAFsdQ7VJrudArXErC
bbCx+h1CpxT+oZYag1oaWksYpxmqD0Vnu/58SVXYzdNduUVUSpSdcbjOd3JDNkt2
Y2ByBZ1K9P6qwFLkDpBHJSx2cG1OS0bAC9BGENjyvjakhLUH1+ldCAIiIq8KO92U
vDf7WvbOKrhXwz6qfyZNhdZLR9n7SH6gvKZzgmbtvblyJjx+Kt/IWnrq4pL+VEPl
9OrXGiuB/6fL+jAjqohCScKBZ9/919FPEEl3Bg==
-----END CERTIFICATE-----
"""

FALLBACK_KEY_PEM = """-----BEGIN PRIVATE KEY-----
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
sjGnEIaVekqFVenxCm96WXXPx9956g==
-----END PRIVATE KEY-----
"""


def _ensure_keys(root: Path) -> tuple[Path, Path]:
    keys = root / CACHE_NAME / "keys"
    private = keys / "mffm-signing-key.pem"
    certificate = keys / "mffm-signing-cert.pem"
    if private.exists() and certificate.exists():
        return private, certificate

    keys.mkdir(parents=True, exist_ok=True)
    try:
        private.write_text(FALLBACK_KEY_PEM.strip() + "\n", encoding="utf-8")
        certificate.write_text(FALLBACK_CERT_PEM.strip() + "\n", encoding="utf-8")
        if os.name != "nt":
            private.chmod(0o600)
            certificate.chmod(0o644)
        return private, certificate
    except Exception:
        pass

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
