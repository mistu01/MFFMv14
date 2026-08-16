"""End-to-end compilation tests with synthetic fonts."""

from pathlib import Path

import pytest
from fontTools.ttLib import TTCollection

from font_module import (
    compile_fonts,
    copy_template,
    inspect_fonts,
    read_props,
    transform_family_name,
    update_module_metadata,
)
from synthfonts import build_synthetic_font

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template"


def build_static_workspace(root: Path) -> Path:
    fonts = root / "Fonts"
    sans = fonts / "Sans"
    sans.mkdir(parents=True)
    build_synthetic_font(sans / "Regular.ttf", family="Fixture Sans", style_name="Regular", us_weight_class=400)
    build_synthetic_font(sans / "Bold.ttf", family="Fixture Sans", style_name="Bold", us_weight_class=700)
    return fonts


def build_variable_workspace(root: Path) -> Path:
    fonts = root / "Fonts"
    sans = fonts / "Sans"
    sans.mkdir(parents=True)
    build_synthetic_font(
        sans / "Var-Roman.ttf", family="Fixture Var", style_name="Regular",
        us_weight_class=400, wght_axis=(100, 400, 900),
    )
    build_synthetic_font(
        sans / "Var-Italic.ttf", family="Fixture Var", style_name="Italic",
        us_weight_class=400, italic=True, wght_axis=(100, 400, 900),
    )
    return fonts


def test_compile_static(tmp_path):
    module = tmp_path / "module"
    result = compile_fonts(build_static_workspace(tmp_path), module)

    assert result.mode == "static"
    assert result.family == transform_family_name("Fixture Sans")
    assert result.payload_files == ("DroidSans.ttf",)
    assert result.family_faces["sans"]
    assert not result.family_faces["bengali"]

    files_dir = module / "Files"
    assert (files_dir / "DroidSans.ttf").is_file()
    assert len(TTCollection(str(files_dir / "DroidSans.ttf")).fonts) == 2
    sans_xml = (files_dir / "sans.xml").read_text(encoding="utf-8")
    assert 'weight="400"' in sans_xml
    assert 'weight="700"' in sans_xml
    assert 'index="0"' in sans_xml and 'index="1"' in sans_xml
    # serif fallback is derived from the sans faces when no custom serif given
    assert (files_dir / "serif.xml").read_text(encoding="utf-8").strip()

    config = (module / "font-config.sh").read_text(encoding="utf-8")
    assert "FONT_MODE='static'" in config
    assert "FONT_PRIMARY='DroidSans.ttf'" in config


def test_compile_static_with_optional_families(tmp_path):
    fonts = build_static_workspace(tmp_path)
    bengali = fonts / "Bengali"
    bengali.mkdir(parents=True)
    build_synthetic_font(
        bengali / "Beng-Medium.ttf", family="Fixture Bengali", style_name="Medium", us_weight_class=500
    )
    serif = fonts / "Serif"
    serif.mkdir(parents=True)
    build_synthetic_font(
        serif / "SerifVF-Roman.ttf", family="Fixture Serif", style_name="Roman",
        us_weight_class=400, wght_axis=(100, 400, 900),
    )

    module = tmp_path / "module"
    result = compile_fonts(fonts, module)

    files_dir = module / "Files"
    assert (files_dir / "bengali.xml").is_file()
    assert (files_dir / "serif.xml").is_file()
    assert len(TTCollection(str(files_dir / "DroidSans.ttf")).fonts) == 4
    assert len(result.family_faces["bengali"]) == 1
    assert len(result.family_faces["serif"]) == 1
    # variable serif next to static sans still produces axis config
    config = (module / "font-config.sh").read_text(encoding="utf-8")
    assert "VF_SERIF_UPRIGHT_AXIS_META=" in config


def test_compile_variable(tmp_path):
    module = tmp_path / "module"
    result = compile_fonts(build_variable_workspace(tmp_path), module)

    assert result.mode == "variable"
    config = (module / "font-config.sh").read_text(encoding="utf-8")
    assert "FONT_MODE='variable'" in config
    assert "VF_UPRIGHT_AXIS_META=" in config
    assert "VF_ITALIC_AXIS_META=" in config
    assert "VF_UPRIGHT_WEIGHTS='100 200 300 400 500 600 700 800 900'" in config

    sans_xml = (module / "Files" / "sans.xml").read_text(encoding="utf-8")
    assert '<axis tag="wght" stylevalue="100"/>' in sans_xml
    assert '<axis tag="wght" stylevalue="900"/>' in sans_xml


def test_compile_rejects_multiple_primary_families(tmp_path):
    fonts = build_static_workspace(tmp_path)
    build_synthetic_font(
        fonts / "Sans" / "Other.ttf", family="Different Family", style_name="Regular", us_weight_class=400
    )
    with pytest.raises(SystemExit, match="multiple font families"):
        compile_fonts(fonts, tmp_path / "module")


def test_inspect_reports_without_building(tmp_path):
    fonts = build_static_workspace(tmp_path)
    report = inspect_fonts(fonts)

    assert report["primary_mode"] == "static"
    assert report["primary_families"] == ["Fixture Sans"]
    assert len(report["categories"]["sans"]["faces"]) == 2
    assert not report["categories"]["sans"]["faces"][0]["axes"]
    assert report["notes"] == []


def test_inspect_notes_missing_sans(tmp_path):
    fonts = tmp_path / "Fonts"
    bengali = fonts / "Bengali"
    bengali.mkdir(parents=True)
    build_synthetic_font(bengali / "Beng.ttf", family="Fixture Bengali", style_name="Regular", us_weight_class=400)

    report = inspect_fonts(fonts)
    assert any("No Sans-serif faces" in note for note in report["notes"])


def test_update_module_metadata(tmp_path):
    module = tmp_path / "module"
    copy_template(TEMPLATE_DIR, module)
    props = update_module_metadata(
        module, "Fixture Sans", "static",
        name="My Font", version="1.2", version_code="42",
        applied_features=("ss01",),
    )
    assert props["id"] == "mffm14_My_Font_ss01"
    assert props["name"] == "[MFFMv14] My Font (ss01)"
    assert props["version"] == "1.2"
    assert props["versionCode"] == "42"
    assert read_props(module / "module.prop")["versionCode"] == "42"
