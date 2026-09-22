#!/usr/bin/env python3
"""Check upstream releases for fontTools and python-build-standalone.

Detects if a newer version of fontTools is available on PyPI or a newer
release tag of python-build-standalone is available on GitHub.
Can automatically update the supply-chain pins in prepare_runtime.py
and export GitHub Actions step outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREPARE_SCRIPT = ROOT / "prepare_runtime.py"
MANIFEST_PATH = ROOT / "runtime-template" / "manifest.json"

PYPI_FONTTOOLS_URL = "https://pypi.org/pypi/fonttools/json"
GITHUB_PYTHON_RELEASES_URL = "https://api.github.com/repos/astral-sh/python-build-standalone/releases?per_page=10"


def current_pinned_values() -> dict[str, str]:
    """Read current pinned constants from prepare_runtime.py."""
    content = PREPARE_SCRIPT.read_text(encoding="utf-8")

    def _extract(pattern: str, default: str = "") -> str:
        m = re.search(pattern, content)
        return m.group(1) if m else default

    return {
        "python_release_tag": _extract(r'PYTHON_RELEASE_TAG\s*=\s*"([^"]+)"'),
        "python_version": _extract(r'PYTHON_VERSION\s*=\s*"([^"]+)"'),
        "python_variant": _extract(r'PYTHON_VARIANT\s*=\s*"([^"]+)"', "lto+static-full"),
        "fonttools_version": _extract(r'FONTTOOLS_VERSION\s*=\s*"([^"]+)"'),
        "fonttools_wheel_sha256": _extract(r'FONTTOOLS_WHEEL_SHA256\s*=\s*"([^"]+)"'),
    }


def fetch_latest_fonttools() -> dict[str, str]:
    """Query PyPI JSON API for the latest fontTools release and pure-python wheel."""
    req = urllib.request.Request(PYPI_FONTTOOLS_URL, headers={"User-Agent": "MFFMv14-runtime-checker"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    version = data["info"]["version"]
    urls = data.get("urls", [])
    # Look for pure python 3 wheel: fonttools-<version>-py3-none-any.whl
    wheel = next(
        (u for u in urls if u["filename"].endswith("-py3-none-any.whl")),
        None,
    )
    if not wheel:
        # Fallback to any wheel ending with none-any.whl
        wheel = next((u for u in urls if u["filename"].endswith("none-any.whl")), None)

    if not wheel:
        raise RuntimeError(f"Could not locate a pure-python wheel for fontTools {version} on PyPI")

    return {
        "version": version,
        "wheel_url": wheel["url"],
        "wheel_sha256": wheel["digests"]["sha256"],
        "filename": wheel["filename"],
    }


def fetch_latest_python(target_variant: str = "lto+static-full") -> dict[str, str]:
    """Query GitHub Releases API for latest python-build-standalone with CPython 3.11 static musl."""
    headers = {"User-Agent": "MFFMv14-runtime-checker", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(GITHUB_PYTHON_RELEASES_URL, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        releases = json.loads(resp.read().decode("utf-8"))

    for rel in releases:
        tag = rel.get("tag_name", "").lstrip("v")
        assets = [a["name"] for a in rel.get("assets", [])]

        # Look for musl static builds for 3.11
        aarch64_asset = next(
            (a for a in assets if "3.11" in a and "aarch64-unknown-linux-musl" in a and target_variant in a),
            None,
        )
        x64_asset = next(
            (a for a in assets if "3.11" in a and "x86_64-unknown-linux-musl" in a and target_variant in a),
            None,
        )

        if aarch64_asset and x64_asset:
            m = re.match(r"cpython-([0-9.]+)\+.*", aarch64_asset)
            py_ver = m.group(1) if m else "3.11.16"
            return {
                "release_tag": tag,
                "python_version": py_ver,
                "aarch64_asset": aarch64_asset,
                "x64_asset": x64_asset,
                "variant": target_variant,
            }

    raise RuntimeError(f"Could not find matching Python 3.11 musl {target_variant} assets in recent releases")


def update_prepare_script(
    fonttools_info: dict[str, str],
    python_info: dict[str, str],
) -> None:
    """Rewrite pinned constants in prepare_runtime.py."""
    content = PREPARE_SCRIPT.read_text(encoding="utf-8")

    content = re.sub(
        r'PYTHON_RELEASE_TAG\s*=\s*"[^"]+"',
        f'PYTHON_RELEASE_TAG = "{python_info["release_tag"]}"',
        content,
    )
    content = re.sub(
        r'PYTHON_VERSION\s*=\s*"[^"]+"',
        f'PYTHON_VERSION = "{python_info["python_version"]}"',
        content,
    )
    content = re.sub(
        r'FONTTOOLS_VERSION\s*=\s*"[^"]+"',
        f'FONTTOOLS_VERSION = "{fonttools_info["version"]}"',
        content,
    )
    # Replace URL (formatted inside parentheses)
    wheel_url = fonttools_info["wheel_url"]
    url_replacement = f'FONTTOOLS_WHEEL_URL = (\n    "{wheel_url}"\n)'
    content = re.sub(
        r'FONTTOOLS_WHEEL_URL\s*=\s*(?:\([^)]*\)|"[^"]*")',
        url_replacement,
        content,
    )
    content = re.sub(
        r'FONTTOOLS_WHEEL_SHA256\s*=\s*"[^"]+"',
        f'FONTTOOLS_WHEEL_SHA256 = "{fonttools_info["wheel_sha256"]}"',
        content,
    )

    PREPARE_SCRIPT.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK] Updated pins in {PREPARE_SCRIPT.name}")


def write_github_output(params: dict[str, str]) -> None:
    """Write outputs to GITHUB_OUTPUT file if running inside GitHub Actions."""
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not gh_out:
        return
    with open(gh_out, "a", encoding="utf-8") as handle:
        for k, v in params.items():
            handle.write(f"{k}={v}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check & update runtime module upstream dependencies")
    parser.add_argument("--check", action="store_true", help="Check only (default)")
    parser.add_argument("--update", action="store_true", help="Apply updates to prepare_runtime.py")
    parser.add_argument("--force", action="store_true", help="Force update flag even if versions match")
    parser.add_argument("--override-fonttools", help="Explicit fontTools version to use")
    parser.add_argument("--override-python-tag", help="Explicit python-build-standalone tag to use")
    parser.add_argument("--exit-code", action="store_true", help="Exit with code 10 if updates are available (for scripts)")
    parser.add_argument("--output-github", action="store_true", help="Export variables to $GITHUB_OUTPUT")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 60)
    print("MFFM Runtime Upstream Dependency Checker")
    print("=" * 60)

    current = current_pinned_values()
    print(f"Current Pinned Versions:")
    print(f"  - fontTools : {current.get('fonttools_version')}")
    print(f"  - Python    : {current.get('python_version')} (release tag: {current.get('python_release_tag')})")
    print()

    # Query latest upstream
    print("[*] Checking PyPI for fontTools...")
    ft_latest = fetch_latest_fonttools()
    print(f"    Latest fontTools: {ft_latest['version']}")

    print("[*] Checking GitHub for python-build-standalone...")
    py_latest = fetch_latest_python(current.get("python_variant", "lto+static-full"))
    print(f"    Latest Python tag: {py_latest['release_tag']} (Python {py_latest['python_version']})")
    print()

    # Apply overrides if specified
    if args.override_fonttools:
        ft_latest["version"] = args.override_fonttools
    if args.override_python_tag:
        py_latest["release_tag"] = args.override_python_tag

    # Determine changes
    ft_changed = (ft_latest["version"] != current["fonttools_version"])
    py_changed = (
        py_latest["release_tag"] != current["python_release_tag"]
        or py_latest["python_version"] != current["python_version"]
    )
    needs_update = ft_changed or py_changed or args.force

    changes = []
    if ft_changed:
        changes.append(f"fontTools {current['fonttools_version']} -> {ft_latest['version']}")
    if py_changed:
        changes.append(f"Python {current['python_release_tag']} -> {py_latest['release_tag']}")
    if args.force:
        changes.append("Forced rebuild")

    summary = ", ".join(changes) if changes else "All dependencies are up to date."
    print("Status:")
    print(f"  - Update Required: {needs_update}")
    print(f"  - Summary        : {summary}")
    print()

    if args.output_github:
        write_github_output({
            "needs_update": "true" if needs_update else "false",
            "fonttools_updated": "true" if ft_changed else "false",
            "python_updated": "true" if py_changed else "false",
            "fonttools_version": ft_latest["version"],
            "python_tag": py_latest["release_tag"],
            "python_version": py_latest["python_version"],
            "summary": summary,
        })

    if args.update and needs_update:
        print("[*] Updating prepare_runtime.py constants...")
        update_prepare_script(ft_latest, py_latest)
        return 0

    if args.exit_code and needs_update:
        return 10

    return 0


if __name__ == "__main__":
    sys.exit(main())
