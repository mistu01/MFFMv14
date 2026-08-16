"""Weight detection tests driven by the shared weight_vectors.json table."""

import json
from pathlib import Path

import pytest
from fontTools.ttLib import TTCollection, TTFont

from font_module import discover_faces
from synthfonts import build_synthetic_font

VECTORS = json.loads((Path(__file__).parent / "weight_vectors.json").read_text(encoding="utf-8"))
PYTHON_CASES = VECTORS["python_cases"]


@pytest.mark.parametrize("case", PYTHON_CASES, ids=[case["name"] for case in PYTHON_CASES])
def test_python_weight_resolution(case, tmp_path):
    fonts_root = tmp_path / "Fonts"
    fonts_dir = fonts_root / case.get("dir", "Sans")
    fonts_dir.mkdir(parents=True)
    build_synthetic_font(
        fonts_dir / case["filename"],
        family=case.get("family", "TestFont"),
        style_name=case.get("style_name", "Regular"),
        us_weight_class=case.get("us_weight_class", 400),
        us_width_class=case.get("us_width_class", 5),
        italic=case.get("italic", False),
        wght_axis=tuple(case["wght_axis"]) if case.get("wght_axis") else None,
    )

    faces = discover_faces(fonts_root)
    assert len(faces) == 1
    face = faces[0]
    assert face.weight == case["expected_weight"]
    assert face.style == case["expected_style"]
    assert face.condensed is case.get("expected_condensed", False)
    assert face.variable is case.get("expected_variable", False)
    if "expected_category" in case:
        assert face.category == case["expected_category"]


def test_ttc_collection_yields_indexed_faces(tmp_path):
    fonts_dir = tmp_path / "Fonts" / "Sans"
    fonts_dir.mkdir(parents=True)
    regular = build_synthetic_font(
        fonts_dir / "pair-Regular.ttf", family="Pair", style_name="Regular", us_weight_class=400
    )
    bold = build_synthetic_font(
        fonts_dir / "pair-Bold.ttf", family="Pair", style_name="Bold", us_weight_class=700
    )
    collection = TTCollection()
    collection.fonts = [TTFont(str(regular)), TTFont(str(bold))]
    collection.save(str(fonts_dir / "Pair.ttc"))
    regular.unlink()
    bold.unlink()

    faces = discover_faces(tmp_path / "Fonts")
    assert sorted(face.weight for face in faces) == [400, 700]
    assert all(face.font_number is not None for face in faces)
