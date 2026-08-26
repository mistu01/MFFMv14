#!/usr/bin/env python3
"""Package MFFMv14 Source Template ZIP for distribution, explicitly excluding RELEASE_POST.txt and all Git-related files."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from build import ROOT, zip_timestamp

# Explicit list of root files to include (RELEASE_POST.txt and Git files are strictly EXCLUDED)
INCLUDE_FILES = (
    "build.py",
    "build_runtime.py",
    "prepare_runtime.py",
    "runtime_helper.py",
    "font_module.py",
    "package_template.py",
    "requirements.txt",
    "requirements-dev.txt",
    "termux-build.sh",
    "update.py",
    "USAGE_GUIDE.md",
    "CHANGELOG.md",
    "zipsigner_auto.py",
)

EMPTY_FOLDERS = (
    "Fonts/Sans",
    "Fonts/Monospace",
    "Fonts/Serif",
    "Fonts/Bengali",
    "template/Files/Sans",
    "template/Files/Monospace",
    "template/Files/Serif",
    "template/Files/Bengali",
    "runtime-template/runtime/aarch64",
    "runtime-template/runtime/x64",
    "Old Modules",
    "dist",
)

EXCLUDED_ASSET_SUFFIXES = (".tar.xz", ".tar.gz", ".tar.zst", ".whl", ".deb", ".zip")


def build_template_zip(output_dir: Path | None = None) -> Path:
    target_dir = (output_dir or (ROOT / "dist")).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    output_zip = target_dir / "MFFMv14-Source-Template.zip"

    timestamp = zip_timestamp()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for f_name in INCLUDE_FILES:
            file_path = ROOT / f_name
            if file_path.is_file():
                info = zipfile.ZipInfo(f_name, timestamp)
                executable = f_name.endswith(".sh") or f_name.endswith(".py")
                info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, file_path.read_bytes())

        for tdir in (ROOT / "template", ROOT / "runtime-template"):
            if tdir.exists():
                for path in sorted(tdir.rglob("*")):
                    if path.is_file() and not path.name.startswith(".git") and not path.name.startswith("."):
                        if "RELEASE_POST" in path.name.upper():
                            continue
                        # Never package heavy prebuilt runtime tarballs or font assets into the source template
                        if any(path.name.endswith(sfx) for sfx in EXCLUDED_ASSET_SUFFIXES):
                            continue
                        rel_path = path.relative_to(ROOT).as_posix()
                        info = zipfile.ZipInfo(rel_path, timestamp)
                        executable = path.name.endswith(".sh") or path.name == "update-binary" or path.name in {"mffm-helper", "python3"}
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
    print("Excluded      : RELEASE_POST.txt, .git*, runtime tarballs (*.tar.xz, *.tar.gz)")
    return output_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Package MFFMv14 Source Template ZIP")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist", help="destination directory for template ZIP")
    args = parser.parse_args()
    build_template_zip(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
