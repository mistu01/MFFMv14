"""Unit tests for the pure-Python helpers in font_module."""

from __future__ import annotations

from pathlib import Path

import pytest

import font_module as fm


def face(
    name: str = "Test-Regular.ttf",
    *,
    weight: int = 400,
    style: str = "normal",
    condensed: bool = False,
    variable: bool = False,
    axes: dict[str, tuple[float, float, float]] | None = None,
    category: str = "sans",
    font_number: int | None = None,
    family: str = "Test Sans",
) -> fm.SourceFace:
    return fm.SourceFace(
        path=Path("/fonts") / name,
        font_number=font_number,
        family=family,
        style_name="Regular",
        weight=weight,
        style=style,
        condensed=condensed,
        variable=variable,
        axes=axes or {},
        sfnt_version="\x00\x01\x00\x00",
        category=category,
    )


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("Monospace/Whatever-Regular.ttf", "mono"),
        ("Mono/Whatever-Regular.ttf", "mono"),
        ("Serif/Whatever-Regular.ttf", "serif"),
        ("Sans/Whatever-Regular.ttf", "sans"),
        ("Sans-Serif/Whatever-Regular.ttf", "sans"),
        ("JetBrainsMono-Regular.ttf", "mono"),
        ("FiraCode-Regular.ttf", "mono"),
        ("Courier-Regular.ttf", "mono"),
        ("NotoSerif-Regular.ttf", "serif"),
        ("SourceSansSerif-Regular.ttf", "sans"),
        ("Inter-Regular.ttf", "sans"),
        # The directory wins over the filename.
        ("Serif/RobotoMono-Regular.ttf", "serif"),
    ],
)
def test_categorize(tmp_path: Path, relative: str, expected: str) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    assert fm.categorize(path, tmp_path) == expected


def test_source_face_is_hashable() -> None:
    """frozen=True advertises hashability; the axes dict must not break it."""
    assert len({face(), face()}) == 1


def test_dedupe_static_prefers_canonical_names() -> None:
    regular = face("Family-Regular.ttf")
    book = face("Family-Book.ttf")
    assert fm._dedupe_static([book, regular]) == [regular]


def test_dedupe_static_keeps_one_face_per_slot_and_sorts() -> None:
    faces = [
        face("Family-Bold.ttf", weight=700),
        face("Family-Italic.ttf", style="italic"),
        face("Family-Regular.ttf"),
        face("Family-CondensedRegular.ttf", condensed=True),
    ]
    result = fm._dedupe_static(faces)
    assert [(f.weight, f.style, f.condensed) for f in result] == [
        (400, "normal", False),
        (700, "normal", False),
        (400, "italic", False),
        (400, "normal", True),
    ]


def test_serif_fragment_falls_back_to_the_nearest_weight() -> None:
    entries = [(400, "normal", "<regular/>"), (900, "normal", "<black/>")]
    fragment = fm._serif_fragment(entries)
    # 700 has no exact match, so the nearest normal-style weight is reused instead of being dropped.
    assert fragment.splitlines() == ["<regular/>", "<black/>"]


def test_serif_fragment_drops_duplicates() -> None:
    assert fm._serif_fragment([(400, "normal", "<only/>")]) == "<only/>"


def test_supported_weights_is_clamped_to_the_axis_range() -> None:
    assert fm._supported_weights(face(axes={"wght": (300.0, 400.0, 700.0)})) == "300 400 500 600 700"


def test_supported_weights_without_a_wght_axis() -> None:
    """A variable font may expose only e.g. opsz; that must not raise."""
    assert fm._supported_weights(face(axes={"opsz": (8.0, 14.0, 60.0)})) == ""


def test_axis_metadata_without_a_wght_axis() -> None:
    meta = fm._axis_metadata(face(axes={"opsz": (8.0, 14.0, 60.0)}), italic=False)
    assert meta == "opsz|8|14|60"


def test_axis_values_clamps_and_resolves_italic_axes() -> None:
    axes = {"wght": (100.0, 400.0, 900.0), "ital": (0.0, 0.0, 1.0), "opsz": (8.0, 14.0, 60.0)}
    assert fm._axis_values(face(axes=axes), 700, True) == {"wght": 700.0, "ital": 1.0, "opsz": 14.0}
    assert fm._axis_values(face(axes=axes), 700, False)["ital"] == 0.0
    # Out of range weights are rejected rather than clamped.
    assert fm._axis_values(face(axes=axes), 1000, False) is None
    assert fm._axis_values(face(axes={}), 400, False) is None


def test_axis_values_uses_the_negative_end_of_slnt_for_italics() -> None:
    values = fm._axis_values(face(axes={"wght": (100.0, 400.0, 900.0), "slnt": (-10.0, 0.0, 0.0)}), 400, True)
    assert values["slnt"] == -10.0


def test_font_xml_emits_index_and_axes() -> None:
    assert fm._font_xml("DroidSans.ttf", 400, "normal", index=3) == (
        '    <font weight="400" style="normal" index="3">DroidSans.ttf</font>'
    )
    assert fm._font_xml("DroidSans.ttf", 700, "italic", index=0, axes={"wght": 700.0}).splitlines() == [
        '    <font weight="700" style="italic" index="0">DroidSans.ttf',
        '      <axis tag="wght" stylevalue="700"/>',
        "    </font>",
    ]


def test_face_indices_track_object_identity() -> None:
    """Two faces can compare equal but must still map to their own TTC index."""
    first, second = face(), face()
    indices = fm._FaceIndices()
    indices.assign(first, 0)
    indices.assign(second, 1)
    assert (indices(first), indices(second)) == (0, 1)
    with pytest.raises(SystemExit):
        indices(face())


def test_separate_primary_reuses_optional_faces_when_no_sans_exists() -> None:
    mono = face("Mono-Regular.ttf", category="mono")
    primary, mono_faces, serif_faces = fm._separate_primary_and_optional_faces([mono])
    assert serif_faces == []
    # Same objects, so _compile_* embeds them once instead of duplicating the collection.
    assert primary[0] is mono_faces[0]


def test_separate_primary_keeps_sans_separate() -> None:
    sans = face("Sans-Regular.ttf")
    mono = face("Mono-Regular.ttf", category="mono")
    primary, mono_faces, _serif = fm._separate_primary_and_optional_faces([sans, mono])
    assert primary == [sans]
    assert mono_faces == [mono]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Roboto Flex", "Roboto Mistu Flex"),
        ("Inter", "Inter Mistu"),
        ("Mistu Inter", "Mistu Inter"),
        ("MFFM Roboto Flex", "Roboto Mistu Flex"),
        ("", "Mistu"),
    ],
)
def test_transform_family_name(value: str, expected: str) -> None:
    assert fm.transform_family_name(value) == expected


def test_display_name_and_slug() -> None:
    assert fm.display_name_for_mode("Inter", "variable") == "Inter VF"
    assert fm.display_name_for_mode("Inter VF", "variable") == "Inter VF"
    assert fm.display_name_for_mode("Inter", "static") == "Inter"
    assert fm.slugify("[VF] Roboto Flex!") == "VF-Roboto-Flex"


def test_shell_quote_escapes_single_quotes() -> None:
    assert fm.shell_quote("it's") == "'it'\"'\"'s'"


def test_props_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "module.prop"
    fm.write_props(path, {"id": "mffm14", "name": "Test"})
    assert fm.read_props(path) == {"id": "mffm14", "name": "Test"}
