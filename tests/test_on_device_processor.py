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


def test_helper_centered_colon_detection_and_injection(tmp_path):
    from runtime_helper import font_has_centered_colon, inject_centered_colon

    font_path = tmp_path / "ColonTest.ttf"
    build_synthetic_font(font_path, family="ColonTest")

    # Initially has no centered colon
    assert not font_has_centered_colon(font_path)

    # Inject centered colon
    ok = inject_centered_colon(font_path)
    assert ok

    # Now has centered colon
    assert font_has_centered_colon(font_path)


def test_helper_name_table_sanitization(tmp_path):
    from runtime_helper import sanitize_name_table

    # 1. Single word family name: "Roboto" -> "Roboto Mistu"
    font_path1 = tmp_path / "SingleWord.ttf"
    build_synthetic_font(font_path1, family="Roboto")
    font1 = TTFont(str(font_path1))
    sanitize_name_table(font1)
    font1.save(str(font_path1))
    font1.close()

    check1 = TTFont(str(font_path1))
    names1 = check1["name"]
    assert names1.getName(1, 3, 1).toStr() == "Roboto Mistu"
    assert names1.getName(4, 3, 1).toStr() == "Roboto Mistu Regular"
    assert names1.getName(5, 3, 1).toStr().endswith(";Mistu")
    assert names1.getName(8, 3, 1).toStr() == "Mistu @ MFFM Inc."
    check1.close()

    # 2. Multi-word family name: "Amazon Ember" -> "Amazon Mistu Ember"
    font_path2 = tmp_path / "MultiWord.ttf"
    build_synthetic_font(font_path2, family="Amazon Ember")
    font2 = TTFont(str(font_path2))
    sanitize_name_table(font2)
    font2.save(str(font_path2))
    font2.close()

    check2 = TTFont(str(font_path2))
    names2 = check2["name"]
    assert names2.getName(1, 3, 1).toStr() == "Amazon Mistu Ember"
    assert names2.getName(4, 3, 1).toStr() == "Amazon Mistu Ember Regular"
    assert names2.getName(5, 3, 1).toStr().endswith(";Mistu")
    check2.close()

    # 3. Three-word family name: "Josefa Rounded Pro" -> "Josefa Mistu Rounded Pro"
    font_path3 = tmp_path / "ThreeWord.ttf"
    build_synthetic_font(font_path3, family="Josefa Rounded Pro")
    font3 = TTFont(str(font_path3))
    sanitize_name_table(font3)
    font3.save(str(font_path3))
    font3.close()

    check3 = TTFont(str(font_path3))
    names3 = check3["name"]
    assert names3.getName(1, 3, 1).toStr() == "Josefa Mistu Rounded Pro"
    assert names3.getName(4, 3, 1).toStr() == "Josefa Mistu Rounded Pro Regular"
    assert names3.getName(5, 3, 1).toStr().endswith(";Mistu")
    check3.close()


def test_helper_feature_reporting_and_freezing(tmp_path):
    from runtime_helper import extract_features_from_dirs, format_category_feature_report, freeze_font_features

    font_path = tmp_path / "FeatTest.ttf"
    build_synthetic_font(font_path, family="FeatTest")

    # Add a mock GSUB table with ss01 and zero features
    font = TTFont(str(font_path))
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables.otTables import GSUB, FeatureList, FeatureRecord, Feature, LookupList, ScriptList
    gsub_wrapper = newTable("GSUB")
    gsub = GSUB()
    gsub.Version = 0x00010000
    gsub.ScriptList = ScriptList(); gsub.ScriptList.ScriptRecord = []
    gsub.FeatureList = FeatureList(); gsub.FeatureList.FeatureRecord = []
    gsub.LookupList = LookupList(); gsub.LookupList.Lookup = []

    f_rec1 = FeatureRecord(); f_rec1.FeatureTag = "ss01"; f_rec1.Feature = Feature(); f_rec1.Feature.LookupListIndex = []; f_rec1.Feature.FeatureParams = None
    f_rec2 = FeatureRecord(); f_rec2.FeatureTag = "zero"; f_rec2.Feature = Feature(); f_rec2.Feature.LookupListIndex = []; f_rec2.Feature.FeatureParams = None
    gsub.FeatureList.FeatureRecord.extend([f_rec1, f_rec2])
    gsub_wrapper.table = gsub
    font["GSUB"] = gsub_wrapper
    font.save(str(font_path))
    font.close()

    feats = extract_features_from_dirs([str(tmp_path)])
    assert "ss01" in feats
    assert "zero" in feats

    report = format_category_feature_report("Sans-serif", feats)
    assert any("ss01" in l for l in report)
    assert any("zero" in l for l in report)

    # Freeze features
    ok = freeze_font_features(font_path, "ss01,zero")
    assert font_path.is_file()


def test_helper_woff_and_woff2_compilation(tmp_path):
    from runtime_helper import compile_bundle

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    mono_dir = tmp_path / "Mono"
    mono_dir.mkdir()

    ttf_temp = tmp_path / "temp.ttf"
    build_synthetic_font(ttf_temp, family="WoffSans", wght_axis=(300, 400, 700))

    # Save as .woff
    f_woff = TTFont(str(ttf_temp))
    f_woff.flavor = "woff"
    f_woff.save(str(sans_dir / "WoffSans-Variable.woff"))
    f_woff.close()

    # Save as .woff2
    f_woff2 = TTFont(str(ttf_temp))
    f_woff2.flavor = "woff2"
    f_woff2.save(str(mono_dir / "WoffMono-Variable.woff2"))
    f_woff2.close()

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        mono_dirs=[str(mono_dir)],
        enable_centered_colon=True,
    )
    assert ret == 0

    assert (out_dir / "DroidSans.ttf").is_file()
    assert (out_dir / "sans.xml").is_file()
    assert (out_dir / "mono.xml").is_file()
    assert (out_dir / "font-config.sh").is_file()

    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    assert len(ttc.fonts) == 2
    for font in ttc.fonts:
        assert font.flavor is None  # Unflavored to native SFNT inside TTC
    ttc.close()


def test_helper_dedupes_multiple_400_weights_preferring_regular(tmp_path):
    from runtime_helper import compile_bundle

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()

    # Create Book (400) and Regular (400)
    build_synthetic_font(sans_dir / "MyFont-Book.ttf", family="MyFont Book", us_weight_class=400)
    build_synthetic_font(sans_dir / "MyFont-Regular.ttf", family="MyFont Regular", us_weight_class=400)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
    )
    assert ret == 0

    # Exactly 1 font should be in the TTC (Regular chosen over Book)
    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    assert len(ttc.fonts) == 1
    
    # Read font-config.sh to check chosen family
    conf = (out_dir / "font-config.sh").read_text(encoding="utf-8")
    assert 'FONT_FAMILY="MFFM MyFont Regular"' in conf or 'FONT_FAMILY="MyFont Regular"' in conf
    ttc.close()


def test_helper_compile_bundle_injects_centered_colon_for_static_fonts(tmp_path):
    from runtime_helper import compile_bundle, font_has_centered_colon

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    build_synthetic_font(sans_dir / "Static-Regular.ttf", family="Static Regular", us_weight_class=400)
    build_synthetic_font(sans_dir / "Static-Bold.ttf", family="Static Bold", us_weight_class=700)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        enable_centered_colon=True,
    )
    assert ret == 0

    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    assert len(ttc.fonts) == 2
    for font in ttc.fonts:
        assert font_has_centered_colon(font)
    ttc.close()


def test_helper_otf_to_ttf_conversion(tmp_path):
    from tests.synthfonts import build_synthetic_otf_font
    from runtime_helper import otf_to_ttf

    otf_path = tmp_path / "Source-Regular.otf"
    build_synthetic_otf_font(otf_path, family="SourceOTF", style_name="Regular")

    font = TTFont(str(otf_path))
    assert font.sfntVersion == "OTTO"
    assert "CFF " in font
    assert "glyf" not in font

    converted = otf_to_ttf(font)
    assert converted is True
    assert font.sfntVersion == "\000\001\000\000"
    assert "glyf" in font
    assert "loca" in font
    assert "CFF " not in font

    out_ttf = tmp_path / "Source-Regular.ttf"
    font.save(str(out_ttf))
    font.close()

    f2 = TTFont(str(out_ttf))
    assert f2.sfntVersion == "\000\001\000\000"
    assert "colon" in f2["glyf"].glyphs
    f2.close()


def test_helper_otf_centered_colon_injection(tmp_path):
    from tests.synthfonts import build_synthetic_otf_font
    from runtime_helper import font_has_centered_colon, inject_centered_colon

    otf_path = tmp_path / "ClockOTF.otf"
    build_synthetic_otf_font(otf_path, family="ClockOTF", style_name="Regular")

    assert not font_has_centered_colon(otf_path)

    ok = inject_centered_colon(otf_path)
    assert ok is True

    assert font_has_centered_colon(otf_path)

    f = TTFont(str(otf_path))
    assert f.sfntVersion == "\000\001\000\000"
    assert "glyf" in f
    assert "colon.case" in f["glyf"].glyphs
    f.close()


def test_helper_otf_compile_bundle(tmp_path):
    from tests.synthfonts import build_synthetic_otf_font
    from runtime_helper import compile_bundle, font_has_centered_colon

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    build_synthetic_otf_font(sans_dir / "OTF-Regular.otf", family="OTF Sans", style_name="Regular", us_weight_class=400)
    build_synthetic_otf_font(sans_dir / "OTF-Bold.otf", family="OTF Sans", style_name="Bold", us_weight_class=700)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        enable_centered_colon=True,
    )
    assert ret == 0

    out_ttc = out_dir / "DroidSans.ttf"
    assert out_ttc.is_file()

    ttc = TTCollection(str(out_ttc))
    assert len(ttc.fonts) == 2
    for f in ttc.fonts:
        assert f.sfntVersion == "\000\001\000\000"
        assert "glyf" in f
        assert font_has_centered_colon(f)
    ttc.close()


def test_helper_cli_otf2ttf(tmp_path):
    import subprocess
    import sys
    from tests.synthfonts import build_synthetic_otf_font

    otf_path = tmp_path / "CliTest.otf"
    ttf_path = tmp_path / "CliTest.ttf"
    build_synthetic_otf_font(otf_path, family="CliTest")

    res = subprocess.run(
        [sys.executable, "runtime_helper.py", "otf2ttf", "--in", str(otf_path), "--out", str(ttf_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert ttf_path.is_file()
    font = TTFont(str(ttf_path))
    assert font.sfntVersion == "\000\001\000\000"
    assert "glyf" in font
    assert "CFF " not in font
    font.close()


def test_helper_equalize_clock_digits(tmp_path):
    from tests.synthfonts import build_synthetic_digit_font
    from runtime_helper import equalize_clock_digits

    font_path = tmp_path / "ProportionalDigits.ttf"
    build_synthetic_digit_font(font_path)

    f_before = TTFont(str(font_path))
    assert f_before["hmtx"].metrics["one"][0] == 350
    assert f_before["hmtx"].metrics["zero"][0] == 600
    f_before.close()

    # First run equalizes and centers
    modified = equalize_clock_digits(font_path)
    assert modified is True

    f_after = TTFont(str(font_path))
    hmtx = f_after["hmtx"]
    glyf = f_after["glyf"]
    for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
        assert hmtx.metrics[d][0] == 600

    # Verify contour centering for 'one': glyph width 200 centered in 600 => lsb = 200, rsb = 200
    assert glyf["one"].xMin == 200
    assert glyf["one"].xMax == 400
    assert hmtx.metrics["one"][1] == 200
    f_after.close()

    # Second run is idempotent (no-op)
    modified_again = equalize_clock_digits(font_path)
    assert modified_again is False


def test_helper_equalize_clock_digits_target_width(tmp_path):
    from tests.synthfonts import build_synthetic_digit_font
    from runtime_helper import equalize_clock_digits

    font_path = tmp_path / "CustomWidthDigits.ttf"
    build_synthetic_digit_font(font_path)

    modified = equalize_clock_digits(font_path, target_width=750)
    assert modified is True

    font = TTFont(str(font_path))
    for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
        assert font["hmtx"].metrics[d][0] == 750
    font.close()


def test_helper_colon_alignment_modes(tmp_path):
    from tests.synthfonts import build_synthetic_digit_font
    from runtime_helper import inject_centered_colon

    # 1. Cap Height alignment (cap_height=700 -> target_center=350)
    p_cap = tmp_path / "ColonCap.ttf"
    build_synthetic_digit_font(p_cap, cap_height=700, x_height=500)
    assert inject_centered_colon(p_cap, alignment="cap_height") is True
    f_cap = TTFont(str(p_cap))
    glyf_cap = f_cap["glyf"]["colon.case"]
    center_cap = (glyf_cap.yMin + glyf_cap.yMax) / 2
    assert center_cap == 350
    f_cap.close()

    # 2. X-Height alignment (x_height=500 -> target_center=250)
    p_xh = tmp_path / "ColonXh.ttf"
    build_synthetic_digit_font(p_xh, cap_height=700, x_height=500)
    assert inject_centered_colon(p_xh, alignment="x_height") is True
    f_xh = TTFont(str(p_xh))
    glyf_xh = f_xh["glyf"]["colon.case"]
    center_xh = (glyf_xh.yMin + glyf_xh.yMax) / 2
    assert center_xh == 250
    f_xh.close()


def test_helper_colon_custom_offset(tmp_path):
    from tests.synthfonts import build_synthetic_digit_font
    from runtime_helper import inject_centered_colon

    p_base = tmp_path / "ColonBase.ttf"
    p_off = tmp_path / "ColonOffset.ttf"
    build_synthetic_digit_font(p_base, cap_height=700)
    build_synthetic_digit_font(p_off, cap_height=700)

    inject_centered_colon(p_base, alignment="cap_height", offset=0)
    inject_centered_colon(p_off, alignment="cap_height", offset=40)

    f_base = TTFont(str(p_base))
    f_off = TTFont(str(p_off))
    base_center = (f_base["glyf"]["colon.case"].yMin + f_base["glyf"]["colon.case"].yMax) / 2
    off_center = (f_off["glyf"]["colon.case"].yMin + f_off["glyf"]["colon.case"].yMax) / 2
    assert off_center == base_center + 40
    f_base.close()
    f_off.close()


def test_helper_colon_rules(tmp_path):
    from tests.synthfonts import build_synthetic_digit_font
    from runtime_helper import inject_centered_colon

    # 1. between_digits rule: ChainContextSubst format 3 has backtrack and lookahead
    p_between = tmp_path / "RuleBetween.ttf"
    build_synthetic_digit_font(p_between)
    inject_centered_colon(p_between, rule="between_digits")
    f_between = TTFont(str(p_between))
    gsub_between = f_between["GSUB"].table
    c_lookup = gsub_between.LookupList.Lookup[1]
    assert c_lookup.LookupType == 6
    st_between = c_lookup.SubTable[0]
    assert st_between.BacktrackGlyphCount == 1
    assert st_between.LookAheadGlyphCount == 1
    # Also includes spaced colon subtable
    assert len(c_lookup.SubTable) >= 2
    f_between.close()

    # 2. after_digit rule: ChainContextSubst format 3 has backtrack but 0 lookahead
    p_after = tmp_path / "RuleAfter.ttf"
    build_synthetic_digit_font(p_after)
    inject_centered_colon(p_after, rule="after_digit")
    f_after = TTFont(str(p_after))
    gsub_after = f_after["GSUB"].table
    st_after = gsub_after.LookupList.Lookup[1].SubTable[0]
    assert st_after.BacktrackGlyphCount == 1
    assert st_after.LookAheadGlyphCount == 0
    f_after.close()

    # 3. always rule: promotes SingleSubst directly into calt
    p_always = tmp_path / "RuleAlways.ttf"
    build_synthetic_digit_font(p_always)
    inject_centered_colon(p_always, rule="always")
    f_always = TTFont(str(p_always))
    gsub_always = f_always["GSUB"].table
    rec = [r for r in gsub_always.FeatureList.FeatureRecord if r.FeatureTag == "calt"][0]
    first_lookup_idx = rec.Feature.LookupListIndex[0]
    assert gsub_always.LookupList.Lookup[first_lookup_idx].LookupType == 1
    f_always.close()


def test_helper_cli_equalize_digits(tmp_path):
    import subprocess
    import sys
    from tests.synthfonts import build_synthetic_digit_font

    in_path = tmp_path / "CliDigitsIn.ttf"
    out_path = tmp_path / "CliDigitsOut.ttf"
    build_synthetic_digit_font(in_path)

    res = subprocess.run(
        [sys.executable, "runtime_helper.py", "equalize-digits", "--in", str(in_path), "--out", str(out_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out_path.is_file()
    font = TTFont(str(out_path))
    for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
        assert font["hmtx"].metrics[d][0] == 600
    font.close()


def test_helper_compile_bundle_with_tabular_digits_and_colon(tmp_path):
    from tests.synthfonts import build_synthetic_digit_font
    from runtime_helper import compile_bundle, font_has_centered_colon

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    build_synthetic_digit_font(sans_dir / "DigitSans-Regular.ttf", family="DigitSans")

    out_dir = tmp_path / "out"
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        enable_tabular_digits=True,
        enable_centered_colon=True,
        colon_alignment="cap_height",
        colon_offset=15,
        colon_rule="between_digits",
    )
    assert ret == 0
    bundle_path = out_dir / "DroidSans.ttf"
    assert bundle_path.is_file()

    ttc = TTCollection(str(bundle_path))
    font = ttc.fonts[0]
    # Digits are equalized
    for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
        assert font["hmtx"].metrics[d][0] == 600
    # Centered colon is present
    assert font_has_centered_colon(font)
    ttc.close()


def test_helper_metrics_safe_standard_font(tmp_path):
    from tests.synthfonts import build_synthetic_font
    from runtime_helper import fix_font_metrics

    p = tmp_path / "StandardMetrics.ttf"
    build_synthetic_font(p)
    font = TTFont(str(p))
    fix_font_metrics(font, mode="safe")

    # Native 1000 UPM: base ascent 1039, base descent -269
    assert font["OS/2"].sTypoAscender == 1039
    assert font["OS/2"].sTypoDescender == -269
    assert font["hhea"].ascent == 1039
    assert font["hhea"].descent == -269
    assert font["OS/2"].usWinAscent == 1039
    assert font["OS/2"].usWinDescent == 269
    assert font["OS/2"].sTypoLineGap == 0
    assert font["hhea"].lineGap == 0
    font.close()


def test_helper_metrics_safe_tall_glyph(tmp_path):
    from tests.synthfonts import build_synthetic_tall_accent_font
    from runtime_helper import fix_font_metrics

    p = tmp_path / "TallMetrics.ttf"
    build_synthetic_tall_accent_font(p, tall_y_max=1250, deep_y_min=-350)
    font = TTFont(str(p))
    fix_font_metrics(font, mode="safe")

    os2 = font["OS/2"]
    hhea = font["hhea"]

    # Base FFIX3 on 1000 UPM: 1039 / -269
    # k_ascent = 1250 / 1039 = 1.20308
    # k_descent = 350 / 269 = 1.30112
    # k = 1.30112
    # ascent = round(1.30112 * 1039) = 1352
    # descent = round(1.30112 * -269) = -350
    assert os2.sTypoAscender == 1352
    assert os2.sTypoDescender == -350
    assert hhea.ascent == 1352
    assert hhea.descent == -350
    assert os2.usWinAscent >= 1250
    assert os2.usWinDescent >= 350
    ratio = os2.sTypoAscender / abs(os2.sTypoDescender)
    ref_ratio = 2128 / 550
    assert abs(ratio - ref_ratio) < 0.05
    font.close()


def test_helper_metrics_compact_mode(tmp_path):
    from tests.synthfonts import build_synthetic_tall_accent_font
    from runtime_helper import fix_font_metrics

    p = tmp_path / "CompactMetrics.ttf"
    build_synthetic_tall_accent_font(p, tall_y_max=1250, deep_y_min=-350)
    font = TTFont(str(p))
    fix_font_metrics(font, mode="compact")

    assert font["OS/2"].sTypoAscender == 1039
    assert font["OS/2"].sTypoDescender == -269
    assert font["hhea"].ascent == 1039
    assert font["hhea"].descent == -269
    font.close()


def test_helper_metrics_preserve_mode(tmp_path):
    from tests.synthfonts import build_synthetic_tall_accent_font
    from runtime_helper import fix_font_metrics

    p = tmp_path / "PreserveMetrics.ttf"
    build_synthetic_tall_accent_font(p)
    font = TTFont(str(p))
    assert font["OS/2"].sTypoAscender == 800
    assert font["OS/2"].sTypoDescender == -200

    fix_font_metrics(font, mode="preserve")
    assert font["OS/2"].sTypoAscender == 800
    assert font["OS/2"].sTypoDescender == -200
    assert font["hhea"].ascent == 800
    assert font["hhea"].descent == -200
    font.close()


def test_helper_cli_metrics_mode(tmp_path):
    import subprocess
    import sys
    from tests.synthfonts import build_synthetic_tall_accent_font

    in_path = tmp_path / "CliMetricsIn.ttf"
    out_path = tmp_path / "CliMetricsOut.ttf"
    build_synthetic_tall_accent_font(in_path, tall_y_max=1250, deep_y_min=-350)

    res = subprocess.run(
        [sys.executable, "runtime_helper.py", "process-font", "--in", str(in_path), "--out", str(out_path), "--metrics-mode", "safe"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out_path.is_file()
    font = TTFont(str(out_path))
    assert font["OS/2"].sTypoAscender == 1352
    assert font["OS/2"].sTypoDescender == -350
    font.close()


def test_helper_compile_bundle_metrics_mode_safe(tmp_path):
    from tests.synthfonts import build_synthetic_tall_accent_font
    from runtime_helper import compile_bundle

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    build_synthetic_tall_accent_font(sans_dir / "TallSans-Regular.ttf", family="TallSans", tall_y_max=1250, deep_y_min=-350)

    out_dir = tmp_path / "out"
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        metrics_mode="safe",
    )
    assert ret == 0
    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    font = ttc.fonts[0]
    assert font["OS/2"].sTypoAscender == 1352
    assert font["OS/2"].sTypoDescender == -350
    ttc.close()


def _inject_test_bloat(font):
    from fontTools.ttLib import newTable
    dsig = newTable("DSIG")
    dsig.ulVersion = 1
    dsig.usNumSigs = 0
    dsig.usFlag = 0
    dsig.signatureRecords = []
    font["DSIG"] = dsig

    fftm = newTable("FFTM")
    fftm.version = 0
    fftm.FFTimeStamp = 0
    fftm.sourceCreated = 0
    fftm.sourceModified = 0
    font["FFTM"] = fftm

    font["name"].setName("Mac Test", 1, 1, 0, 0)
    font["name"].setName("Win Test", 1, 3, 1, 0x409)


def test_helper_optimize_font_tables(tmp_path):
    from tests.synthfonts import build_synthetic_font
    from runtime_helper import optimize_font_tables

    font_path = tmp_path / "BloatFont.ttf"
    build_synthetic_font(font_path)
    font = TTFont(str(font_path))
    _inject_test_bloat(font)

    assert "DSIG" in font
    assert "FFTM" in font
    assert any(rec.platformID == 1 for rec in font["name"].names)

    ok = optimize_font_tables(font, keep_hinting=False)
    assert ok is True
    assert "DSIG" not in font
    assert "FFTM" not in font
    assert not any(rec.platformID == 1 for rec in font["name"].names)
    assert any(rec.platformID == 3 for rec in font["name"].names)
    font.close()


def test_helper_optimize_font_tables_preserves_glyphs_and_order(tmp_path):
    from tests.synthfonts import build_synthetic_font
    from runtime_helper import optimize_font_tables

    font_path = tmp_path / "PreserveGlyphs.ttf"
    build_synthetic_font(font_path)
    font = TTFont(str(font_path))
    initial_glyphs = font.getGlyphOrder()

    optimize_font_tables(font, keep_hinting=False)
    assert font.getGlyphOrder() == initial_glyphs
    assert "glyf" in font
    assert "cmap" in font
    font.close()


def test_helper_cli_optimize(tmp_path):
    import subprocess
    import sys
    from tests.synthfonts import build_synthetic_font

    in_path = tmp_path / "CliBloatIn.ttf"
    out_path = tmp_path / "CliBloatOut.ttf"
    build_synthetic_font(in_path)
    font = TTFont(str(in_path))
    _inject_test_bloat(font)
    font.save(str(in_path))
    font.close()

    res = subprocess.run(
        [sys.executable, "runtime_helper.py", "optimize", "--in", str(in_path), "--out", str(out_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out_path.is_file()
    opt_font = TTFont(str(out_path))
    assert "DSIG" not in opt_font
    assert "FFTM" not in opt_font
    opt_font.close()


def test_helper_compile_bundle_optimization_default_false(tmp_path):
    from tests.synthfonts import build_synthetic_font
    from runtime_helper import compile_bundle

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    font_path = sans_dir / "Sans-Regular.ttf"
    build_synthetic_font(font_path, family="SansTest")
    font = TTFont(str(font_path))
    _inject_test_bloat(font)
    font.save(str(font_path))
    font.close()

    out_dir = tmp_path / "out_no_opt"
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        optimize_tables=False,  # default behavior
    )
    assert ret == 0
    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    assert "DSIG" in ttc.fonts[0]
    ttc.close()


def test_helper_compile_bundle_with_optimization_flag(tmp_path):
    from tests.synthfonts import build_synthetic_font
    from runtime_helper import compile_bundle

    sans_dir = tmp_path / "Sans"
    sans_dir.mkdir()
    font_path = sans_dir / "Sans-Regular.ttf"
    build_synthetic_font(font_path, family="SansTest")
    font = TTFont(str(font_path))
    _inject_test_bloat(font)
    font.save(str(font_path))
    font.close()

    out_dir = tmp_path / "out_opt"
    ret = compile_bundle(
        out_dir=str(out_dir),
        sans_dirs=[str(sans_dir)],
        optimize_tables=True,  # enabled via flag
    )
    assert ret == 0
    ttc = TTCollection(str(out_dir / "DroidSans.ttf"))
    assert "DSIG" not in ttc.fonts[0]
    assert "FFTM" not in ttc.fonts[0]
    ttc.close()







