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
    "module.prop", "customize.sh", "service.sh", "action.sh", "uninstall.sh", "post-mount.sh",
    "META-INF", "Files",
)

BUILD_CONFIG_NAME = ".mffm-build.json"
BUILD_CONFIG_KEYS = (
    "fonts_dir", "mode", "name", "version", "version_code", "output_dir",
    "keep_hinting", "no_prefix", "features", "mono_features", "serif_features",
    "bengali_features", "centered_colon", "colon_offset", "colon_shift",
    "colon_alignment", "colon_rule", "equalize_digits", "pua_colon",
    "synthetic_italic", "synthetic_italic_angle", "interactive",
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
    parser.add_argument("--colon-offset", "--colon-shift", type=int, default=0, help="vertical offset in font units (+/-) for centered colon (clock colon shift, e.g. +20, -30)")
    parser.add_argument("--colon-alignment", choices=("center", "cap_height", "x_height"), default="center", help="alignment target for centered colon: center, cap_height, or x_height (default: center)")
    parser.add_argument("--colon-rule", choices=("between_digits", "after_digit", "always"), default="between_digits", help="contextual rule for centered colon substitution (default: between_digits)")
    parser.add_argument("--equalize-digits", action="store_true", default=None, help="equalize advance widths of digits (0-9) and center contours for wobble-free clocks")
    parser.add_argument("--no-equalize-digits", action="store_false", dest="equalize_digits", help="do not equalize digit advance widths")
    parser.add_argument("--pua-colon", action="store_true", default=None, help="force mapping colon to Android lockscreen clock PUA (U+EE01, U+2236, U+2982)")
    parser.add_argument("--no-pua-colon", action="store_false", dest="pua_colon", help="disable Android lockscreen clock PUA mapping")
    parser.add_argument("--synthetic-italic", action="store_true", default=None, help="synthesize Sans-serif italic companion faces if missing")
    parser.add_argument("--no-synthetic-italic", action="store_false", dest="synthetic_italic", help="disable synthetic italic generation")
    parser.add_argument("--synthetic-italic-angle", type=float, default=-12.0, help="slant angle in degrees for synthetic italic (default: -12.0)")
    parser.add_argument("--config", type=Path, help=f"build config file to load (default: {BUILD_CONFIG_NAME} in the project root, when present)")
    parser.add_argument("--no-config", action="store_true", help="ignore any build config file")
    parser.add_argument("--save-config", action="store_true", help=f"save the effective build options to the config file (default: {BUILD_CONFIG_NAME})")
    parser.add_argument("--inspect", action="store_true", help="report detected fonts, weights and modes without building")
    parser.add_argument("--template", action="store_true", help="package MFFMv14-Source-Template.zip (excluding RELEASE_POST.txt)")
    parser.add_argument("--standalone-template", action="store_true", help="package MFFMv14-Standalone-Template.zip")
    parser.add_argument("--runtime", action="store_true", help="build MFFM Runtime module ZIP (shared Python + fontTools)")
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
        "colon_offset": args.colon_offset,
        "colon_alignment": args.colon_alignment,
        "colon_rule": args.colon_rule,
        "equalize_digits": bool(args.equalize_digits),
        "pua_colon": bool(args.pua_colon),
        "synthetic_italic": bool(args.synthetic_italic),
        "synthetic_italic_angle": float(args.synthetic_italic_angle or -12.0),
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
            data = source.read_bytes()
            if relative.suffix.lower() in {".sh", ".prop", ".xml", ".json", ".conf", ".txt", ".md", ".py"} or relative.name in {"update-binary", "updater-script"}:
                data = data.replace(b"\r\n", b"\n")
            archive.writestr(info, data)


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

    fonts_dir = (args.fonts_dir or (ROOT / "Fonts")).resolve()
    out_dir = (args.output_dir or (ROOT / "dist")).resolve()

    print("=" * 64, flush=True)
    print("  MFFMv14 Module Builder", flush=True)
    print("=" * 64, flush=True)
    print(f"  Source Directory : {fonts_dir}", flush=True)
    print(f"  Output Directory : {out_dir}", flush=True)
    print(f"  Detection Mode   : {args.mode or 'auto'}", flush=True)
    print(f"  TrueType Hinting : {'Preserve' if args.keep_hinting else 'Strip (Clean rendering)'}", flush=True)
    print(f"  Family Prefix    : {'Disabled (--no-prefix)' if args.no_prefix else 'Enabled ([MFFM] / Mistu)'}", flush=True)
    if args.features:
        print(f"  Sans Features    : {args.features}", flush=True)
    if args.centered_colon is not False:
        offset_str = f" ({args.colon_offset:+d} font units)" if getattr(args, "colon_offset", 0) else ""
        print(f"  Centered Colon   : Enabled [{getattr(args, 'colon_alignment', 'center')}, {getattr(args, 'colon_rule', 'between_digits')}{offset_str}]", flush=True)
    if getattr(args, "equalize_digits", False):
        print("  Digit Widths     : Equalize for wobble-free clocks", flush=True)
    if args.pua_colon:
        print("  Lockscreen PUA   : Map to U+EE01, U+2236, U+2982", flush=True)
    if args.synthetic_italic:
        print(f"  Synthetic Italic : Enabled ({args.synthetic_italic_angle or -12.0}° slant)", flush=True)
    print("-" * 64, flush=True)
    print(flush=True)

    work_dir = Path(tempfile.mkdtemp(prefix="mffm-build-"))
    module_dir = work_dir / "module"
    try:
        copy_template(TEMPLATE_DIR, module_dir)
        result = compile_fonts(
            fonts_dir,
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
            colon_offset=int(getattr(args, "colon_offset", 0) or 0),
            colon_alignment=str(getattr(args, "colon_alignment", "center") or "center"),
            colon_rule=str(getattr(args, "colon_rule", "between_digits") or "between_digits"),
            equalize_digits=bool(getattr(args, "equalize_digits", False)),
            pua_colon=args.pua_colon,
            synthetic_italic=args.synthetic_italic,
            synthetic_italic_angle=float(args.synthetic_italic_angle or -12.0),
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
            injected_colon=result.injected_colon,
            synthesized_italic=result.synthesized_italic,
        )

        print(flush=True)
        print("-" * 64, flush=True)
        print("  Packaging & Signing Flashable Module", flush=True)
        print("-" * 64, flush=True)
        print("  * Updating module metadata (module.prop)...", flush=True)
        print(f"    -> Name        : {props.get('name', display_name)}", flush=True)
        print(f"    -> ID          : {props.get('id', '')}", flush=True)
        print(f"    -> Version     : {props.get('version', '')} (code: {props.get('versionCode', '')})", flush=True)

        if args.no_zip:
            print(f"  * Prepared module files at: {module_dir}", flush=True)
            return None

        if result.applied_features and not any(f in slugify(display_name) for f in result.applied_features):
            file_slug = slugify(f"{display_name} {' '.join(result.applied_features)}")
        else:
            file_slug = slugify(display_name)

        output = out_dir / f"mffm14-{file_slug}-{props['version']}.zip"
        if output.exists():
            output.unlink()

        print(f"  * Compressing module archive: {output.name}...", flush=True)
        write_zip(module_dir, output)
        size_bytes = output.stat().st_size
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.1f} KB"
        print(f"    -> Archive created ({size_str}) [OK]", flush=True)

        if not args.no_sign:
            print("  * Signing archive with ZipSignerust...", flush=True)
            try:
                sign_zip(output, ROOT)
                print("    -> Signature verified successfully [OK]", flush=True)
            except ZipSignerError as exc:
                output.unlink(missing_ok=True)
                raise SystemExit(str(exc)) from exc
        else:
            print("  * Signing skipped (--no-sign)", flush=True)

        print(flush=True)
        print("=" * 64, flush=True)
        print("  MFFMv14 Module Built Successfully!", flush=True)
        print("=" * 64, flush=True)
        print(f"  Module Name   : {props.get('name', display_name)}", flush=True)
        print(f"  Module ID     : {props.get('id', '')}", flush=True)
        print(f"  Version       : {props.get('version', '')} (code: {props.get('versionCode', '')})", flush=True)
        print(f"  Detected Mode : {result.mode}", flush=True)
        print(f"  Font Family   : {result.family}", flush=True)
        if result.applied_features:
            print(f"  Freezer Tags  : {', '.join(result.applied_features)}", flush=True)
        print(f"  Source Faces  : {len(result.faces)}", flush=True)
        print(f"  Payload Fonts : {', '.join(result.payload_files)}", flush=True)
        print(f"  Output File   : {output}", flush=True)
        print(f"  File Size     : {size_str}", flush=True)
        print("  Status        : Ready to flash in Magisk / KernelSU / APatch", flush=True)
        print("=" * 64, flush=True)
        return output
    finally:
        if not args.no_zip:
            shutil.rmtree(work_dir, ignore_errors=True)


def main() -> int:
    args = parse_args()
    if args.runtime:
        from build_runtime import build_runtime
        if args.output_dir is None:
            args.output_dir = ROOT / "dist"
        else:
            args.output_dir = _config_path(args.output_dir)
        build_runtime(args)
        return 0
    if args.template:
        from package_template import build_template_zip
        build_template_zip(args.output_dir if args.output_dir is not None else ROOT / "dist")
        return 0
    if args.standalone_template:
        from build_standalone import package_standalone_template_zip
        package_standalone_template_zip(args.output_dir if args.output_dir is not None else ROOT / "dist")
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
