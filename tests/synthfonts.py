"""Minimal synthetic TTF builder for tests and CI fixture generation.

The generated fonts are structurally valid but contain only a handful of box
glyphs — enough for discovery, weight detection, TTC packing and module
compilation to run against them without shipping binary fixtures.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._f_v_a_r import Axis


def build_synthetic_font(
    path: Path,
    *,
    family: str = "TestFont",
    style_name: str = "Regular",
    us_weight_class: int = 400,
    us_width_class: int = 5,
    italic: bool = False,
    wght_axis: tuple[float, float, float] | None = None,
) -> Path:
    """Write a small TTF with the requested OS/2 and name-table metadata."""
    glyph_order = [".notdef", "space", "a", "b", "colon"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x20: "space", 0x61: "a", 0x62: "b", 0x3A: "colon"})
    glyphs = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0))
        pen.lineTo((50, 650))
        pen.lineTo((450, 650))
        pen.lineTo((450, 0))
        pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({name: (500, 50) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": style_name})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200,
        usWeightClass=us_weight_class, usWidthClass=us_width_class,
    )
    fb.setupMaxp()
    fb.setupPost()
    fb.save(path)

    if not italic and wght_axis is None:
        return path

    font = TTFont(path)
    if italic:
        font["OS/2"].fsSelection = (int(font["OS/2"].fsSelection) & ~0x40) | 0x01
        font["head"].macStyle = int(font["head"].macStyle) | 0x02
    if wght_axis is not None:
        axis = Axis()
        axis.axisTag = "wght"
        axis.minValue, axis.defaultValue, axis.maxValue = wght_axis
        axis.flags = 0
        axis.axisNameID = 256
        font["name"].setName("Weight", 256, 3, 1, 0x409)
        fvar = newTable("fvar")
        fvar.axes = [axis]
        font["fvar"] = fvar
    font.save(path)
    return path


def build_synthetic_otf_font(
    path: Path,
    *,
    family: str = "TestOTFFont",
    style_name: str = "Regular",
    us_weight_class: int = 400,
    us_width_class: int = 5,
    italic: bool = False,
) -> Path:
    """Write a small OTF (CFF) with requested metadata."""
    from fontTools.pens.t2CharStringPen import T2CharStringPen

    glyph_order = [".notdef", "space", "a", "b", "colon", "zero", "one", "two"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x20: "space", 0x61: "a", 0x62: "b", 0x3A: "colon", 0x30: "zero", 0x31: "one", 0x32: "two"})
    charstrings = {}
    for name in glyph_order:
        pen = T2CharStringPen(500, None)
        pen.moveTo((50, 0))
        pen.lineTo((50, 650))
        pen.lineTo((450, 650))
        pen.lineTo((450, 0))
        pen.closePath()
        charstrings[name] = pen.getCharString()
    fb.setupCFF(f"{family}-{style_name}", {"FamilyName": family}, charstrings, {})
    fb.setupHorizontalMetrics({name: (500, 50) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": style_name})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200,
        usWeightClass=us_weight_class, usWidthClass=us_width_class,
    )
    fb.setupMaxp()
    fb.setupPost()
    fb.save(path)

    if italic:
        font = TTFont(path)
        font["OS/2"].fsSelection = (int(font["OS/2"].fsSelection) & ~0x40) | 0x01
        font["head"].macStyle = int(font["head"].macStyle) | 0x02
        font.save(path)

    return path


def build_synthetic_digit_font(
    path: Path,
    *,
    family: str = "DigitFont",
    style_name: str = "Regular",
    us_weight_class: int = 400,
    cap_height: int = 700,
    x_height: int = 500,
) -> Path:
    """Write a TTF with proportional digits (e.g. 1 is narrower than other digits) and a colon."""
    glyph_order = [".notdef", "space", "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "colon"]
    glyph_order = list(dict.fromkeys(glyph_order))
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    cmap = {
        0x20: "space",
        0x30: "zero", 0x31: "one", 0x32: "two", 0x33: "three", 0x34: "four",
        0x35: "five", 0x36: "six", 0x37: "seven", 0x38: "eight", 0x39: "nine",
        0x3A: "colon",
    }
    fb.setupCharacterMap(cmap)
    glyphs = {}
    hmetrics = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        if name == "one":
            pen.moveTo((50, 0)); pen.lineTo((50, 700)); pen.lineTo((250, 700)); pen.lineTo((250, 0)); pen.closePath()
            hmetrics[name] = (350, 50)
        elif name in ("zero", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
            pen.moveTo((50, 0)); pen.lineTo((50, 700)); pen.lineTo((550, 700)); pen.lineTo((550, 0)); pen.closePath()
            hmetrics[name] = (600, 50)
        elif name == "colon":
            pen.moveTo((100, 50)); pen.lineTo((100, 150)); pen.lineTo((200, 150)); pen.lineTo((200, 50)); pen.closePath()
            pen.moveTo((100, 250)); pen.lineTo((100, 350)); pen.lineTo((200, 350)); pen.lineTo((200, 250)); pen.closePath()
            hmetrics[name] = (300, 100)
        else:
            pen.moveTo((0, 0)); pen.lineTo((0, 500)); pen.lineTo((250, 500)); pen.lineTo((250, 0)); pen.closePath()
            hmetrics[name] = (250, 0)
        glyphs[name] = pen.glyph()

    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(hmetrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": style_name})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200,
        sCapHeight=cap_height, sxHeight=x_height,
        usWeightClass=us_weight_class, usWidthClass=5,
    )
    fb.setupMaxp()
    fb.setupPost()
    fb.save(path)
    return path


def build_synthetic_tall_accent_font(
    path: Path,
    *,
    family: str = "TallFont",
    style_name: str = "Regular",
    tall_y_max: int = 1250,
    deep_y_min: int = -350,
) -> Path:
    """Write a TTF with glyphs exceeding standard FFIX3 ascent/descent on 1000 UPM."""
    glyph_order = [".notdef", "space", "A", "Aacute"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    cmap = {
        0x20: "space",
        0x41: "A",
        0xC1: "Aacute",
    }
    fb.setupCharacterMap(cmap)
    glyphs = {}
    hmetrics = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        if name == "A":
            pen.moveTo((50, 0)); pen.lineTo((50, 700)); pen.lineTo((450, 700)); pen.lineTo((450, 0)); pen.closePath()
            hmetrics[name] = (500, 50)
        elif name == "Aacute":
            pen.moveTo((50, deep_y_min)); pen.lineTo((50, tall_y_max)); pen.lineTo((450, tall_y_max)); pen.lineTo((450, deep_y_min)); pen.closePath()
            hmetrics[name] = (500, 50)
        else:
            pen.moveTo((0, 0)); pen.lineTo((0, 500)); pen.lineTo((250, 500)); pen.lineTo((250, 0)); pen.closePath()
            hmetrics[name] = (250, 0)
        glyphs[name] = pen.glyph()

    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(hmetrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": style_name})
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200,
        sCapHeight=700, sxHeight=500,
        usWeightClass=400, usWidthClass=5,
    )
    fb.setupMaxp()
    fb.setupPost()
    fb.save(path)
    return path



