#!/usr/bin/env python3
"""MFFM Runtime Helper — on-device font metrics normalization, TTC bundling, and indexed XML compilation."""

import argparse
import os
import re
import sys
from pathlib import Path

FFIX3_REFERENCE_UPM = 2048
FFIX3_METRICS = (
    ("hhea", "ascent", 2128),
    ("hhea", "descent", -550),
    ("hhea", "lineGap", 0),
    ("OS/2", "sTypoAscender", 2128),
    ("OS/2", "sTypoDescender", -550),
    ("OS/2", "sTypoLineGap", 0),
    ("OS/2", "sCapHeight", 1456),
    ("OS/2", "sxHeight", 1082),
    ("head", "yMax", 2163),
    ("head", "yMin", -555),
)

WEIGHT_NAMES = {
    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular",
    500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black",
}

WEIGHT_LABELS = (
    (r"extra[\s_-]*black|ultra[\s_-]*black", 900),
    (r"extra[\s_-]*bold|ultra[\s_-]*bold", 800),
    (r"semi[\s_-]*bold|demi[\s_-]*bold", 600),
    (r"extra[\s_-]*light|ultra[\s_-]*light", 200),
    (r"thin|hairline", 100),
    (r"black|heavy", 900),
    (r"bold", 700),
    (r"medium", 500),
    (r"light", 300),
    (r"regular|normal|book|roman", 400),
)


def _scale_value(val: int, from_upm: int, to_upm: int = 2048) -> int:
    return int(round(val * to_upm / from_upm))


def fix_font_metrics(font, target_upm: int = 2048) -> None:
    head = font.get("head")
    os2 = font.get("OS/2")
    hhea = font.get("hhea")
    if head is None:
        return
    upm = int(getattr(head, "unitsPerEm", target_upm))

    for table_name, field_name, ref_val in FFIX3_METRICS:
        table = font.get(table_name)
        if table is not None and hasattr(table, field_name):
            setattr(table, field_name, int(round(ref_val * upm / target_upm)))

    if os2 is not None:
        os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
        if "fvar" in font:
            os2.usWeightClass = 400


def remove_font_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()


def inspect_face(path: str, font_num: int | None = None) -> dict:
    from fontTools.ttLib import TTFont
    kwargs = {"lazy": True}
    if font_num is not None:
        kwargs["fontNumber"] = font_num
    with TTFont(path, **kwargs) as font:
        os2 = font.get("OS/2")
        head = font.get("head")
        name = font.get("name")
        family = (name.getDebugName(16) or name.getDebugName(1) or os.path.splitext(os.path.basename(path))[0]) if name else ""
        sub = (name.getDebugName(17) or name.getDebugName(2) or "") if name else ""
        full = (name.getDebugName(4) or "") if name else ""
        label = f"{sub} {family} {full} {os.path.splitext(os.path.basename(path))[0]}".lower()

        italic = bool(
            "italic" in label or "oblique" in label
            or (os2 is not None and int(getattr(os2, "fsSelection", 0)) & 1)
            or (head is not None and int(getattr(head, "macStyle", 0)) & 2)
        )
        width_class = int(getattr(os2, "usWidthClass", 5)) if os2 is not None else 5
        condensed = width_class <= 4 or "condensed" in label or "narrow" in label
        os2_w = int(getattr(os2, "usWeightClass", 0)) if os2 is not None else 0

        name_wt = None
        for pattern, w in WEIGHT_LABELS:
            if re.search(rf"(?i)(?:^|[\s_-])(?:{pattern})(?:$|[\s_-])", label):
                name_wt = w
                break

        if os2_w in WEIGHT_NAMES and os2_w != 400:
            if name_wt and name_wt != os2_w and abs(name_wt - 400) > abs(os2_w - 400):
                weight = name_wt
            else:
                weight = os2_w
        elif name_wt:
            weight = name_wt
        elif os2_w in WEIGHT_NAMES:
            weight = os2_w
        else:
            weight = min(WEIGHT_NAMES, key=lambda w: (abs(w - (os2_w or 400)), w))

        axes = {}
        if "fvar" in font:
            for axis in font["fvar"].axes:
                axes[axis.axisTag] = (float(axis.minValue), float(axis.defaultValue), float(axis.maxValue))

        return {
            "path": path,
            "font_number": font_num,
            "family": family,
            "style_name": sub,
            "weight": weight,
            "style": "italic" if italic else "normal",
            "condensed": condensed,
            "variable": bool(axes),
            "axes": axes,
        }


def format_num(val: float) -> str:
    return str(int(val)) if float(val).is_integer() else f"{val:g}"


def font_xml(filename: str, weight: int, style: str, index: int | None = None, axes: dict[str, float] | None = None) -> str:
    attrs = f' weight="{weight}" style="{style}"'
    if index is not None:
        attrs += f' index="{index}"'
    if not axes:
        return f"    <font{attrs}>{filename}</font>"
    lines = [f"    <font{attrs}>{filename}"]
    for tag, val in axes.items():
        lines.append(f'      <axis tag="{tag}" stylevalue="{format_num(val)}"/>')
    lines.append("    </font>")
    return "\n".join(lines)


def calc_axis_values(face: dict, weight: int, italic: bool) -> dict[str, float] | None:
    if "wght" not in face["axes"]:
        return None
    min_w, def_w, max_w = face["axes"]["wght"]
    if not min_w <= weight <= max_w:
        return None
    values = {}
    for tag, (a_min, a_def, a_max) in face["axes"].items():
        if tag == "wght":
            v = float(weight)
        elif tag == "ital":
            v = 1.0 if italic else 0.0
        elif tag == "slnt":
            v = (a_min if a_min < 0 else a_max) if italic else (0.0 if a_min <= 0 <= a_max else a_def)
        else:
            v = a_def
        values[tag] = max(a_min, min(a_max, v))
    return values


def scan_weights(dirs: list[str]) -> None:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.stderr.write("fontTools not available\n"); sys.exit(1)
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not (f.lower().endswith(".ttf") or f.lower().endswith(".otf")):
                continue
            path = os.path.join(d, f)
            try:
                face = inspect_face(path)
                print(f"{face['weight']}:{face['style']}:{face['path']}")
            except Exception as e:
                sys.stderr.write(f"scan skip {path}: {e}\n")


def build_ttc(out_path: str, files: list[str]) -> None:
    try:
        from fontTools.ttLib import TTFont, TTCollection
    except ImportError:
        sys.stderr.write("fontTools not available for TTC\n"); sys.exit(1)
    if not files:
        sys.stderr.write("no input files for TTC\n"); sys.exit(1)
    col = TTCollection()
    for f in files:
        f = f.strip()
        if not f: continue
        try:
            col.fonts.append(TTFont(f))
        except Exception as e:
            sys.stderr.write(f"Error loading {f}: {e}\n")
    if not col.fonts:
        sys.stderr.write("no fonts loaded\n"); sys.exit(1)
    col.save(out_path)
    print(f"TTC saved {out_path} with {len(col.fonts)} fonts")


def format_axis_meta(face: dict, italic: bool = False) -> str:
    if not face.get("axes"): return ""
    default_vals = calc_axis_values(face, int(face["axes"]["wght"][1]), italic) or {} if "wght" in face["axes"] else {}
    parts = []
    for tag, (a_min, a_def, a_max) in face["axes"].items():
        val = default_vals.get(tag, a_def)
        parts.append(f"{tag}|{format_num(a_min)}|{format_num(val)}|{format_num(a_max)}")
    return " ".join(parts)


def supported_weights_str(face: dict) -> str:
    if "wght" not in face.get("axes", {}): return ""
    a_min, _, a_max = face["axes"]["wght"]
    return " ".join(str(w) for w in WEIGHT_NAMES if a_min <= w <= a_max)


def compile_bundle(out_dir: str, sans_dirs: list[str], mono_dirs: list[str] = None, serif_dirs: list[str] = None, bengali_dirs: list[str] = None, keep_hinting: bool = False, fix_metrics: bool = True) -> int:
    from fontTools.ttLib import TTFont, TTCollection
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    def collect_faces(dirs):
        faces = []
        seen_files = set()
        if not dirs: return faces
        for d in dirs:
            if not d or not os.path.isdir(d): continue
            for f in sorted(os.listdir(d)):
                if not (f.lower().endswith(".ttf") or f.lower().endswith(".otf") or f.lower().endswith(".ttc")):
                    continue
                fp = os.path.join(d, f)
                try:
                    real_fp = os.path.realpath(fp)
                except Exception:
                    real_fp = fp
                file_key = (os.path.normcase(real_fp), f.lower())
                if file_key in seen_files:
                    continue
                seen_files.add(file_key)
                try:
                    col = TTCollection(fp, lazy=True)
                    for i in range(len(col.fonts)):
                        faces.append(inspect_face(fp, i))
                    col.close()
                except Exception:
                    try:
                        faces.append(inspect_face(fp, None))
                    except Exception as e:
                        sys.stderr.write(f"skip {fp}: {e}\n")
        return faces

    sans_faces = collect_faces(sans_dirs)
    mono_faces = collect_faces(mono_dirs)
    serif_faces = collect_faces(serif_dirs)
    bengali_faces = collect_faces(bengali_dirs)

    if not sans_faces:
        sys.stderr.write("No Sans fonts found to compile\n")
        return 1

    primary = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"] and f["weight"] == 400),
                   next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0]))
    mode = "variable" if primary["variable"] else "static"
    family_name = primary["family"] or "Custom Font"

    ttc_fonts = []
    output_filename = "DroidSans.ttf"

    def process_and_open(face):
        kw = {"lazy": False, "recalcBBoxes": False, "recalcTimestamp": False}
        if face["font_number"] is not None:
            kw["fontNumber"] = face["font_number"]
        font = TTFont(face["path"], **kw)
        if not keep_hinting:
            remove_font_hinting(font)
        if fix_metrics:
            fix_font_metrics(font)
        return font

    # Process Sans
    sans_entries = []
    normal_entries = []
    condensed_entries = []

    if mode == "variable":
        upright = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0])
        italic = next((f for f in sans_faces if f["style"] == "italic" and not f["condensed"]), None)

        upright_idx = len(ttc_fonts)
        ttc_fonts.append(process_and_open(upright))

        italic_idx = upright_idx
        if italic and italic["path"] != upright["path"]:
            italic_idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(italic))

        for st, f_face, f_idx in (("normal", upright, upright_idx), ("italic", italic or upright, italic_idx)):
            for w in WEIGHT_NAMES:
                ax = calc_axis_values(f_face, w, st == "italic")
                if ax:
                    sans_entries.append((w, st, font_xml(output_filename, w, st, index=f_idx, axes=ax)))
        sans_entries.sort(key=lambda item: (item[1] == "italic", item[0]))
        sans_xml_str = "\n".join(x for _, _, x in sans_entries)
        condensed_xml_str = sans_xml_str
    else:
        def dedupe_static(faces):
            chosen = {}
            for f in faces:
                k = (f["condensed"], f["style"], f["weight"])
                if k not in chosen:
                    chosen[k] = f
            return list(chosen.values())

        ordered_sans = dedupe_static(sans_faces)
        ordered_sans.sort(key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))

        for f in ordered_sans:
            idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(f))
            xml_line = font_xml(output_filename, f["weight"], f["style"], index=idx)
            (condensed_entries if f["condensed"] else normal_entries).append((f["weight"], f["style"], xml_line))

        if not normal_entries:
            normal_entries = list(condensed_entries)
        sans_xml_str = "\n".join(x for _, _, x in normal_entries)
        condensed_xml_str = "\n".join(x for _, _, x in (condensed_entries or normal_entries))

    # Process Optional Families (Mono, Serif, Bengali)
    def process_family(faces):
        if not faces: return [], None
        f_lines = []
        first_idx = None
        var_upright = next((f for f in faces if f["variable"] and "wght" in f["axes"]), None)
        if var_upright:
            idx = len(ttc_fonts)
            first_idx = idx
            ttc_fonts.append(process_and_open(var_upright))
            var_italic = next((f for f in faces if f["style"] == "italic" and f["variable"] and "wght" in f["axes"]), None)
            ital_idx = idx
            if var_italic and var_italic["path"] != var_upright["path"]:
                ital_idx = len(ttc_fonts)
                ttc_fonts.append(process_and_open(var_italic))
            for st, vf, f_i in (("normal", var_upright, idx), ("italic", var_italic or var_upright, ital_idx)):
                for w in WEIGHT_NAMES:
                    ax = calc_axis_values(vf, w, st == "italic")
                    if ax:
                        f_lines.append(font_xml(output_filename, w, st, index=f_i, axes=ax))
        else:
            slot_map = {}
            for f in faces:
                slot_key = (f["weight"], f["style"], f["condensed"])
                if slot_key not in slot_map:
                    slot_map[slot_key] = f

            sorted_faces = sorted(slot_map.values(), key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))
            for f in sorted_faces:
                idx = len(ttc_fonts)
                if first_idx is None: first_idx = idx
                ttc_fonts.append(process_and_open(f))
                f_lines.append(font_xml(output_filename, f["weight"], f["style"], index=idx))
        return f_lines, first_idx

    mono_lines, mono_idx = process_family(mono_faces)
    serif_lines, serif_idx = process_family(serif_faces)
    bengali_lines, bengali_idx = process_family(bengali_faces)

    # Save TTCollection
    ttc = TTCollection()
    ttc.fonts = ttc_fonts
    ttc.save(str(out_path / output_filename))
    for f in ttc_fonts:
        f.close()

    # Write XML fragments
    (out_path / "sans.xml").write_text(sans_xml_str + "\n", encoding="utf-8", newline="\n")
    (out_path / "condensed.xml").write_text(condensed_xml_str + "\n", encoding="utf-8", newline="\n")

    if serif_lines:
        (out_path / "serif.xml").write_text("\n".join(serif_lines) + "\n", encoding="utf-8", newline="\n")
    else:
        serif_fallback = []
        for w, s in ((400, "normal"), (700, "normal"), (400, "italic"), (700, "italic")):
            match = next((x for item_w, item_s, x in (sans_entries if mode == "variable" else normal_entries) if item_w == w and item_s == s), None)
            if match and match not in serif_fallback:
                serif_fallback.append(match)
        (out_path / "serif.xml").write_text("\n".join(serif_fallback) + "\n", encoding="utf-8", newline="\n")

    if mono_lines:
        (out_path / "mono.xml").write_text("\n".join(mono_lines) + "\n", encoding="utf-8", newline="\n")
    if bengali_lines:
        (out_path / "bengali.xml").write_text("\n".join(bengali_lines) + "\n", encoding="utf-8", newline="\n")

    conf_lines = [
        f'FONT_MODE="{mode}"',
        f'FONT_FAMILY="{family_name}"',
        f'HAS_CUSTOM_MONO="{"true" if mono_lines else "false"}"',
        f'HAS_CUSTOM_SERIF="{"true" if serif_lines else "false"}"',
        f'HAS_CUSTOM_BENGALI="{"true" if bengali_lines else "false"}"',
        f'TTC_TOTAL_FONTS="{len(ttc_fonts)}"',
    ]

    if mode == "variable":
        upright = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0])
        italic = next((f for f in sans_faces if f["style"] == "italic" and not f["condensed"]), None)
        if upright and upright.get("axes") and "wght" in upright["axes"]:
            conf_lines.append(f'VF_UPRIGHT_AXIS_META="{format_axis_meta(upright, False)}"')
            conf_lines.append(f'VF_UPRIGHT_WEIGHTS="{supported_weights_str(upright)}"')
        if italic and italic.get("axes") and "wght" in italic["axes"] and italic["path"] != upright["path"]:
            conf_lines.append(f'VF_ITALIC_AXIS_META="{format_axis_meta(italic, True)}"')
            conf_lines.append(f'VF_ITALIC_WEIGHTS="{supported_weights_str(italic)}"')

    mono_var = next((f for f in mono_faces if f["variable"] and "wght" in f.get("axes", {})), None)
    if mono_var:
        conf_lines.append(f'VF_MONO_AXIS_META="{format_axis_meta(mono_var, False)}"')
        conf_lines.append(f'VF_MONO_WEIGHTS="{supported_weights_str(mono_var)}"')

    serif_var_upright = next((f for f in serif_faces if f["variable"] and f["style"] == "normal" and "wght" in f.get("axes", {})), None)
    if serif_var_upright:
        conf_lines.append(f'VF_SERIF_UPRIGHT_AXIS_META="{format_axis_meta(serif_var_upright, False)}"')
        conf_lines.append(f'VF_SERIF_UPRIGHT_WEIGHTS="{supported_weights_str(serif_var_upright)}"')
    serif_var_italic = next((f for f in serif_faces if f["variable"] and f["style"] == "italic" and "wght" in f.get("axes", {})), None)
    if serif_var_italic:
        conf_lines.append(f'VF_SERIF_ITALIC_AXIS_META="{format_axis_meta(serif_var_italic, True)}"')
        conf_lines.append(f'VF_SERIF_ITALIC_WEIGHTS="{supported_weights_str(serif_var_italic)}"')

    beng_var = next((f for f in bengali_faces if f["variable"] and "wght" in f.get("axes", {})), None)
    if beng_var:
        conf_lines.append(f'VF_BENGALI_AXIS_META="{format_axis_meta(beng_var, False)}"')
        conf_lines.append(f'VF_BENGALI_WEIGHTS="{supported_weights_str(beng_var)}"')

    (out_path / "font-config.sh").write_text("\n".join(conf_lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Compiled unified TTC ({output_filename}) with {len(ttc_fonts)} fonts -> {out_dir}")
    return 0


def main():
    p = argparse.ArgumentParser(prog="mffm-helper", description="MFFM runtime font helper")
    sub = p.add_subparsers(dest="cmd")

    s_scan = sub.add_parser("scan", help="Scan directories and print OS/2 weights & styles")
    s_scan.add_argument("dirs", nargs="+")

    s_ttc = sub.add_parser("ttc", help="Bundle input fonts into TTC collection")
    s_ttc.add_argument("--out", required=True, help="Output TTC path")
    s_ttc.add_argument("files", nargs="*", help="Input font files")

    s_proc = sub.add_parser("process-font", help="Normalize font metrics and strip hinting")
    s_proc.add_argument("--in", dest="input_file", required=True)
    s_proc.add_argument("--out", dest="output_file")
    s_proc.add_argument("--no-hinting", action="store_true")
    s_proc.add_argument("--no-fix-metrics", action="store_true")

    s_comp = sub.add_parser("compile-bundle", help="Compile multiple font directories into unified indexed TTC")
    s_comp.add_argument("--out-dir", required=True)
    s_comp.add_argument("--sans-dir", action="append", default=[])
    s_comp.add_argument("--mono-dir", action="append", default=[])
    s_comp.add_argument("--serif-dir", action="append", default=[])
    s_comp.add_argument("--bengali-dir", action="append", default=[])
    s_comp.add_argument("--keep-hinting", action="store_true")
    s_comp.add_argument("--no-fix-metrics", action="store_true")

    args = p.parse_args()
    if args.cmd == "scan":
        scan_weights(args.dirs)
    elif args.cmd == "ttc":
        files = args.files
        if not files:
            files = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
        build_ttc(args.out, files)
    elif args.cmd == "process-font":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        if args.no_hinting:
            remove_font_hinting(font)
        if not args.no_fix_metrics:
            fix_font_metrics(font)
        font.save(out_f)
        font.close()
        print(f"Processed {args.input_file} -> {out_f}")
    elif args.cmd == "compile-bundle":
        ret = compile_bundle(
            out_dir=args.out_dir,
            sans_dirs=args.sans_dir,
            mono_dirs=args.mono_dir,
            serif_dirs=args.serif_dir,
            bengali_dirs=args.bengali_dir,
            keep_hinting=args.keep_hinting,
            fix_metrics=not args.no_fix_metrics,
        )
        sys.exit(ret)
    else:
        p.print_help(); sys.exit(1)


if __name__ == "__main__":
    main()
