"""Tests for the awk XML rewriters in customize.sh.

The installer cannot be run off-device, but its XML surgery is pure text processing: the shell
functions are extracted and executed with `sh` against a captured fonts.xml snippet, and the output
has to stay well-formed XML.
"""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

CUSTOMIZE = Path(__file__).resolve().parents[1] / "customize.sh"

STUBS = """
status_warn() { echo "WARN: $*" >&2; }
status_ok() { :; }
fail() { echo "FAIL: $*" >&2; exit 1; }
"""

FONTS_XML = """<?xml version="1.0" encoding="utf-8"?>
<familyset version="23">
  <family name="sans-serif">
    <font weight="400" style="normal">Roboto-Regular.ttf</font>
    <font weight="700" style="normal">Roboto-Bold.ttf</font>
  </family>
  <family name="monospace">
    <font weight="400" style="normal">DroidSansMono.ttf</font>
  </family>
  <family lang="und-Beng" variant="elegant">
    <font weight="400" style="normal">NotoSerifBengali-VF.ttf</font>
  </family>
  <family lang="und-Arab">
    <font weight="400" style="normal">NotoNaskhArabic-Regular.ttf</font>
  </family>
</familyset>
"""


def shell_function(name: str) -> str:
    source = CUSTOMIZE.read_text(encoding="utf-8")
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}$", source, re.MULTILINE | re.DOTALL)
    assert match, f"{name}() not found in customize.sh"
    return match.group(0)


def run_shell(script: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", "-c", script], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def xml_file(tmp_path: Path) -> Path:
    path = tmp_path / "fonts.xml"
    path.write_text(FONTS_XML, encoding="utf-8")
    return path


def test_replace_family_rewrites_a_multiline_family(tmp_path: Path, xml_file: Path) -> None:
    fragment = tmp_path / "mono.xml"
    fragment.write_text('    <font weight="400" style="normal" index="1">DroidSans.ttf</font>\n', encoding="utf-8")

    run_shell(f'{STUBS}\n{shell_function("replace_family")}\nreplace_family "{xml_file}" monospace "{fragment}"', tmp_path)

    root = ET.fromstring(xml_file.read_text(encoding="utf-8"))
    mono = next(f for f in root.iter("family") if f.get("name") == "monospace")
    assert [font.text for font in mono] == ["DroidSans.ttf"]
    # Unrelated families are untouched.
    assert len(next(f for f in root.iter("family") if f.get("name") == "sans-serif")) == 2
    assert any(f.get("lang") == "und-Arab" for f in root.iter("family"))


def test_replace_family_splits_the_sans_family(tmp_path: Path, xml_file: Path) -> None:
    fragment = tmp_path / "sans.xml"
    fragment.write_text('    <font weight="400" style="normal" index="0">DroidSans.ttf</font>\n', encoding="utf-8")

    run_shell(f'{STUBS}\n{shell_function("replace_family")}\nreplace_family "{xml_file}" sans-serif "{fragment}"', tmp_path)

    root = ET.fromstring(xml_file.read_text(encoding="utf-8"))
    named = next(f for f in root.iter("family") if f.get("name") == "sans-serif")
    assert [font.text for font in named] == ["DroidSans.ttf"]
    # The original fonts move into an unnamed fallback family instead of being dropped.
    unnamed = [f for f in root.iter("family") if not f.attrib]
    assert [font.text for font in unnamed[0]] == ["Roboto-Regular.ttf", "Roboto-Bold.ttf"]


def test_replace_family_refuses_a_single_line_family(tmp_path: Path) -> None:
    """Rewriting a one-line family would swallow every family up to the next </family>."""
    xml = tmp_path / "fonts.xml"
    xml.write_text(
        '<familyset version="23">\n'
        '  <family name="monospace"><font weight="400" style="normal">DroidSansMono.ttf</font></family>\n'
        '  <family lang="und-Arab">\n'
        '    <font weight="400" style="normal">NotoNaskhArabic-Regular.ttf</font>\n'
        "  </family>\n"
        "</familyset>\n",
        encoding="utf-8",
    )
    fragment = tmp_path / "mono.xml"
    fragment.write_text('    <font weight="400" style="normal" index="1">DroidSans.ttf</font>\n', encoding="utf-8")
    before = xml.read_text(encoding="utf-8")

    result = run_shell(
        f'{STUBS}\n{shell_function("replace_family")}\nreplace_family "{xml}" monospace "{fragment}"', tmp_path
    )

    assert "WARN:" in result.stderr
    assert xml.read_text(encoding="utf-8") == before


def test_replace_beng_family_replaces_in_place(tmp_path: Path, xml_file: Path) -> None:
    script = f'{STUBS}\n{shell_function("replace_beng_family")}\nreplace_beng_family "{xml_file}" elegant'
    run_shell(script, tmp_path)

    root = ET.fromstring(xml_file.read_text(encoding="utf-8"))
    beng = [f for f in root.iter("family") if f.get("lang") == "und-Beng"]
    assert len(beng) == 1
    assert [font.text for font in beng[0]] == [
        "NotoSansBengali-VF.ttf",
        "NotoSerifBengali-VF.ttf",
        "NotoSansBengaliUI-VF.ttf",
    ]
    # The family that follows must survive; the old sed range consumed it on toybox.
    assert any(f.get("lang") == "und-Arab" for f in root.iter("family"))


def test_replace_beng_family_refuses_a_single_line_family(tmp_path: Path) -> None:
    """Replacing whole lines would drop whatever else the ROM packed onto the Bengali line."""
    xml = tmp_path / "fonts.xml"
    xml.write_text(
        '<familyset version="23">\n'
        '  <family lang="und-Arab">\n'
        '    <font weight="400" style="normal">NotoNaskhArabic-Regular.ttf</font>\n'
        '  </family><family lang="und-Beng" variant="elegant">\n'
        '    <font weight="400" style="normal">NotoSerifBengali-VF.ttf</font>\n'
        "  </family>\n"
        "</familyset>\n",
        encoding="utf-8",
    )
    before = xml.read_text(encoding="utf-8")

    result = run_shell(
        f'{STUBS}\n{shell_function("replace_beng_family")}\nreplace_beng_family "{xml}" elegant', tmp_path
    )

    assert "WARN:" in result.stderr
    assert xml.read_text(encoding="utf-8") == before


def test_replace_beng_family_is_a_no_op_without_a_match(tmp_path: Path, xml_file: Path) -> None:
    before = xml_file.read_text(encoding="utf-8")
    run_shell(
        f'{STUBS}\n{shell_function("replace_beng_family")}\nreplace_beng_family "{xml_file}" compact', tmp_path
    )
    assert xml_file.read_text(encoding="utf-8") == before
