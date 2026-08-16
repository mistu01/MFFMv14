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
