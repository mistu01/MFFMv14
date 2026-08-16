#!/usr/bin/env python3
"""Compile static or variable fonts into a flashable MFFM Android module."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from font_module import (
    WEIGHT_NAMES,
    compile_fonts,
    copy_template,
    display_name_for_mode,
    inspect_fonts,
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

BUILD_CONFIG_NAME = ".mffm-build.json"
BUILD_CONFIG_KEYS = (
    "fonts_dir", "mode", "name", "version", "version_code", "output_dir",
    "keep_hinting", "no_prefix", "features", "mono_features", "serif_features",
    "bengali_features", "centered_colon", "interactive",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one static or variable Android font module")
    parser.add_argument("--fonts-dir", type=Path, help="source font directory (default: ./Fonts)")
    parser.add_argument("--mode", choices=("auto", "static", "variable"), help="font mode detection (default: auto)")
    parser.add_argument("--name", help="module display name override")
    parser.add_argument("--version", help="module version override")
    parser.add_argument("--version-code", help="numeric module versionCode override")
    parser.add_argument("--output-dir", type=Path, help="output directory for the ZIP (default: ./dist)")
    parser.add_argument("--no-zip", action="store_true", default=None, help="prepare module files without packaging")
    parser.add_argument("--no-sign", action="store_true", default=None, help="create an unsigned debugging ZIP")
    parser.add_argument("--keep-hinting", action="store_true", default=None, help="do not remove TrueType hinting")
    parser.add_argument("--no-prefix", action="store_true", default=None, help="do not prefix internal family metadata with MFFM")
    parser.add_argument("--features", help="comma-separated OpenType feature tags to freeze for Sans-serif (or all families)")
    parser.add_argument("--mono-features", help="comma-separated OpenType feature tags to freeze for Monospace font family")
    parser.add_argument("--serif-features", help="comma-separated OpenType feature tags to freeze for Serif font family")
    parser.add_argument("--bengali-features", help="comma-separated OpenType feature tags to freeze for Bengali font family")
    parser.add_argument("--interactive", action="store_true", default=None, help="force interactive feature prompt")
    parser.add_argument("--no-interactive", action="store_false", dest="interactive", help="disable interactive feature prompt")
    parser.add_argument("--centered-colon", action="store_true", default=None, help="force centered colon generation/injection for digits (12:30)")
    parser.add_argument("--no-centered-colon", action="store_false", dest="centered_colon", help="disable centered colon injection")
    parser.add_argument("--config", type=Path, help=f"build config file to load (default: {BUILD_CONFIG_NAME} in the project root, when present)")
    parser.add_argument("--no-config", action="store_true", help="ignore any build config file")
    parser.add_argument("--save-config", action="store_true", help=f"save the effective build options to the config file (default: {BUILD_CONFIG_NAME})")
    parser.add_argument("--inspect", action="store_true", help="report detected fonts, weights and modes without building")
    parser.add_argument("--template", action="store_true", help="package MFFMv14-Source-Template.zip (excluding RELEASE_POST.txt)")
    return parser.parse_args()


def load_build_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read build config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Build config {path} must contain a JSON object")
    unknown = sorted(set(data) - set(BUILD_CONFIG_KEYS))
    if unknown:
        raise SystemExit(f"Unknown keys in {path}: {', '.join(unknown)}")
    return data


def load_config_for(args: argparse.Namespace) -> tuple[dict | None, str | None]:
    if args.no_config:
        return None, None
    if args.config is not None:
        if not args.config.is_file():
            if args.save_config:
                return None, None  # bootstrapping a new config file
            raise SystemExit(f"Build config not found: {args.config}")
        return load_build_config(args.config), str(args.config)
    default = ROOT / BUILD_CONFIG_NAME
    if default.is_file():
        return load_build_config(default), BUILD_CONFIG_NAME
    return None, None


def _config_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def apply_build_config(args: argparse.Namespace, config: dict | None, source: str | None) -> None:
    """Resolve effective options: explicit CLI flags win, then config, then defaults."""
    if config:
        for key in BUILD_CONFIG_KEYS:
            if getattr(args, key, None) is None and key in config:
                setattr(args, key, config[key])
        if source:
            print(f"Build config    : loaded {source}")
    if args.fonts_dir is not None:
        args.fonts_dir = _config_path(args.fonts_dir)
    else:
        args.fonts_dir = ROOT / "Fonts"
    if args.output_dir is not None:
        args.output_dir = _config_path(args.output_dir)
    else:
        args.output_dir = ROOT / "dist"
    if args.mode is None:
        args.mode = "auto"


def _relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def save_build_config(path: Path, args: argparse.Namespace) -> None:
    payload = {
        "fonts_dir": _relative_to_root(args.fonts_dir),
        "mode": args.mode,
        "name": args.name,
        "version": args.version,
        "version_code": args.version_code,
        "output_dir": _relative_to_root(args.output_dir),
        "keep_hinting": bool(args.keep_hinting),
        "no_prefix": bool(args.no_prefix),
        "features": args.features,
        "mono_features": args.mono_features,
        "serif_features": args.serif_features,
        "bengali_features": args.bengali_features,
        "centered_colon": args.centered_colon,
        "interactive": args.interactive,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Build config    : saved {path}")


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


def zip_timestamp() -> tuple[int, int, int, int, int, int]:
    """Archive entry timestamp; honours SOURCE_DATE_EPOCH for reproducible
    output (clamped to the 1980 ZIP format epoch)."""
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw:
        try:
            epoch = int(raw)
        except ValueError:
            raise SystemExit(f"SOURCE_DATE_EPOCH must be an integer, got: {raw!r}")
        return time.gmtime(max(epoch, 315532800))[:6]
    return dt.datetime.now().timetuple()[:6]


def write_zip(module_dir: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = zip_timestamp()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in payload_files(module_dir):
            info = zipfile.ZipInfo(relative.as_posix(), timestamp)
            executable = relative.name.endswith(".sh") or relative.name == "update-binary"
            info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())


def run_inspection(args: argparse.Namespace) -> None:
    report = inspect_fonts(args.fonts_dir.resolve(), args.mode)
    print("=" * 60)
    print("MFFMv14 font inspection")
    print("=" * 60)
    print(f"Fonts directory: {report['fonts_dir']}")
    if "primary_mode" in report:
        print(f"Primary mode   : {report['primary_mode']}")
        print(f"Primary family : {', '.join(report['primary_families'])}")
    for key, info in report["categories"].items():
        faces = info["faces"]
        if not faces:
            print(f"- {info['label']:<10}: not provided")
            continue
        print(f"- {info['label']:<10}: {', '.join(info['families'])} [{info['mode']}]")
        for face in faces:
            axes = ", ".join(
                f"{tag}={values[0]:g}..{values[2]:g}" for tag, values in face["axes"].items()
            ) or "static"
            print(
                f"    * {face['file']}: {face['weight_name']} {face['style']}"
                f"{' condensed' if face['condensed'] else ''} [{axes}]"
            )
    for note in report["notes"]:
        print(f"[!] {note}")


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
            keep_hinting=bool(args.keep_hinting),
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

        family_faces = result.family_faces or {"sans": result.faces}
        print("Font families :")
        for cat, label in (
            ("sans", "Sans-serif"),
            ("mono", "Monospace"),
            ("serif", "Serif"),
            ("bengali", "Bengali"),
        ):
            cat_faces = tuple(family_faces.get(cat, ()))
            if not cat_faces:
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
        build_template_zip(args.output_dir if args.output_dir is not None else ROOT / "dist")
        return 0
    config, config_source = load_config_for(args)
    apply_build_config(args, config, config_source)
    if args.save_config:
        save_build_config(args.config if args.config is not None else ROOT / BUILD_CONFIG_NAME, args)
    if args.inspect:
        run_inspection(args)
        return 0
    build_module(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
