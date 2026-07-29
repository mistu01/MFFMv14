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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

Mode = Literal["static", "variable"]
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2"}
GENERATED_FILES = {
    "DroidSans.ttf", "DroidSans.otf", "DroidSans.ttc",
    "DroidSans-Italic.ttf", "DroidSans-Italic.otf", "DroidSans-Bold.ttf",
    "sans.xml", "condensed.xml", "serif.xml", "clock.xml",
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
    (r"light", 300),
    (r"regular|normal|book|roman", 400),
    (r"medium", 500),
    (r"bold", 700),
    (r"black|heavy", 900),
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


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-") or "font"


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


def _inspect_font(path: Path, font_number: int | None) -> SourceFace:
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
        named_weight = _weight_from_label(metadata_label) or _weight_from_label(path.stem)
        weight = named_weight or _nearest_weight(int(getattr(os2, "usWeightClass", 400)) if os2 is not None else 400)

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
        )


def discover_faces(fonts_dir: Path) -> list[SourceFace]:
    TTCollection, _font = require_fonttools()
    if not fonts_dir.is_dir():
        raise SystemExit(f"Font input directory does not exist: {fonts_dir}")
    paths = sorted(path for path in fonts_dir.iterdir() if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS)
    if not paths:
        raise SystemExit(f"No TTF, OTF, TTC, or OTC fonts found in {fonts_dir}")

    faces: list[SourceFace] = []
    for path in paths:
        try:
            collection = TTCollection(str(path), lazy=True)
        except Exception as exc:
            if exc.__class__.__name__ != "TTLibFileIsCollectionError" and path.suffix.lower() in {".ttc", ".otc"}:
                raise SystemExit(f"Could not read collection {path}: {exc}") from exc
            faces.append(_inspect_font(path, None))
        else:
            try:
                count = len(collection.fonts)
            finally:
                collection.close()
            faces.extend(_inspect_font(path, index) for index in range(count))
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


def _prefix_metadata(font, prefix: str) -> None:
    family = _name(font, 16, 1) or "Font"
    if family.lower().startswith(prefix.strip().lower()):
        return
    new_family = f"{prefix}{family}".strip()
    style = _name(font, 17, 2) or "Regular"
    full_name = f"{new_family} {style}".strip()
    postscript = re.sub(r"[^A-Za-z0-9-]", "", f"{new_family.replace(' ', '')}-{style.replace(' ', '')}")[:63]
    for name_id in (1, 16):
        _set_name(font, name_id, new_family)
    _set_name(font, 4, full_name)
    _set_name(font, 6, postscript)


def _process_font(font, *, keep_hinting: bool, prefix_family: bool) -> None:
    if not keep_hinting:
        _remove_hinting(font)
    _fix_metrics(font)
    if prefix_family:
        _prefix_metadata(font, "MFFM ")


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


def _static_sort(face: SourceFace) -> tuple[int, int, int, str, int]:
    return (int(face.condensed), int(face.style == "italic"), face.weight, face.path.name.lower(), face.font_number or 0)


def _dedupe_static(faces: list[SourceFace]) -> list[SourceFace]:
    found: dict[tuple[int, str, bool], SourceFace] = {}
    for face in sorted(faces, key=_static_sort):
        key = (face.weight, face.style, face.condensed)
        if key in found:
            raise SystemExit(f"Duplicate static face for {key}: {found[key].label} and {face.label}")
        found[key] = face
    return sorted(found.values(), key=_static_sort)


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


def _write_fragments(files_dir: Path, normal: list[tuple[int, str, str]], condensed: list[tuple[int, str, str]], clock: str) -> None:
    normal_xml = "\n".join(xml for _weight, _style, xml in normal)
    condensed_xml = "\n".join(xml for _weight, _style, xml in (condensed or normal))
    (files_dir / "sans.xml").write_text(normal_xml + "\n", encoding="utf-8", newline="\n")
    (files_dir / "condensed.xml").write_text(condensed_xml + "\n", encoding="utf-8", newline="\n")
    (files_dir / "serif.xml").write_text(_serif_fragment(normal) + "\n", encoding="utf-8", newline="\n")
    (files_dir / "clock.xml").write_text(clock + "\n", encoding="utf-8", newline="\n")


def _compile_static(faces: list[SourceFace], files_dir: Path, *, keep_hinting: bool, prefix_family: bool) -> tuple[list[SourceFace], tuple[str, ...]]:
    TTCollection, _font = require_fonttools()
    ordered = _dedupe_static(faces)

    if len(ordered) == 1:
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
        clock = _font_xml("GoogleSansClock-Regular.ttf", face.weight, face.style)
        _write_fragments(files_dir, entries, [], clock)
        return ordered, (output_name,)

    fonts = []
    try:
        for face in ordered:
            font = _open_font(face)
            _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
            fonts.append(font)
        output_name = "DroidSans.ttf"
        collection = TTCollection()
        collection.fonts = fonts
        collection.save(str(files_dir / output_name))
    finally:
        for font in fonts:
            font.close()

    normal: list[tuple[int, str, str]] = []
    condensed: list[tuple[int, str, str]] = []
    for index, face in enumerate(ordered):
        xml = _font_xml(output_name, face.weight, face.style, index=index)
        (condensed if face.condensed else normal).append((face.weight, face.style, xml))
    if not normal:
        normal = list(condensed)

    regular_index = min(
        range(len(ordered)),
        key=lambda index: (ordered[index].style != "normal", abs(ordered[index].weight - 400), ordered[index].condensed),
    )
    clock = _font_xml("GoogleSansClock-Regular.ttf", 400, "normal", index=regular_index)
    _write_fragments(files_dir, normal, condensed, clock)
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


def _compile_variable(faces: list[SourceFace], files_dir: Path, *, keep_hinting: bool, prefix_family: bool) -> tuple[list[SourceFace], tuple[str, ...]]:
    upright, italic = _pick_variable_faces(faces)
    upright_name = f"DroidSans{_variable_extension(upright)}"
    italic_name = upright_name
    _save_face(upright, files_dir / upright_name, keep_hinting=keep_hinting, prefix_family=prefix_family)
    payload = [upright_name]

    if italic != upright:
        italic_name = "DroidSans-Bold.ttf"
        _save_face(italic, files_dir / italic_name, keep_hinting=keep_hinting, prefix_family=prefix_family)
        payload.append(italic_name)

    entries: list[tuple[int, str, str]] = []
    for style, face, filename in (("normal", upright, upright_name), ("italic", italic, italic_name)):
        for weight in WEIGHT_NAMES:
            axes = _axis_values(face, weight, style == "italic")
            if axes is not None:
                entries.append((weight, style, _font_xml(filename, weight, style, axes=axes)))
    entries.sort(key=lambda item: (item[1] == "italic", item[0]))
    if not entries:
        raise SystemExit("The variable font has no usable wght axis values between 100 and 900")

    clock_axes = _axis_values(upright, 400, False)
    if clock_axes is None:
        closest = min(WEIGHT_NAMES, key=lambda weight: abs(weight - upright.axes["wght"][1]))
        clock_axes = _axis_values(upright, closest, False)
    clock_name = "GoogleSansClock-Regular" + _variable_extension(upright)
    clock = _font_xml(clock_name, 400, "normal", axes=clock_axes)
    _write_fragments(files_dir, entries, [], clock)
    return [upright] + ([italic] if italic != upright else []), tuple(payload)


def extract_opentype_features(font_path: Path) -> dict[str, str]:
    """Inspect GSUB table to discover Stylistic Sets (ss01-ss20) and Character Variants (cv01-cv99)."""
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
            if tag and (tag.startswith("ss") or tag.startswith("cv")):
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
                features[tag] = ui_name
    finally:
        font.close()

    return features


def extract_features_from_fonts(font_paths: Iterable[Path]) -> dict[str, str]:
    """Extract all available Stylistic Sets and Character Variants from multiple font files."""
    aggregated: dict[str, str] = {}
    for path in font_paths:
        feats = extract_opentype_features(path)
        for tag, name in feats.items():
            if tag not in aggregated or (not aggregated[tag] and name):
                aggregated[tag] = name
    return dict(sorted(aggregated.items()))


def prompt_feature_selection(available_features: dict[str, str]) -> list[str]:
    """Prompt user interactively to select Stylistic Sets or Character Variants to freeze."""
    if not available_features:
        print("\nNo OpenType Stylistic Sets or Character Variants detected in input font(s).")
        return []

    print("\n------------------------------------------------------------")
    print("OpenType Feature Freezer Tool Integration")
    print("------------------------------------------------------------")
    choice = input("Do you want to use any Stylistic Sets (for example ss01 Open digits), or Character Variants (for example cv01 Alternate One)? (y/N): ").strip().lower()
    if choice not in ("y", "yes"):
        print("Skipping feature freezing.")
        return []

    print("\nAvailable Stylistic Sets and Character Variants:")
    for tag, name in sorted(available_features.items()):
        label = f"  {tag}  -  {name}" if name else f"  {tag}"
        print(label)

    print("\n[Visual Preview]")
    print("For visual representation of available sets, visit:")
    print("https://www.adamjagosz.com/bulletproof/lettering and upload your font.")
    print("------------------------------------------------------------\n")

    user_entries = input("Enter your desired entries (comma or space separated, e.g. ss01, cv01): ").strip()
    if not user_entries:
        print("No features entered. Proceeding without feature freezing.")
        return []

    raw_tags = re.split(r"[,\s]+", user_entries)
    selected = [t.lower() for t in raw_tags if t.strip()]
    if selected:
        print(f"Selected features to freeze: {', '.join(selected)}")
    return selected


def freeze_font_features(font_path: Path, features: list[str] | str) -> None:
    """Freeze OpenType features into a font file using pyftfeatfreeze / opentype-feature-freezer."""
    if isinstance(features, str):
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
    else:
        feature_list = [f.strip() for f in features if f.strip()]

    if not feature_list:
        return

    feat_str = ",".join(feature_list)
    executable = shutil.which("pyftfeatfreeze") or "pyftfeatfreeze"
    temp_output = font_path.with_suffix(".frozen" + font_path.suffix)

    cmd = [executable, "-f", feat_str, str(font_path), str(temp_output)]
    log.info(f"Freezing features '{feat_str}' in {font_path.name}...")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if temp_output.exists():
            shutil.move(temp_output, font_path)
            print(f"Successfully froze features [{feat_str}] in {font_path.name}")
        else:
            log.warning(f"Feature freezer completed but output file missing for {font_path.name}")
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


def compile_fonts(
    fonts_dir: Path,
    module_dir: Path,
    *,
    requested_mode: str = "auto",
    keep_hinting: bool = False,
    prefix_family: bool = True,
    features: list[str] | str | None = None,
    interactive_features: bool | None = None,
) -> CompileResult:
    files_dir = module_dir / "Files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_FILES:
        (files_dir / name).unlink(missing_ok=True)

    temp_fonts_dir = module_dir / ".temp_ttf_fonts"
    if temp_fonts_dir.exists():
        shutil.rmtree(temp_fonts_dir, ignore_errors=True)
    temp_fonts_dir.mkdir(parents=True, exist_ok=True)

    try:
        for path in fonts_dir.iterdir():
            if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS:
                _ensure_ttf(path, temp_fonts_dir)

        temp_ttf_paths = sorted(p for p in temp_fonts_dir.iterdir() if p.is_file() and p.suffix.lower() in FONT_EXTENSIONS)
        selected_features: list[str] = []

        if features is not None:
            if isinstance(features, str):
                selected_features = [f.strip() for f in features.split(",") if f.strip()]
            else:
                selected_features = [f.strip() for f in features if f.strip()]
        else:
            should_prompt = interactive_features if interactive_features is not None else sys.stdin.isatty()
            if should_prompt:
                available = extract_features_from_fonts(temp_ttf_paths)
                selected_features = prompt_feature_selection(available)

        if selected_features:
            for font_path in temp_ttf_paths:
                freeze_font_features(font_path, selected_features)

        faces = discover_faces(temp_fonts_dir)
        mode = detect_mode(faces, requested_mode)
        families = {face.family for face in faces}
        if len(families) > 1:
            raise SystemExit("Input files contain multiple font families: " + ", ".join(sorted(families)))
        family = next(iter(families))
        if mode == "static":
            selected, payload = _compile_static(faces, files_dir, keep_hinting=keep_hinting, prefix_family=prefix_family)
        else:
            selected, payload = _compile_variable(faces, files_dir, keep_hinting=keep_hinting, prefix_family=prefix_family)

        primary = payload[0]
        config = [
            f"FONT_MODE={shell_quote(mode)}",
            f"FONT_FAMILY={shell_quote(family)}",
            f"FONT_FILES={shell_quote(' '.join(payload))}",
            f"FONT_PRIMARY={shell_quote(primary)}",
            f"CLOCK_FONT={shell_quote('GoogleSansClock-Regular' + Path(primary).suffix)}",
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
        return CompileResult(mode, family, tuple(selected), payload, tuple(selected_features))
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
