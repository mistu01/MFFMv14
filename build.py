#!/usr/bin/env python3
"""Compile static or variable fonts into a flashable MFFM Android module."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import zipfile
from pathlib import Path

from font_module import compile_fonts, display_name_for_mode, slugify, update_module_metadata
from zipsigner_auto import ZipSignerError, sign_zip

ROOT = Path(__file__).resolve().parent
PAYLOAD_NAMES = (
    "module.prop", "customize.sh", "service.sh", "uninstall.sh", "post-mount.sh",
    "font-config.sh", "fontlib.sh", "font-config", "META-INF", "Files",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one static or variable Android font module")
    parser.add_argument("--fonts-dir", type=Path, default=ROOT / "Fonts", help="source font directory")
    parser.add_argument("--mode", choices=("auto", "static", "variable"), default="auto")
    parser.add_argument("--name", help="module display name override")
    parser.add_argument("--version", help="module version override")
    parser.add_argument("--version-code", help="numeric module versionCode override")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--no-zip", action="store_true", help="prepare module files without packaging")
    parser.add_argument("--no-sign", action="store_true", help="create an unsigned debugging ZIP")
    parser.add_argument("--keep-hinting", action="store_true", help="do not remove TrueType hinting")
    parser.add_argument("--no-prefix", action="store_true", help="do not prefix internal family metadata with MFFM")
    parser.add_argument("--features", help="comma-separated OpenType feature tags to freeze for Sans-serif (or all families)")
    parser.add_argument("--mono-features", help="comma-separated OpenType feature tags to freeze for Monospace font family")
    parser.add_argument("--serif-features", help="comma-separated OpenType feature tags to freeze for Serif font family")
    parser.add_argument("--interactive", action="store_true", default=None, help="force interactive feature prompt")
    parser.add_argument("--no-interactive", action="store_false", dest="interactive", help="disable interactive feature prompt")
    parser.add_argument("--centered-colon", action="store_true", default=None, help="force centered colon generation/injection for digits (12:30)")
    parser.add_argument("--no-centered-colon", action="store_false", dest="centered_colon", help="disable centered colon injection")
    return parser.parse_args()


def payload_files(module_dir: Path):
    for name in PAYLOAD_NAMES:
        path = module_dir / name
        if not path.exists():
            continue
        if path.is_file():
            yield path, Path(name)
        else:
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.name != ".gitkeep":
                    yield child, child.relative_to(module_dir)


def write_zip(module_dir: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().timetuple()[:6]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in payload_files(module_dir):
            info = zipfile.ZipInfo(relative.as_posix(), timestamp)
            executable = relative.name.endswith(".sh") or relative.name in {"update-binary", "font-config"}
            info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())


def build_module(args: argparse.Namespace, module_dir: Path = ROOT) -> Path | None:
    result = compile_fonts(
        args.fonts_dir.resolve(),
        module_dir,
        requested_mode=args.mode,
        keep_hinting=args.keep_hinting,
        prefix_family=not args.no_prefix,
        features=args.features,
        mono_features=args.mono_features,
        serif_features=args.serif_features,
        interactive_features=args.interactive,
        centered_colon=args.centered_colon,
    )
    display_name = display_name_for_mode(args.name or result.family, result.mode)
    props = update_module_metadata(
        module_dir,
        result.family,
        result.mode,
        name=display_name,
        version=args.version,
        version_code=args.version_code,
        applied_features=result.applied_features,
    )
    print(f"Detected mode : {result.mode}")
    print(f"Font family   : {result.family}")
    if result.applied_features:
        print(f"Freezer sets  : {', '.join(result.applied_features)}")
    print(f"Source faces  : {len(result.faces)}")
    for face in result.faces:
        axes = ", ".join(face.axes) if face.variable else "static"
        print(f"  {face.label}: {face.weight} {face.style}{' condensed' if face.condensed else ''} [{axes}]")
    print(f"Payload fonts : {', '.join(result.payload_files)}")

    if args.no_zip:
        print("Prepared module files; ZIP creation skipped.")
        return None

    if result.applied_features and not any(f in slugify(display_name) for f in result.applied_features):
        file_slug = slugify(f"{display_name} {' '.join(result.applied_features)}")
    else:
        file_slug = slugify(display_name)

    output = args.output_dir.resolve() / f"{props['id']}-{file_slug}-{props['version']}.zip"
    if output.exists():
        output.unlink()
    write_zip(module_dir, output)

    if not args.no_sign:
        try:
            sign_zip(output, ROOT)
        except ZipSignerError as exc:
            output.unlink(missing_ok=True)
            raise SystemExit(str(exc)) from exc
        print("Signature     : verified")
    else:
        print("Signature     : skipped (--no-sign)")

    print(f"Output        : {output}")
    return output


def check_payload(root: Path) -> None:
    for required in ("customize.sh", "fontlib.sh", "font-config"):
        if not (root / required).exists():
            raise SystemExit(f"Template payload is incomplete: {required} is missing")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    check_payload(ROOT)
    build_module(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
