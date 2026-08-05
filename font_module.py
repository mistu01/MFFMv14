#!/usr/bin/env python3
"""Shared font compiler core for the MFFMv14 static and variable module template."""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

Mode = Literal["static", "variable"]
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2"}
GENERATED_FILES = {
    "DroidSans.ttf", "DroidSans.otf", "DroidSans.ttc",
    "DroidSans-Italic.ttf", "DroidSans-Italic.otf", "DroidSans-Bold.ttf",
    "sans.xml", "condensed.xml", "serif.xml", "mono.xml",
    "Mono.ttf", "DroidSansMono.ttf", "CutiveMono.ttf",
}
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


@dataclass(frozen=True)
class SourceFace:
    path: Path
    font_number: int | None
    family: str
    style_name: str
    weight: int
    style: str
    condensed: bool
    variable: bool
    # Excluded from the generated __hash__: a dict field would make the frozen instance unhashable.
    axes: dict[str, tuple[float, float, float]] = field(hash=False)
    sfnt_version: str
    category: str = "sans"

    @property
    def label(self) -> str:
        suffix = f"#{self.font_number}" if self.font_number is not None else ""
        return f"{self.path.name}{suffix}"


@dataclass(frozen=True)
class CompileResult:
    mode: Mode
    family: str
    faces: tuple[SourceFace, ...]
    payload_files: tuple[str, ...]
    applied_features: tuple[str, ...] = ()


def require_fonttools():
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError as exc:
        raise SystemExit("fontTools is required: python -m pip install fonttools") from exc
    return TTCollection, TTFont


def read_props(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.exists():
        return props
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def write_props(path: Path, props: dict[str, str]) -> None:
    preferred = (
        "id", "name", "version", "versionCode", "author", "description",
        "minMagisk", "minKernelSU", "minAPatch",
    )
    keys = [key for key in preferred if key in props]
    keys.extend(key for key in props if key not in keys)
    path.write_text("".join(f"{key}={props[key]}\n" for key in keys), encoding="utf-8", newline="\n")


def clean_family_name(value: str) -> str:
    value = re.sub(r"(?i)\bmffm\b", "", value)
    value = re.sub(r"\s+", " ", value).strip(" -_")
    return value or "Unknown Font"


def _base_family_name(value: str) -> str:
    style_words = (
        r"extra[\s_-]*light|ultra[\s_-]*light|semi[\s_-]*bold|demi[\s_-]*bold|"
        r"extra[\s_-]*bold|ultra[\s_-]*bold|extra[\s_-]*black|ultra[\s_-]*black|"
        r"thin|hairline|light|regular|normal|book|roman|medium|bold|black|heavy|"
        r"italic|oblique|condensed|narrow"
    )
    previous = ""
    result = value.strip()
    while result != previous:
        previous = result
        result = re.sub(rf"(?i)[\s_-]+(?:{style_words})$", "", result).strip()
    return clean_family_name(result)


def _weight_from_label(label: str) -> int | None:
    for pattern, weight in WEIGHT_LABELS:
        if re.search(rf"(?i)(?:^|[\s_-])(?:{pattern})(?:$|[\s_-])", label):
            return weight
    return None


def clean_slug_name(value: str) -> str:
    cleaned = re.sub(r"(?i)\b(?:MFFM|Mistu|Variable)\b", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    return cleaned or "Font"


def slugify(value: str) -> str:
    cleaned = clean_slug_name(value)
    return re.sub(r"[^A-Za-z0-9]+", "-", cleaned).strip("-") or "font"


def display_name_for_mode(value: str, mode: Mode) -> str:
    display = re.sub(r"\s+", " ", value).strip()
    if mode == "variable" and not re.search(r"(?i)(?:^|[\s_-])VF$", display):
        display = f"{display} VF"
    return display


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


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


def _nearest_weight(value: int) -> int:
    return min(WEIGHT_NAMES, key=lambda weight: (abs(weight - value), weight))


def _open_font(face: SourceFace, *, lazy: bool = False):
    _collection, TTFont = require_fonttools()
    kwargs = {"lazy": lazy, "recalcBBoxes": False, "recalcTimestamp": False}
    if face.font_number is not None:
        kwargs["fontNumber"] = face.font_number
    return TTFont(str(face.path), **kwargs)


def _inspect_font(path: Path, font_number: int | None, category: str = "sans") -> SourceFace:
    _collection, TTFont = require_fonttools()
    kwargs = {"lazy": True}
    if font_number is not None:
        kwargs["fontNumber"] = font_number

    with TTFont(str(path), **kwargs) as font:
        family_value = _name(font, 16, 1, 4) or path.stem
        style_name = _name(font, 17, 2) or path.stem
        os2 = font.get("OS/2")
        head = font.get("head")
        metadata_label = f"{style_name} {family_value} {_name(font, 4)}".strip()
        label = f"{metadata_label} {path.stem}".lower()

        italic = bool(
            "italic" in label or "oblique" in label
            or (os2 is not None and int(getattr(os2, "fsSelection", 0)) & 1)
            or (head is not None and int(getattr(head, "macStyle", 0)) & 2)
        )
        width_class = int(getattr(os2, "usWidthClass", 5)) if os2 is not None else 5
        condensed = width_class <= 4 or "condensed" in label or "narrow" in label
        os2_w = int(getattr(os2, "usWeightClass", 0)) if os2 is not None else 0
        stem_w = _weight_from_label(path.stem)

        if os2_w in WEIGHT_NAMES:
            weight = os2_w
        elif stem_w:
            weight = stem_w
        else:
            named_weight = _weight_from_label(style_name) or _weight_from_label(metadata_label)
            weight = named_weight or _nearest_weight(os2_w or 400)

        axes: dict[str, tuple[float, float, float]] = {}
        if "fvar" in font:
            for axis in font["fvar"].axes:
                axes[axis.axisTag] = (float(axis.minValue), float(axis.defaultValue), float(axis.maxValue))

        return SourceFace(
            path=path,
            font_number=font_number,
            family=_base_family_name(family_value),
            style_name=style_name,
            weight=weight,
            style="italic" if italic else "normal",
            condensed=condensed,
            variable=bool(axes),
            axes=axes,
            sfnt_version=str(font.sfntVersion),
            category=category,
        )


def categorize(path: Path, fonts_dir: Path) -> str:
    """Classify a source font as sans, mono, or serif by its folder, falling back to its filename."""
    rel_parts = [part.lower() for part in path.relative_to(fonts_dir).parts[:-1]]
    if any(part in ("monospace", "mono") for part in rel_parts):
        return "mono"
    if any(part == "serif" for part in rel_parts):
        return "serif"
    if any(part in ("sans", "sans-serif") for part in rel_parts):
        return "sans"
    stem_lower = path.stem.lower()
    if any(tag in stem_lower for tag in ("mono", "code", "consolas", "courier")):
        return "mono"
    if "serif" in stem_lower and "sans" not in stem_lower:
        return "serif"
    return "sans"


def source_entries(fonts_dir: Path) -> list[tuple[Path, str]]:
    return [
        (path, categorize(path, fonts_dir))
        for path in sorted(fonts_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS
    ]


def discover_faces(fonts_dir: Path) -> list[SourceFace]:
    TTCollection, _font = require_fonttools()
    if not fonts_dir.is_dir():
        raise SystemExit(f"Font input directory does not exist: {fonts_dir}")

    file_entries = source_entries(fonts_dir)
    if not file_entries:
        raise SystemExit(f"No TTF, OTF, TTC, or OTC fonts found in {fonts_dir}")

    faces: list[SourceFace] = []
    for path, cat in file_entries:
        try:
            collection = TTCollection(str(path), lazy=True)
        except Exception as exc:
            if exc.__class__.__name__ != "TTLibFileIsCollectionError" and path.suffix.lower() in {".ttc", ".otc"}:
                raise SystemExit(f"Could not read collection {path}: {exc}") from exc
            faces.append(_inspect_font(path, None, category=cat))
        else:
            try:
                count = len(collection.fonts)
            finally:
                collection.close()
            faces.extend(_inspect_font(path, index, category=cat) for index in range(count))

    return faces


def detect_mode(faces: Iterable[SourceFace], requested: str = "auto") -> Mode:
    face_list = list(faces)
    variable_count = sum(face.variable for face in face_list)
    if requested in {"static", "variable"}:
        mode: Mode = requested  # type: ignore[assignment]
        if mode == "variable" and variable_count != len(face_list):
            raise SystemExit("--mode variable requires every selected font to contain an fvar table")
        if mode == "static" and variable_count:
            raise SystemExit("--mode static cannot compile variable fonts; instantiate them first")
        return mode
    if variable_count == len(face_list):
        return "variable"
    if variable_count == 0:
        return "static"
    raise SystemExit("Mixed static and variable inputs are ambiguous. Keep one font model in Fonts/ or pass --mode.")


def _remove_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()


log = logging.getLogger("mffm.font_module")

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
USE_TYPO_METRICS = 1 << 7


def _scale_ffix3_value(value: int, units_per_em: int) -> int:
    return int(round(value / FFIX3_REFERENCE_UPM * units_per_em))


def _set_font_metric(font, table_name: str, field_name: str, value: int) -> None:
    table = font.get(table_name)
    if table is not None and hasattr(table, field_name):
        setattr(table, field_name, value)


def _fix_metrics(font) -> None:
    head = font.get("head")
    os2 = font.get("OS/2")
    if head is None:
        return

    units_per_em = int(getattr(head, "unitsPerEm", FFIX3_REFERENCE_UPM))
    for table_name, field_name, reference_value in FFIX3_METRICS:
        _set_font_metric(font, table_name, field_name, _scale_ffix3_value(reference_value, units_per_em))

    if os2 is None:
        return
    os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & ~USE_TYPO_METRICS
    if "fvar" in font:
        os2.usWeightClass = 400


def _glyphs_to_quadratic(glyphs, max_err=1.0, reverse_direction=True):
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


def _update_hmtx(tt_font, glyf):
    hmtx = tt_font["hmtx"]
    for glyph_name, glyph in glyf.glyphs.items():
        if hasattr(glyph, "xMin"):
            hmtx[glyph_name] = (hmtx[glyph_name][0], glyph.xMin)


def _otf_to_ttf(tt_font, post_format=2.0, max_err=1.0, reverse_direction=True):
    from fontTools.ttLib import newTable
    assert tt_font.sfntVersion == "OTTO"
    assert "CFF " in tt_font or "CFF2" in tt_font
    glyph_order = tt_font.getGlyphOrder()
    tt_font["loca"] = newTable("loca")
    tt_font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = glyph_order
    glyf.glyphs = _glyphs_to_quadratic(tt_font.getGlyphSet(), max_err=max_err, reverse_direction=reverse_direction)
    if "CFF " in tt_font:
        del tt_font["CFF "]
    if "CFF2" in tt_font:
        del tt_font["CFF2"]
    glyf.compile(tt_font)
    _update_hmtx(tt_font, glyf)

    tt_font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = max(len(g.components if hasattr(g, "components") else []) for g in glyf.glyphs.values())
    maxp.compile(tt_font)

    post = tt_font["post"]
    post.formatType = post_format
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = glyph_order
    try:
        post.compile(tt_font)
    except OverflowError:
        post.formatType = 3
        log.warning("Dropping glyph names, they do not fit in 'post' table.")
    tt_font.sfntVersion = "\000\001\000\000"


def _ensure_ttf(input_path: Path, output_dir: Path) -> Path:
    from fontTools.ttLib import TTFont
    output_path = output_dir / (input_path.stem + ".ttf")
    if input_path.suffix.lower() in {".ttc", ".otc"}:
        TTCollection, _ = require_fonttools()
        try:
            collection = TTCollection(str(input_path))
            for i in range(len(collection.fonts)):
                sub_path = output_dir / f"{input_path.stem}_{i}.ttf"
                collection.fonts[i].save(str(sub_path))
            return output_dir / f"{input_path.stem}_0.ttf"
        except Exception:
            shutil.copy2(input_path, output_path)
            return output_path

    try:
        font = TTFont(str(input_path))
    except ImportError as exc:
        if "brotli" in str(exc).lower():
            raise SystemExit("ERROR: The Brotli Python extension is required to decompress WOFF2 fonts. Install it with: pip install brotli") from exc
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "TTLibFileIsCollectionError":
            shutil.copy2(input_path, output_path)
            return output_path
        raise

    needs_save = False
    if font.flavor is not None:
        font.flavor = None
        needs_save = True
    if font.sfntVersion == "OTTO":
        log.info(f"Converting CFF outlines to TrueType outlines for {input_path.name}")
        _otf_to_ttf(font)
        needs_save = True

    if needs_save or input_path.suffix.lower() != ".ttf":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(str(output_path))
        font.close()
        return output_path

    font.close()
    shutil.copy2(input_path, output_path)
    return output_path


def _set_name(font, name_id: int, value: str) -> None:
    if "name" not in font:
        return
    table = font["name"]
    records = [record for record in table.names if record.nameID == name_id]
    for record in records:
        try:
            record.string = value.encode(record.getEncoding(), errors="replace")
        except Exception:
            pass
    if not records:
        table.setName(value, name_id, 3, 1, 0x409)


def transform_family_name(family: str) -> str:
    cleaned = re.sub(r"(?i)\bmffm\b", "", family).strip(" -_")
    words = cleaned.split()
    if not words:
        return "Mistu"
    if "Mistu" in words:
        return cleaned
    if len(words) == 1:
        return f"{words[0]} Mistu"
    else:
        return f"{words[0]} Mistu {' '.join(words[1:])}"


def _apply_custom_metadata(font) -> None:
    raw_family = _name(font, 16, 1) or "Font"
    new_family = transform_family_name(raw_family)
    style = _name(font, 17, 2) or "Regular"
    full_name = f"{new_family} {style}".strip()
    postscript = re.sub(r"[^A-Za-z0-9-]", "", f"{new_family.replace(' ', '')}-{style.replace(' ', '')}")[:63]

    for name_id in (1, 16):
        _set_name(font, name_id, new_family)
    _set_name(font, 4, full_name)
    _set_name(font, 6, postscript)

    version_str = _name(font, 5) or "Version 1.000"
    if not version_str.endswith(";Mistu"):
        if version_str.endswith(";"):
            new_version_str = f"{version_str}Mistu"
        else:
            new_version_str = f"{version_str};Mistu"
        _set_name(font, 5, new_version_str)

    _set_name(font, 8, "Mistu @ MFFM Inc.")


def _process_font(font, *, keep_hinting: bool, prefix_family: bool) -> None:
    if not keep_hinting:
        _remove_hinting(font)
    _fix_metrics(font)
    if prefix_family:
        _apply_custom_metadata(font)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _axis_metadata(face: SourceFace, *, italic: bool) -> str:
    weight_axis = face.axes.get("wght")
    style_values = (_axis_values(face, int(weight_axis[1]), italic) or {}) if weight_axis else {}
    return " ".join(
        "|".join((tag, _format_number(minimum), _format_number(style_values.get(tag, default)), _format_number(maximum)))
        for tag, (minimum, default, maximum) in face.axes.items()
    )


def _variable_config_identity(faces: list[SourceFace]) -> str:
    digest = hashlib.sha256()
    seen_paths: set[Path] = set()
    for face in sorted(
        faces,
        key=lambda item: (item.path.name.lower(), item.font_number if item.font_number is not None else -1, item.style),
    ):
        digest.update(face.path.name.encode("utf-8", errors="replace"))
        digest.update(str(face.font_number).encode("ascii"))
        digest.update(face.family.encode("utf-8", errors="replace"))
        digest.update(face.style.encode("ascii"))
        digest.update(_axis_metadata(face, italic=face.style == "italic").encode("ascii"))
        resolved = face.path.resolve()
        if resolved not in seen_paths:
            seen_paths.add(resolved)
            with resolved.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return "vf-" + digest.hexdigest()[:20]


def _supported_weights(face: SourceFace) -> str:
    weight_axis = face.axes.get("wght")
    if weight_axis is None:
        return ""
    minimum, _default, maximum = weight_axis
    return " ".join(str(weight) for weight in WEIGHT_NAMES if minimum <= weight <= maximum)


def _axis_values(face: SourceFace, weight: int, italic: bool) -> dict[str, float] | None:
    if "wght" not in face.axes:
        return None
    minimum, _default, maximum = face.axes["wght"]
    if not minimum <= weight <= maximum:
        return None
    values: dict[str, float] = {}
    for tag, (axis_min, axis_default, axis_max) in face.axes.items():
        if tag == "wght":
            value = float(weight)
        elif tag == "ital":
            value = 1.0 if italic else 0.0
        elif tag == "slnt":
            value = (axis_min if axis_min < 0 else axis_max) if italic else (0.0 if axis_min <= 0 <= axis_max else axis_default)
        else:
            value = axis_default
        values[tag] = max(axis_min, min(axis_max, value))
    return values


def _font_xml(filename: str, weight: int, style: str, *, index: int | None = None, axes: dict[str, float] | None = None) -> str:
    attrs = f' weight="{weight}" style="{style}"'
    if index is not None:
        attrs += f' index="{index}"'
    if not axes:
        return f"    <font{attrs}>{filename}</font>"
    lines = [f"    <font{attrs}>{filename}"]
    lines.extend(f'      <axis tag="{tag}" stylevalue="{_format_number(value)}"/>' for tag, value in axes.items())
    lines.append("    </font>")
    return "\n".join(lines)


def _generate_full_family_xml(faces: list[SourceFace], filename: str, get_index_fn) -> list[str]:
    """Generates XML lines for a set of faces (full 100..900 for variable, exact faces for static)."""
    lines: list[str] = []
    upright_faces = [f for f in faces if f.style == "normal"]
    italic_faces = [f for f in faces if f.style == "italic"]

    for style, s_faces in (("normal", upright_faces), ("italic", italic_faces)):
        if not s_faces:
            continue
        var_face = next((f for f in s_faces if f.variable and "wght" in f.axes), None)
        if var_face is not None:
            idx = get_index_fn(var_face)
            for weight in WEIGHT_NAMES:
                axes = _axis_values(var_face, weight, style == "italic")
                if axes is not None:
                    lines.append(_font_xml(filename, weight, style, index=idx, axes=axes))
        else:
            for face in s_faces:
                idx = get_index_fn(face)
                lines.append(_font_xml(filename, face.weight, face.style, index=idx))
    return lines


def _static_sort(face: SourceFace) -> tuple[int, int, int, str, int]:
    return (int(face.condensed), int(face.style == "italic"), face.weight, face.path.name.lower(), face.font_number or 0)


def _face_preference_score(face: SourceFace) -> int:
    name = face.path.stem.lower()
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
    if face.font_number is None:
        score += 5
    return score


def _dedupe_static(faces: list[SourceFace]) -> list[SourceFace]:
    grouped: dict[tuple[int, str, bool], list[SourceFace]] = {}
    for face in faces:
        key = (face.weight, face.style, face.condensed)
        grouped.setdefault(key, []).append(face)

    selected: list[SourceFace] = []
    for key, group in grouped.items():
        if len(group) == 1:
            selected.append(group[0])
        else:
            best = max(group, key=_face_preference_score)
            other_labels = [f.label for f in group if f != best]
            log.info(f"Duplicate face slot {key}: selected {best.label} over {', '.join(other_labels)}")
            selected.append(best)

    return sorted(selected, key=_static_sort)


def _serif_fragment(entries: list[tuple[int, str, str]]) -> str:
    selected: list[str] = []
    for weight, style in ((400, "normal"), (700, "normal"), (400, "italic"), (700, "italic")):
        exact = next((xml for item_weight, item_style, xml in entries if item_weight == weight and item_style == style), None)
        if exact is None:
            candidates = [(abs(item_weight - weight), xml) for item_weight, item_style, xml in entries if item_style == style]
            exact = min(candidates, default=(0, ""), key=lambda item: item[0])[1]
        if exact and exact not in selected:
            selected.append(exact)
    return "\n".join(selected)


def _write_fragments(files_dir: Path, normal: list[tuple[int, str, str]], condensed: list[tuple[int, str, str]], has_custom_serif: bool = False) -> None:
    normal_xml = "\n".join(xml for _weight, _style, xml in normal)
    condensed_xml = "\n".join(xml for _weight, _style, xml in (condensed or normal))
    (files_dir / "sans.xml").write_text(normal_xml + "\n", encoding="utf-8", newline="\n")
    (files_dir / "condensed.xml").write_text(condensed_xml + "\n", encoding="utf-8", newline="\n")
    if not has_custom_serif:
        (files_dir / "serif.xml").write_text(_serif_fragment(normal) + "\n", encoding="utf-8", newline="\n")


class _FaceIndices:
    """Tracks which TTC face index every source face was written to, by object identity.

    A face can belong to two families at once: when no dedicated sans-serif source was supplied,
    the monospace or serif faces also act as the primary family, and must still be embedded once.
    """

    def __init__(self) -> None:
        self._pairs: list[tuple[SourceFace, int]] = []

    def assign(self, face: SourceFace, index: int) -> None:
        self._pairs.append((face, index))

    def get(self, face: SourceFace) -> int | None:
        for candidate, index in self._pairs:
            if candidate is face:
                return index
        return None

    def __call__(self, face: SourceFace) -> int:
        index = self.get(face)
        if index is None:
            raise SystemExit(f"Internal error: {face.label} was not embedded in the collection")
        return index


def _compile_static(faces: list[SourceFace], files_dir: Path, *, keep_hinting: bool, prefix_family: bool, mono_faces: list[SourceFace] | None = None, serif_faces: list[SourceFace] | None = None) -> tuple[list[SourceFace], tuple[str, ...]]:
    TTCollection, _font = require_fonttools()
    ordered = _dedupe_static(faces)
    fonts = []

    if len(ordered) == 1 and not mono_faces and not serif_faces:
        face = ordered[0]
        output_name = "DroidSans.ttf"
        font = _open_font(face)
        try:
            _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
            font.save(str(files_dir / output_name))
        finally:
            font.close()

        xml = _font_xml(output_name, face.weight, face.style)
        entries = [(face.weight, face.style, xml)]
        _write_fragments(files_dir, entries, [])
        return ordered, (output_name,)

    indices = _FaceIndices()
    try:
        for face in ordered:
            font = _open_font(face)
            _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
            indices.assign(face, len(fonts))
            fonts.append(font)

        for optional_faces in (mono_faces, serif_faces):
            for face in optional_faces or ():
                if indices.get(face) is not None:
                    continue
                font = _open_font(face)
                _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
                indices.assign(face, len(fonts))
                fonts.append(font)

        output_name = "DroidSans.ttf"
        collection = TTCollection()
        collection.fonts = fonts
        collection.save(str(files_dir / output_name))
    finally:
        for font in fonts:
            font.close()

    if mono_faces:
        mono_lines = _generate_full_family_xml(mono_faces, output_name, indices)
        (files_dir / "mono.xml").write_text("\n".join(mono_lines) + "\n", encoding="utf-8", newline="\n")

    if serif_faces:
        serif_lines = _generate_full_family_xml(serif_faces, output_name, indices)
        (files_dir / "serif.xml").write_text("\n".join(serif_lines) + "\n", encoding="utf-8", newline="\n")

    normal: list[tuple[int, str, str]] = []
    condensed: list[tuple[int, str, str]] = []
    for face in ordered:
        xml = _font_xml(output_name, face.weight, face.style, index=indices(face))
        (condensed if face.condensed else normal).append((face.weight, face.style, xml))
    if not normal:
        normal = list(condensed)

    _write_fragments(files_dir, normal, condensed, has_custom_serif=bool(serif_faces))
    return ordered, (output_name,)


def _pick_variable_faces(faces: list[SourceFace]) -> tuple[SourceFace, SourceFace]:
    if any(face.condensed for face in faces):
        raise SystemExit("Variable condensed families are not accepted as the primary family; use a non-condensed variable face")
    uprights = [face for face in faces if face.style == "normal"]
    italics = [face for face in faces if face.style == "italic"]
    if len(uprights) != 1:
        labels = ", ".join(face.label for face in uprights) or "none"
        raise SystemExit(f"Variable builds need exactly one upright source (found: {labels})")
    if len(italics) > 1:
        raise SystemExit("Variable builds accept at most one separate italic source")
    upright = uprights[0]
    italic = italics[0] if italics else upright
    return upright, italic


def _variable_extension(face: SourceFace) -> str:
    return ".otf" if face.sfnt_version == "OTTO" else ".ttf"


def _save_face(face: SourceFace, output: Path, *, keep_hinting: bool, prefix_family: bool) -> None:
    font = _open_font(face)
    try:
        _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
        font.save(str(output))
    finally:
        font.close()


def _compile_variable(faces: list[SourceFace], files_dir: Path, *, keep_hinting: bool, prefix_family: bool, mono_faces: list[SourceFace] | None = None, serif_faces: list[SourceFace] | None = None) -> tuple[list[SourceFace], tuple[str, ...]]:
    TTCollection, _font = require_fonttools()
    upright, italic = _pick_variable_faces(faces)
    output_name = "DroidSans.ttf"
    var_fonts = []
    indices = _FaceIndices()

    upright_font = _open_font(upright)
    _process_font(upright_font, keep_hinting=keep_hinting, prefix_family=prefix_family)
    upright_idx = 0
    indices.assign(upright, upright_idx)
    var_fonts.append(upright_font)

    italic_idx = 0
    if italic != upright:
        italic_font = _open_font(italic)
        _process_font(italic_font, keep_hinting=keep_hinting, prefix_family=prefix_family)
        italic_idx = len(var_fonts)
        indices.assign(italic, italic_idx)
        var_fonts.append(italic_font)

    for optional_faces in (mono_faces, serif_faces):
        for face in optional_faces or ():
            if indices.get(face) is not None:
                continue
            font = _open_font(face)
            _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
            indices.assign(face, len(var_fonts))
            var_fonts.append(font)

    if mono_faces:
        mono_lines = _generate_full_family_xml(mono_faces, output_name, indices)
        (files_dir / "mono.xml").write_text("\n".join(mono_lines) + "\n", encoding="utf-8", newline="\n")

    if serif_faces:
        serif_lines = _generate_full_family_xml(serif_faces, output_name, indices)
        (files_dir / "serif.xml").write_text("\n".join(serif_lines) + "\n", encoding="utf-8", newline="\n")

    collection = TTCollection()
    collection.fonts = var_fonts
    collection.save(str(files_dir / output_name))
    for font in var_fonts:
        font.close()
    payload = [output_name]

    entries: list[tuple[int, str, str]] = []
    for style, face, idx in (("normal", upright, upright_idx), ("italic", italic, italic_idx)):
        for weight in WEIGHT_NAMES:
            axes = _axis_values(face, weight, style == "italic")
            if axes is not None:
                entries.append((weight, style, _font_xml(output_name, weight, style, index=idx, axes=axes)))
    entries.sort(key=lambda item: (item[1] == "italic", item[0]))
    if not entries:
        raise SystemExit("The variable font has no usable wght axis values between 100 and 900")

    _write_fragments(files_dir, entries, [], has_custom_serif=bool(serif_faces))
    return [upright] + ([italic] if italic != upright else []), tuple(payload)


STANDARD_FEATURE_NAMES: dict[str, str] = {
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

UNSAFE_FEATURES: dict[str, str] = {
    "aalt": "UNSAFE: Enables multiple/all alternate glyphs simultaneously across font",
    "calt": "Enabled by default in font layout engines (Contextual)",
    "ccmp": "System layout feature",
    "locl": "System script/language feature",
    "kern": "System layout feature",
    "liga": "Standard Ligature (Enabled by default in font layout engines)",
}

CAUTION_FEATURES: dict[str, str] = {
    "frac": "NOT RECOMMENDED TO FREEZE: Alters normal number sequences (e.g. 123456 -> 1²3456) system-wide!",
    "numr": "Numerators (Shrinks letters/numbers into superior position)",
    "dnom": "Denominators (Shrinks letters/numbers into inferior position)",
    "subs": "Subscript (Shrinks/lowers letters/numbers into subscript)",
    "sups": "Superscript (Shrinks/raises letters/numbers into superscript)",
    "sinf": "Scientific Inferiors (Shrinks numbers into inferior position)",
    "ordn": "Ordinals (Shrinks letters into ordinal position)",
    "onum": "Changes default numbers to oldstyle height",
}


def extract_opentype_features(font_path: Path) -> dict[str, str]:
    """Inspect GSUB table to discover all available OpenType Layout features for any font."""
    _collection, TTFont = require_fonttools()
    features: dict[str, str] = {}
    try:
        font = TTFont(str(font_path), lazy=True)
    except Exception:
        return features

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
            if params:
                name_id = (
                    getattr(params, "UINameID", None)
                    or getattr(params, "FeatUILabelNameID", None)
                    or getattr(params, "featUINameID", None)
                    or getattr(params, "FirstParamUILabelNameID", None)
                )
                if name_id and name_table:
                    for nrec in name_table.names:
                        if nrec.nameID == name_id:
                            try:
                                ui_name = nrec.toUnicode().strip()
                            except Exception:
                                pass
                            if ui_name:
                                break
            if not ui_name:
                if tag in STANDARD_FEATURE_NAMES:
                    ui_name = STANDARD_FEATURE_NAMES[tag]
                elif tag.startswith("ss") and tag[2:].isdigit():
                    ui_name = f"Stylistic Set {int(tag[2:])}"
                elif tag.startswith("cv") and tag[2:].isdigit():
                    ui_name = f"Character Variant {int(tag[2:])}"

            features[tag] = ui_name
    finally:
        font.close()

    return features


def extract_features_from_fonts(font_paths: Iterable[Path]) -> dict[str, str]:
    """Extract all available OpenType Layout features from multiple font files."""
    aggregated: dict[str, str] = {}
    for path in font_paths:
        feats = extract_opentype_features(path)
        for tag, name in feats.items():
            if tag not in aggregated or (not aggregated[tag] and name):
                aggregated[tag] = name
    return dict(sorted(aggregated.items()))


def font_has_centered_colon(font_path: Path) -> bool:
    """Check if font has a built-in centered colon feature (colon.case, colon.centered, or GSUB case/calt colon rules)."""
    _collection, TTFont = require_fonttools()
    try:
        font = TTFont(str(font_path), lazy=True)
    except Exception:
        return True

    try:
        glyph_order = font.getGlyphOrder()
        for name in ("colon.case", "colon.centered", "colon.cap", "colon.case.tf", "colon.centered.tf"):
            if name in glyph_order:
                return True
        if "GSUB" in font and font["GSUB"].table is not None:
            gsub = font["GSUB"].table
            if gsub.FeatureList and gsub.FeatureList.FeatureRecord:
                records = {rec.FeatureTag: rec.Feature for rec in gsub.FeatureList.FeatureRecord if rec.FeatureTag}
                if "case" in records:
                    lookups = gsub.LookupList.Lookup
                    for lidx in records["case"].LookupListIndex:
                        if lidx < len(lookups):
                            for st in getattr(lookups[lidx], "SubTable", []):
                                mapping = getattr(st, "mapping", {})
                                if "colon" in mapping:
                                    return True
    finally:
        font.close()

    return False


def prompt_add_centered_colon_if_missing(font_paths: Iterable[Path], interactive: bool = False) -> bool:
    """Check if input font(s) lack centered colon support and prompt user interactively to add it."""
    if not interactive:
        return False

    font_list = list(font_paths)
    missing = [p for p in font_list if not font_has_centered_colon(p)]
    if not missing:
        return False

    print("\n------------------------------------------------------------")
    print("Centered Colon Feature Check")
    print("------------------------------------------------------------")
    print(f"No centered colon feature (e.g. colon.case for clock 12:30 display) detected in: {', '.join(p.name for p in missing)}")
    choice = input("Do you want to generate & add a vertically centered colon feature for digits/time displays? (y/N): ").strip().lower()
    if choice in ("y", "yes"):
        print("Centered colon generation approved.")
        return True
    return False


def prompt_feature_selection(available_features: dict[str, str], category_name: str = "Sans-serif") -> list[str]:
    """Prompt user interactively to view all OpenType features with safety recommendations and select ones to freeze."""
    if not available_features:
        print(f"\nNo OpenType Layout features detected in {category_name} font(s).")
        return []

    print("\n------------------------------------------------------------")
    print(f"OpenType Feature Freezer Tool Integration — {category_name}")
    print("------------------------------------------------------------")
    choice = input(f"Do you want to freeze any OpenType layout features for {category_name} font family? (y/N): ").strip().lower()
    if choice not in ("y", "yes"):
        print(f"Skipping feature freezing for {category_name}.")
        return []

    safe_feats = {k: v for k, v in available_features.items() if k not in UNSAFE_FEATURES and k not in CAUTION_FEATURES}
    caution_feats = {k: v for k, v in available_features.items() if k in CAUTION_FEATURES}
    unsafe_feats = {k: v for k, v in available_features.items() if k in UNSAFE_FEATURES}

    print("\nAvailable OpenType Layout Features:")

    if safe_feats:
        print("\n  [RECOMMENDED / SAFE TO FREEZE] (Stylistic & Character Alternates, Digit Toggles):")
        for tag, name in sorted(safe_feats.items()):
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            print(label)

    if caution_feats:
        print("\n  [CAUTION - USE WITH CARE] (Layout/Position features - shrinks/repositions text globally):")
        for tag, name in sorted(caution_feats.items()):
            note = CAUTION_FEATURES.get(tag, "")
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            if note:
                label += f" ({note})"
            print(label)

    if unsafe_feats:
        print("\n  [NOT RECOMMENDED / SYSTEM & MASTER ALTERNATE FEATURES]:")
        for tag, name in sorted(unsafe_feats.items()):
            note = UNSAFE_FEATURES.get(tag, "")
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            if note:
                label += f" ({note})"
            print(label)

    print("\n[Visual Preview & Feature Inspection]")
    print("For visual representation and testing of available features, upload your font to:")
    print("  • https://www.adamjagosz.com/bulletproof/lettering")
    print("  • https://wakamaifondue.com/")
    print("------------------------------------------------------------\n")

    user_entries = input("Enter your desired entries (comma or space separated, e.g. ss01, cv01, zero, tnum): ").strip()
    if not user_entries:
        print("No features entered. Proceeding without feature freezing.")
        return []

    raw_tags = re.split(r"[,\s]+", user_entries)
    selected = [t.lower() for t in raw_tags if t.strip()]

    warned = False
    for tag in selected:
        if tag in UNSAFE_FEATURES:
            print(f"\n  [WARNING] '{tag}' is classified as UNSAFE ({UNSAFE_FEATURES[tag]}).")
            warned = True

    if warned:
        confirm = input("Are you sure you want to include these unsafe feature(s)? (y/N): ").strip().lower()
        if confirm not in ("y", "yes"):
            selected = [t for t in selected if t not in UNSAFE_FEATURES]
            print(f"Filtered out unsafe features. Proceeding with: {', '.join(selected) if selected else 'None'}")

    if selected:
        print(f"Selected features to freeze: {', '.join(selected)}")
    return selected


def freeze_font_features(font_path: Path, features: list[str] | str) -> None:
    """Freeze OpenType features into a font file using pyftfeatfreeze for 1-to-1 cmap remappings
    and GSUB lookup promotion into default 'calt'/'liga' features for multi-glyph/contextual rules (like dlig, frac, hlig).
    """
    if isinstance(features, str):
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
    else:
        feature_list = [f.strip() for f in features if f.strip()]

    if not feature_list:
        return

    _collection, TTFont = require_fonttools()

    contextual_candidates = {"dlig", "hlig", "clig", "rvrn"}
    contextual_feats = [f for f in feature_list if f.lower() in contextual_candidates]
    single_feats = [f for f in feature_list if f.lower() not in contextual_candidates]

    temp_output = font_path.with_suffix(".frozen" + font_path.suffix)
    if temp_output.exists():
        temp_output.unlink()

    if single_feats:
        feat_str = ",".join(single_feats)
        executable = shutil.which("pyftfeatfreeze") or "pyftfeatfreeze"
        cmd = [executable, "-f", feat_str, str(font_path), str(temp_output)]
        log.info(f"Freezing 1-to-1 features '{feat_str}' in {font_path.name}...")
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            if temp_output.exists():
                temp_output.unlink()
            err_msg = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise SystemExit(f"Failed to freeze features [{feat_str}] for {font_path.name}: {err_msg}") from exc
        except FileNotFoundError:
            raise SystemExit(
                "opentype-feature-freezer (pyftfeatfreeze) is not installed or not in PATH.\n"
                "Please install it using: pip install opentype-feature-freezer (or pipx install opentype-feature-freezer)"
            )
    else:
        shutil.copy2(font_path, temp_output)

    if contextual_feats:
        try:
            font = TTFont(str(temp_output))
            if "GSUB" in font and font["GSUB"].table is not None and font["GSUB"].table.FeatureList is not None:
                gsub = font["GSUB"].table
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

                tags_to_promote = set(contextual_feats)

                def collect_lookup_and_children(lookup_idx: int, collected_indices: set[int]) -> None:
                    if lookup_idx in collected_indices or lookup_idx >= len(gsub.LookupList.Lookup):
                        return
                    collected_indices.add(lookup_idx)
                    lookup = gsub.LookupList.Lookup[lookup_idx]
                    for st in getattr(lookup, "SubTable", []):
                        sub_recs = getattr(st, "SubstLookupRecord", None)
                        if sub_recs:
                            for sr in sub_recs:
                                collect_lookup_and_children(sr.LookupListIndex, collected_indices)

                indices_to_promote: set[int] = set()
                for tag in tags_to_promote:
                    if tag in records:
                        for idx in records[tag].LookupListIndex:
                            collect_lookup_and_children(idx, indices_to_promote)

                if indices_to_promote:
                    # Sort numerically to preserve OpenType lookup execution sequence
                    added = 0
                    for idx in sorted(indices_to_promote):
                        if idx not in target_feat.LookupListIndex:
                            target_feat.LookupListIndex.append(idx)
                            added += 1
                    if added:
                        log.info(f"Promoted {added} contextual feature lookups (including dependencies) into default active layout feature for {font_path.name}")
                font.save(str(temp_output))
            font.close()
        except Exception as exc:
            log.warning(f"Could not promote contextual lookups in {font_path.name}: {exc}")

    if temp_output.exists():
        shutil.move(temp_output, font_path)
        print(f"Successfully froze features [{','.join(feature_list)}] in {font_path.name}")


def inject_centered_colon(font_path: Path) -> bool:
    """Inject a contextual digit colon rule (digit + colon + digit -> digit + colon.case + digit) into calt
    so colons center automatically for clock displays (12:30) without affecting paragraph body text (note: example).
    If the font lacks a centered colon glyph, generates colon.case dynamically.
    """
    _collection, TTFont = require_fonttools()
    from fontTools.ttLib import newTable
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables.otTables import (
        GSUB, ChainContextSubst, Coverage, Feature, FeatureList, FeatureRecord, LangSys,
        Lookup, LookupList, Script, ScriptList, ScriptRecord, SingleSubst, SubstLookupRecord,
    )

    try:
        try:
            font = TTFont(str(font_path))
        except Exception:
            font = TTFont(str(font_path), fontNumber=0)
    except Exception as exc:
        log.warning(f"Could not open {font_path.name} for centered colon injection: {exc}")
        return False

    try:
        glyph_order = font.getGlyphOrder()
        if "colon" not in glyph_order:
            font.close()
            return False

        centered_glyph = None
        for candidate in ("colon.case.tf", "colon.case", "colon.centered", "colon.cap", "colon.centered.tf"):
            if candidate in glyph_order:
                centered_glyph = candidate
                break

        # Dynamically generate colon.case if font lacks a pre-existing centered colon glyph
        if not centered_glyph and "glyf" in font:
            glyf = font["glyf"]
            hmtx = font["hmtx"]

            coords, _, _ = glyf["colon"].getCoordinates(glyf)
            if coords:
                y_coords = [y for _, y in coords]
                colon_yMin, colon_yMax = min(y_coords), max(y_coords)
                colon_center = (colon_yMin + colon_yMax) / 2

                digit_y_maxes = []
                for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3"):
                    if d in glyph_order:
                        d_coords, _, _ = glyf[d].getCoordinates(glyf)
                        if d_coords:
                            digit_y_maxes.append(max(y for _, y in d_coords))

                cap_height = getattr(font.get("OS/2"), "sCapHeight", None) or 1400
                target_center = (max(digit_y_maxes) / 2) if digit_y_maxes else (cap_height / 2)
                dy = round(target_center - colon_center)
                if dy > 30:
                    pen = TTGlyphPen(font.getGlyphSet())
                    tpen = TransformPen(pen, (1, 0, 0, 1, 0, dy))
                    font.getGlyphSet()["colon"].draw(tpen)

                    centered_glyph = "colon.case"
                    font.setGlyphOrder(glyph_order + [centered_glyph])
                    glyf[centered_glyph] = pen.glyph()
                    hmtx[centered_glyph] = hmtx["colon"]
                    glyph_order = font.getGlyphOrder()
                    log.info(f"Dynamically generated [{centered_glyph}] with vertical offset dy=+{dy} for {font_path.name}")

        if not centered_glyph:
            font.close()
            return False

        # Ensure GSUB table exists
        if "GSUB" not in font or font["GSUB"].table is None:
            if "GSUB" not in font:
                font["GSUB"] = newTable("GSUB")
            gsub = font["GSUB"].table = GSUB()
            gsub.Version = 0x00010000
            gsub.ScriptList = ScriptList()
            gsub.FeatureList = FeatureList()
            gsub.LookupList = LookupList()
            gsub.FeatureList.FeatureRecord = []
            gsub.LookupList.Lookup = []
            # Without a script record the injected feature would be unreachable by any shaper.
            default_lang_sys = LangSys()
            default_lang_sys.LookupOrder = None
            default_lang_sys.ReqFeatureIndex = 0xFFFF
            default_lang_sys.FeatureIndex = []
            script = Script()
            script.DefaultLangSys = default_lang_sys
            script.LangSysRecord = []
            script_record = ScriptRecord()
            script_record.ScriptTag = "DFLT"
            script_record.Script = script
            gsub.ScriptList.ScriptRecord = [script_record]

        gsub = font["GSUB"].table
        if gsub.FeatureList is None:
            gsub.FeatureList = FeatureList()
        if gsub.FeatureList.FeatureRecord is None:
            gsub.FeatureList.FeatureRecord = []
        if gsub.LookupList is None:
            gsub.LookupList = LookupList()
        if gsub.LookupList.Lookup is None:
            gsub.LookupList.Lookup = []

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

        if target_feat.LookupListIndex is None:
            target_feat.LookupListIndex = []

        # Ensure calt_rec_idx is registered in ScriptList for DFLT and latn scripts
        if gsub.ScriptList and gsub.ScriptList.ScriptRecord:
            for srec in gsub.ScriptList.ScriptRecord:
                script = srec.Script
                lang_sys_list = []
                if script.DefaultLangSys:
                    lang_sys_list.append(script.DefaultLangSys)
                if script.LangSysRecord:
                    for lrec in script.LangSysRecord:
                        lang_sys_list.append(lrec.LangSys)

                for lsys in lang_sys_list:
                    if lsys.FeatureIndex is None:
                        lsys.FeatureIndex = []
                    if calt_rec_idx not in lsys.FeatureIndex:
                        lsys.FeatureIndex.append(calt_rec_idx)

        # 1. SingleSubst lookup: colon -> centered_glyph
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

        # 2. ChainContextSubst lookup matching digit + colon + digit
        c_lookup = Lookup()
        c_lookup.LookupType = 6
        c_lookup.LookupFlag = 0

        st6 = ChainContextSubst()
        st6.Format = 3

        pure_digits: set[str] = set()
        cmap = font.getBestCmap()
        for codepoint, gname in cmap.items():
            if (0x0030 <= codepoint <= 0x0039) or (0xFF10 <= codepoint <= 0xFF19) or (0x0660 <= codepoint <= 0x0669) or (0x0966 <= codepoint <= 0x096F):
                pure_digits.add(gname)

        exact_digit_bases = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
        for g in glyph_order:
            parts = g.split(".")
            if parts[0].lower() in exact_digit_bases:
                pure_digits.add(g)

        sorted_digits = sorted(list(pure_digits), key=lambda g: font.getGlyphID(g))

        bcov = Coverage()
        bcov.glyphs = sorted_digits
        icov = Coverage()
        icov.glyphs = sorted([g for g in ("colon", "colon.tf") if g in glyph_order], key=lambda g: font.getGlyphID(g))
        lcov = Coverage()
        lcov.glyphs = sorted_digits

        st6.BacktrackGlyphCount = 1
        st6.BacktrackCoverage = [bcov]
        st6.InputGlyphCount = 1
        st6.InputCoverage = [icov]
        st6.LookAheadGlyphCount = 1
        st6.LookAheadCoverage = [lcov]

        srec = SubstLookupRecord()
        srec.SequenceIndex = 0
        srec.LookupListIndex = s_lidx
        st6.SubstLookupRecord = [srec]

        c_lookup.SubTable = [st6]
        gsub.LookupList.Lookup.append(c_lookup)
        c_lidx = len(gsub.LookupList.Lookup) - 1

        if c_lidx not in target_feat.LookupListIndex:
            target_feat.LookupListIndex.append(c_lidx)
            log.info(f"Injected contextual digit colon lookup [{c_lidx}] into default active layout feature for {font_path.name}")

        font.save(str(font_path))
        font.close()
        return True
    except Exception as exc:
        log.warning(f"Failed to inject contextual centered colon into {font_path.name}: {exc}")
        return False


def _separate_primary_and_optional_faces(all_faces: list[SourceFace]) -> tuple[list[SourceFace], list[SourceFace], list[SourceFace]]:
    sans_faces: list[SourceFace] = []
    mono_faces: list[SourceFace] = []
    serif_faces: list[SourceFace] = []

    for face in all_faces:
        if face.category == "mono":
            mono_faces.append(face)
        elif face.category == "serif":
            serif_faces.append(face)
        else:
            sans_faces.append(face)

    mono_faces = _dedupe_static(mono_faces)
    serif_faces = _dedupe_static(serif_faces)
    # With no dedicated sans-serif source the mono (else serif) faces double as the primary family.
    # They are embedded once, and both fragments point at the same collection indices.
    primary_faces = sans_faces or mono_faces or serif_faces
    return primary_faces, mono_faces, serif_faces


def compile_fonts(
    fonts_dir: Path,
    module_dir: Path,
    *,
    requested_mode: str = "auto",
    keep_hinting: bool = False,
    prefix_family: bool = True,
    features: list[str] | str | None = None,
    mono_features: list[str] | str | None = None,
    serif_features: list[str] | str | None = None,
    interactive_features: bool | None = None,
    centered_colon: bool | None = None,
) -> CompileResult:
    files_dir = module_dir / "Files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_FILES:
        (files_dir / name).unlink(missing_ok=True)
    (files_dir / "clock.xml").unlink(missing_ok=True)

    temp_fonts_dir = module_dir / ".temp_ttf_fonts"
    if temp_fonts_dir.exists():
        shutil.rmtree(temp_fonts_dir, ignore_errors=True)
    temp_fonts_dir.mkdir(parents=True, exist_ok=True)

    try:
        for path, cat in source_entries(fonts_dir):
            sub_dir = temp_fonts_dir / cat
            sub_dir.mkdir(parents=True, exist_ok=True)
            _ensure_ttf(path, sub_dir)

        all_faces = discover_faces(temp_fonts_dir)
        faces, mono_faces, serif_faces = _separate_primary_and_optional_faces(all_faces)

        sans_ttf_paths = sorted({face.path for face in faces})
        mono_ttf_paths = sorted({face.path for face in mono_faces})
        serif_ttf_paths = sorted({face.path for face in serif_faces})

        applied_features: list[str] = []
        do_colon = centered_colon
        should_prompt = interactive_features if interactive_features is not None else sys.stdin.isatty()

        if features is not None or mono_features is not None or serif_features is not None:
            def parse_feat(val):
                if val is None:
                    return []
                if isinstance(val, str):
                    return [f.strip() for f in val.split(",") if f.strip()]
                return [f.strip() for f in val if f.strip()]

            sans_feats = parse_feat(features)
            mono_feats = parse_feat(mono_features) if mono_features is not None else sans_feats
            serif_feats = parse_feat(serif_features) if serif_features is not None else sans_feats

            for p in sans_ttf_paths:
                freeze_font_features(p, sans_feats)
            for p in mono_ttf_paths:
                freeze_font_features(p, mono_feats)
            for p in serif_ttf_paths:
                freeze_font_features(p, serif_feats)

            applied_features.extend(list(dict.fromkeys(sans_feats + mono_feats + serif_feats)))
        elif should_prompt:
            if do_colon is None:
                do_colon = prompt_add_centered_colon_if_missing(sans_ttf_paths, interactive=should_prompt)

            if sans_ttf_paths:
                avail_sans = extract_features_from_fonts(sans_ttf_paths)
                if avail_sans:
                    feat_sans = prompt_feature_selection(avail_sans, category_name="Sans-serif")
                    if feat_sans:
                        for p in sans_ttf_paths:
                            freeze_font_features(p, feat_sans)
                        applied_features.extend(feat_sans)

            if mono_ttf_paths:
                avail_mono = extract_features_from_fonts(mono_ttf_paths)
                if avail_mono:
                    feat_mono = prompt_feature_selection(avail_mono, category_name="Monospace")
                    if feat_mono:
                        for p in mono_ttf_paths:
                            freeze_font_features(p, feat_mono)
                        applied_features.extend(feat_mono)

            if serif_ttf_paths:
                avail_serif = extract_features_from_fonts(serif_ttf_paths)
                if avail_serif:
                    feat_serif = prompt_feature_selection(avail_serif, category_name="Serif")
                    if feat_serif:
                        for p in serif_ttf_paths:
                            freeze_font_features(p, feat_serif)
                        applied_features.extend(feat_serif)

        if do_colon:
            for font_path in sans_ttf_paths:
                inject_centered_colon(font_path)

        all_faces = discover_faces(temp_fonts_dir)
        faces, mono_faces, serif_faces = _separate_primary_and_optional_faces(all_faces)
        mode = detect_mode(faces, requested_mode)
        families = {face.family for face in faces}
        if len(families) > 1:
            raise SystemExit("Input files contain multiple font families: " + ", ".join(sorted(families)))
        family = next(iter(families))
        if prefix_family:
            family = transform_family_name(family)
        if mode == "static":
            selected, payload = _compile_static(faces, files_dir, keep_hinting=keep_hinting, prefix_family=prefix_family, mono_faces=mono_faces, serif_faces=serif_faces)
        else:
            selected, payload = _compile_variable(faces, files_dir, keep_hinting=keep_hinting, prefix_family=prefix_family, mono_faces=mono_faces, serif_faces=serif_faces)

        primary = payload[0]
        config = [
            f"FONT_MODE={shell_quote(mode)}",
            f"FONT_FAMILY={shell_quote(family)}",
            f"FONT_FILES={shell_quote(' '.join(payload))}",
            f"FONT_PRIMARY={shell_quote(primary)}",
        ]
        if mode == "variable":
            upright, italic = _pick_variable_faces(faces)
            config.extend(
                (
                    "VF_CONFIG_SCHEMA='2'",
                    f"VF_UPRIGHT_AXIS_META={shell_quote(_axis_metadata(upright, italic=False))}",
                    f"VF_ITALIC_AXIS_META={shell_quote(_axis_metadata(italic, italic=True))}",
                    f"VF_UPRIGHT_WEIGHTS={shell_quote(_supported_weights(upright))}",
                    f"VF_ITALIC_WEIGHTS={shell_quote(_supported_weights(italic))}",
                    f"VF_CONFIG_ID={shell_quote(_variable_config_identity(faces))}",
                )
            )
        (module_dir / "font-config.sh").write_text("\n".join(config) + "\n", encoding="utf-8", newline="\n")
        return CompileResult(mode, family, tuple(selected), payload, tuple(applied_features))
    finally:
        shutil.rmtree(temp_fonts_dir, ignore_errors=True)


def update_module_metadata(
    module_dir: Path,
    family: str,
    mode: Mode,
    *,
    name: str | None = None,
    version: str | None = None,
    version_code: str | None = None,
    applied_features: Iterable[str] | None = None,
) -> dict[str, str]:
    path = module_dir / "module.prop"
    props = read_props(path)
    display = display_name_for_mode(name or clean_family_name(family), mode)
    if applied_features and not any(f"({f}" in display for f in applied_features):
        feat_str = ", ".join(applied_features)
        display = f"{display} ({feat_str})"
    now = dt.datetime.now().astimezone()
    version = version or now.strftime("%Y.%m.%d")
    version_code = version_code or now.strftime("%Y%m%d%H%M")
    props["id"] = "mffm14"
    props["name"] = f"[MFFMv14] {display}"
    props["version"] = version
    props["versionCode"] = version_code
    props.setdefault("author", "MFFM")
    props["description"] = (
        f'Replaces Android\'s default Roboto family with "{display}" ({mode}). '
        "Compatible with Magisk, KernelSU, and APatch."
    )
    props.setdefault("minMagisk", "20400")
    props.setdefault("minKernelSU", "10940")
    props.setdefault("minAPatch", "11000")
    write_props(path, props)
    return props
