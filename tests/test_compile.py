"""End-to-end tests for compile_fonts and the update.py migration path.

These cover the regressions that unit tests cannot see: how many faces end up in the collection and
which TTC index each generated XML fragment points at.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fontTools.ttLib import TTCollection

import font_module as fm
import update
from conftest import make_font


def collection_size(files_dir: Path) -> int:
    with TTCollection(str(files_dir / "DroidSans.ttf")) as collection:
        return len(collection.fonts)


def indices(files_dir: Path, fragment: str) -> list[int]:
    path = files_dir / fragment
    if not path.is_file():
        return []
    return [int(value) for value in re.findall(r'index="(\d+)"', path.read_text(encoding="utf-8"))]


@pytest.fixture
def files_dir(tmp_path: Path) -> Path:
    module = tmp_path / "module"
    (module / "Files").mkdir(parents=True)
    return module / "Files"


def compile_static(fonts_dir: Path, files_dir: Path) -> fm.CompileResult:
    return fm.compile_fonts(
        fonts_dir,
        files_dir.parent,
        requested_mode="static",
        keep_hinting=False,
        prefix_family=False,
        interactive_features=False,
        centered_colon=False,
    )


def test_static_build_indexes_each_family(tmp_path: Path, files_dir: Path) -> None:
    fonts = tmp_path / "Fonts"
    make_font(fonts / "Test-Regular.ttf", family="Test Sans")
    make_font(fonts / "Test-Bold.ttf", family="Test Sans", style="Bold", weight=700)
    make_font(fonts / "Monospace/Test-Regular.ttf", family="Test Mono")
    make_font(fonts / "Serif/Test-Regular.ttf", family="Test Serif")

    result = compile_static(fonts, files_dir)

    assert result.mode == "static"
    assert collection_size(files_dir) == 4
    assert indices(files_dir, "sans.xml") == [0, 1]
    assert indices(files_dir, "mono.xml") == [2]
    assert indices(files_dir, "serif.xml") == [3]


@pytest.mark.parametrize(("directory", "fragment"), [("Monospace", "mono.xml"), ("Serif", "serif.xml")])
def test_single_category_input_is_embedded_once(tmp_path: Path, files_dir: Path, directory: str, fragment: str) -> None:
    """Without a sans source the mono/serif faces are also the primary family, not a second copy."""
    fonts = tmp_path / "Fonts"
    make_font(fonts / directory / "Test-Regular.ttf", family="Test Family")
    make_font(fonts / directory / "Test-Bold.ttf", family="Test Family", style="Bold", weight=700)

    compile_static(fonts, files_dir)

    assert collection_size(files_dir) == 2
    assert indices(files_dir, "sans.xml") == [0, 1]
    assert indices(files_dir, fragment) == [0, 1]


def test_variable_build_emits_axis_config(tmp_path: Path, files_dir: Path) -> None:
    fonts = tmp_path / "Fonts"
    make_font(
        fonts / "Test-VF.ttf",
        family="Test Sans",
        axes=[("wght", 300.0, 400.0, 800.0), ("opsz", 8.0, 14.0, 60.0)],
    )

    result = fm.compile_fonts(
        fonts, files_dir.parent, requested_mode="variable",
        keep_hinting=False, prefix_family=False, interactive_features=False, centered_colon=False,
    )

    assert result.mode == "variable"
    config = (files_dir.parent / "font-config.sh").read_text(encoding="utf-8")
    assert "VF_UPRIGHT_WEIGHTS='300 400 500 600 700 800'" in config
    assert "opsz|8|14|60" in config
    assert "MONO_INDEX" not in config


def test_variable_font_without_wght_is_rejected_clearly(tmp_path: Path, files_dir: Path) -> None:
    fonts = tmp_path / "Fonts"
    make_font(fonts / "Test-VF.ttf", family="Test Sans", axes=[("opsz", 8.0, 14.0, 60.0)])

    with pytest.raises(SystemExit, match="wght"):
        fm.compile_fonts(
            fonts, files_dir.parent, requested_mode="variable",
            keep_hinting=False, prefix_family=False, interactive_features=False, centered_colon=False,
        )


def test_migration_restores_the_family_split(tmp_path: Path, files_dir: Path) -> None:
    """A v14 module bundles every family in one collection; migrating must not flatten it to sans."""
    fonts = tmp_path / "Fonts"
    make_font(fonts / "Test-Regular.ttf", family="Test Sans")
    make_font(fonts / "Monospace/Test-Regular.ttf", family="Test Mono")
    make_font(fonts / "Serif/Test-Regular.ttf", family="Test Serif")
    compile_static(fonts, files_dir)

    sources = tmp_path / "sources"
    sources.mkdir()
    assert update.split_collection(files_dir / "DroidSans.ttf", files_dir.parent, sources) is True
    assert sorted(path.parent.name for path in sources.rglob("*.ttf")) == ["Monospace", "Sans", "Serif"]

    migrated = tmp_path / "migrated"
    (migrated / "Files").mkdir(parents=True)
    compile_static(sources, migrated / "Files")
    assert indices(migrated / "Files", "sans.xml") == [0]
    assert indices(migrated / "Files", "mono.xml") == [1]
    assert indices(migrated / "Files", "serif.xml") == [2]


def test_migration_leaves_single_face_payloads_alone(tmp_path: Path, files_dir: Path) -> None:
    fonts = tmp_path / "Fonts"
    make_font(fonts / "Test-Regular.ttf", family="Test Sans")
    compile_static(fonts, files_dir)

    sources = tmp_path / "sources"
    sources.mkdir()
    assert update.split_collection(files_dir / "DroidSans.ttf", files_dir.parent, sources) is False
    assert list(sources.iterdir()) == []


def test_centered_colon_injection_creates_a_missing_gsub(tmp_path: Path) -> None:
    path = make_font(tmp_path / "NoGsub.ttf", family="Test Sans")
    from fontTools.ttLib import TTFont

    with TTFont(str(path)) as font:
        assert "GSUB" not in font

    assert fm.inject_centered_colon(path) is True

    with TTFont(str(path)) as font:
        gsub = font["GSUB"].table
        assert [record.ScriptTag for record in gsub.ScriptList.ScriptRecord] == ["DFLT"]
        features = {record.FeatureTag for record in gsub.FeatureList.FeatureRecord}
        assert "calt" in features
    assert fm.font_has_centered_colon(path) is True
