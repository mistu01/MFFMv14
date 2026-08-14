#!/usr/bin/env python3
"""Compile static or variable fonts into a flashable MFFM Android module."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import tempfile
import zipfile
from pathlib import Path

from font_module import (
    WEIGHT_NAMES,
    compile_fonts,
    display_name_for_mode,
    slugify,
    update_module_metadata,
)
from zipsigner_auto import ZipSignerError, sign_zip

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "template"
PAYLOAD_NAMES = (
    "module.prop", "customize.sh", "service.sh", "uninstall.sh", "post-mount.sh",
    "font-config.sh", "META-INF", "Files",
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
    parser.add_argument("--bengali-features", help="comma-separated OpenType feature tags to freeze for Bengali font family")
    parser.add_argument("--interactive", action="store_true", default=None, help="force interactive feature prompt")
    parser.add_argument("--no-interactive", action="store_false", dest="interactive", help="disable interactive feature prompt")
    parser.add_argument("--centered-colon", action="store_true", default=None, help="force centered colon generation/injection for digits (12:30)")
    parser.add_argument("--no-centered-colon", action="store_false", dest="centered_colon", help="disable centered colon injection")
    parser.add_argument("--template", action="store_true", help="package MFFMv14-Source-Template.zip (excluding RELEASE_POST.txt)")
    return parser.parse_args()


def copy_template(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for name in ("module.prop", "customize.sh", "service.sh", "uninstall.sh", "post-mount.sh", "META-INF"):
        source = source_dir / name
        target = destination_dir / name
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.is_file():
            shutil.copy2(source, target)
    (destination_dir / "Files").mkdir(exist_ok=True)


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
            executable = relative.name.endswith(".sh") or relative.name == "update-binary"
            info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())


def build_module(args: argparse.Namespace) -> Path | None:
    if not (TEMPLATE_DIR / "customize.sh").exists():
        raise SystemExit(f"Template payload is incomplete: customize.sh is missing in {TEMPLATE_DIR}")

    work_dir = Path(tempfile.mkdtemp(prefix="mffm-build-"))
    module_dir = work_dir / "module"
    try:
        copy_template(TEMPLATE_DIR, module_dir)
        result = compile_fonts(
            args.fonts_dir.resolve(),
            module_dir,
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
        print("=" * 60)
        print("MFFMv14 module compiled")
        print("=" * 60)
        print(f"Module name   : {props.get('name', display_name)}")
        print(f"Module id     : {props.get('id', '')}")
        print(f"Version       : {props.get('version', '')} (versionCode {props.get('versionCode', '')})")
        print(f"Detected mode : {result.mode}")
        print(f"Font family   : {result.family}")
        if result.applied_features:
            print(f"Freezer sets  : {', '.join(result.applied_features)}")
        print(f"Source faces  : {len(result.faces)}")
        print(f"Payload fonts : {', '.join(result.payload_files)}")

        # Per-family breakdown covering EVERY provided/detected family, not just
        # Sans. `result.family_faces` maps each category to its detected faces.
        family_labels = (
            ("sans", "Sans-serif"),
            ("serif", "Serif"),
            ("mono", "Monospace"),
            ("bengali", "Bengali"),
        )
        family_faces = result.family_faces or {"sans": result.faces}
        print("Font families :")
        for cat, label in family_labels:
            cat_faces = tuple(family_faces.get(cat, ()))
            if not cat_faces:
                # Mandatory Sans should always be present; other families are
                # optional. Never hide a family that was actually provided.
                print(f"  - {label:<10}: not provided")
                continue
            display_names = sorted({face.family for face in cat_faces}) or [result.family]
            fam_display = ", ".join(display_names)
            fam_mode = "variable" if any(face.variable for face in cat_faces) else "static"
            source_files = sorted({face.path.name for face in cat_faces})
            print(f"  - {label:<10}: {fam_display}")
            print(f"      mode      : {fam_mode}")
            print(f"      faces     : {len(cat_faces)}")
            print(f"      source    : {', '.join(source_files)}")
            for face in cat_faces:
                axes = ", ".join(face.axes) if face.variable else "static"
                weight_name = WEIGHT_NAMES.get(face.weight, str(face.weight))
                print(
                    f"        * {face.label}: {weight_name} {face.style}"
                    f"{' condensed' if face.condensed else ''} [{axes}]"
                )

        if args.no_zip:
            print(f"Prepared module files at: {module_dir}")
            return None

        if result.applied_features and not any(f in slugify(display_name) for f in result.applied_features):
            file_slug = slugify(f"{display_name} {' '.join(result.applied_features)}")
        else:
            file_slug = slugify(display_name)

        output = args.output_dir.resolve() / f"mffm14-{file_slug}-{props['version']}.zip"
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
    finally:
        if not args.no_zip:
            shutil.rmtree(work_dir, ignore_errors=True)


def main() -> int:
    args = parse_args()
    if args.template:
        from package_template import build_template_zip
        build_template_zip(args.output_dir)
        return 0
    build_module(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
