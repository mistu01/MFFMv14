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
    "sans.xml", "condensed.xml", "serif.xml", "mono.xml", "bengali.xml",
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
    axes: dict[str, tuple[float, float, float]]
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
    # Per-category source faces detected during compilation, keyed by category
    # ("sans", "mono", "serif", "bengali"). Populated by compile_fonts so the
    # build summary can report every provided family, not just Sans.
    family_faces: dict[str, tuple[SourceFace, ...]] = field(default_factory=dict)


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
    value = re.sub(r"(?i)\b(?:MFFM|Mistu)\b", "", value)
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
        named_weight = _weight_from_label(style_name) or _weight_from_label(metadata_label) or stem_w

        if os2_w in WEIGHT_NAMES and os2_w != 400:
            # Trust OS/2 unless named weight contradicts more strongly
            if named_weight and named_weight != os2_w and abs(named_weight - 400) > abs(os2_w - 400):
                weight = named_weight
            else:
                weight = os2_w
        elif named_weight:
            weight = named_weight
        elif os2_w in WEIGHT_NAMES:
            weight = os2_w
        else:
            weight = _nearest_weight(os2_w or 400)


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


def discover_faces(fonts_dir: Path) -> list[SourceFace]:
    TTCollection, _font = require_fonttools()
    if not fonts_dir.is_dir():
        fonts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Automatically ensure mandatory family subdirectories exist
    for sub in ("Sans", "Monospace", "Serif", "Bengali"):
        (fonts_dir / sub).mkdir(parents=True, exist_ok=True)

    # 2. Strict Rule: Reject font files placed directly in root of fonts_dir
    root_fonts = [
        p for p in fonts_dir.iterdir()
        if p.is_file() and p.suffix.lower() in FONT_EXTENSIONS
    ]
    if root_fonts:
        sample_names = ", ".join(p.name for p in root_fonts[:3])
        raise SystemExit(
            f"Strict layout rule error: Font file(s) [{sample_names}] found directly in '{fonts_dir}'.\n"
            f"Fonts MUST be placed inside their respective subdirectories:\n"
            f"  - Primary Sans-serif font -> '{fonts_dir / 'Sans'}'\n"
            f"  - Monospace font          -> '{fonts_dir / 'Monospace'}'\n"
            f"  - Serif font              -> '{fonts_dir / 'Serif'}'\n"
            f"  - Bengali font            -> '{fonts_dir / 'Bengali'}'\n"
            f"Please move your fonts into '{fonts_dir / 'Sans'}' (or 'Monospace'/'Serif'/'Bengali')."
        )

    file_entries: list[tuple[Path, str]] = []
    for p in sorted(fonts_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in FONT_EXTENSIONS:
            rel_parts = [part.lower() for part in p.relative_to(fonts_dir).parts[:-1]]
            if not rel_parts:
                continue
            if any(part in ("monospace", "mono") for part in rel_parts):
                cat = "mono"
            elif any(part == "serif" for part in rel_parts):
                cat = "serif"
            elif any(part in ("bengali", "beng") for part in rel_parts):
                cat = "bengali"
            elif any(part in ("sans", "sans-serif") for part in rel_parts):
                cat = "sans"
            else:
                stem_lower = p.stem.lower()
                if any(m in stem_lower for m in ("mono", "code", "consolas", "courier")):
                    cat = "mono"
                elif "serif" in stem_lower and "sans" not in stem_lower:
                    cat = "serif"
                elif any(m in stem_lower for m in ("bengali", "beng")):
                    cat = "bengali"
                else:
                    cat = "sans"
            file_entries.append((p, cat))

    if not file_entries:
        raise SystemExit(
            f"No font files found in '{fonts_dir / 'Sans'}', '{fonts_dir / 'Monospace'}', '{fonts_dir / 'Serif'}', or '{fonts_dir / 'Bengali'}'.\n"
            f"Please place your primary body font file(s) into '{fonts_dir / 'Sans'}'."
        )

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
    if not face_list:
        raise SystemExit("No font faces found to detect mode.")
    if requested in {"static", "variable"}:
        return requested  # type: ignore[return-value]

    # Primary mode is determined by the primary body font face
    primary_upright = next(
        (f for f in face_list if f.style == "normal" and not f.condensed and f.weight == 400),
        next((f for f in face_list if f.style == "normal" and not f.condensed), face_list[0])
    )
    return "variable" if primary_upright.variable else "static"



def _remove_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()


log = logging.getLogger("font_metrics_rewriter")

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

REFERENCE_STATIC_UPRIGHT = {
    ("head", "yMin"): -555, ("head", "yMax"): 2163, ("head", "macStyle"): 0,
    ("hhea", "ascent"): 1900, ("hhea", "descent"): -500, ("hhea", "lineGap"): 0,
    ("hhea", "caretSlopeRise"): 1, ("hhea", "caretSlopeRun"): 0, ("hhea", "caretOffset"): 0,
    ("hhea", "reserved0"): 0, ("hhea", "reserved1"): 0, ("hhea", "reserved2"): 0, ("hhea", "reserved3"): 0,
    ("hhea", "metricDataFormat"): 0,
    ("OS/2", "sTypoAscender"): 2146, ("OS/2", "sTypoDescender"): -555, ("OS/2", "sTypoLineGap"): 0,
    ("OS/2", "usWinAscent"): 2146, ("OS/2", "usWinDescent"): 555, ("OS/2", "sxHeight"): 1082,
    ("OS/2", "sCapHeight"): 1456, ("OS/2", "usDefaultChar"): 0, ("OS/2", "usBreakChar"): 32,
    ("OS/2", "usMaxContext"): 3,
    ("post", "underlinePosition"): -150, ("post", "underlineThickness"): 100,
    ("vhea", "ascent"): 800, ("vhea", "descent"): -800, ("vhea", "lineGap"): 0,
    ("post", "italicAngle"): 0.0, ("hhea", "italicAngle"): 0,
}

REFERENCE_STATIC_ITALIC = dict(REFERENCE_STATIC_UPRIGHT)
REFERENCE_STATIC_ITALIC.update({
    ("head", "macStyle"): 2,
    ("post", "italicAngle"): -12.0,
})

REFERENCE_VAR = dict(REFERENCE_STATIC_UPRIGHT)

WRITABLE_METRICS = [
    ("head", "yMin"), ("head", "yMax"),
    ("hhea", "ascent"), ("hhea", "descent"), ("hhea", "lineGap"),
    ("hhea", "caretSlopeRise"), ("hhea", "caretSlopeRun"), ("hhea", "caretOffset"),
    ("OS/2", "sTypoAscender"), ("OS/2", "sTypoDescender"), ("OS/2", "sTypoLineGap"),
    ("OS/2", "usWinAscent"), ("OS/2", "usWinDescent"), ("OS/2", "sxHeight"), ("OS/2", "sCapHeight"),
    ("post", "underlinePosition"), ("post", "underlineThickness"),
    ("vhea", "ascent"), ("vhea", "descent"), ("vhea", "lineGap"),
]

ITALIC_METRICS = [
    ("post", "italicAngle"),
    ("hhea", "italicAngle"),
]

MVAR_METRIC_TAGS = {"hasc", "hdsc", "hlgp", "tasc", "tdsc", "tlgp", "wasc", "wdsc", "unds", "undt", "dscs"}
HVAR_METRIC_TAGS = {"LsbMap"}


class FontMetricRewriter:
    REFERENCE_UPM = 2048
    FAMILY_SUFFIX = "MFFM"
    FAMILY_NAME_IDS = {1, 16, 21}
    POSTSCRIPT_NAME_IDS = {6, 20, 25}

    def __init__(self, reference_font_path: str = None):
        self.reference = dict(REFERENCE_STATIC_UPRIGHT)
        self._extract_from_reference_file = False
        if reference_font_path:
            self._load_from_reference_file(reference_font_path)

    def _load_from_reference_file(self, path: str):
        try:
            from fontTools.ttLib import TTFont
            reference_font = TTFont(path)
        except Exception as exc:
            log.warning(f"Could not load reference font '{path}': {exc}. Using built-in reference values.")
            return

        extracted = {}
        for (tbl, fld) in WRITABLE_METRICS:
            table = reference_font.get(tbl)
            if table and hasattr(table, fld):
                extracted[(tbl, fld)] = getattr(table, fld)

        for (tbl, fld) in ITALIC_METRICS:
            table = reference_font.get(tbl)
            if table and hasattr(table, fld):
                extracted[(tbl, fld)] = getattr(table, fld)

        if extracted:
            self.reference = extracted
            self._extract_from_reference_file = True
            log.info(f"Extracted {len(extracted)} metrics from reference font: {path}")
        else:
            log.warning("No metrics extracted from reference font. Using built-in reference values.")
        reference_font.close()

    def _select_reference(self, font):
        if self._extract_from_reference_file:
            return
        is_var = self._is_variable(font)
        is_italic = False
        post = font.get("post")
        if post and getattr(post, "italicAngle", 0) != 0:
            is_italic = True
        head = font.get("head")
        if head and (getattr(head, "macStyle", 0) & 2):
            is_italic = True

        if is_var:
            self.reference = dict(REFERENCE_VAR)
        elif is_italic:
            self.reference = dict(REFERENCE_STATIC_ITALIC)
        else:
            self.reference = dict(REFERENCE_STATIC_UPRIGHT)

    @staticmethod
    def _get_upm(font) -> int:
        head = font.get("head")
        if head is None:
            raise ValueError("Font missing 'head' table; cannot determine UPM.")
        return head.unitsPerEm

    @staticmethod
    def _scale(val: int, from_upm: int, to_upm: int) -> int:
        return int(round(val * to_upm / from_upm))

    def _scale_all_references(self, target_upm: int) -> dict:
        return {key: self._scale(val, self.REFERENCE_UPM, target_upm) for key, val in self.reference.items()}

    def extract_metrics(self, font, include_italic: bool = False) -> dict:
        metrics = {}
        field_list = list(WRITABLE_METRICS)
        if include_italic:
            field_list.extend(ITALIC_METRICS)
        for (tbl, fld) in field_list:
            table = font.get(tbl)
            if table is not None and hasattr(table, fld):
                metrics[(tbl, fld)] = getattr(table, fld)
        return metrics

    @staticmethod
    def _decode_name_record(record) -> str | None:
        try:
            return record.toUnicode()
        except Exception:
            try:
                return record.string.decode(record.getEncoding(), errors="replace")
            except Exception:
                return None

    @staticmethod
    def _encode_name_record(record, value: str) -> None:
        try:
            record.string = value.encode(record.getEncoding(), errors="replace")
        except Exception:
            record.string = value.encode("utf-16-be", errors="replace")

    @staticmethod
    def _name_record_priority(record) -> tuple:
        if record.platformID == 3 and record.langID in (0x409, 0):
            return (0, record.nameID)
        if record.platformID == 3:
            return (1, record.nameID)
        if record.platformID == 0:
            return (2, record.nameID)
        if record.platformID == 1 and record.langID == 0:
            return (3, record.nameID)
        return (4, record.nameID)

    @classmethod
    def _append_family_suffix(cls, family_name: str) -> str:
        cleaned = family_name.strip()
        if not cleaned:
            return cleaned
        parts = cleaned.split()
        if parts and parts[-1].upper() == cls.FAMILY_SUFFIX:
            return cleaned
        return f"{cleaned} {cls.FAMILY_SUFFIX}"

    @staticmethod
    def _postscript_safe_name(value: str) -> str:
        forbidden = set("[](){}<>/%")
        chars = [char for char in value if not char.isspace() and char not in forbidden and 33 <= ord(char) <= 126]
        return "".join(chars)

    def extract_family_name(self, font) -> str | None:
        name_table = font.get("name")
        if name_table is None:
            return None
        for name_id in (16, 1, 21):
            records = [rec for rec in name_table.names if rec.nameID == name_id]
            for record in sorted(records, key=self._name_record_priority):
                text = self._decode_name_record(record)
                if text and text.strip():
                    return text.strip()
        return None

    def rewrite_family_names(self, font) -> dict:
        name_table = font.get("name")
        if name_table is None:
            log.warning("Font has no name table; skipping family name rewrite.")
            return {}

        family_name = self.extract_family_name(font)
        if not family_name:
            log.warning("Could not extract a family name; skipping name table rewrite.")
            return {}

        new_family_name = self._append_family_suffix(family_name)
        old_ps_family = self._postscript_safe_name(family_name)
        new_ps_family = self._postscript_safe_name(new_family_name)
        changes = {}

        for record in name_table.names:
            text = self._decode_name_record(record)
            if not text:
                continue

            if record.nameID in self.FAMILY_NAME_IDS:
                rewritten = text
                if new_family_name not in rewritten and new_ps_family not in rewritten:
                    for old, new in ((family_name, new_family_name), (old_ps_family, new_ps_family)):
                        if old and old in rewritten:
                            rewritten = rewritten.replace(old, new)
                            break
                    else:
                        rewritten = self._append_family_suffix(text)
            elif record.nameID in self.POSTSCRIPT_NAME_IDS:
                rewritten = text
                if new_ps_family not in rewritten:
                    for old, new in ((old_ps_family, new_ps_family), (family_name, new_ps_family)):
                        if old and old in rewritten:
                            rewritten = rewritten.replace(old, new)
                            break
            else:
                rewritten = text
                if new_family_name not in rewritten and new_ps_family not in rewritten:
                    for old, new in ((family_name, new_family_name), (old_ps_family, new_ps_family)):
                        if old and old in rewritten:
                            rewritten = rewritten.replace(old, new)
                            break

            if rewritten == text:
                continue

            self._encode_name_record(record, rewritten)
            changes[record.nameID] = changes.get(record.nameID, 0) + 1

        if changes:
            changed_ids = ", ".join(f"nameID {name_id} ({count})" for name_id, count in sorted(changes.items()))
            log.info(f"Family name rewrite: '{family_name}' -> '{new_family_name}' | {changed_ids}")
        else:
            log.info(f"Family name already uses suffix: '{new_family_name}'")
        return changes

    def rewrite_static(self, font, include_italic: bool = False) -> dict:
        self._select_reference(font)
        target_upm = self._get_upm(font)
        scaled = self._scale_all_references(target_upm)
        log.info(f"UPM: {target_upm} | Scale factor: {target_upm}/{self.REFERENCE_UPM} = {target_upm / self.REFERENCE_UPM:.6f}")
        changes = {}
        field_list = list(WRITABLE_METRICS)
        if include_italic:
            field_list.extend(ITALIC_METRICS)

        for (tbl, fld) in field_list:
            key = (tbl, fld)
            if key not in scaled:
                continue
            new_val = scaled[key]
            table = font.get(tbl)
            if table is None or not hasattr(table, fld):
                continue
            old_val = getattr(table, fld)
            if old_val == new_val:
                continue
            setattr(table, fld, new_val)
            changes[(tbl, fld)] = (old_val, new_val)
            log.info(f"  {tbl}.{fld}: {old_val} -> {new_val}")
        return changes

    @staticmethod
    def _is_variable(font) -> bool:
        return "fvar" in font or "STAT" in font

    def rewrite_variable(self, font, include_italic: bool = False, set_default_wght: bool = True) -> dict:
        self._select_reference(font)
        target_upm = self._get_upm(font)
        scale_factor = target_upm / self.REFERENCE_UPM
        log.info(f"Variable font detected | UPM: {target_upm} | scale factor: {scale_factor:.6f}")
        changes = self.rewrite_static(font, include_italic=include_italic)
        mvar_changes = self._rescale_mvar_store(font, scale_factor)
        hvar_changes = self._rescale_hvar_store(font, scale_factor)
        vvar_changes = self._rescale_vvar_store(font, scale_factor)
        fvar_changes = self._rescale_fvar_axes(font, scale_factor, set_default_wght=set_default_wght)
        return {**changes, **mvar_changes, **hvar_changes, **vvar_changes, **fvar_changes}

    def _rescale_mvar_store(self, font, scale_factor: float) -> dict:
        if "MVAR" not in font:
            return {}
        mvar_table = font["MVAR"].table
        if not hasattr(mvar_table, "VarStore") or mvar_table.VarStore is None:
            return {}
        count = self._rescale_var_store_inner(mvar_table.VarStore, scale_factor)
        log.info(f"MVAR: rescaled {count} delta values")
        return {"MVAR.VarStore": ("rescaled", count)}

    def _rescale_hvar_store(self, font, scale_factor: float) -> dict:
        if "HVAR" not in font:
            return {}
        hvar_table = font["HVAR"].table
        if not hvar_table or not hasattr(hvar_table, "VarStore"):
            return {}
        count = self._rescale_var_store_inner(hvar_table.VarStore, scale_factor)
        log.info(f"HVAR: rescaled {count} delta values")
        return {"HVAR.VarStore": ("rescaled", count)}

    def _rescale_vvar_store(self, font, scale_factor: float) -> dict:
        if "VVAR" not in font:
            return {}
        vvar_table = font["VVAR"].table
        if not vvar_table or not hasattr(vvar_table, "VarStore"):
            return {}
        count = self._rescale_var_store_inner(vvar_table.VarStore, scale_factor)
        log.info(f"VVAR: rescaled {count} delta values")
        return {"VVAR.VarStore": ("rescaled", count)}

    def _rescale_var_store_inner(self, var_store, scale_factor: float) -> int:
        if not hasattr(var_store, "ItemVariationStore"):
            return 0
        ivs = var_store.ItemVariationStore
        if not hasattr(ivs, "VariationData") or not ivs.VariationData:
            return 0
        total = 0
        for var_data in ivs.VariationData:
            if var_data is None:
                continue
            fmt = getattr(var_data, "Format", 1)
            if fmt == 1:
                total += self._scale_var_data_fmt1(var_data, scale_factor)
            elif fmt == 2:
                total += self._scale_var_data_fmt2(var_data, scale_factor)
            elif fmt == 3:
                total += self._scale_var_data_fmt3(var_data, scale_factor)
        return total

    @staticmethod
    def _scale_var_data_fmt1(var_data, scale_factor: float) -> int:
        count = 0
        if not hasattr(var_data, "RegionIdxCount") or not hasattr(var_data, "RegionIndex"):
            return count
        rows = var_data.VarDataRows
        if not rows:
            return count
        for row in rows:
            if row is None:
                continue
            if hasattr(row, "RegionDelta"):
                for i, delta in enumerate(row.RegionDelta):
                    if isinstance(delta, (int, float)):
                        row.RegionDelta[i] = int(round(delta * scale_factor))
                        count += 1
            elif hasattr(row, "getDeltas"):
                deltas = row.getDeltas()
                scaled = [int(round(d * scale_factor)) for d in deltas]
                row.setDeltas(scaled)
                count += len(deltas)
        return count

    @staticmethod
    def _scale_var_data_fmt2(var_data, scale_factor: float) -> int:
        count = 0
        if hasattr(var_data, "DeltaSet"):
            for ds in var_data.DeltaSet:
                if ds is None:
                    continue
                if hasattr(ds, "DeltaValue"):
                    for dv in ds.DeltaValue:
                        if dv is not None and hasattr(dv, "Value"):
                            old = dv.Value
                            if isinstance(old, (int, float)):
                                dv.Value = int(round(old * scale_factor))
                                count += 1
        if hasattr(var_data, "getDeltas"):
            deltas = var_data.getDeltas()
            scaled = [int(round(d * scale_factor)) for d in deltas]
            var_data.setDeltas(scaled)
            count += len(deltas)
        return count

    @staticmethod
    def _scale_var_data_fmt3(var_data, scale_factor: float) -> int:
        count = 0
        if hasattr(var_data, "getDeltas"):
            deltas = var_data.getDeltas()
            scaled = [int(round(d * scale_factor)) for d in deltas]
            var_data.setDeltas(scaled)
            count += len(deltas)
        return count

    def _rescale_fvar_axes(self, font, scale_factor: float, set_default_wght: bool = True) -> dict:
        if "fvar" not in font:
            return {}
        fvar = font["fvar"]
        if not hasattr(fvar, "axes"):
            return {}
        udm_axes = {"opsz"}
        changes = {}
        for axis in fvar.axes:
            if axis.axisTag == "wght" and set_default_wght:
                old_default = axis.defaultValue
                axis.defaultValue = 400
                log.info(f"fvar axis 'wght': default {old_default}->400")
                changes["fvar.wght"] = (old_default, 400)
            if axis.axisTag not in udm_axes:
                continue
            old_default = axis.defaultValue
            old_min = getattr(axis, "minValue", None)
            old_max = getattr(axis, "maxValue", None)
            axis.defaultValue = int(round(old_default * scale_factor))
            if old_min is not None:
                axis.minValue = int(round(old_min * scale_factor))
            if old_max is not None:
                axis.maxValue = int(round(old_max * scale_factor))
            log.info(f"fvar axis '{axis.axisTag}': default {old_default}->{axis.defaultValue}, min {old_min}->{axis.minValue}, max {old_max}->{axis.maxValue}")
            changes[f"fvar.{axis.axisTag}"] = (old_default, axis.defaultValue)
        return changes


def _scale_ffix3_value(value: int, units_per_em: int) -> int:
    return int(value / FFIX3_REFERENCE_UPM * units_per_em)


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
    os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
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
    style_values = _axis_values(face, int(face.axes["wght"][1]), italic) or {}
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
        if face.axes and "wght" in face.axes:
            digest.update(_axis_metadata(face, italic=face.style == "italic").encode("ascii"))
        resolved = face.path.resolve()
        if resolved not in seen_paths:
            seen_paths.add(resolved)
            with resolved.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return "vf-" + digest.hexdigest()[:20]


def _supported_weights(face: SourceFace) -> str:
    minimum, _default, maximum = face.axes["wght"]
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


def _compile_static(faces: list[SourceFace], files_dir: Path, *, keep_hinting: bool, prefix_family: bool, mono_faces: list[SourceFace] | None = None, serif_faces: list[SourceFace] | None = None, bengali_faces: list[SourceFace] | None = None) -> tuple[list[SourceFace], tuple[str, ...], int | None]:
    TTCollection, _font = require_fonttools()
    ordered = _dedupe_static(faces)
    fonts = []
    mono_index: int | None = None

    if len(ordered) == 1 and not mono_faces and not serif_faces and not bengali_faces:
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
        return ordered, (output_name,), None

    try:
        for face in ordered:
            font = _open_font(face)
            _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
            fonts.append(font)

        mface_idx_map: dict[int, int] = {}
        if mono_faces:
            for mface in mono_faces:
                mfont = _open_font(mface)
                _process_font(mfont, keep_hinting=keep_hinting, prefix_family=prefix_family)
                midx = len(fonts)
                mface_idx_map[id(mface)] = midx
                if mono_index is None:
                    mono_index = midx
                fonts.append(mfont)

        sface_idx_map: dict[int, int] = {}
        if serif_faces:
            for sface in serif_faces:
                sfont = _open_font(sface)
                _process_font(sfont, keep_hinting=keep_hinting, prefix_family=prefix_family)
                sidx = len(fonts)
                sface_idx_map[id(sface)] = sidx
                fonts.append(sfont)

        bface_idx_map: dict[int, int] = {}
        if bengali_faces:
            for bface in bengali_faces:
                bfont = _open_font(bface)
                _process_font(bfont, keep_hinting=keep_hinting, prefix_family=prefix_family)
                bidx = len(fonts)
                bface_idx_map[id(bface)] = bidx
                fonts.append(bfont)

        output_name = "DroidSans.ttf"
        collection = TTCollection()
        collection.fonts = fonts
        collection.save(str(files_dir / output_name))
    finally:
        for font in fonts:
            font.close()

    if mono_faces:
        mono_lines = _generate_full_family_xml(mono_faces, "DroidSans.ttf", lambda f: mface_idx_map[id(f)])
        (files_dir / "mono.xml").write_text("\n".join(mono_lines) + "\n", encoding="utf-8", newline="\n")

    if serif_faces:
        serif_lines = _generate_full_family_xml(serif_faces, "DroidSans.ttf", lambda f: sface_idx_map[id(f)])
        (files_dir / "serif.xml").write_text("\n".join(serif_lines) + "\n", encoding="utf-8", newline="\n")

    if bengali_faces:
        bengali_lines = _generate_full_family_xml(bengali_faces, "DroidSans.ttf", lambda f: bface_idx_map[id(f)])
        (files_dir / "bengali.xml").write_text("\n".join(bengali_lines) + "\n", encoding="utf-8", newline="\n")

    normal: list[tuple[int, str, str]] = []
    condensed: list[tuple[int, str, str]] = []
    for index, face in enumerate(ordered):
        xml = _font_xml(output_name, face.weight, face.style, index=index)
        (condensed if face.condensed else normal).append((face.weight, face.style, xml))
    if not normal:
        normal = list(condensed)

    _write_fragments(files_dir, normal, condensed, has_custom_serif=bool(serif_faces))
    return ordered, (output_name,), mono_index


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


def _compile_variable(faces: list[SourceFace], files_dir: Path, *, keep_hinting: bool, prefix_family: bool, mono_faces: list[SourceFace] | None = None, serif_faces: list[SourceFace] | None = None, bengali_faces: list[SourceFace] | None = None) -> tuple[list[SourceFace], tuple[str, ...], int | None]:
    TTCollection, _font = require_fonttools()
    upright, italic = _pick_variable_faces(faces)
    output_name = "DroidSans.ttf"
    var_fonts = []
    mono_index: int | None = None

    upright_font = _open_font(upright)
    _process_font(upright_font, keep_hinting=keep_hinting, prefix_family=prefix_family)
    var_fonts.append(upright_font)
    upright_idx = 0

    italic_idx = 0
    if italic != upright:
        italic_font = _open_font(italic)
        _process_font(italic_font, keep_hinting=keep_hinting, prefix_family=prefix_family)
        italic_idx = len(var_fonts)
        var_fonts.append(italic_font)

    mface_idx_map: dict[int, int] = {}
    if mono_faces:
        for mface in mono_faces:
            mfont = _open_font(mface)
            _process_font(mfont, keep_hinting=keep_hinting, prefix_family=prefix_family)
            midx = len(var_fonts)
            mface_idx_map[id(mface)] = midx
            if mono_index is None:
                mono_index = midx
            var_fonts.append(mfont)
        mono_lines = _generate_full_family_xml(mono_faces, output_name, lambda f: mface_idx_map[id(f)])
        (files_dir / "mono.xml").write_text("\n".join(mono_lines) + "\n", encoding="utf-8", newline="\n")

    sface_idx_map: dict[int, int] = {}
    if serif_faces:
        for sface in serif_faces:
            sfont = _open_font(sface)
            _process_font(sfont, keep_hinting=keep_hinting, prefix_family=prefix_family)
            sidx = len(var_fonts)
            sface_idx_map[id(sface)] = sidx
            var_fonts.append(sfont)
        serif_lines = _generate_full_family_xml(serif_faces, output_name, lambda f: sface_idx_map[id(f)])
        (files_dir / "serif.xml").write_text("\n".join(serif_lines) + "\n", encoding="utf-8", newline="\n")

    bface_idx_map: dict[int, int] = {}
    if bengali_faces:
        for bface in bengali_faces:
            bfont = _open_font(bface)
            _process_font(bfont, keep_hinting=keep_hinting, prefix_family=prefix_family)
            bidx = len(var_fonts)
            bface_idx_map[id(bface)] = bidx
            var_fonts.append(bfont)
        bengali_lines = _generate_full_family_xml(bengali_faces, output_name, lambda f: bface_idx_map[id(f)])
        (files_dir / "bengali.xml").write_text("\n".join(bengali_lines) + "\n", encoding="utf-8", newline="\n")

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
    return [upright] + ([italic] if italic != upright else []), tuple(payload), mono_index


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


def prompt_add_centered_colon_if_missing(font_paths: Iterable[Path], interactive: bool = False, category: str = "font") -> bool:
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
    print(f"No centered colon feature (e.g. colon.case for clock 12:30 display) detected in {category} font(s): {', '.join(p.name for p in missing)}")
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
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables.otTables import ChainContextSubst, Coverage, Lookup, SingleSubst, SubstLookupRecord, FeatureRecord, Feature

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

        # Ensure GSUB table exists (fontTools newTable wrapper + inner otTables structure)
        if "GSUB" not in font or font["GSUB"].table is None:
            from fontTools.ttLib import newTable
            from fontTools.ttLib.tables.otTables import GSUB, FeatureList, LookupList, ScriptList
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
        if gsub.FeatureList is None:
            gsub.FeatureList = FeatureList()
        if gsub.FeatureList.FeatureRecord is None:
            gsub.FeatureList.FeatureRecord = []
        if gsub.LookupList is None:
            gsub.LookupList = LookupList()
        if gsub.LookupList.Lookup is None:
            gsub.LookupList.Lookup = []

        records = {rec.FeatureTag: rec.Feature for rec in gsub.FeatureList.FeatureRecord if rec.FeatureTag}
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
                    if calt_rec_idx not in lsys.FeatureIndex:
                        lsys.FeatureIndex.append(calt_rec_idx)
        elif gsub.ScriptList is not None:
            # No scripts defined (font had no GSUB): create DFLT + latn so the calt feature applies
            from fontTools.ttLib.tables.otTables import DefaultLangSys, Script, ScriptRecord
            for script_tag in ("DFLT", "latn"):
                srec = ScriptRecord()
                srec.ScriptTag = script_tag
                srec.Script = Script()
                srec.Script.DefaultLangSys = DefaultLangSys()
                srec.Script.DefaultLangSys.ReqFeatureIndex = 0xFFFF
                srec.Script.DefaultLangSys.FeatureIndex = [calt_rec_idx]
                srec.Script.LangSysRecord = []
                gsub.ScriptList.ScriptRecord.append(srec)

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


def _separate_primary_and_optional_faces(all_faces: list[SourceFace], files_dir: Path) -> tuple[list[SourceFace], list[SourceFace], list[SourceFace], list[SourceFace]]:
    sans_faces: list[SourceFace] = []
    mono_faces: list[SourceFace] = []
    serif_faces: list[SourceFace] = []
    bengali_faces: list[SourceFace] = []

    for face in all_faces:
        fam = face.family.lower()
        sub = face.style_name.lower()
        if face.category == "mono" or any(m in fam or m in sub for m in ("mono", "code", "consolas", "courier")):
            mono_faces.append(face)
        elif face.category == "serif" or any(m in fam or m in sub for m in ("serif", "bookerly", "times", "georgia")):
            serif_faces.append(face)
        elif face.category == "bengali" or any(m in fam or m in sub for m in ("bengali", "beng")):
            bengali_faces.append(face)
        else:
            sans_faces.append(face)

    return (sans_faces or all_faces), _dedupe_static(mono_faces), _dedupe_static(serif_faces), _dedupe_static(bengali_faces)




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
    bengali_features: list[str] | str | None = None,
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
        source_entries: list[tuple[Path, str]] = []
        for path in sorted(fonts_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS:
                rel_parts = [part.lower() for part in path.relative_to(fonts_dir).parts[:-1]]
                if any(part in ("monospace", "mono") for part in rel_parts):
                    cat = "mono"
                elif any(part == "serif" for part in rel_parts):
                    cat = "serif"
                elif any(part in ("bengali", "beng") for part in rel_parts):
                    cat = "bengali"
                elif any(part in ("sans", "sans-serif") for part in rel_parts):
                    cat = "sans"
                else:
                    stem_lower = path.stem.lower()
                    if any(m in stem_lower for m in ("mono", "code", "consolas", "courier")):
                        cat = "mono"
                    elif "serif" in stem_lower and "sans" not in stem_lower:
                        cat = "serif"
                    elif any(m in stem_lower for m in ("bengali", "beng")):
                        cat = "bengali"
                    else:
                        cat = "sans"
                source_entries.append((path, cat))

        for path, cat in source_entries:
            sub_dir = temp_fonts_dir / cat
            sub_dir.mkdir(parents=True, exist_ok=True)
            _ensure_ttf(path, sub_dir)

        all_faces = discover_faces(temp_fonts_dir)
        faces, mono_faces, serif_faces, bengali_faces = _separate_primary_and_optional_faces(all_faces, files_dir)

        sans_ttf_paths = sorted({face.path for face in faces})
        mono_ttf_paths = sorted({face.path for face in mono_faces})
        serif_ttf_paths = sorted({face.path for face in serif_faces})
        bengali_ttf_paths = sorted({face.path for face in bengali_faces})

        applied_features: list[str] = []
        category_paths = (
            ("sans", sans_ttf_paths, "Sans-serif"),
            ("mono", mono_ttf_paths, "Monospace"),
            ("serif", serif_ttf_paths, "Serif"),
            ("bengali", bengali_ttf_paths, "Bengali"),
        )
        # Per-category centered colon decisions. None = unset (prompt in interactive mode);
        # a global --centered-colon/--no-centered-colon flag applies to every category.
        colon_choice = {key: centered_colon for key, _paths, _label in category_paths}
        should_prompt = interactive_features if interactive_features is not None else sys.stdin.isatty()

        if features is not None or mono_features is not None or serif_features is not None or bengali_features is not None:
            def parse_feat(val):
                if val is None:
                    return []
                if isinstance(val, str):
                    return [f.strip() for f in val.split(",") if f.strip()]
                return [f.strip() for f in val if f.strip()]

            sans_feats = parse_feat(features)
            mono_feats = parse_feat(mono_features) if mono_features is not None else sans_feats
            serif_feats = parse_feat(serif_features) if serif_features is not None else sans_feats
            beng_feats = parse_feat(bengali_features) if bengali_features is not None else sans_feats

            for p in sans_ttf_paths:
                freeze_font_features(p, sans_feats)
            for p in mono_ttf_paths:
                freeze_font_features(p, mono_feats)
            for p in serif_ttf_paths:
                freeze_font_features(p, serif_feats)
            for p in bengali_ttf_paths:
                freeze_font_features(p, beng_feats)

            applied_features.extend(list(dict.fromkeys(sans_feats + mono_feats + serif_feats + beng_feats)))
        elif should_prompt:
            for colon_key, colon_paths, colon_label in category_paths:
                if colon_choice[colon_key] is None and colon_paths:
                    colon_choice[colon_key] = prompt_add_centered_colon_if_missing(
                        colon_paths, interactive=should_prompt, category=colon_label
                    )

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

            if bengali_ttf_paths:
                avail_beng = extract_features_from_fonts(bengali_ttf_paths)
                if avail_beng:
                    feat_beng = prompt_feature_selection(avail_beng, category_name="Bengali")
                    if feat_beng:
                        for p in bengali_ttf_paths:
                            freeze_font_features(p, feat_beng)
                        applied_features.extend(feat_beng)

        for colon_key, colon_paths, _colon_label in category_paths:
            if colon_choice[colon_key] and colon_paths:
                for font_path in colon_paths:
                    inject_centered_colon(font_path)

        all_faces = discover_faces(temp_fonts_dir)
        faces, mono_faces, serif_faces, bengali_faces = _separate_primary_and_optional_faces(all_faces, files_dir)
        primary_faces = faces or bengali_faces or serif_faces or mono_faces
        if not primary_faces:
            raise SystemExit("No valid font faces were found in input subdirectories.")
        mode = detect_mode(primary_faces, requested_mode)
        families = {face.family for face in primary_faces}
        if len(families) > 1:
            raise SystemExit("Input files contain multiple font families: " + ", ".join(sorted(families)))
        family = next(iter(families))
        if prefix_family:
            family = transform_family_name(family)
        if mode == "static":
            selected, payload, mono_index = _compile_static(primary_faces if not faces else faces, files_dir, keep_hinting=keep_hinting, prefix_family=prefix_family, mono_faces=mono_faces if faces else [], serif_faces=serif_faces if faces else [], bengali_faces=bengali_faces if faces else [])
        else:
            selected, payload, mono_index = _compile_variable(primary_faces if not faces else faces, files_dir, keep_hinting=keep_hinting, prefix_family=prefix_family, mono_faces=mono_faces if faces else [], serif_faces=serif_faces if faces else [], bengali_faces=bengali_faces if faces else [])

        primary = payload[0]
        has_any_vf = (mode == "variable") or any(f.variable for f in mono_faces) or any(f.variable for f in serif_faces) or any(f.variable for f in bengali_faces)
        if has_any_vf:
            comp_vf_faces = [f for f in (faces or primary_faces) if f.variable] + [f for f in (mono_faces + serif_faces + bengali_faces) if f.variable]
            vf_id = _variable_config_identity(comp_vf_faces if comp_vf_faces else (faces or primary_faces))
        else:
            digest = hashlib.sha256()
            digest.update(family.encode("utf-8", errors="replace"))
            for f in sorted(payload):
                p = files_dir / f
                if p.is_file():
                    digest.update(f.encode("utf-8"))
                    digest.update(p.read_bytes())
            vf_id = "vf-" + digest.hexdigest()[:20]
        config = [
            f"FONT_MODE={shell_quote(mode)}",
            f"FONT_FAMILY={shell_quote(family)}",
            f"FONT_FILES={shell_quote(' '.join(payload))}",
            f"FONT_PRIMARY={shell_quote(primary)}",
            f"CLOCK_FONT={shell_quote('GoogleSansClock-Regular' + Path(primary).suffix)}",
            "VF_CONFIG_SCHEMA='2'",
            f"VF_CONFIG_ID={shell_quote(vf_id)}",
        ]
        if mono_index is not None:
            config.append(f"MONO_INDEX={shell_quote(str(mono_index))}")
        if mode == "variable":
            upright, italic = _pick_variable_faces(faces)
            config.extend(
                (
                    f"VF_UPRIGHT_AXIS_META={shell_quote(_axis_metadata(upright, italic=False))}",
                    f"VF_ITALIC_AXIS_META={shell_quote(_axis_metadata(italic, italic=True))}",
                    f"VF_UPRIGHT_WEIGHTS={shell_quote(_supported_weights(upright))}",
                    f"VF_ITALIC_WEIGHTS={shell_quote(_supported_weights(italic))}",
                )
            )
        if mono_faces and any(f.variable for f in mono_faces):
            mono_var = [f for f in mono_faces if f.variable]
            upright_mono = next((f for f in mono_var if f.style == "normal"), mono_var[0])
            if upright_mono.axes and "wght" in upright_mono.axes:
                config.extend(
                    (
                        f"VF_MONO_AXIS_META={shell_quote(_axis_metadata(upright_mono, italic=False))}",
                        f"VF_MONO_WEIGHTS={shell_quote(_supported_weights(upright_mono))}",
                    )
                )
        if serif_faces and any(f.variable for f in serif_faces):
            serif_var = [f for f in serif_faces if f.variable]
            upright_serif = next((f for f in serif_var if f.style == "normal"), serif_var[0])
            italic_serif = next((f for f in serif_var if f.style == "italic"), None)
            if upright_serif.axes and "wght" in upright_serif.axes:
                config.extend(
                    (
                        f"VF_SERIF_UPRIGHT_AXIS_META={shell_quote(_axis_metadata(upright_serif, italic=False))}",
                        f"VF_SERIF_UPRIGHT_WEIGHTS={shell_quote(_supported_weights(upright_serif))}",
                    )
                )
            if italic_serif and italic_serif.axes and "wght" in italic_serif.axes:
                config.extend(
                    (
                        f"VF_SERIF_ITALIC_AXIS_META={shell_quote(_axis_metadata(italic_serif, italic=True))}",
                        f"VF_SERIF_ITALIC_WEIGHTS={shell_quote(_supported_weights(italic_serif))}",
                    )
                )
        if bengali_faces and any(f.variable for f in bengali_faces):
            beng_var = [f for f in bengali_faces if f.variable]
            upright_beng = next((f for f in beng_var if f.style == "normal"), beng_var[0])
            if upright_beng.axes and "wght" in upright_beng.axes:
                config.extend(
                    (
                        f"VF_BENGALI_AXIS_META={shell_quote(_axis_metadata(upright_beng, italic=False))}",
                        f"VF_BENGALI_WEIGHTS={shell_quote(_supported_weights(upright_beng))}",
                    )
                )
        (module_dir / "font-config.sh").write_text("\n".join(config) + "\n", encoding="utf-8", newline="\n")
        family_faces = {
            "sans": tuple(faces),
            "mono": tuple(mono_faces),
            "serif": tuple(serif_faces),
            "bengali": tuple(bengali_faces),
        }
        return CompileResult(
            mode,
            family,
            tuple(selected),
            payload,
            tuple(applied_features),
            family_faces,
        )
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
    clean_name = clean_family_name(name or family)
    display = display_name_for_mode(clean_name, mode)
    if applied_features and not any(f"({f}" in display for f in applied_features):
        feat_str = ", ".join(applied_features)
        display = f"{display} ({feat_str})"
    now = dt.datetime.now().astimezone()
    version = version or now.strftime("%Y.%m.%d")
    version_code = version_code or now.strftime("%y%m%d")
    slug = slugify(display)
    props["id"] = f"mffm14_{slug.replace('-', '_')}"
    props["name"] = f"[MFFMv14] {display}"
    props["version"] = version
    props["versionCode"] = version_code
    props.setdefault("author", "MFFM")
    props["description"] = f"MFFMv14 font module: {display} ({mode})"
    props.setdefault("minMagisk", "20400")
    props.setdefault("minKernelSU", "10940")
    props.setdefault("minAPatch", "11000")
    write_props(path, props)
    return props
