#!/usr/bin/env python3
"""Shared compiler core for the unified MFFM static/variable template."""

from __future__ import annotations

import datetime as dt
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal


Mode = Literal["static", "variable"]
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}
GENERATED_FILES = {
    "DroidSans.ttf",
    "DroidSans.otf",
    "DroidSans.ttc",
    "DroidSans-Italic.ttf",
    "DroidSans-Italic.otf",
    "sans.xml",
    "condensed.xml",
    "serif.xml",
    "clock.xml",
}
WEIGHT_NAMES = {
    100: "Thin",
    200: "ExtraLight",
    300: "Light",
    400: "Regular",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
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
    """Strip legacy per-face style suffixes from a family name."""
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
            "italic" in label
            or "oblique" in label
            or (os2 is not None and int(getattr(os2, "fsSelection", 0)) & 1)
            or (head is not None and int(getattr(head, "macStyle", 0)) & 2)
        )
        width_class = int(getattr(os2, "usWidthClass", 5)) if os2 is not None else 5
        condensed = width_class <= 4 or "condensed" in label or "narrow" in label
        # Collection filenames are often generic (for example
        # RobotoStatic-Regular.ttf), so metadata must win over the path.
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
    paths = sorted(
        path for path in fonts_dir.iterdir()
        if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS
    )
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
    raise SystemExit(
        "Mixed static and variable inputs are ambiguous. Keep one font model in Fonts/ "
        "or pass --mode after removing the other files."
    )


def _remove_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            # fontTools expects a Program object while compiling. Its helper
            # clears bytecode safely for both simple and composite glyphs.
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()


def _fix_metrics(font) -> None:
    os2 = font.get("OS/2")
    hhea = font.get("hhea")
    if os2 is None or hhea is None:
        return
    ascenders = [int(getattr(hhea, "ascent", 0)), int(getattr(os2, "sTypoAscender", 0)), int(getattr(os2, "usWinAscent", 0))]
    descenders = [int(getattr(hhea, "descent", 0)), int(getattr(os2, "sTypoDescender", 0)), -int(getattr(os2, "usWinDescent", 0))]
    ascent = max(ascenders)
    descent = min(descenders)
    if ascent > 0 and descent < 0:
        hhea.ascent = os2.sTypoAscender = ascent
        hhea.descent = os2.sTypoDescender = descent
        hhea.lineGap = os2.sTypoLineGap = 0
        os2.usWinAscent = max(int(getattr(os2, "usWinAscent", 0)), ascent)
        os2.usWinDescent = max(int(getattr(os2, "usWinDescent", 0)), abs(descent))
        os2.fsSelection = int(getattr(os2, "fsSelection", 0)) | (1 << 7)


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

    # A single static face does not need a collection wrapper. Keep the
    # canonical Android payload name and describe its real weight/style
    # directly in XML (for example Bold.ttf -> 700 normal).
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
        clock = _font_xml(
            "GoogleSansClock-Regular.ttf",
            face.weight,
            face.style,
        )
        _write_fragments(files_dir, entries, [], clock)
        return ordered, (output_name,)

    fonts = []
    try:
        for face in ordered:
            font = _open_font(face)
            _process_font(font, keep_hinting=keep_hinting, prefix_family=prefix_family)
            fonts.append(font)
        output_name = "DroidSans.ttc"
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
    regular_index = min(range(len(ordered)), key=lambda index: (ordered[index].style != "normal", abs(ordered[index].weight - 400), ordered[index].condensed))
    clock = _font_xml("GoogleSansClock-Regular.ttc", 400, "normal", index=regular_index)
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
        italic_name = f"DroidSans-Italic{_variable_extension(italic)}"
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


def compile_fonts(
    fonts_dir: Path,
    module_dir: Path,
    *,
    requested_mode: str = "auto",
    keep_hinting: bool = False,
    prefix_family: bool = True,
) -> CompileResult:
    files_dir = module_dir / "Files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_FILES:
        (files_dir / name).unlink(missing_ok=True)

    faces = discover_faces(fonts_dir)
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
        "# Generated by build.py/update.py. Do not edit by hand.",
        f"FONT_MODE={shell_quote(mode)}",
        f"FONT_FAMILY={shell_quote(family)}",
        f"FONT_FILES={shell_quote(' '.join(payload))}",
        f"FONT_PRIMARY={shell_quote(primary)}",
        f"CLOCK_FONT={shell_quote('GoogleSansClock-Regular' + Path(primary).suffix)}",
    ]
    (module_dir / "font-config.sh").write_text("\n".join(config) + "\n", encoding="utf-8", newline="\n")
    return CompileResult(mode, family, tuple(selected), payload)


def update_module_metadata(module_dir: Path, family: str, mode: Mode, *, name: str | None = None, version: str | None = None, version_code: str | None = None) -> dict[str, str]:
    path = module_dir / "module.prop"
    props = read_props(path)
    display = name or clean_family_name(family)
    now = dt.datetime.now().astimezone()
    version = version or now.strftime("%Y.%m.%d")
    version_code = version_code or now.strftime("%Y%m%d%H%M")
    props.setdefault("id", "mffm-unified")
    props["name"] = f"[MFFM] {display}"
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
