"""Tests for on-device font metrics normalization, TTC bundling, and indexed XML compilation."""

import os
from pathlib import Path
from fontTools.ttLib import TTCollection, TTFont

import pytest
from tests.synthfonts import build_synthetic_font
from runtime_helper import compile_bundle, fix_font_metrics, inspect_face


def test_helper_process_and_compile(tmp_path):
    # 1. Create a synthetic variable font for Sans
    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    var_upright = sans_dir / "TestSans-VF.ttf"
    build_synthetic_font(var_upright, family="TestSans", wght_axis=(100, 400, 900))

    # 2. Create static Mono fonts
    mono_dir = tmp_path / "Monospace"
    mono_dir.mkdir()
    build_synthetic_font(mono_dir / "Mono-Regular.ttf", family="TestMono", style_name="Regular", us_weight_class=400)
    build_synthetic_font(mono_dir / "Mono-Bold.ttf", family="TestMono", style_name="Bold", us_weight_class=700)

    # 3. Create static Bengali font
    bengali_dir = tmp_path / "Bengali"
    bengali_dir.mkdir()
    build_synthetic_font(bengali_dir / "Bengali-Regular.ttf", family="NotoSansBengali", style_name="Regular", us_weight_class=400)
    build_synthetic_font(bengali_dir / "Bengali-Bold.ttf", family="NotoSansBengali", style_name="Bold", us_weight_class=700)

    # 4. Compile bundle
    out_dir = tmp_path / "out"
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        mono_dirs=[str(mono_dir)],
        bengali_dirs=[str(bengali_dir)],
        keep_hinting=False,
        fix_metrics=True,
    )
    assert ret == 0

    # 5. Verify output files
    assert (out_dir / "DroidSans.ttf").is_file()
    assert (out_dir / "sans.xml").is_file()
    assert (out_dir / "condensed.xml").is_file()
    assert (out_dir / "serif.xml").is_file()
    assert (out_dir / "mono.xml").is_file()
    assert (out_dir / "bengali.xml").is_file()
    assert (out_dir / "font-config.sh").is_file()

    # 6. Verify TTC contents
    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    # Sans (1) + Mono (2) + Bengali (2) = 5 fonts
    assert len(ttc.fonts) == 5

    # Check metrics normalization
    first_font = ttc.fonts[0]
    head = first_font["head"]
    os2 = first_font["OS/2"]
    hhea = first_font["hhea"]
    assert head.unitsPerEm == 1000
    assert os2.sTypoLineGap == 0
    assert hhea.lineGap == 0
    # Scaled to 1000 UPM from 2048 reference (2128 * 1000 / 2048 = 1039)
    assert os2.sTypoAscender == int(round(2128 * 1000 / 2048))
    assert os2.sTypoDescender == int(round(-550 * 1000 / 2048))

    # 7. Verify indexed XML fragments
    sans_xml = (out_dir / "sans.xml").read_text(encoding="utf-8")
    assert 'index="0"' in sans_xml
    assert 'weight="400"' in sans_xml
    assert 'weight="900"' in sans_xml

    mono_xml = (out_dir / "mono.xml").read_text(encoding="utf-8")
    assert 'index="1"' in mono_xml
    assert 'index="2"' in mono_xml

    bengali_xml = (out_dir / "bengali.xml").read_text(encoding="utf-8")
    assert 'index="3"' in bengali_xml
    assert 'index="4"' in bengali_xml

    # 8. Verify font-config.sh
    conf = (out_dir / "font-config.sh").read_text(encoding="utf-8")
    assert 'FONT_MODE="variable"' in conf
    assert 'HAS_CUSTOM_MONO="true"' in conf
    assert 'HAS_CUSTOM_BENGALI="true"' in conf
    assert 'TTC_TOTAL_FONTS="5"' in conf
    assert 'VF_UPRIGHT_AXIS_META=' in conf
    assert 'VF_UPRIGHT_WEIGHTS=' in conf


def test_helper_process_static_bundle(tmp_path):
    # Test static Sans family compilation into unified TTC
    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    build_synthetic_font(sans_dir / "Sans-Light.ttf", family="StaticSans", style_name="Light", us_weight_class=300)
    build_synthetic_font(sans_dir / "Sans-Regular.ttf", family="StaticSans", style_name="Regular", us_weight_class=400)
    build_synthetic_font(sans_dir / "Sans-Bold.ttf", family="StaticSans", style_name="Bold", us_weight_class=700)

    serif_dir = tmp_path / "Serif"
    serif_dir.mkdir()
    build_synthetic_font(serif_dir / "Serif-Regular.ttf", family="StaticSerif", style_name="Regular", us_weight_class=400)
    build_synthetic_font(serif_dir / "Serif-Bold.ttf", family="StaticSerif", style_name="Bold", us_weight_class=700)

    out_dir = tmp_path / "out"
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        serif_dirs=[str(serif_dir)],
        keep_hinting=False,
        fix_metrics=True,
    )
    assert ret == 0

    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    # Sans (3) + Serif (2) = 5 fonts
    assert len(ttc.fonts) == 5

    sans_xml = (out_dir / "sans.xml").read_text(encoding="utf-8")
    assert 'index="0"' in sans_xml
    assert 'index="1"' in sans_xml
    assert 'index="2"' in sans_xml

    serif_xml = (out_dir / "serif.xml").read_text(encoding="utf-8")
    assert 'index="3"' in serif_xml
    assert 'index="4"' in serif_xml

    conf = (out_dir / "font-config.sh").read_text(encoding="utf-8")
    assert 'FONT_MODE="static"' in conf
    assert 'HAS_CUSTOM_SERIF="true"' in conf


def test_helper_duplicate_dirs_and_five_bengali_faces(tmp_path):
    # 1. Variable Sans
    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    build_synthetic_font(sans_dir / "Sans-VF.ttf", family="TestSans", wght_axis=(100, 400, 900))

    # 2. Five static Bengali fonts
    bengali_dir = tmp_path / "Bengali"
    bengali_dir.mkdir()
    build_synthetic_font(bengali_dir / "Bengali-Light.ttf", family="TestBengali", style_name="Light", us_weight_class=300)
    build_synthetic_font(bengali_dir / "Bengali-Regular.ttf", family="TestBengali", style_name="Regular", us_weight_class=400)
    build_synthetic_font(bengali_dir / "Bengali-Medium.ttf", family="TestBengali", style_name="Medium", us_weight_class=500)
    build_synthetic_font(bengali_dir / "Bengali-Bold.ttf", family="TestBengali", style_name="Bold", us_weight_class=700)
    build_synthetic_font(bengali_dir / "Bengali-Black.ttf", family="TestBengali", style_name="Black", us_weight_class=900)

    out_dir = tmp_path / "out"
    # Pass bengali_dir TWICE to simulate case-insensitive /sdcard scan
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir), str(sans_dir)],
        bengali_dirs=[str(bengali_dir), str(bengali_dir)],
        keep_hinting=False,
        fix_metrics=True,
    )
    assert ret == 0

    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    # Exactly 1 Sans + 5 Bengali = 6 fonts (no duplicates!)
    assert len(ttc.fonts) == 6

    bengali_lines = [l for l in (out_dir / "bengali.xml").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(bengali_lines) == 5
    assert 'weight="300" style="normal" index="1"' in bengali_lines[0]
    assert 'weight="400" style="normal" index="2"' in bengali_lines[1]
    assert 'weight="500" style="normal" index="3"' in bengali_lines[2]
    assert 'weight="700" style="normal" index="4"' in bengali_lines[3]
    assert 'weight="900" style="normal" index="5"' in bengali_lines[4]

