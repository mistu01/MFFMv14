#!/usr/bin/env python3
"""Migrate old static or variable MFFM ZIPs onto the unified template."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

from build import ROOT, write_zip
from font_module import FONT_EXTENSIONS, clean_family_name, compile_fonts, read_props, slugify, update_module_metadata
from zipsigner_auto import ZipSignerError, sign_zip


TEMPLATE_ITEMS = (
    "module.prop", "customize.sh", "service.sh", "uninstall.sh", "post-mount.sh", "META-INF",
)
OLD_PRIMARY_NAMES = (
    "DroidSans.ttc", "DroidSans.ttf", "DroidSans.otf", "RobotoStatic-Regular.ttf",
    "DroidSans-Italic.ttf", "DroidSans-Italic.otf", "DroidSans-Bold.ttf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update old MFFM module ZIPs to the unified template")
    parser.add_argument("--old-dir", type=Path, default=ROOT / "Old Modules")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "Updated Modules")
    parser.add_argument("--mode", choices=("auto", "static", "variable"), default="auto")
    parser.add_argument("--name", help="override every output display name (best for one input ZIP)")
    parser.add_argument("--version")
    parser.add_argument("--version-code")
    parser.add_argument("--no-sign", action="store_true")
    parser.add_argument("--keep-hinting", action="store_true")
    parser.add_argument("--no-prefix", action="store_true")
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


def find_sources(old_root: Path) -> list[Path]:
    files_dir = old_root / "Files"
    candidates: list[Path] = []
    for name in OLD_PRIMARY_NAMES:
        path = files_dir / name
        if path.is_file() and path not in candidates:
            candidates.append(path)
    if not candidates:
        candidates.extend(
            path for path in files_dir.iterdir()
            if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS
            and not path.name.startswith(("Beng", "Serif", "Mono"))
        ) if files_dir.is_dir() else None
    if not candidates:
        for directory in (old_root / "system" / "fonts", old_root):
            if directory.is_dir():
                candidates.extend(
                    path for path in directory.iterdir()
                    if path.is_file() and path.name in OLD_PRIMARY_NAMES
                )
    if not candidates:
        raise SystemExit(f"No prepared primary font payload found in {old_root}")

    # DroidSans-Bold.ttf was v13's italic variable payload. In static v12 the
    # single collection is sufficient, so remove fallback extras after probing.
    primary = candidates[0]
    if primary.suffix.lower() in {".ttc", ".otc"}:
        return [primary]
    if primary.name in {"DroidSans.ttf", "DroidSans.otf"}:
        selected = [primary]
        for path in candidates[1:]:
            if path.name in {"DroidSans-Italic.ttf", "DroidSans-Italic.otf", "DroidSans-Bold.ttf"}:
                selected.append(path)
                break
        return selected
    return candidates


def copy_template(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATE_ITEMS:
        source = ROOT / name
        target = destination / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    (destination / "Files").mkdir()


def copy_optional_assets(old_root: Path, new_root: Path) -> None:
    old_files = old_root / "Files"
    if not old_files.is_dir():
        return
    for path in old_files.iterdir():
        if path.is_file() and path.name.startswith(("Beng", "Serif", "Mono")):
            shutil.copy2(path, new_root / "Files" / path.name)


def old_display_name(old_root: Path) -> str | None:
    name = read_props(old_root / "module.prop").get("name", "")
    name = name.split("]", 1)[-1] if "]" in name else name
    return clean_family_name(name) if name.strip() else None


def reserve_output(output_dir: Path, stem: str, force: bool, reserved: set[Path]) -> Path:
    output = output_dir / f"{stem}.zip"
    if output not in reserved and (force or not output.exists()):
        reserved.add(output)
        return output
    if not force and output.exists():
        raise SystemExit(f"Output exists (use --force): {output}")
    index = 2
    while True:
        candidate = output_dir / f"{stem}-{index}.zip"
        if candidate not in reserved and (force or not candidate.exists()):
            reserved.add(candidate)
            return candidate
        index += 1


def update_one(zip_path: Path, args: argparse.Namespace, reserved: set[Path]) -> Path:
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
        sources = find_sources(old_root)
        for index, source in enumerate(sources):
            # Preserve a style-bearing name where possible; metadata is the primary signal.
            target_name = source.name
            if (source_dir / target_name).exists():
                target_name = f"{index}-{target_name}"
            shutil.copy2(source, source_dir / target_name)

        copy_template(module_dir)
        copy_optional_assets(old_root, module_dir)
        result = compile_fonts(
            source_dir, module_dir,
            requested_mode=args.mode,
            keep_hinting=args.keep_hinting,
            prefix_family=not args.no_prefix,
        )
        display = args.name or old_display_name(old_root) or result.family
        props = update_module_metadata(
            module_dir, result.family, result.mode,
            name=display, version=args.version, version_code=args.version_code,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = reserve_output(
            args.output_dir.resolve(),
            f"{props['id']}-{slugify(display)}-{props['version']}",
            args.force,
            reserved,
        )
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
        if args.keep_temp:
            print(f"  temp   : {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    args = parse_args()
    if not args.old_dir.is_dir():
        raise SystemExit(f"Old module directory does not exist: {args.old_dir}")
    inputs = sorted(args.old_dir.glob("*.zip"))
    if not inputs:
        raise SystemExit(f"No ZIP modules found in {args.old_dir}")
    reserved: set[Path] = set()
    for zip_path in inputs:
        update_one(zip_path, args, reserved)
    print(f"Updated {len(inputs)} module(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
