"""Unit tests for the pure helper logic in font_module."""

from pathlib import Path

from font_module import (
    SourceFace,
    _base_family_name,
    _dedupe_static,
    _font_xml,
    _nearest_weight,
    _serif_fragment,
    _static_sort,
    _weight_from_label,
    clean_family_name,
    display_name_for_mode,
    read_props,
    shell_quote,
    slugify,
    write_props,
)


def make_face(filename="Test.ttf", *, family="Test", style_name="Regular", weight=400,
              style="normal", condensed=False, variable=False):
    return SourceFace(
        path=Path(filename),
        font_number=None,
        family=family,
        style_name=style_name,
        weight=weight,
        style=style,
        condensed=condensed,
        variable=variable,
        axes={},
        sfnt_version="\x00\x01\x00\x00",
    )


def test_slugify_normalizes():
    assert slugify("Noto Sans Bengali!") == "Noto-Sans-Bengali"
    assert slugify("  Multiple   Spaces ") == "Multiple-Spaces"
    assert slugify("...") == "font"


def test_slugify_strips_brand_and_variable_markers():
    assert slugify("Mistu Sans Variable") == "Sans"
    assert slugify("MFFM Demo") == "Demo"


def test_clean_family_name_strips_brand():
    assert clean_family_name("MFFM Foo Bar ") == "Foo Bar"
    assert clean_family_name("Mistu") == "Unknown Font"


def test_display_name_for_mode_adds_vf_suffix():
    assert display_name_for_mode("Foo", "variable") == "Foo VF"
    assert display_name_for_mode("Foo VF", "variable") == "Foo VF"
    assert display_name_for_mode("Foo", "static") == "Foo"


def test_weight_from_label():
    assert _weight_from_label("ExtraBold") == 800
    assert _weight_from_label("Semi Bold") == 600
    assert _weight_from_label("ultra-light") == 200
    assert _weight_from_label("Regular") == 400
    assert _weight_from_label("Nothing") is None


def test_base_family_name_strips_style_words():
    assert _base_family_name("My Font Bold Italic") == "My Font"
    assert _base_family_name("My-Font-ExtraLight") == "My-Font"


def test_nearest_weight_ties_break_low():
    assert _nearest_weight(550) == 500
    assert _nearest_weight(850) == 800
    assert _nearest_weight(620) == 600


def test_shell_quote():
    assert shell_quote("plain") == "'plain'"
    assert shell_quote("it's") == "'it'\"'\"'s'"


def test_font_xml_static_and_axis_forms():
    assert (
        _font_xml("DroidSans.ttf", 700, "normal", index=2)
        == '    <font weight="700" style="normal" index="2">DroidSans.ttf</font>'
    )
    axes_xml = _font_xml("DroidSans.ttf", 400, "normal", index=0, axes={"wght": 400.0})
    assert '<axis tag="wght" stylevalue="400"/>' in axes_xml


def test_static_sort_orders_normal_first_then_weight():
    faces = [
        make_face("A-Italic.ttf", weight=400, style="italic"),
        make_face("A-Bold.ttf", weight=700),
        make_face("A-Regular.ttf", weight=400),
    ]
    ordered = sorted(faces, key=_static_sort)
    assert [f.weight for f in ordered] == [400, 700, 400]
    assert ordered[-1].style == "italic"


def test_dedupe_static_prefers_descriptive_filename():
    faces = [
        make_face("Test.ttf"),
        make_face("Test-Regular.ttf"),
        make_face("Test-Bold.ttf", weight=700),
    ]
    selected = _dedupe_static(faces)
    assert len(selected) == 2
    regular = next(f for f in selected if f.weight == 400)
    assert regular.path.name == "Test-Regular.ttf"


def test_serif_fragment_picks_exact_then_nearest():
    entries = [
        (400, "normal", '<font weight="400" style="normal">a</font>'),
        (500, "normal", '<font weight="500" style="normal">b</font>'),
        (400, "italic", '<font weight="400" style="italic">c</font>'),
    ]
    fragment = _serif_fragment(entries)
    assert 'weight="400" style="normal"' in fragment
    assert 'weight="500" style="normal"' in fragment  # nearest to 700? no: 500 is nearest of the two
    assert 'weight="400" style="italic"' in fragment


def test_props_round_trip(tmp_path):
    path = tmp_path / "module.prop"
    write_props(path, {"name": "N", "id": "i", "version": "1"})
    assert read_props(path) == {"name": "N", "id": "i", "version": "1"}
    assert path.read_text(encoding="utf-8").splitlines()[0].startswith("id=")


def test_shell_scripts_syntax():
    import os
    import shutil
    import subprocess

    bash = shutil.which("bash") or shutil.which("sh")
    if not bash:
        for candidate in [r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\sh.exe"]:
            if os.path.isfile(candidate):
                bash = candidate
                break
    if not bash:
        return

    root = Path(__file__).resolve().parent.parent
    scripts = [
        root / "template" / "customize.sh",
        root / "template" / "service.sh",
        root / "template" / "action.sh",
        root / "template" / "uninstall.sh",
        root / "template" / "post-mount.sh",
        root / "runtime-template" / "customize.sh",
        root / "runtime-template" / "service.sh",
        root / "runtime-template" / "uninstall.sh",
        root / "runtime-template" / "post-mount.sh",
    ]
    for script in scripts:
        if script.is_file():
            res = subprocess.run([bash, "-n"], input=script.read_bytes(), capture_output=True)
            assert res.returncode == 0, f"Syntax error in {script.name}: {res.stderr.decode('utf-8', errors='ignore')}"

