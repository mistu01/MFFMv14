#!/usr/bin/env python3
"""Package MFFMv14 Source Template ZIP for distribution, explicitly excluding RELEASE_POST.txt and all Git-related files."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from build import ROOT, zip_timestamp

# Explicit list of documentation and helper files to include at root alongside the template
ROOT_EXTRA_FILES = (
    "USAGE_GUIDE.md",
    "CHANGELOG.md",
    "RUNTIME_ENHANCEMENTS.md",
)

EMPTY_FOLDERS = (
    "Files/Sans",
    "Files/Monospace",
    "Files/Serif",
    "Files/Bengali",
)

EXCLUDED_ASSET_SUFFIXES = (".tar.xz", ".tar.gz", ".tar.zst", ".whl", ".deb", ".zip")


def build_template_zip(output_dir: Path | None = None) -> Path:
    target_dir = (output_dir or (ROOT / "dist")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    output_zip = target_dir / "MFFMv14-Source-Template.zip"

    timestamp = zip_timestamp()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        # 1. Package template skeleton directly at root
        template_dir = ROOT / "template"
        if template_dir.exists():
            for path in sorted(template_dir.rglob("*")):
                if path.is_file() and not path.name.startswith(".git") and not path.name.startswith("."):
                    if "RELEASE_POST" in path.name.upper():
                        continue
                    if any(path.name.endswith(sfx) for sfx in EXCLUDED_ASSET_SUFFIXES):
                        continue
                    rel_path = path.relative_to(template_dir).as_posix()
                    info = zipfile.ZipInfo(rel_path, timestamp)
                    executable = path.name.endswith(".sh") or path.name == "update-binary"
                    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes())

        # 2. Package documentation and shell builder at root
        for f_name in ROOT_EXTRA_FILES:
            file_path = ROOT / f_name
            if file_path.is_file():
                info = zipfile.ZipInfo(f_name, timestamp)
                executable = f_name.endswith(".sh")
                info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, file_path.read_bytes())

        # 3. Create empty font directory entries cleanly
        for folder in EMPTY_FOLDERS:
            info = zipfile.ZipInfo(f"{folder}/", timestamp)
            info.external_attr = (0o755 & 0xFFFF) << 16
            archive.writestr(info, "")

    print("=" * 60)
    print("MFFMv14 Source Template Packaged")
    print("=" * 60)
    print(f"Output        : {output_zip}")
    print("Contents      : Standalone font module template + USAGE_GUIDE.md, CHANGELOG.md")
    return output_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Package MFFMv14 Source Template ZIP")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist", help="destination directory for template ZIP")
    args = parser.parse_args()
    build_template_zip(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
