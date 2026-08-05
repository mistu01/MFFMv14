"""Tests for the axis substitution shared by customize.sh and system/bin/font-config.

font-config is the on-device tool that re-applies edited axis values without a re-flash. It runs
against a fake module tree here: `mffm/` holds what the installer saved (metadata, fontlib, pristine
fragments and the ROM's untouched XML), and the module's own fonts.xml is rebuilt from it.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FONTLIB = ROOT / "fontlib.sh"
FONT_CONFIG = ROOT / "font-config"

STUBS = f"""
ui_print() {{ echo "$*"; }}
status_warn() {{ echo "WARN: $*" >&2; }}
status_ok() {{ :; }}
status_skip() {{ :; }}
fail() {{ echo "FAIL: $*" >&2; exit 1; }}
. "{FONTLIB}"
"""

SANS_FRAGMENT = """    <font weight="400" style="normal" index="0">DroidSans.ttf
      <axis tag="wght" stylevalue="400"/>
      <axis tag="opsz" stylevalue="14"/>
    </font>
    <font weight="700" style="normal" index="0">DroidSans.ttf
      <axis tag="wght" stylevalue="700"/>
      <axis tag="opsz" stylevalue="14"/>
    </font>
"""

FONTS_XML = """<?xml version="1.0" encoding="utf-8"?>
<familyset version="23">
  <family name="sans-serif">
    <font weight="400" style="normal">Roboto-Regular.ttf</font>
  </family>
  <family lang="und-Arab">
    <font weight="400" style="normal">NotoNaskhArabic-Regular.ttf</font>
  </family>
</familyset>
"""

METADATA = """FONT_MODE='variable'
FONT_FAMILY='Test Variable'
FONT_FILES='DroidSans.ttf'
FONT_PRIMARY='DroidSans.ttf'
VF_CONFIG_SCHEMA='2'
VF_CONFIG_ID='vf-0123456789abcdef0123'
VF_UPRIGHT_AXIS_META='wght|100|400|900 opsz|8|14|144'
VF_ITALIC_AXIS_META=''
VF_UPRIGHT_WEIGHTS='400 700'
VF_ITALIC_WEIGHTS=''
"""

CONFIG = """CONFIG_SCHEMA=2
MODULE_IDENTITY=vf-0123456789abcdef0123
SANS_UPRIGHT_REGULAR_WGHT=350
SANS_UPRIGHT_BOLD_WGHT=650
SANS_UPRIGHT_OPSZ=24
"""


def font_config_argv(module: Path) -> list[str]:
    """font-config takes explicit paths rather than reading them from the environment."""
    return [
        "sh", str(FONT_CONFIG),
        "--module-path", str(module),
        "--config-dir", str(module / "sdcard-MFFM"),
    ]


def run_shell(script: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", "-c", script], cwd=cwd, capture_output=True, text=True, check=True)


def axis_values(family: ET.Element) -> dict[tuple[str, str], str]:
    return {
        (font.get("weight", ""), axis.get("tag", "")): axis.get("stylevalue", "")
        for font in family
        for axis in font
    }


def fragment_axis_values(fragment: str) -> dict[tuple[str, str], str]:
    return axis_values(ET.fromstring(f"<family>{fragment}</family>"))


@pytest.fixture
def module(tmp_path: Path) -> Path:
    """A module tree in the state customize.sh leaves behind for a variable build."""
    runtime = tmp_path / "mffm"
    (runtime / "fragments").mkdir(parents=True)
    (runtime / "original").mkdir()
    (runtime / "fragments" / "sans.xml").write_text(SANS_FRAGMENT, encoding="utf-8")
    (runtime / "original" / "fonts.xml").write_text(FONTS_XML, encoding="utf-8")
    (runtime / "fontlib.sh").write_text(FONTLIB.read_text(encoding="utf-8"), encoding="utf-8")
    (runtime / "font-config.sh").write_text(METADATA, encoding="utf-8")

    etc = tmp_path / "system" / "etc"
    etc.mkdir(parents=True)
    # The installed copy still carries the values from the last flash.
    (etc / "fonts.xml").write_text(FONTS_XML, encoding="utf-8")

    settings = tmp_path / "sdcard-MFFM"
    settings.mkdir()
    (settings / "MFFMv14_Test_Variable_vf-0123456789abcdef0123.conf").write_text(CONFIG, encoding="utf-8")
    return tmp_path


def test_apply_axis_profiles_substitutes_configured_values(tmp_path: Path) -> None:
    fragment = tmp_path / "sans.xml"
    fragment.write_text(SANS_FRAGMENT, encoding="utf-8")
    config = tmp_path / "axes.conf"
    config.write_text(CONFIG, encoding="utf-8")

    run_shell(
        f'{STUBS}\n'
        f'VF_CONFIG_FILE="{config}" VF_CONFIG_CREATED=0\n'
        f"VF_UPRIGHT_AXIS_META='wght|100|400|900 opsz|8|14|144' VF_UPRIGHT_WEIGHTS='400 700'\n"
        f"VF_ITALIC_AXIS_META='' VF_ITALIC_WEIGHTS=''\n"
        f'apply_axis_profiles "{tmp_path}"',
        tmp_path,
    )

    assert fragment_axis_values(fragment.read_text(encoding="utf-8")) == {
        ("400", "wght"): "350",
        ("400", "opsz"): "24",
        ("700", "wght"): "650",
        ("700", "opsz"): "24",
    }


def test_apply_axis_profiles_resets_an_out_of_range_value(tmp_path: Path) -> None:
    fragment = tmp_path / "sans.xml"
    fragment.write_text(SANS_FRAGMENT, encoding="utf-8")
    config = tmp_path / "axes.conf"
    config.write_text("SANS_UPRIGHT_REGULAR_WGHT=1200\n", encoding="utf-8")

    result = run_shell(
        f'{STUBS}\n'
        f'VF_CONFIG_FILE="{config}" VF_CONFIG_CREATED=0\n'
        f"VF_UPRIGHT_AXIS_META='wght|100|400|900' VF_UPRIGHT_WEIGHTS='400'\n"
        f"VF_ITALIC_AXIS_META='' VF_ITALIC_WEIGHTS=''\n"
        f'apply_axis_profiles "{tmp_path}"',
        tmp_path,
    )

    assert "WARN:" in result.stderr
    assert "SANS_UPRIGHT_REGULAR_WGHT=400" in config.read_text(encoding="utf-8")
    assert fragment_axis_values(fragment.read_text(encoding="utf-8"))[("400", "wght")] == "400"


def test_font_config_rebuilds_the_installed_xml(module: Path) -> None:
    result = subprocess.run(
        font_config_argv(module),
        cwd=module,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr

    root = ET.fromstring((module / "system" / "etc" / "fonts.xml").read_text(encoding="utf-8"))
    named = next(f for f in root.iter("family") if f.get("name") == "sans-serif")
    assert [font.text.strip() for font in named] == ["DroidSans.ttf", "DroidSans.ttf"]
    assert axis_values(named) == {
        ("400", "wght"): "350",
        ("400", "opsz"): "24",
        ("700", "wght"): "650",
        ("700", "opsz"): "24",
    }
    # Unrelated families and the pristine snapshot survive a re-apply.
    assert any(f.get("lang") == "und-Arab" for f in root.iter("family"))
    assert (module / "mffm" / "original" / "fonts.xml").read_text(encoding="utf-8") == FONTS_XML
    # The staging directory is cleaned up.
    assert not (module / "mffm" / ".work").exists()


def test_font_config_is_idempotent(module: Path) -> None:
    env = {"PATH": "/usr/bin:/bin"}
    installed = module / "system" / "etc" / "fonts.xml"
    subprocess.run(font_config_argv(module), cwd=module, env=env, check=True, capture_output=True)
    first = installed.read_text(encoding="utf-8")
    subprocess.run(font_config_argv(module), cwd=module, env=env, check=True, capture_output=True)

    assert installed.read_text(encoding="utf-8") == first


def test_font_config_refuses_a_static_module(module: Path) -> None:
    (module / "mffm" / "font-config.sh").write_text(
        METADATA.replace("FONT_MODE='variable'", "FONT_MODE='static'"), encoding="utf-8"
    )
    before = (module / "system" / "etc" / "fonts.xml").read_text(encoding="utf-8")

    result = subprocess.run(
        font_config_argv(module),
        cwd=module,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 1
    assert "static" in result.stderr
    assert (module / "system" / "etc" / "fonts.xml").read_text(encoding="utf-8") == before


def test_font_config_needs_the_saved_runtime_payload(tmp_path: Path) -> None:
    result = subprocess.run(
        font_config_argv(tmp_path),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 1
    assert "re-flash" in result.stderr
