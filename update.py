#!/usr/bin/env python3
"""Migrate old static or variable MFFM ZIPs onto the MFFMv14 template."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

from build import ROOT, write_zip
from font_module import (
    FONT_EXTENSIONS, classify_source_path, clean_family_name, compile_fonts, copy_template,
    display_name_for_mode, read_props, slugify, update_module_metadata,
)
from zipsigner_auto import ZipSignerError, sign_zip

OLD_PRIMARY_NAMES = (
    "DroidSans.ttc", "DroidSans.ttf", "DroidSans.otf", "RobotoStatic-Regular.ttf",
    "DroidSans-Italic.ttf", "DroidSans-Italic.otf", "DroidSans-Bold.ttf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update old MFFM module ZIPs to the MFFMv14 template")
    parser.add_argument(
        "--old-dir", "--input", "-i",
        type=Path,
        default=ROOT / "Old Modules",
        dest="old_dir",
        help="input directory containing old ZIP modules, or path to a single ZIP file",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--mode", choices=("auto", "static", "variable"), default="auto")
    parser.add_argument("--name", help="override every output display name (best for one input ZIP)")
    parser.add_argument("--version")
    parser.add_argument("--version-code")
    parser.add_argument("--no-sign", action="store_true")
    parser.add_argument("--keep-hinting", action="store_true")
    parser.add_argument("--no-prefix", action="store_true")
    parser.add_argument("--features", help="comma-separated OpenType feature tags to freeze for Sans-serif (or all families)")
    parser.add_argument("--mono-features", help="comma-separated OpenType feature tags to freeze for Monospace font family")
    parser.add_argument("--serif-features", help="comma-separated OpenType feature tags to freeze for Serif font family")
    parser.add_argument("--bengali-features", help="comma-separated OpenType feature tags to freeze for Bengali font family")
    parser.add_argument("--interactive", action="store_true", default=None, help="force interactive feature prompt")
    parser.add_argument("--no-interactive", action="store_false", dest="interactive", help="disable interactive feature prompt")
    parser.add_argument("--centered-colon", action="store_true", default=None, help="force centered colon generation/injection for digits (12:30)")
    parser.add_argument("--no-centered-colon", action="store_false", dest="centered_colon", help="disable centered colon injection")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-temp", action="store_true")
    return parser.parse_args()


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise SystemExit(f"Unsafe ZIP path: {member.filename}")
    archive.extractall(destination)


def locate_module_root(extracted: Path) -> Path:
    if (extracted / "module.prop").exists():
        return extracted
    matches = list(extracted.rglob("module.prop"))
    if len(matches) == 1:
        return matches[0].parent
    raise SystemExit(f"Could not identify a unique module root in {extracted}")


def find_categorized_sources(old_root: Path) -> dict[str, list[Path]]:
    files_dir = old_root / "Files"
    categorized: dict[str, list[Path]] = {"sans": [], "mono": [], "serif": [], "bengali": []}

    if files_dir.is_dir():
        for path in sorted(files_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in FONT_EXTENSIONS:
                continue
            rel_parts = [part.lower() for part in path.relative_to(files_dir).parts[:-1]]
            category = classify_source_path(rel_parts, path.stem.lower())
            categorized[category].append(path)

    if not any(categorized.values()):
        for directory in (old_root / "system" / "fonts", old_root):
            if directory.is_dir():
                for path in sorted(directory.iterdir()):
                    if not path.is_file() or path.suffix.lower() not in FONT_EXTENSIONS:
                        continue
                    if path.name in OLD_PRIMARY_NAMES:
                        categorized["sans"].append(path)

    return categorized


TEMPLATE_DIR = ROOT / "template"


def old_display_name(old_root: Path) -> str | None:
    name = read_props(old_root / "module.prop").get("name", "")
    name = name.split("]", 1)[-1] if "]" in name else name
    return clean_family_name(name) if name.strip() else None


def reserve_output(output_dir: Path, stem: str, force: bool, reserved: set[Path]) -> Path | None:
    output = output_dir / f"{stem}.zip"
    if output not in reserved and (force or not output.exists()):
        reserved.add(output)
        return output
    if not force and output.exists():
        return None
    index = 2
    while True:
        candidate = output_dir / f"{stem}-{index}.zip"
        if candidate not in reserved and (force or not candidate.exists()):
            reserved.add(candidate)
            return candidate
        index += 1


def update_one(zip_path: Path, args: argparse.Namespace, reserved: set[Path]) -> Path | None:
    work = Path(tempfile.mkdtemp(prefix="mffm-update-"))
    extracted = work / "old"
    source_dir = work / "sources"
    module_dir = work / "module"
    extracted.mkdir()
    source_dir.mkdir()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            safe_extract(archive, extracted)
        old_root = locate_module_root(extracted)
        categorized = find_categorized_sources(old_root)
        if not any(categorized.values()):
            raise SystemExit(f"No prepared font payload found in {old_root}")

        cat_names = {"sans": "Sans", "mono": "Monospace", "serif": "Serif", "bengali": "Bengali"}
        for cat_key, paths in categorized.items():
            if not paths:
                continue
            cat_dir = source_dir / cat_names[cat_key]
            cat_dir.mkdir(parents=True, exist_ok=True)
            for index, source in enumerate(paths):
                target_name = source.name
                if (cat_dir / target_name).exists():
                    target_name = f"{index}-{target_name}"
                shutil.copy2(source, cat_dir / target_name)

        copy_template(TEMPLATE_DIR, module_dir)
        result = compile_fonts(
            source_dir, module_dir,
            requested_mode=args.mode,
            keep_hinting=args.keep_hinting,
            prefix_family=not args.no_prefix,
            features=args.features,
            mono_features=args.mono_features,
            serif_features=args.serif_features,
            bengali_features=args.bengali_features,
            interactive_features=args.interactive,
            centered_colon=args.centered_colon,
        )
        display = display_name_for_mode(
            args.name or old_display_name(old_root) or result.family,
            result.mode,
        )
        props = update_module_metadata(
            module_dir, result.family, result.mode,
            name=display, version=args.version, version_code=args.version_code,
            applied_features=result.applied_features,
        )
        if result.applied_features and not any(f in slugify(display) for f in result.applied_features):
            file_slug = slugify(f"{display} {' '.join(result.applied_features)}")
        else:
            file_slug = slugify(display)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = reserve_output(
            args.output_dir.resolve(),
            f"mffm14-{file_slug}-{props['version']}",
            args.force,
            reserved,
        )
        if output is None:
            existing = args.output_dir.resolve() / f"mffm14-{file_slug}-{props['version']}.zip"
            print(f"Skipping {zip_path.name}: output already exists (use --force to overwrite): {existing}")
            return None
        write_zip(module_dir, output)
        if not args.no_sign:
            try:
                sign_zip(output, ROOT)
            except ZipSignerError as exc:
                output.unlink(missing_ok=True)
                raise SystemExit(str(exc)) from exc
        print(f"Updated {zip_path.name}")
        print(f"  mode   : {result.mode}")
        print(f"  family : {display}")
        print(f"  output : {output}")
        return output
    finally:
        if getattr(args, "keep_temp", False):
            print(f"  temp   : {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    args = parse_args()
    if args.old_dir.is_file():
        inputs = [args.old_dir]
    elif args.old_dir.is_dir():
        inputs = sorted(args.old_dir.glob("*.zip"))
        if not inputs:
            raise SystemExit(f"No ZIP modules found in {args.old_dir}")
    else:
        raise SystemExit(f"Old module directory or file does not exist: {args.old_dir}")
    reserved: set[Path] = set()
    updated = 0
    skipped = 0
    for zip_path in inputs:
        if update_one(zip_path, args, reserved) is None:
            skipped += 1
        else:
            updated += 1
    print(f"Updated {updated} module(s), skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
