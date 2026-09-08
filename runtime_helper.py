#!/usr/bin/env python3
"""MFFM Runtime Helper — on-device font metrics normalization, TTC bundling, OpenType feature freezing, centered colon injection, and indexed XML compilation."""

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

SUPPORTED_EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2")

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

STANDARD_FEATURE_NAMES = {
    "aalt": "Access All Alternates",
    "calt": "Contextual Alternates",
    "case": "Case-Sensitive Forms",
    "ccmp": "Glyph Composition / Decomposition",
    "cpsp": "Capital Spacing",
    "dlig": "Discretionary Ligatures",
    "dnom": "Denominators",
    "frac": "Fractions",
    "kern": "Kerning",
    "liga": "Standard Ligatures",
    "locl": "Localized Forms",
    "lnum": "Lining Figures",
    "numr": "Numerators",
    "onum": "Oldstyle Figures",
    "ordn": "Ordinals",
    "pnum": "Proportional Figures",
    "salt": "Stylistic Alternates",
    "sinf": "Scientific Inferiors",
    "subs": "Subscript",
    "sups": "Superscript",
    "tnum": "Tabular Figures",
    "zero": "Slashed Zero",
}

UNSAFE_FEATURES = {
    "aalt": "UNSAFE: Enables multiple/all alternate glyphs simultaneously across font",
    "calt": "Enabled by default in font layout engines (Contextual)",
    "ccmp": "System layout feature",
    "locl": "System script/language feature",
    "kern": "System layout feature",
    "liga": "Standard Ligature (Enabled by default in font layout engines)",
}

CAUTION_FEATURES = {
    "frac": "NOT RECOMMENDED TO FREEZE: Alters normal number sequences (e.g. 123456 -> 1²3456) system-wide!",
    "numr": "Numerators (Shrinks letters/numbers into superior position)",
    "dnom": "Denominators (Shrinks letters/numbers into inferior position)",
    "subs": "Subscript (Shrinks/lowers letters/numbers into subscript)",
    "sups": "Superscript (Shrinks/raises letters/numbers into superscript)",
    "sinf": "Scientific Inferiors (Shrinks numbers into inferior position)",
    "ordn": "Ordinals (Shrinks letters into ordinal position)",
    "onum": "Changes default numbers to oldstyle height",
}


def _name(font, *ids: int) -> str:
    if "name" not in font:
        return ""
    for name_id in ids:
        records = [record for record in font["name"].names if record.nameID == name_id]
        records.sort(key=lambda record: (record.platformID != 3, record.langID not in (0x409, 0)))
        for record in records:
            try:
                value = record.toUnicode().strip()
            except Exception:
                continue
            if value:
                return value
    return ""


def _set_name(font, name_id: int, value: str) -> None:
    name_table = font.get("name")
    if name_table is None:
        return
    records = [record for record in name_table.names if record.nameID == name_id]
    if records:
        for record in records:
            record.string = value.encode("utf-16be" if record.platformID == 3 else "latin1", errors="replace")
    else:
        name_table.setName(value, name_id, 3, 1, 0x409)


def sanitize_name_table(font, prefix: str = "") -> None:
    raw_family = _name(font, 16, 1) or "Font"
    cleaned = re.sub(r"(?i)\b(?:MFFM|Mistu|Variable)\b", "", raw_family).strip(" -_")
    cleaned = re.sub(r"\s+", " ", cleaned).strip() or "Font"
    if prefix:
        cleaned = f"{prefix} {cleaned}".strip()

    words = cleaned.split()
    if len(words) >= 2:
        new_family = f"{words[0]} Mistu {' '.join(words[1:])}".strip()
    else:
        new_family = f"{words[0]} Mistu".strip()

    style = _name(font, 17, 2) or "Regular"
    full_name = f"{new_family} {style}".strip()
    postscript = re.sub(r"[^A-Za-z0-9-]", "", f"{new_family.replace(' ', '')}-{style.replace(' ', '')}")[:63]

    for name_id in (1, 16):
        _set_name(font, name_id, new_family)
    _set_name(font, 4, full_name)
    _set_name(font, 6, postscript)

    ver = (_name(font, 5) or "Version 1.000").strip()
    if not ver.endswith(";Mistu"):
        if ver.endswith(";"):
            ver = f"{ver}Mistu"
        else:
            ver = f"{ver};Mistu"
    _set_name(font, 5, ver)
    _set_name(font, 8, "Mistu @ MFFM Inc.")


def fix_font_metrics(font, target_upm: int = 2048, mode: str = "compact") -> None:
    head = font.get("head")
    os2 = font.get("OS/2")
    hhea = font.get("hhea")
    if head is None:
        return
    upm = int(getattr(head, "unitsPerEm", target_upm))
    mode_lower = (mode or "compact").strip().lower()

    if mode_lower == "preserve":
        if os2 is not None:
            os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
            if "fvar" in font:
                os2.usWeightClass = 400
        return

    base_ascent = int(round(2128 * upm / target_upm))
    base_descent = int(round(-550 * upm / target_upm))

    actual_y_max = None
    actual_y_min = None

    if mode_lower == "safe":
        if "glyf" in font and hasattr(font["glyf"], "glyphs"):
            for g in font["glyf"].glyphs.values():
                if hasattr(g, "numberOfContours") and g.numberOfContours != 0:
                    if hasattr(g, "yMax"):
                        if actual_y_max is None or g.yMax > actual_y_max:
                            actual_y_max = g.yMax
                    if hasattr(g, "yMin"):
                        if actual_y_min is None or g.yMin < actual_y_min:
                            actual_y_min = g.yMin

        head_y_max = getattr(head, "yMax", None)
        head_y_min = getattr(head, "yMin", None)
        if head_y_max is not None:
            if actual_y_max is None or head_y_max > actual_y_max:
                actual_y_max = head_y_max
        if head_y_min is not None:
            if actual_y_min is None or head_y_min < actual_y_min:
                actual_y_min = head_y_min

        k_ascent = (actual_y_max / base_ascent) if (actual_y_max is not None and base_ascent > 0) else 1.0
        k_descent = (abs(actual_y_min) / abs(base_descent)) if (actual_y_min is not None and base_descent < 0) else 1.0
        ascent = int(round(max(1.0, k_ascent) * base_ascent))
        descent = int(round(-max(1.0, k_descent) * abs(base_descent)))
    else:  # compact mode
        ascent = base_ascent
        descent = base_descent

    # 1. hhea
    if hhea is not None:
        hhea.ascent = ascent
        hhea.descent = descent
        hhea.lineGap = 0

    # 2. OS/2
    if os2 is not None:
        os2.sTypoAscender = ascent
        os2.sTypoDescender = descent
        os2.sTypoLineGap = 0

        win_ascent = max(ascent, actual_y_max) if actual_y_max is not None else ascent
        win_descent = max(abs(descent), abs(actual_y_min)) if actual_y_min is not None else abs(descent)
        os2.usWinAscent = int(win_ascent)
        os2.usWinDescent = int(win_descent)

        if hasattr(os2, "sCapHeight"):
            os2.sCapHeight = int(round(1456 * upm / target_upm))
        if hasattr(os2, "sxHeight"):
            os2.sxHeight = int(round(1082 * upm / target_upm))

        os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
        if "fvar" in font:
            os2.usWeightClass = 400

    # 3. head
    if hasattr(head, "yMax"):
        curr_max = getattr(head, "yMax", 0)
        head.yMax = max(curr_max, ascent, actual_y_max if actual_y_max is not None else ascent)
    if hasattr(head, "yMin"):
        curr_min = getattr(head, "yMin", 0)
        head.yMin = min(curr_min, descent, actual_y_min if actual_y_min is not None else descent)


def remove_font_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()




def glyphs_to_quadratic(glyphs, max_err: float = 1.0, reverse_direction: bool = True) -> dict:
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    quad_glyphs = {}
    for gname in glyphs.keys():
        glyph = glyphs[gname]
        tt_pen = TTGlyphPen(glyphs)
        cu2qu_pen = Cu2QuPen(tt_pen, max_err, reverse_direction=reverse_direction)
        glyph.draw(cu2qu_pen)
        quad_glyphs[gname] = tt_pen.glyph()
    return quad_glyphs


def update_hmtx_lsb(tt_font, glyf) -> None:
    if "hmtx" not in tt_font:
        return
    hmtx = tt_font["hmtx"]
    metrics = getattr(hmtx, "metrics", {})
    for glyph_name, glyph in glyf.glyphs.items():
        if hasattr(glyph, "xMin") and glyph_name in metrics:
            advance = metrics[glyph_name][0]
            metrics[glyph_name] = (advance, glyph.xMin)


def otf_to_ttf(tt_font, post_format: float = 2.0, max_err: float = 1.0, reverse_direction: bool = True) -> bool:
    """Convert CFF/OTF cubic outlines to TrueType quadratic outlines."""
    from fontTools.ttLib import newTable

    is_cff = "CFF " in tt_font or "CFF2" in tt_font or getattr(tt_font, "sfntVersion", None) == "OTTO"
    if not is_cff:
        return False

    glyph_order = tt_font.getGlyphOrder()
    tt_font["loca"] = newTable("loca")
    tt_font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = glyph_order
    glyf.glyphs = glyphs_to_quadratic(tt_font.getGlyphSet(), max_err=max_err, reverse_direction=reverse_direction)
    for glyph in glyf.glyphs.values():
        glyph.recalcBounds(glyf)

    if "CFF " in tt_font:
        del tt_font["CFF "]
    if "CFF2" in tt_font:
        del tt_font["CFF2"]
    if "VORG" in tt_font:
        del tt_font["VORG"]

    glyf.compile(tt_font)
    update_hmtx_lsb(tt_font, glyf)

    tt_font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.recalc(tt_font)
    maxp.compile(tt_font)

    if "post" in tt_font:
        post = tt_font["post"]
        post.formatType = post_format
        post.extraNames = []
        post.mapping = {}
        post.glyphOrder = glyph_order
        try:
            post.compile(tt_font)
        except OverflowError:
            post.formatType = 3
    else:
        tt_font["post"] = post = newTable("post")
        post.formatType = 3

    tt_font.sfntVersion = "\000\001\000\000"
    return True


COLON_GLYPH_PATTERNS = re.compile(
    r"^(colon[._-](case|cent|cap|mid|vert|uc|up|alt|tab|tf|tnum|cv|ss)|(case|cent|cap|mid|vert)[._-]colon|uniEE01|glyphEE01|uEE01|ratio$)",
    re.IGNORECASE,
)

COLON_UNICODES = (
    0xEE01,  # Android clock colon PUA (Google Sans / Roboto / system clock)
    0x2236,  # RATIO (∶)
    0x2982,  # Z NOTATION TYPE COLON (⦂)
    0xA789,  # MODIFIER LETTER COLON (꞉)
    0xFE30,  # PRESENTATION FORM FOR VERTICAL TWO DOT LEADER (︰)
)

LOCKSCREEN_COLON_CODEPOINTS = (
    0xEE01,  # Android clock colon PUA (Google Sans / Roboto / AOSP lockscreen clock)
    0x2236,  # RATIO (∶)
    0x2982,  # Z NOTATION TYPE COLON (⦂)
)


def _unwrap_subtables(subtables):
    unwrapped = []
    for st in subtables:
        if st is None:
            continue
        if hasattr(st, "ExtSubTable") and st.ExtSubTable is not None:
            unwrapped.append(st.ExtSubTable)
        else:
            unwrapped.append(st)
    return unwrapped


def font_has_centered_colon(font_or_path) -> bool:
    """Exhaustively inspect whether a font or font collection implements a centered or clock colon."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen

    if isinstance(font_or_path, (str, Path)):
        p = Path(font_or_path)
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    if font_has_centered_colon(child):
                        return True
            return False
        if not p.is_file():
            return False
        try:
            font = TTFont(str(p), lazy=True)
            should_close = True
        except Exception:
            try:
                from fontTools.ttLib import TTCollection
                ttc = TTCollection(str(p))
                for f in ttc.fonts:
                    if font_has_centered_colon(f):
                        return True
                return False
            except Exception:
                return False
    else:
        font = font_or_path
        should_close = False

    try:
        glyph_order = set(font.getGlyphOrder())
        cmap = font.getBestCmap() if hasattr(font, "getBestCmap") else {}
        if not cmap and "cmap" in font:
            cmap = font["cmap"].getBestCmap() or {}

        colon_glyph = cmap.get(0x003A, "colon")
        target_colons = {colon_glyph, "colon", "colon.tf", "colon.tab"}

        # 1. Direct glyph names for centered/case/clock colon variants
        for name in glyph_order:
            if name in target_colons:
                continue
            if COLON_GLYPH_PATTERNS.search(name):
                return True

        # 2. Unicode codepoints (PUA clock colon, ratio)
        if cmap:
            glyph_set = font.getGlyphSet() if hasattr(font, "getGlyphSet") else None
            for cp in COLON_UNICODES:
                mapped_glyph = cmap.get(cp)
                if mapped_glyph and mapped_glyph in glyph_order:
                    if glyph_set is not None and mapped_glyph in glyph_set:
                        try:
                            pen = BoundsPen(glyph_set)
                            glyph_set[mapped_glyph].draw(pen)
                            if pen.bounds:
                                return True
                        except Exception:
                            return True
                    else:
                        return True

        # 3. OpenType GSUB table substitutions
        if "GSUB" in font and font["GSUB"].table is not None:
            gsub = font["GSUB"].table
            feature_list = getattr(gsub, "FeatureList", None)
            lookup_list = getattr(gsub, "LookupList", None)
            if feature_list and lookup_list and feature_list.FeatureRecord:
                features_to_check = {
                    rec.FeatureTag: rec.Feature
                    for rec in feature_list.FeatureRecord
                    if rec.FeatureTag
                }
                lookups = getattr(lookup_list, "Lookup", [])

                for tag, feat in features_to_check.items():
                    is_candidate = bool(
                        tag in ("case", "calt", "clig", "liga", "tnum", "locl")
                        or tag.startswith(("ss", "cv"))
                    )
                    if not is_candidate:
                        continue

                    for lidx in feat.LookupListIndex:
                        if lidx >= len(lookups):
                            continue
                        lookup = lookups[lidx]
                        subtables = _unwrap_subtables(getattr(lookup, "SubTable", []))

                        for st in subtables:
                            # SingleSubst
                            mapping = getattr(st, "mapping", {})
                            for src_g, dst_g in mapping.items():
                                if src_g in target_colons:
                                    if tag in ("case", "calt", "tnum") or COLON_GLYPH_PATTERNS.search(dst_g):
                                        return True

                            # AlternateSubst
                            alternates = getattr(st, "alternates", {})
                            for src_g, alts in alternates.items():
                                if src_g in target_colons:
                                    if tag in ("case", "calt") or any(COLON_GLYPH_PATTERNS.search(a) for a in alts):
                                        return True

                            # LigatureSubst
                            ligatures = getattr(st, "ligatures", {})
                            for first_g, lig_list in ligatures.items():
                                for lig in lig_list:
                                    comps = [first_g] + list(getattr(lig, "Component", []))
                                    if any(c in target_colons for c in comps):
                                        if any(c.isdigit() or "zero" in c or "one" in c for c in comps):
                                            return True

                            # ContextSubst / ChainContextSubst (Format 3 coverage)
                            input_coverages = getattr(st, "InputCoverage", [])
                            for icov in input_coverages:
                                cov_glyphs = getattr(icov, "glyphs", [])
                                if any(c in target_colons for c in cov_glyphs):
                                    return True

                            coverage = getattr(st, "Coverage", None)
                            if coverage:
                                cov_glyphs = getattr(coverage, "glyphs", [])
                                if tag in ("case", "calt") and any(c in target_colons for c in cov_glyphs):
                                    return True

        # 4. OpenType GPOS vertical positioning shifts
        if "GPOS" in font and font["GPOS"].table is not None:
            gpos = font["GPOS"].table
            feature_list = getattr(gpos, "FeatureList", None)
            lookup_list = getattr(gpos, "LookupList", None)
            if feature_list and lookup_list and feature_list.FeatureRecord:
                gpos_records = {
                    rec.FeatureTag: rec.Feature
                    for rec in feature_list.FeatureRecord
                    if rec.FeatureTag in ("case", "calt")
                }
                gpos_lookups = getattr(lookup_list, "Lookup", [])
                for tag, feat in gpos_records.items():
                    for lidx in feat.LookupListIndex:
                        if lidx >= len(gpos_lookups):
                            continue
                        lookup = gpos_lookups[lidx]
                        subtables = _unwrap_subtables(getattr(lookup, "SubTable", []))
                        for st in subtables:
                            coverage = getattr(st, "Coverage", None)
                            if not coverage:
                                continue
                            cov_glyphs = getattr(coverage, "glyphs", [])
                            if not any(c in target_colons for c in cov_glyphs):
                                continue

                            # SinglePos
                            val = getattr(st, "Value", None)
                            if val and getattr(val, "YPlacement", 0) != 0:
                                return True
                            val_list = getattr(st, "Value", [])
                            if isinstance(val_list, list):
                                for v in val_list:
                                    if getattr(v, "YPlacement", 0) != 0:
                                        return True

        # 5. Glyph Outline Geometry (Native Centered Colon Detection)
        glyph_set = font.getGlyphSet() if hasattr(font, "getGlyphSet") else None
        if glyph_set and colon_glyph in glyph_set:
            try:
                c_pen = BoundsPen(glyph_set)
                glyph_set[colon_glyph].draw(c_pen)
                if c_pen.bounds:
                    col_ymin, col_ymax = c_pen.bounds[1], c_pen.bounds[3]
                    digit_bounds = []
                    for d in "0123456789":
                        dg = cmap.get(ord(d))
                        if dg and dg in glyph_set:
                            dpen = BoundsPen(glyph_set)
                            glyph_set[dg].draw(dpen)
                            if dpen.bounds:
                                digit_bounds.append(dpen.bounds)

                    if digit_bounds:
                        avg_ymin = sum(b[1] for b in digit_bounds) / len(digit_bounds)
                        avg_ymax = sum(b[3] for b in digit_bounds) / len(digit_bounds)
                        digit_h = avg_ymax - avg_ymin
                        digit_center = (avg_ymin + avg_ymax) / 2.0
                        colon_center = (col_ymin + col_ymax) / 2.0

                        if digit_h > 0:
                            if col_ymin >= (0.12 * digit_h) and abs(colon_center - digit_center) <= (0.12 * digit_h):
                                return True
            except Exception:
                pass
    finally:
        if should_close:
            font.close()

    return False


def font_has_pua_colon(font_or_path, pua_codepoints: tuple[int, ...] = (0xEE01,)) -> bool:
    """Exhaustively inspect whether a font implements Android lockscreen clock colon PUA (U+EE01)."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen

    should_close = False
    if isinstance(font_or_path, (str, Path)):
        p = Path(font_or_path)
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    if font_has_pua_colon(child, pua_codepoints):
                        return True
            return False
        if not p.is_file():
            return False
        try:
            font = TTFont(str(p), lazy=True)
            should_close = True
        except Exception:
            try:
                from fontTools.ttLib import TTCollection
                ttc = TTCollection(str(p))
                for f in ttc.fonts:
                    if font_has_pua_colon(f, pua_codepoints):
                        return True
                return False
            except Exception:
                return False
    else:
        font = font_or_path

    try:
        glyph_order = set(font.getGlyphOrder())
        cmap = font.getBestCmap() if hasattr(font, "getBestCmap") else {}
        if not cmap and "cmap" in font:
            cmap = font["cmap"].getBestCmap() or {}

        glyph_set = font.getGlyphSet() if hasattr(font, "getGlyphSet") else None
        for cp in pua_codepoints:
            mapped = cmap.get(cp)
            if mapped and mapped in glyph_order and mapped != ".notdef":
                if glyph_set is not None and mapped in glyph_set:
                    try:
                        pen = BoundsPen(glyph_set)
                        glyph_set[mapped].draw(pen)
                        if pen.bounds:
                            return True
                    except Exception:
                        return True
                else:
                    return True

        for name in ("uniEE01", "glyphEE01", "uEE01", "colon.pua", "colon_pua"):
            if name in glyph_order:
                return True

        return False
    finally:
        if should_close:
            try:
                font.close()
            except Exception:
                pass


def equalize_clock_digits(font_or_path, target_width: int | None = None) -> bool:
    """Equalize advance widths of digits (0-9) and center their contours for wobble-free clocks."""
    from fontTools.ttLib import TTFont

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        if getattr(font, "flavor", None) is not None:
            font.flavor = None

        if "CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO":
            otf_to_ttf(font)

        if "glyf" not in font or "hmtx" not in font:
            if should_save_and_close:
                font.close()
            return False

        glyph_order = font.getGlyphOrder()
        cmap = font.getBestCmap() or {}
        digit_set = set()
        for cp in range(0x30, 0x3A):
            if cp in cmap:
                digit_set.add(cmap[cp])
        exact_digit_bases = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
        for g in glyph_order:
            if g.split(".")[0].lower() in exact_digit_bases:
                digit_set.add(g)

        hmtx = font["hmtx"]
        glyf = font["glyf"]
        metrics = getattr(hmtx, "metrics", {})
        digits = [g for g in glyph_order if g in digit_set and g in metrics]
        if not digits:
            if should_save_and_close:
                font.close()
            return False

        advances = [metrics[d][0] for d in digits]
        w_target = int(target_width) if target_width is not None else max(advances)
        if target_width is None and len(set(advances)) == 1:
            if should_save_and_close:
                font.close()
            return False

        modified = False
        for d in digits:
            g = glyf[d]
            orig_adv, orig_lsb = metrics[d]
            if hasattr(g, "numberOfContours") and g.numberOfContours > 0:
                glyph_w = g.xMax - g.xMin
                new_lsb = round((w_target - glyph_w) / 2)
                dx = new_lsb - g.xMin
                if dx != 0:
                    coords = g.coordinates
                    for i in range(len(coords)):
                        coords[i] = (coords[i][0] + dx, coords[i][1])
                    g.recalcBounds(glyf)
                    modified = True
                metrics[d] = (w_target, g.xMin)
                if orig_adv != w_target or orig_lsb != g.xMin:
                    modified = True
            elif hasattr(g, "components") and g.components:
                glyph_w = g.xMax - g.xMin
                new_lsb = round((w_target - glyph_w) / 2)
                dx = new_lsb - g.xMin
                if dx != 0:
                    for comp in g.components:
                        if hasattr(comp, "x"):
                            comp.x += dx
                    g.recalcBounds(glyf)
                    modified = True
                metrics[d] = (w_target, g.xMin)
                if orig_adv != w_target or orig_lsb != g.xMin:
                    modified = True
            else:
                if orig_adv != w_target:
                    metrics[d] = (w_target, orig_lsb)
                    modified = True

        if modified and "OS/2" in font:
            try:
                font["OS/2"].recalc(font)
            except Exception:
                pass

        if should_save_and_close:
            if modified:
                font.save(str(font_or_path))
            font.close()
        return modified
    except Exception as exc:
        sys.stderr.write(f"equalize_clock_digits error: {exc}\n")
        if should_save_and_close:
            try:
                font.close()
            except Exception:
                pass
        return False


def inject_centered_colon(
    font_or_path,
    alignment: str = "center",
    offset: int = 0,
    rule: str = "between_digits",
) -> bool:
    from fontTools.ttLib import TTFont, newTable
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables.otTables import (
        ChainContextSubst, Coverage, DefaultLangSys, Feature, FeatureList,
        FeatureRecord, GSUB, Lookup, LookupList, Script, ScriptList,
        ScriptRecord, SingleSubst, SubstLookupRecord
    )

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        glyph_order = font.getGlyphOrder()
        if "colon" not in glyph_order:
            return False

        centered_glyph = None
        for candidate in ("colon.case.tf", "colon.case", "colon.centered", "colon.cap", "colon.centered.tf"):
            if candidate in glyph_order:
                centered_glyph = candidate
                break

        if not centered_glyph and "glyf" not in font:
            if "CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO":
                otf_to_ttf(font)
                glyph_order = font.getGlyphOrder()

        if not centered_glyph and "glyf" in font:
            glyf = font["glyf"]
            hmtx = font["hmtx"]
            coords, _, _ = glyf["colon"].getCoordinates(glyf)
            if coords:
                y_coords = [y for _, y in coords]
                colon_center = (min(y_coords) + max(y_coords)) / 2

                cap_height = getattr(font.get("OS/2"), "sCapHeight", None) or 1400
                x_height = getattr(font.get("OS/2"), "sxHeight", None) or 1000
                align_lower = (alignment or "center").strip().lower()

                if align_lower in ("cap_height", "capheight", "caps"):
                    target_center = cap_height / 2
                elif align_lower in ("x_height", "xheight", "lowercase"):
                    target_center = x_height / 2
                else:
                    digit_y_maxes = []
                    digit_y_mins = []
                    for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3"):
                        if d in glyph_order:
                            try:
                                d_coords, _, _ = glyf[d].getCoordinates(glyf)
                                if d_coords:
                                    digit_y_maxes.append(max(y for _, y in d_coords))
                                    digit_y_mins.append(min(y for _, y in d_coords))
                            except Exception:
                                pass
                    if digit_y_maxes:
                        d_min = min(digit_y_mins) if digit_y_mins else 0
                        d_max = max(digit_y_maxes)
                        target_center = (d_min + d_max) / 2
                    else:
                        target_center = cap_height / 2

                dy = round(target_center - colon_center) + int(offset or 0)
                pen = TTGlyphPen(font.getGlyphSet())
                tpen = TransformPen(pen, (1, 0, 0, 1, 0, dy))
                font.getGlyphSet()["colon"].draw(tpen)
                centered_glyph = "colon.case"
                font.setGlyphOrder(glyph_order + [centered_glyph])
                new_glyph = pen.glyph()
                new_glyph.recalcBounds(glyf)
                glyf[centered_glyph] = new_glyph
                hmtx[centered_glyph] = hmtx["colon"]
                if "vmtx" in font:
                    vmtx = font["vmtx"]
                    if "colon" in getattr(vmtx, "metrics", {}):
                        vmtx[centered_glyph] = vmtx["colon"]
                    else:
                        vmtx[centered_glyph] = (0, 0)
                glyph_order = font.getGlyphOrder()

        if not centered_glyph:
            return False

        if "GSUB" not in font or font["GSUB"].table is None:
            gsub_wrapper = newTable("GSUB")
            gsub = GSUB()
            gsub.Version = 0x00010000
            gsub.ScriptList = ScriptList()
            gsub.FeatureList = FeatureList()
            gsub.LookupList = LookupList()
            gsub.ScriptList.ScriptRecord = []
            gsub.FeatureList.FeatureRecord = []
            gsub.LookupList.Lookup = []
            gsub_wrapper.table = gsub
            font["GSUB"] = gsub_wrapper

        gsub = font["GSUB"].table
        if gsub.FeatureList is None: gsub.FeatureList = FeatureList()
        if gsub.FeatureList.FeatureRecord is None: gsub.FeatureList.FeatureRecord = []
        if gsub.LookupList is None: gsub.LookupList = LookupList()
        if gsub.LookupList.Lookup is None: gsub.LookupList.Lookup = []

        calt_rec_idx = None
        for idx, rec in enumerate(gsub.FeatureList.FeatureRecord):
            if rec.FeatureTag == "calt":
                calt_rec_idx = idx
                target_feat = rec.Feature
                break

        if calt_rec_idx is None:
            new_rec = FeatureRecord()
            new_rec.FeatureTag = "calt"
            new_rec.Feature = Feature()
            new_rec.Feature.LookupListIndex = []
            new_rec.Feature.FeatureParams = None
            gsub.FeatureList.FeatureRecord.append(new_rec)
            calt_rec_idx = len(gsub.FeatureList.FeatureRecord) - 1
            target_feat = new_rec.Feature

        if gsub.ScriptList and gsub.ScriptList.ScriptRecord:
            for srec in gsub.ScriptList.ScriptRecord:
                script = srec.Script
                lang_sys_list = []
                if script.DefaultLangSys: lang_sys_list.append(script.DefaultLangSys)
                if script.LangSysRecord:
                    for lrec in script.LangSysRecord: lang_sys_list.append(lrec.LangSys)
                for lsys in lang_sys_list:
                    if calt_rec_idx not in lsys.FeatureIndex:
                        lsys.FeatureIndex.append(calt_rec_idx)
        elif gsub.ScriptList is not None:
            for script_tag in ("DFLT", "latn"):
                srec = ScriptRecord()
                srec.ScriptTag = script_tag
                srec.Script = Script()
                srec.Script.DefaultLangSys = DefaultLangSys()
                srec.Script.DefaultLangSys.ReqFeatureIndex = 0xFFFF
                srec.Script.DefaultLangSys.FeatureIndex = [calt_rec_idx]
                srec.Script.LangSysRecord = []
                gsub.ScriptList.ScriptRecord.append(srec)

        rule_lower = (rule or "between_digits").strip().lower()

        s_lookup = Lookup()
        s_lookup.LookupType = 1
        s_lookup.LookupFlag = 0
        st1 = SingleSubst()
        st1.Format = 1
        st1.mapping = {}
        if "colon" in glyph_order:
            st1.mapping["colon"] = centered_glyph
        if "colon.tf" in glyph_order and "colon.case.tf" in glyph_order:
            st1.mapping["colon.tf"] = "colon.case.tf"
        st1.mapping = dict(sorted(st1.mapping.items(), key=lambda item: font.getGlyphID(item[0])))
        s_lookup.SubTable = [st1]
        gsub.LookupList.Lookup.append(s_lookup)
        s_lidx = len(gsub.LookupList.Lookup) - 1

        if rule_lower == "always":
            if s_lidx not in target_feat.LookupListIndex:
                target_feat.LookupListIndex.append(s_lidx)
        else:
            pure_digits = set()
            cmap = font.getBestCmap() or {}
            for codepoint, gname in cmap.items():
                if (0x0030 <= codepoint <= 0x0039) or (0xFF10 <= codepoint <= 0xFF19) or (0x0660 <= codepoint <= 0x0669) or (0x0966 <= codepoint <= 0x096F):
                    pure_digits.add(gname)
            exact_digit_bases = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
            for g in glyph_order:
                if g.split(".")[0].lower() in exact_digit_bases:
                    pure_digits.add(g)
            sorted_digits = sorted(list(pure_digits), key=lambda g: font.getGlyphID(g))

            bcov = Coverage(); bcov.glyphs = sorted_digits
            icov = Coverage(); icov.glyphs = sorted([g for g in ("colon", "colon.tf") if g in glyph_order], key=lambda g: font.getGlyphID(g))
            lcov = Coverage(); lcov.glyphs = sorted_digits

            c_lookup = Lookup()
            c_lookup.LookupType = 6
            c_lookup.LookupFlag = 0

            st6 = ChainContextSubst()
            st6.Format = 3
            st6.BacktrackGlyphCount = 1
            st6.BacktrackCoverage = [bcov]
            st6.InputGlyphCount = 1
            st6.InputCoverage = [icov]

            if rule_lower in ("after_digit", "trailing", "after"):
                st6.LookAheadGlyphCount = 0
                st6.LookAheadCoverage = []
            else:
                st6.LookAheadGlyphCount = 1
                st6.LookAheadCoverage = [lcov]

            srec = SubstLookupRecord()
            srec.SequenceIndex = 0
            srec.LookupListIndex = s_lidx
            st6.SubstLookupRecord = [srec]
            c_lookup.SubTable = [st6]

            space_glyphs = [g for g in ("space", "uni0020", "u0020", "thinspace", "uni2009", "u2009") if g in glyph_order]
            if space_glyphs:
                scov = Coverage(); scov.glyphs = sorted(space_glyphs, key=lambda g: font.getGlyphID(g))
                if rule_lower in ("after_digit", "trailing", "after"):
                    # digit + space + colon ("12 :")
                    st_after_space = ChainContextSubst()
                    st_after_space.Format = 3
                    st_after_space.BacktrackGlyphCount = 2
                    st_after_space.BacktrackCoverage = [scov, bcov]
                    st_after_space.InputGlyphCount = 1
                    st_after_space.InputCoverage = [icov]
                    st_after_space.LookAheadGlyphCount = 0
                    st_after_space.LookAheadCoverage = []
                    st_after_space.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_after_space)
                else:
                    # 1. digit + space + colon + space + digit ("12 : 30")
                    st_space = ChainContextSubst()
                    st_space.Format = 3
                    st_space.BacktrackGlyphCount = 2
                    st_space.BacktrackCoverage = [scov, bcov]
                    st_space.InputGlyphCount = 1
                    st_space.InputCoverage = [icov]
                    st_space.LookAheadGlyphCount = 2
                    st_space.LookAheadCoverage = [scov, lcov]
                    st_space.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_space)

                    # 2. digit + colon + space + digit ("12: 30")
                    st_lead = ChainContextSubst()
                    st_lead.Format = 3
                    st_lead.BacktrackGlyphCount = 1
                    st_lead.BacktrackCoverage = [bcov]
                    st_lead.InputGlyphCount = 1
                    st_lead.InputCoverage = [icov]
                    st_lead.LookAheadGlyphCount = 2
                    st_lead.LookAheadCoverage = [scov, lcov]
                    st_lead.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_lead)

                    # 3. digit + space + colon + digit ("12 :30")
                    st_trail = ChainContextSubst()
                    st_trail.Format = 3
                    st_trail.BacktrackGlyphCount = 2
                    st_trail.BacktrackCoverage = [scov, bcov]
                    st_trail.InputGlyphCount = 1
                    st_trail.InputCoverage = [icov]
                    st_trail.LookAheadGlyphCount = 1
                    st_trail.LookAheadCoverage = [lcov]
                    st_trail.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_trail)

            gsub.LookupList.Lookup.append(c_lookup)
            c_lidx = len(gsub.LookupList.Lookup) - 1

            if c_lidx not in target_feat.LookupListIndex:
                target_feat.LookupListIndex.append(c_lidx)

        if should_save_and_close:
            font.save(str(font_or_path))
            font.close()
        return True
    except Exception as exc:
        sys.stderr.write(f"inject_centered_colon error: {exc}\n")
        return False


def copy_colon_to_pua(font_or_path, codepoints: tuple[int, ...] = LOCKSCREEN_COLON_CODEPOINTS) -> bool:
    """Copy/map the colon (or centered colon) glyph to Android lockscreen clock colon PUA (U+EE01) and symbols (U+2236, U+2982)."""
    from fontTools.ttLib import TTFont

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        glyph_order = font.getGlyphOrder()
        cmap = font.getBestCmap() if hasattr(font, "getBestCmap") else {}
        if not cmap and "cmap" in font:
            cmap = font["cmap"].getBestCmap() or {}

        # Determine the best colon glyph to map
        # Prefer centered colon if one was created or exists, otherwise standard colon
        target_glyph = None
        for candidate in ("colon.case.tf", "colon.case", "colon.centered", "colon.cap", "colon.centered.tf", "colon_centered"):
            if candidate in glyph_order:
                target_glyph = candidate
                break

        if not target_glyph:
            if 0x003A in cmap and cmap[0x003A] in glyph_order:
                target_glyph = cmap[0x003A]
            elif "colon" in glyph_order:
                target_glyph = "colon"

        if not target_glyph or "cmap" not in font:
            if should_save_and_close:
                font.close()
            return False

        changed = False
        for table in font["cmap"].tables:
            if table.isUnicode():
                for cp in codepoints:
                    if table.cmap.get(cp) != target_glyph:
                        table.cmap[cp] = target_glyph
                        changed = True

        if should_save_and_close:
            if changed:
                font.save(str(font_or_path))
            font.close()
        return changed
    except Exception as exc:
        sys.stderr.write(f"copy_colon_to_pua error: {exc}\n")
        if should_save_and_close:
            try:
                font.close()
            except Exception:
                pass
        return False


def extract_opentype_features(font_or_path) -> dict[str, str]:
    from fontTools.ttLib import TTFont
    should_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path), lazy=True)
            should_close = True
        except Exception:
            return {}
    else:
        font = font_or_path

    features = {}
    try:
        if "GSUB" not in font or font["GSUB"].table is None or font["GSUB"].table.FeatureList is None:
            return features
        gsub = font["GSUB"].table
        name_table = font.get("name")
        for record in gsub.FeatureList.FeatureRecord:
            tag = record.FeatureTag
            if not tag:
                continue
            ui_name = ""
            params = getattr(record.Feature, "FeatureParams", None)
            if params and name_table:
                name_id = (
                    getattr(params, "UINameID", None)
                    or getattr(params, "FeatUILabelNameID", None)
                    or getattr(params, "featUINameID", None)
                    or getattr(params, "FirstParamUILabelNameID", None)
                )
                if name_id:
                    for nrec in name_table.names:
                        if nrec.nameID == name_id:
                            try: ui_name = nrec.toUnicode().strip()
                            except Exception: pass
                            if ui_name: break
            if not ui_name:
                if tag in STANDARD_FEATURE_NAMES:
                    ui_name = STANDARD_FEATURE_NAMES[tag]
                elif tag.startswith("ss") and tag[2:].isdigit():
                    ui_name = f"Stylistic Set {int(tag[2:])}"
                elif tag.startswith("cv") and tag[2:].isdigit():
                    ui_name = f"Character Variant {int(tag[2:])}"
            features[tag] = ui_name
    finally:
        if should_close:
            font.close()
    return features


def extract_features_from_dirs(dirs: list[str]) -> dict[str, str]:
    from fontTools.ttLib import TTCollection
    aggregated = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not any(f.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                continue
            fp = os.path.join(d, f)
            try:
                col = TTCollection(fp, lazy=True)
                for font in col.fonts:
                    for tag, name in extract_opentype_features(font).items():
                        if tag not in aggregated or (not aggregated[tag] and name):
                            aggregated[tag] = name
                col.close()
            except Exception:
                for tag, name in extract_opentype_features(fp).items():
                    if tag not in aggregated or (not aggregated[tag] and name):
                        aggregated[tag] = name
    return dict(sorted(aggregated.items()))


def format_category_feature_report(category_name: str, features: dict[str, str]) -> list[str]:
    lines = [f"# {category_name.upper()} AVAILABLE FEATURES:"]
    if not features:
        lines.append("#   (none detected)")
        return lines

    safe = {k: v for k, v in features.items() if k not in UNSAFE_FEATURES and k not in CAUTION_FEATURES}
    caution = {k: v for k, v in features.items() if k in CAUTION_FEATURES}
    unsafe = {k: v for k, v in features.items() if k in UNSAFE_FEATURES}

    if safe:
        lines.append("#   [RECOMMENDED / SAFE TO FREEZE]:")
        for tag, name in sorted(safe.items()):
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            lines.append(f"#{label}")
    if caution:
        lines.append("#   [CAUTION - USE WITH CARE]:")
        for tag, name in sorted(caution.items()):
            note = CAUTION_FEATURES.get(tag, "")
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            if note: label += f" ({note})"
            lines.append(f"#{label}")
    if unsafe:
        lines.append("#   [SYSTEM / NOT RECOMMENDED]:")
        for tag, name in sorted(unsafe.items()):
            note = UNSAFE_FEATURES.get(tag, "")
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            if note: label += f" ({note})"
            lines.append(f"#{label}")
    return lines


def freeze_font_features(font_or_path, features: list[str] | str) -> bool:
    from fontTools.ttLib import TTFont
    if isinstance(features, str):
        feature_list = [f.strip().lower() for f in features.split(",") if f.strip()]
    else:
        feature_list = [f.strip().lower() for f in features if f.strip()]

    if not feature_list:
        return False

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        if "GSUB" not in font or font["GSUB"].table is None:
            return False
        gsub = font["GSUB"].table
        if not gsub.FeatureList or not gsub.FeatureList.FeatureRecord:
            return False

        contextual_candidates = {"dlig", "hlig", "clig", "rvrn"}
        contextual_feats = [f for f in feature_list if f in contextual_candidates]
        single_feats = [f for f in feature_list if f not in contextual_candidates]

        modified = False

        if single_feats and gsub.LookupList and gsub.LookupList.Lookup:
            target_tags = set(single_feats)
            lookup_indices = []
            for rec in gsub.FeatureList.FeatureRecord:
                if rec.FeatureTag in target_tags and rec.Feature:
                    lookup_indices.extend(rec.Feature.LookupListIndex)
            lookup_indices = sorted(set(lookup_indices))

            glyph_order = font.getGlyphOrder()
            subs = {g: g for g in glyph_order}

            for lidx in lookup_indices:
                if lidx >= len(gsub.LookupList.Lookup):
                    continue
                lookup = gsub.LookupList.Lookup[lidx]
                for st in getattr(lookup, "SubTable", []):
                    mapping = {}
                    alternates = {}
                    if getattr(st, "LookupType", None) == 1:
                        mapping = getattr(st, "mapping", {})
                    elif getattr(st, "LookupType", None) == 3:
                        alternates = getattr(st, "alternates", {})
                    elif getattr(st, "LookupType", None) == 7:
                        ext = getattr(st, "ExtSubTable", None)
                        if ext and getattr(ext, "LookupType", None) == 1:
                            mapping = getattr(ext, "mapping", {})
                        elif ext and getattr(ext, "LookupType", None) == 3:
                            alternates = getattr(ext, "alternates", {})

                    for in_g, out_g in mapping.items():
                        for k, v in subs.items():
                            if v == in_g: subs[k] = out_g
                    for in_g, out_list in alternates.items():
                        if out_list:
                            out_first = out_list[0]
                            for k, v in subs.items():
                                if v == in_g: subs[k] = out_first

            if "cmap" in font and font["cmap"].tables:
                for cmaptable in font["cmap"].tables:
                    if not getattr(cmaptable, "cmap", None): continue
                    for cp, gname in list(cmaptable.cmap.items()):
                        target = subs.get(gname, gname)
                        if target != gname:
                            cmaptable.cmap[cp] = target
                            modified = True

        if contextual_feats and gsub.FeatureList and gsub.LookupList:
            records = {rec.FeatureTag: rec.Feature for rec in gsub.FeatureList.FeatureRecord if rec.FeatureTag}
            target_feat = records.get("calt") or records.get("liga")
            if not target_feat:
                from fontTools.ttLib.tables.otTables import FeatureRecord, Feature
                new_rec = FeatureRecord()
                new_rec.FeatureTag = "calt"
                new_rec.Feature = Feature()
                new_rec.Feature.LookupListIndex = []
                new_rec.Feature.FeatureParams = None
                gsub.FeatureList.FeatureRecord.append(new_rec)
                target_feat = new_rec.Feature

            def collect_lookups(lidx: int, collected: set[int]):
                if lidx in collected or lidx >= len(gsub.LookupList.Lookup): return
                collected.add(lidx)
                lk = gsub.LookupList.Lookup[lidx]
                for st in getattr(lk, "SubTable", []):
                    for sr in getattr(st, "SubstLookupRecord", []) or []:
                        collect_lookups(sr.LookupListIndex, collected)

            to_promote = set()
            for tag in contextual_feats:
                if tag in records:
                    for idx in records[tag].LookupListIndex:
                        collect_lookups(idx, to_promote)

            for idx in sorted(to_promote):
                if idx not in target_feat.LookupListIndex:
                    target_feat.LookupListIndex.append(idx)
                    modified = True

        if should_save_and_close:
            font.save(str(font_or_path))
            font.close()
        return modified
    except Exception as exc:
        sys.stderr.write(f"freeze_font_features error: {exc}\n")
        return False


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
            if not any(f.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
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
            font = TTFont(f)
            if getattr(font, "flavor", None) is not None:
                font.flavor = None
            col.fonts.append(font)
        except Exception as e:
            sys.stderr.write(f"Error loading {f}: {e}\n")
    if not col.fonts:
        sys.stderr.write("no fonts loaded\n"); sys.exit(1)
    col.save(out_path)
    print(f"TTC saved {out_path} with {len(col.fonts)} fonts")


def face_preference_score(face: dict) -> int:
    name = Path(face["path"]).stem.lower()
    score = 0
    if "hairline" in name: score -= 10
    if "thin" in name: score += 10
    if "extralight" in name: score += 10
    if "ultralight" in name: score -= 5
    if "regular" in name: score += 20
    if "normal" in name: score += 15
    if "book" in name: score -= 5
    if "medium" in name: score += 10
    if "semibold" in name: score += 10
    if "demibold" in name: score -= 5
    if "extrabold" in name: score += 10
    if "ultrabold" in name: score -= 5
    if "black" in name: score += 10
    if "heavy" in name: score -= 5
    if face.get("font_number") is None:
        score += 5
    return score


def compile_bundle(
    out_dir: str,
    sans_dirs: list[str],
    mono_dirs: list[str] = None,
    serif_dirs: list[str] = None,
    bengali_dirs: list[str] = None,
    keep_hinting: bool = False,
    fix_metrics: bool = True,
    sanitize_names: bool = True,
    enable_centered_colon: bool = False,
    enable_pua_colon: bool = False,
    convert_otf: bool = True,
    enable_tabular_digits: bool = False,
    colon_alignment: str = "center",
    colon_offset: int = 0,
    colon_rule: str = "between_digits",
    metrics_mode: str = "compact",
    freeze_sans: list[str] | str | None = None,
    freeze_mono: list[str] | str | None = None,
    freeze_serif: list[str] | str | None = None,
    freeze_bengali: list[str] | str | None = None,
) -> int:
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
                if not any(f.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    continue
                if os.path.abspath(d) == os.path.abspath(out_dir) and f.lower() in ("droidsans.ttf", "droidsans.ttc", "droidsans.otf", "droidsans.otc", "droidsans.woff", "droidsans.woff2"):
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

    candidates_400 = [f for f in sans_faces if f["style"] == "normal" and not f["condensed"] and f["weight"] == 400]
    if candidates_400:
        primary = max(candidates_400, key=face_preference_score)
    else:
        normal_candidates = [f for f in sans_faces if f["style"] == "normal" and not f["condensed"]]
        if normal_candidates:
            primary = max(normal_candidates, key=face_preference_score)
        else:
            primary = max(sans_faces, key=face_preference_score)

    mode = "variable" if primary["variable"] else "static"
    family_name = primary["family"] or "Custom Font"

    ttc_fonts = []
    output_filename = "DroidSans.ttf"

    def process_and_open(face, category: str = "sans"):
        kw = {"lazy": False, "recalcBBoxes": False, "recalcTimestamp": False}
        if face["font_number"] is not None:
            kw["fontNumber"] = face["font_number"]
        font = TTFont(face["path"], **kw)
        if getattr(font, "flavor", None) is not None:
            font.flavor = None

        # 0. Convert CFF/OTF outlines to TrueType
        if convert_otf and ("CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO"):
            otf_to_ttf(font)

        # 1. Hinting stripping
        if not keep_hinting:
            remove_font_hinting(font)

        # 2. Equalize clock digits (0-9)
        if enable_tabular_digits:
            equalize_clock_digits(font)

        # 3. Feature freezing
        feat_target = None
        if category == "sans": feat_target = freeze_sans
        elif category == "mono": feat_target = freeze_mono
        elif category == "serif": feat_target = freeze_serif
        elif category == "bengali": feat_target = freeze_bengali
        if feat_target:
            freeze_font_features(font, feat_target)

        # 4. Centered colon (Sans only)
        if category == "sans" and enable_centered_colon:
            inject_centered_colon(
                font,
                alignment=colon_alignment,
                offset=colon_offset,
                rule=colon_rule,
            )

        # 5. Lockscreen clock colon PUA (Sans only)
        if category == "sans" and enable_pua_colon:
            copy_colon_to_pua(font)

        # 6. Name table sanitization
        if sanitize_names:
            sanitize_name_table(font)

        # 7. Metrics normalization
        if fix_metrics:
            fix_font_metrics(font, mode=metrics_mode)

        return font

    # Process Sans
    sans_entries = []
    normal_entries = []
    condensed_entries = []

    if mode == "variable":
        upright = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0])
        italic = next((f for f in sans_faces if f["style"] == "italic" and not f["condensed"]), None)

        print(f"[*] Processing variable Sans upright: {upright.get('family', 'Font')}...", flush=True)
        upright_idx = len(ttc_fonts)
        ttc_fonts.append(process_and_open(upright, "sans"))

        italic_idx = upright_idx
        if italic and italic["path"] != upright["path"]:
            print(f"[*] Processing variable Sans italic: {italic.get('family', 'Font')}...", flush=True)
            italic_idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(italic, "sans"))

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
            grouped = {}
            for f in faces:
                k = (f["condensed"], f["style"], f["weight"])
                grouped.setdefault(k, []).append(f)
            return [max(group, key=face_preference_score) for group in grouped.values()]

        ordered_sans = dedupe_static(sans_faces)
        ordered_sans.sort(key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))

        for idx, f in enumerate(ordered_sans):
            print(f"[*] Processing Sans font {idx + 1}/{len(ordered_sans)}: {f.get('family', 'Font')} ({f.get('weight', 400)} {f.get('style', 'normal')})...", flush=True)
            ttc_fonts.append(process_and_open(f, "sans"))
            xml_line = font_xml(output_filename, f["weight"], f["style"], index=len(ttc_fonts) - 1)
            (condensed_entries if f["condensed"] else normal_entries).append((f["weight"], f["style"], xml_line))

        if not normal_entries:
            normal_entries = list(condensed_entries)
        sans_xml_str = "\n".join(x for _, _, x in normal_entries)
        condensed_xml_str = "\n".join(x for _, _, x in (condensed_entries or normal_entries))

    # Process Optional Families (Mono, Serif, Bengali)
    def process_family(faces, cat_name):
        if not faces: return [], None
        f_lines = []
        first_idx = None
        var_upright = next((f for f in faces if f["variable"] and "wght" in f["axes"]), None)
        if var_upright:
            print(f"[*] Processing variable {cat_name} upright: {var_upright.get('family', 'Font')}...", flush=True)
            idx = len(ttc_fonts)
            first_idx = idx
            ttc_fonts.append(process_and_open(var_upright, cat_name))
            var_italic = next((f for f in faces if f["style"] == "italic" and f["variable"] and "wght" in f["axes"]), None)
            ital_idx = idx
            if var_italic and var_italic["path"] != var_upright["path"]:
                print(f"[*] Processing variable {cat_name} italic: {var_italic.get('family', 'Font')}...", flush=True)
                ital_idx = len(ttc_fonts)
                ttc_fonts.append(process_and_open(var_italic, cat_name))
            for st, vf, f_i in (("normal", var_upright, idx), ("italic", var_italic or var_upright, ital_idx)):
                for w in WEIGHT_NAMES:
                    ax = calc_axis_values(vf, w, st == "italic")
                    if ax:
                        f_lines.append(font_xml(output_filename, w, st, index=f_i, axes=ax))
        else:
            grouped_static = {}
            for f in faces:
                slot_key = (f["weight"], f["style"], f["condensed"])
                grouped_static.setdefault(slot_key, []).append(f)

            deduped = [max(group, key=face_preference_score) for group in grouped_static.values()]
            sorted_faces = sorted(deduped, key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))
            for idx, f in enumerate(sorted_faces):
                print(f"[*] Processing {cat_name} font {idx + 1}/{len(sorted_faces)}: {f.get('family', 'Font')} ({f.get('weight', 400)} {f.get('style', 'normal')})...", flush=True)
                if first_idx is None: first_idx = len(ttc_fonts)
                ttc_fonts.append(process_and_open(f, cat_name))
                f_lines.append(font_xml(output_filename, f["weight"], f["style"], index=len(ttc_fonts) - 1))
        return f_lines, first_idx

    mono_lines, mono_idx = process_family(mono_faces, "mono")
    serif_lines, serif_idx = process_family(serif_faces, "serif")
    bengali_lines, bengali_idx = process_family(bengali_faces, "bengali")

    # Save TTCollection
    print(f"[*] Packaging {len(ttc_fonts)} fonts into TrueType collection ({output_filename})...", flush=True)
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
    s_proc.add_argument("--metrics-mode", choices=["safe", "compact", "preserve"], default="compact", help="Metrics mode (safe=auto-clamp FFIX3 ratio, compact=fixed FFIX3, preserve=keep original)")
    s_proc.add_argument("--sanitize-names", action="store_true")
    s_proc.add_argument("--inject-colon", action="store_true")
    s_proc.add_argument("--colon-alignment", choices=["center", "cap_height", "x_height"], default="center")
    s_proc.add_argument("--colon-offset", type=int, default=0)
    s_proc.add_argument("--colon-rule", choices=["between_digits", "after_digit", "always"], default="between_digits")
    s_proc.add_argument("--equalize-digits", action="store_true", help="Equalize advance widths of digits (0-9)")
    s_proc.add_argument("--digit-width", type=int, help="Target advance width for digits")
    s_proc.add_argument("--freeze-features")
    s_proc.add_argument("--copy-pua-colon", action="store_true", help="Copy/map colon to Android lockscreen clock colon PUA (U+EE01, U+2236, U+2982)")
    s_proc.add_argument("--convert-otf", action="store_true", help="Convert CFF/OTF outlines to TrueType")
    s_proc.add_argument("--no-convert-otf", action="store_true", help="Skip OTF to TTF conversion")

    s_comp = sub.add_parser("compile-bundle", help="Compile multiple font directories into unified indexed TTC")
    s_comp.add_argument("--out-dir", required=True)
    s_comp.add_argument("--sans-dir", action="append", default=[])
    s_comp.add_argument("--mono-dir", action="append", default=[])
    s_comp.add_argument("--serif-dir", action="append", default=[])
    s_comp.add_argument("--bengali-dir", action="append", default=[])
    s_comp.add_argument("--keep-hinting", action="store_true")
    s_comp.add_argument("--no-fix-metrics", action="store_true")
    s_comp.add_argument("--metrics-mode", choices=["safe", "compact", "preserve"], default="compact", help="Metrics mode (safe=auto-clamp FFIX3 ratio, compact=fixed FFIX3, preserve=keep original)")
    s_comp.add_argument("--no-sanitize-names", action="store_true")
    s_comp.add_argument("--enable-centered-colon", action="store_true")
    s_comp.add_argument("--enable-pua-colon", action="store_true", help="Copy/map colon to Android lockscreen clock colon PUA (U+EE01, U+2236, U+2982)")
    s_comp.add_argument("--colon-alignment", choices=["center", "cap_height", "x_height"], default="center")
    s_comp.add_argument("--colon-offset", type=int, default=0)
    s_comp.add_argument("--colon-rule", choices=["between_digits", "after_digit", "always"], default="between_digits")
    s_comp.add_argument("--enable-tabular-digits", action="store_true", help="Equalize digit advance widths for wobble-free clock")
    s_comp.add_argument("--no-convert-otf", action="store_true", help="Do not convert CFF/OTF outlines to TrueType")
    s_comp.add_argument("--freeze-sans")
    s_comp.add_argument("--freeze-mono")
    s_comp.add_argument("--freeze-serif")
    s_comp.add_argument("--freeze-bengali")

    s_otf2ttf = sub.add_parser("otf2ttf", help="Convert CFF/OTF font to TrueType font using cu2qu")
    s_otf2ttf.add_argument("--in", dest="input_file", required=True, help="Input OTF font")
    s_otf2ttf.add_argument("--out", dest="output_file", help="Output TTF font (default replaces .otf with .ttf)")
    s_otf2ttf.add_argument("--max-err", type=float, default=1.0, help="Maximum approximation error for cu2qu (default: 1.0)")
    s_otf2ttf.add_argument("--post-format", type=float, default=2.0, help="Post table format (default: 2.0)")

    s_eq_digits = sub.add_parser("equalize-digits", help="Equalize digit advance widths and center contours for clocks")
    s_eq_digits.add_argument("--in", dest="input_file", required=True, help="Input font file")
    s_eq_digits.add_argument("--out", dest="output_file", help="Output font file (default overwrites input)")
    s_eq_digits.add_argument("--width", type=int, help="Target advance width for digits (default: max digit advance)")

    s_colon = sub.add_parser("check-colon", help="Check if font or directory contains centered colon")
    s_colon.add_argument("paths", nargs="+", help="Path(s) to font file(s) or director(ies)")

    s_pua_col = sub.add_parser("check-pua-colon", help="Check if font or directory contains Android lockscreen clock colon PUA (U+EE01)")
    s_pua_col.add_argument("paths", nargs="+", help="Path(s) to font file(s) or director(ies)")

    s_inj_col = sub.add_parser("inject-colon", help="Inject centered colon into font")
    s_inj_col.add_argument("--in", dest="input_file", required=True)
    s_inj_col.add_argument("--out", dest="output_file")
    s_inj_col.add_argument("--alignment", choices=["center", "cap_height", "x_height"], default="center")
    s_inj_col.add_argument("--offset", type=int, default=0)
    s_inj_col.add_argument("--rule", choices=["between_digits", "after_digit", "always"], default="between_digits")

    s_copy_pua = sub.add_parser("copy-pua-colon", help="Copy/map colon to Android lockscreen clock colon PUA (U+EE01, U+2236, U+2982)")
    s_copy_pua.add_argument("--in", dest="input_file", required=True)
    s_copy_pua.add_argument("--out", dest="output_file")

    s_freeze = sub.add_parser("freeze-features", help="Freeze OpenType features into font")
    s_freeze.add_argument("--in", dest="input_file", required=True)
    s_freeze.add_argument("--features", required=True, help="Comma-separated feature tags (e.g. ss01,zero)")
    s_freeze.add_argument("--out", dest="output_file")

    s_report = sub.add_parser("report-features", help="Discover and report available OpenType features per category")
    s_report.add_argument("--sans-dir", action="append", default=[])
    s_report.add_argument("--mono-dir", action="append", default=[])
    s_report.add_argument("--serif-dir", action="append", default=[])
    s_report.add_argument("--bengali-dir", action="append", default=[])
    s_report.add_argument("--out", help="Write report to output file")

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
        if getattr(font, "flavor", None) is not None:
            font.flavor = None
        if not args.no_convert_otf and (args.convert_otf or args.inject_colon or "CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO"):
            otf_to_ttf(font)
        if args.no_hinting:
            remove_font_hinting(font)
        if args.equalize_digits:
            equalize_clock_digits(font, target_width=args.digit_width)
        if args.freeze_features:
            freeze_font_features(font, args.freeze_features)
        if args.inject_colon:
            inject_centered_colon(
                font,
                alignment=args.colon_alignment,
                offset=args.colon_offset,
                rule=args.colon_rule,
            )
        if args.copy_pua_colon:
            copy_colon_to_pua(font)
        if args.sanitize_names:
            sanitize_name_table(font)
        if not args.no_fix_metrics:
            fix_font_metrics(font, mode=args.metrics_mode)
        font.save(out_f)
        font.close()
        print(f"Processed {args.input_file} -> {out_f}")
    elif args.cmd == "otf2ttf":
        from fontTools.ttLib import TTFont
        in_path = Path(args.input_file)
        out_path = Path(args.output_file) if args.output_file else in_path.with_suffix(".ttf")
        font = TTFont(str(in_path))
        if getattr(font, "flavor", None) is not None:
            font.flavor = None
        ok = otf_to_ttf(font, post_format=args.post_format, max_err=args.max_err)
        if ok or in_path != out_path:
            font.save(str(out_path))
            font.close()
            print(f"Converted {in_path} -> {out_path}")
        else:
            font.close()
            print(f"{in_path} is already TrueType and input equals output")
    elif args.cmd == "equalize-digits":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = equalize_clock_digits(font, target_width=args.width)
        font.save(out_f)
        font.close()
        if ok:
            print(f"Equalized clock digits in {out_f}")
        else:
            print(f"Clock digits already tabular or not modified in {args.input_file}")
    elif args.cmd == "check-colon":
        has_col = any(font_has_centered_colon(p) for p in args.paths)
        print("true" if has_col else "false")
    elif args.cmd == "check-pua-colon":
        has_pua = any(font_has_pua_colon(p) for p in args.paths)
        print("true" if has_pua else "false")
    elif args.cmd == "inject-colon":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = inject_centered_colon(
            font,
            alignment=args.alignment,
            offset=args.offset,
            rule=args.rule,
        )
        if ok:
            font.save(out_f)
            font.close()
            print(f"Injected centered colon into {out_f}")
        else:
            font.close()
            print(f"Centered colon already present or not applicable in {args.input_file}")
    elif args.cmd == "copy-pua-colon":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = copy_colon_to_pua(font)
        if ok:
            font.save(out_f)
            font.close()
            print(f"Copied colon to Android clock PUA in {out_f}")
        else:
            font.close()
            print(f"Android clock PUA already present or not applicable in {args.input_file}")
    elif args.cmd == "freeze-features":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = freeze_font_features(font, args.features)
        font.save(out_f)
        font.close()
        print(f"Froze features [{args.features}] -> {out_f}")
    elif args.cmd == "report-features":
        report_lines = []
        if args.sans_dir:
            f_sans = extract_features_from_dirs(args.sans_dir)
            report_lines.extend(format_category_feature_report("Sans-serif", f_sans))
            report_lines.append("")
        if args.mono_dir:
            f_mono = extract_features_from_dirs(args.mono_dir)
            report_lines.extend(format_category_feature_report("Monospace", f_mono))
            report_lines.append("")
        if args.serif_dir:
            f_serif = extract_features_from_dirs(args.serif_dir)
            report_lines.extend(format_category_feature_report("Serif", f_serif))
            report_lines.append("")
        if args.bengali_dir:
            f_beng = extract_features_from_dirs(args.bengali_dir)
            report_lines.extend(format_category_feature_report("Bengali", f_beng))
            report_lines.append("")

        report_txt = "\n".join(report_lines).rstrip() + "\n"
        if args.out:
            Path(args.out).write_text(report_txt, encoding="utf-8")
        else:
            sys.stdout.write(report_txt)
    elif args.cmd == "compile-bundle":
        ret = compile_bundle(
            out_dir=args.out_dir,
            sans_dirs=args.sans_dir,
            mono_dirs=args.mono_dir,
            serif_dirs=args.serif_dir,
            bengali_dirs=args.bengali_dir,
            keep_hinting=args.keep_hinting,
            fix_metrics=not args.no_fix_metrics,
            metrics_mode=args.metrics_mode,
            sanitize_names=not args.no_sanitize_names,
            enable_centered_colon=args.enable_centered_colon,
            enable_pua_colon=args.enable_pua_colon,
            convert_otf=not args.no_convert_otf,
            enable_tabular_digits=args.enable_tabular_digits,
            colon_alignment=args.colon_alignment,
            colon_offset=args.colon_offset,
            colon_rule=args.colon_rule,
            freeze_sans=args.freeze_sans,
            freeze_mono=args.freeze_mono,
            freeze_serif=args.freeze_serif,
            freeze_bengali=args.freeze_bengali,
        )
        sys.exit(ret)
    else:
        p.print_help(); sys.exit(1)


if __name__ == "__main__":
    main()
