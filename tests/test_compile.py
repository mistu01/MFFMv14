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
    assert result.family_faces["sans"]
    assert not result.family_faces["bengali"]

    files_dir = module / "Files"
    assert (files_dir / "Sans" / "Regular.ttf").is_file()
    assert (files_dir / "Sans" / "Bold.ttf").is_file()

    config = (module / "font-config.sh").read_text(encoding="utf-8")
    assert "FONT_MODE='static'" in config


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
    assert (files_dir / "Sans" / "Regular.ttf").is_file()
    assert (files_dir / "Bengali" / "Beng-Medium.ttf").is_file()
    assert (files_dir / "Serif" / "SerifVF-Roman.ttf").is_file()
    assert len(result.family_faces["bengali"]) == 1
    assert len(result.family_faces["serif"]) == 1


def test_compile_variable(tmp_path):
    module = tmp_path / "module"
    result = compile_fonts(build_variable_workspace(tmp_path), module)

    assert result.mode == "variable"
    files_dir = module / "Files"
    assert (files_dir / "Sans" / "Var-Roman.ttf").is_file()
    assert (files_dir / "Sans" / "Var-Italic.ttf").is_file()
    config = (module / "font-config.sh").read_text(encoding="utf-8")
    assert "FONT_MODE='variable'" in config


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


def test_update_module_migration(tmp_path):
    import argparse
    import zipfile
    from update import update_one

    # Create synthetic old module ZIP
    old_mod = tmp_path / "old_mod"
    old_files = old_mod / "Files"
    old_files.mkdir(parents=True)
    build_synthetic_font(old_files / "DroidSans.ttf", family="Legacy Sans", us_weight_class=400)
    build_synthetic_font(old_files / "Mono-Regular.ttf", family="Legacy Mono", us_weight_class=400)
    build_synthetic_font(old_files / "Beng-Regular.ttf", family="Legacy Beng", us_weight_class=400)
    (old_mod / "module.prop").write_text("id=old_mod\nname=[MFFM] Legacy Font\nversion=1.0\nversionCode=10\n", encoding="utf-8")

    old_zip = tmp_path / "old_module.zip"
    with zipfile.ZipFile(old_zip, "w") as z:
        for p in old_mod.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(old_mod).as_posix())

    out_dir = tmp_path / "dist"
    args = argparse.Namespace(
        mode="auto", name=None, version=None, version_code=None,
        output_dir=out_dir, no_sign=True, keep_hinting=False, no_prefix=False,
        features=None, mono_features=None, serif_features=None, bengali_features=None,
        interactive=False, centered_colon=False, force=True,
    )
    reserved = set()
    result_zip = update_one(old_zip, args, reserved)

    assert result_zip is not None and result_zip.is_file()

    # Verify extracted contents of the updated ZIP
    updated_dir = tmp_path / "updated"
    with zipfile.ZipFile(result_zip) as z:
        z.extractall(updated_dir)

    files_dir = updated_dir / "Files"
    assert (files_dir / "Sans" / "DroidSans.ttf").is_file()
    assert (files_dir / "Monospace" / "Mono-Regular.ttf").is_file()
    assert (files_dir / "Bengali" / "Beng-Regular.ttf").is_file()

