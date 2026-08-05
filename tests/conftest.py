"""Synthetic font fixtures.

The repository intentionally keeps no font binaries in git (`.gitignore` excludes `*.ttf`), so the
tests build the fonts they need with fontTools instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GLYPHS = (".notdef", "space", "zero", "one", "colon")
CHARACTERS = {0x20: "space", 0x30: "zero", 0x31: "one", 0x3A: "colon"}


def _box(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, height))
    pen.lineTo((width - 50, height))
    pen.lineTo((width - 50, 0))
    pen.closePath()
    return pen.glyph()


def make_font(
    path: Path,
    *,
    family: str = "Test Sans",
    style: str = "Regular",
    weight: int = 400,
    italic: bool = False,
    units_per_em: int = 1000,
    axes: list[tuple[str, float, float, float]] | None = None,
) -> Path:
    builder = FontBuilder(units_per_em, isTTF=True)
    builder.setupGlyphOrder(list(GLYPHS))
    builder.setupCharacterMap(CHARACTERS)
    # The colon sits low (baseline-aligned) while the digits are full height, so
    # inject_centered_colon has a real offset to compute.
    outlines = {name: _box(600, 700) for name in GLYPHS}
    outlines["colon"] = _box(600, 300)
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics({name: (600, 50) for name in GLYPHS})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(
        {
            "familyName": family,
            "styleName": style,
            "fullName": f"{family} {style}",
            "psName": f"{family}-{style}".replace(" ", ""),
            "version": "1.000",
        }
    )
    builder.setupOS2(usWeightClass=weight, sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=0)
    builder.setupPost()
    if axes:
        builder.setupFvar(
            axes=[(tag, minimum, default, maximum, tag) for tag, minimum, default, maximum in axes],
            instances=[],
        )
        builder.setupGvar({})
    builder.font["head"].macStyle = (2 if italic else 0) | (1 if weight >= 700 else 0)
    if italic:
        builder.font["post"].italicAngle = -12.0

    path.parent.mkdir(parents=True, exist_ok=True)
    builder.save(str(path))
    return path


@pytest.fixture
def font_factory(tmp_path: Path):
    def factory(relative: str, **kwargs) -> Path:
        return make_font(tmp_path / relative, **kwargs)

    return factory
