#!/usr/bin/env python3
"""Package MFFMv14 Source Template ZIP for distribution, explicitly excluding RELEASE_POST.txt and all Git-related files."""

from __future__ import annotations

import argparse
import datetime as dt
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Explicit list of root files to include (RELEASE_POST.txt and Git files are strictly EXCLUDED)
INCLUDE_FILES = (
    "build.py",
    "font_module.py",
    "requirements.txt",
    "termux-build.sh",
    "update.py",
    "USAGE_GUIDE.md",
    "MFFMv14_DISTRIBUTION_GUIDE.txt",
    "RELEASE_NOTES.txt",
    "zipsigner_auto.py",
)

EMPTY_FOLDERS = (
    "Fonts/Sans",
    "Fonts/Monospace",
    "Fonts/Serif",
    "Fonts/Bengali",
    "template/Files",
    "Old Modules",
    "dist",
)


def build_template_zip(output_dir: Path | None = None) -> Path:
    target_dir = (output_dir or (ROOT / "dist")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    output_zip = target_dir / "MFFMv14-Source-Template.zip"

    timestamp = dt.datetime.now().timetuple()[:6]
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for f_name in INCLUDE_FILES:
            file_path = ROOT / f_name
            if file_path.is_file():
                info = zipfile.ZipInfo(f_name, timestamp)
                executable = f_name.endswith(".sh") or f_name.endswith(".py")
                info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, file_path.read_bytes())

        template_dir = ROOT / "template"
        if template_dir.exists():
            for path in sorted(template_dir.rglob("*")):
                if path.is_file() and not path.name.startswith(".git") and not path.name.startswith("."):
                    if "RELEASE_POST" in path.name.upper():
                        continue
                    rel_path = path.relative_to(ROOT).as_posix()
                    info = zipfile.ZipInfo(rel_path, timestamp)
                    executable = path.name.endswith(".sh") or path.name == "update-binary"
                    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes())

        # Create empty directory entries cleanly without .gitkeep files
        for folder in EMPTY_FOLDERS:
            info = zipfile.ZipInfo(f"{folder}/", timestamp)
            info.external_attr = (0o755 & 0xFFFF) << 16
            archive.writestr(info, "")

    print("=" * 60)
    print("MFFMv14 Source Template Packaged")
    print("=" * 60)
    print(f"Output        : {output_zip}")
    print("Excluded      : RELEASE_POST.txt, .gitignore, .gitattributes, .gitkeep, .git*")
    return output_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Package MFFMv14 Source Template ZIP")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist", help="destination directory for template ZIP")
    args = parser.parse_args()
    build_template_zip(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
