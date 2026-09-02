import os
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
CUSTOMIZE_SH = ROOT / "template" / "customize.sh"

def _find_bash():
    for cand in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
    ):
        if cand and Path(cand).is_file() and "system32" not in str(cand).lower():
            return str(cand)
    return None

BASH = _find_bash()

@pytest.mark.skipif(BASH is None, reason="bash required")
def test_config_isolation_and_cleanup(tmp_path):
    mffm_dir = tmp_path / "MFFM"
    mffm_dir.mkdir()

    # Create old Josefa config and an old log
    old_conf = mffm_dir / "MFFMv14_Josefa_Mistu_Rounded_Pro_vf-ef216fa30b0425888164.conf"
    old_conf.write_text(
        "# Font: Josefa Mistu Rounded Pro\nMODULE_IDENTITY=vf-ef216fa30b0425888164\nENABLE_CENTERED_COLON=yes\n",
        encoding="utf-8"
    )
    old_log = mffm_dir / "mffmv14_debug_20260901_000000.log"
    old_log.write_text("old log\n", encoding="utf-8")

    current_log = mffm_dir / "mffmv14_debug_current.log"

    # Create a small runner script that sources ensure_variable_config_file
    runner = tmp_path / "test_run.sh"
    runner.write_text(f"""#!/bin/bash
MFFM_DIR="{mffm_dir.as_posix()}"
MFFM_STORAGE="{tmp_path.as_posix()}"
LOG_DIR="{mffm_dir.as_posix()}"
LOG_FILE="{current_log.as_posix()}"
FONT_FAMILY="Spotify Mix UI Title Var VF"
VF_CONFIG_ID="vf-1070a4fc07773d6d24b2"
VF_CONFIG_SCHEMA="2"
ui_print() {{ echo "$1"; }}
fail() {{ echo "FAIL: $1" >&2; exit 1; }}

# Extract ensure_variable_config_file from customize.sh
sed -n '/^ensure_variable_config_file() {{/,/^}}/p' "{CUSTOMIZE_SH.as_posix()}" > /tmp/ensure_fn.sh
. /tmp/ensure_fn.sh
ensure_variable_config_file
echo "VF_CONFIG_FILE=$VF_CONFIG_FILE"
""", encoding="utf-8")

    proc = subprocess.run([BASH, runner.as_posix()], capture_output=True, text=True)
    assert proc.returncode == 0, f"Failed:\n{proc.stderr}\n{proc.stdout}"

    # Verify:
    # 1. Old Josefa config MUST BE GONE (deleted)
    assert not old_conf.exists(), "Old Josefa config should have been deleted!"
    # 2. Old log MUST BE GONE (deleted)
    assert not old_log.exists(), "Old debug log should have been deleted!"
    # 3. New Spotify config MUST EXIST
    spotify_conf = mffm_dir / "MFFMv14_Spotify_Mix_UI_Title_Var_VF_vf-1070a4fc07773d6d24b2.conf"
    assert spotify_conf.exists(), "Spotify config was not created!"
    content = spotify_conf.read_text(encoding="utf-8")
    assert "Spotify Mix UI Title Var VF" in content
    assert "vf-1070a4fc07773d6d24b2" in content
    assert "Josefa" not in content
    assert "vf-ef216fa30b0425888164" not in content


@pytest.mark.skipif(BASH is None, reason="bash required")
def test_config_reflash_preserves_own_config_and_deletes_others(tmp_path):
    mffm_dir = tmp_path / "MFFM"
    mffm_dir.mkdir()

    # Create existing Spotify config with user customized option
    spotify_conf = mffm_dir / "MFFMv14_Spotify_Mix_UI_Title_Var_VF_vf-1070a4fc07773d6d24b2.conf"
    spotify_conf.write_text(
        "# Font: Spotify Mix UI Title Var VF\nMODULE_IDENTITY=vf-1070a4fc07773d6d24b2\nENABLE_CENTERED_COLON=yes\nMETRICS_MODE=compact\n",
        encoding="utf-8"
    )

    # Some stale config from another experiment
    stale_conf = mffm_dir / "MFFMv14_SomeOtherFont_vf-999.conf"
    stale_conf.write_text("# Font: Other\nMODULE_IDENTITY=vf-999\n", encoding="utf-8")

    stale_log = mffm_dir / "mffmv14_debug_old.log"
    stale_log.write_text("old log\n", encoding="utf-8")

    current_log = mffm_dir / "mffmv14_debug_current2.log"

    runner = tmp_path / "test_reflash.sh"
    runner.write_text(f"""#!/bin/bash
MFFM_DIR="{mffm_dir.as_posix()}"
MFFM_STORAGE="{tmp_path.as_posix()}"
LOG_DIR="{mffm_dir.as_posix()}"
LOG_FILE="{current_log.as_posix()}"
FONT_FAMILY="Spotify Mix UI Title Var VF"
VF_CONFIG_ID="vf-1070a4fc07773d6d24b2"
VF_CONFIG_SCHEMA="2"
ui_print() {{ echo "$1"; }}
fail() {{ echo "FAIL: $1" >&2; exit 1; }}

sed -n '/^ensure_variable_config_file() {{/,/^}}/p' "{CUSTOMIZE_SH.as_posix()}" > /tmp/ensure_fn2.sh
. /tmp/ensure_fn2.sh
ensure_variable_config_file
echo "VF_CONFIG_FILE=$VF_CONFIG_FILE"
""", encoding="utf-8")

    proc = subprocess.run([BASH, runner.as_posix()], capture_output=True, text=True)
    assert proc.returncode == 0, f"Failed:\n{proc.stderr}\n{proc.stdout}"

    # Verify:
    # 1. Spotify config was preserved and has custom settings
    assert spotify_conf.exists()
    content = spotify_conf.read_text(encoding="utf-8")
    assert "ENABLE_CENTERED_COLON=yes" in content
    assert "METRICS_MODE=compact" in content

    # 2. Stale config and log are wiped out
    assert not stale_conf.exists()
    assert not stale_log.exists()


@pytest.mark.skipif(BASH is None, reason="bash required")
def test_corrupted_config_with_different_module_identity_is_discarded(tmp_path):
    """If a config file exists on disk with matching name but alien MODULE_IDENTITY, it must be discarded."""
    mffm_dir = tmp_path / "MFFM"
    mffm_dir.mkdir()

    # Pre-existing file with Spotify filename but hijacked Josefa identity and ENABLE_CENTERED_COLON=yes
    corrupted_conf = mffm_dir / "MFFMv14_Spotify_Mix_UI_Title_Var_VF_vf-1070a4fc07773d6d24b2.conf"
    corrupted_conf.write_text(
        "# Font: Josefa Mistu\nMODULE_IDENTITY=vf-ef216fa30b0425888164\nENABLE_CENTERED_COLON=yes\n",
        encoding="utf-8"
    )

    current_log = mffm_dir / "mffmv14_debug_current3.log"

    runner = tmp_path / "test_corrupt.sh"
    runner.write_text(f"""#!/bin/bash
MFFM_DIR="{mffm_dir.as_posix()}"
MFFM_STORAGE="{tmp_path.as_posix()}"
LOG_DIR="{mffm_dir.as_posix()}"
LOG_FILE="{current_log.as_posix()}"
FONT_FAMILY="Spotify Mix UI Title Var VF"
VF_CONFIG_ID="vf-1070a4fc07773d6d24b2"
VF_CONFIG_SCHEMA="2"
ui_print() {{ echo "$1"; }}
fail() {{ echo "FAIL: $1" >&2; exit 1; }}

# Extract clean_mod_slug and ensure_variable_config_file from customize.sh
sed -n '/^clean_mod_slug() {{/,/^}}/p' "{CUSTOMIZE_SH.as_posix()}" > /tmp/slug_fn.sh
sed -n '/^ensure_variable_config_file() {{/,/^}}/p' "{CUSTOMIZE_SH.as_posix()}" > /tmp/ensure_fn3.sh
. /tmp/slug_fn.sh
. /tmp/ensure_fn3.sh
ensure_variable_config_file
echo "VF_CONFIG_FILE=$VF_CONFIG_FILE"
""", encoding="utf-8")

    proc = subprocess.run([BASH, runner.as_posix()], capture_output=True, text=True)
    assert proc.returncode == 0, f"Failed:\n{proc.stderr}\n{proc.stdout}"

    # Verify:
    assert corrupted_conf.exists()
    content = corrupted_conf.read_text(encoding="utf-8")
    # Must have the correct module identity now
    assert "MODULE_IDENTITY=vf-1070a4fc07773d6d24b2" in content
    # Alien identity must be gone
    assert "vf-ef216fa30b0425888164" not in content
    # The hijacked ENABLE_CENTERED_COLON=yes must NOT be in the fresh file!
    assert "ENABLE_CENTERED_COLON=yes" not in content


@pytest.mark.skipif(BASH is None, reason="bash required")
def test_post_runtime_config_migration(tmp_path):
    """If font name table is sanitized at runtime, the post-compile gate must migrate the config cleanly."""
    mffm_dir = tmp_path / "MFFM"
    mffm_dir.mkdir()

    current_log = mffm_dir / "mffmv14_debug_current4.log"

    runner = tmp_path / "test_migration.sh"
    runner.write_text(f"""#!/bin/bash
MFFM_DIR="{mffm_dir.as_posix()}"
MFFM_STORAGE="{tmp_path.as_posix()}"
LOG_DIR="{mffm_dir.as_posix()}"
LOG_FILE="{current_log.as_posix()}"
FONT_FAMILY="Spotify Mix UI Title Var VF"
VF_CONFIG_ID="vf-1070a4fc07773d6d24b2"
VF_CONFIG_SCHEMA="2"
ui_print() {{ echo "$1"; }}
fail() {{ echo "FAIL: $1" >&2; exit 1; }}

sed -n '/^clean_mod_slug() {{/,/^}}/p' "{CUSTOMIZE_SH.as_posix()}" > /tmp/slug_fn.sh
sed -n '/^ensure_variable_config_file() {{/,/^}}/p' "{CUSTOMIZE_SH.as_posix()}" > /tmp/ensure_fn4.sh
. /tmp/slug_fn.sh
. /tmp/ensure_fn4.sh

# 1. Pre-compile config creation
prepare_variable_config() {{
  ensure_variable_config_file
}}
prepare_variable_config
echo "PRE_CONFIG=$VF_CONFIG_FILE"

# User had customized this file
echo "ENABLE_CENTERED_COLON=no" >> "$VF_CONFIG_FILE"
echo "METRICS_MODE=safe" >> "$VF_CONFIG_FILE"

# 2. Simulate runtime compile updating FONT_FAMILY to sanitized name
FONT_FAMILY="Spotify Mistu Mix UI Title Var"
_prev_vf_conf="$VF_CONFIG_FILE"
VF_CONFIG_FILE=""
prepare_variable_config
if [ -n "$_prev_vf_conf" ] && [ -f "$_prev_vf_conf" ] && [ "$_prev_vf_conf" != "$VF_CONFIG_FILE" ]; then
  cp -f "$_prev_vf_conf" "$VF_CONFIG_FILE" 2>/dev/null && rm -f "$_prev_vf_conf" 2>/dev/null
fi
echo "POST_CONFIG=$VF_CONFIG_FILE"
""", encoding="utf-8")

    proc = subprocess.run([BASH, runner.as_posix()], capture_output=True, text=True)
    assert proc.returncode == 0, f"Failed:\n{proc.stderr}\n{proc.stdout}"

    # Verify:
    # 1. Old pre-compile file should be gone
    old_conf = mffm_dir / "MFFMv14_Spotify_Mix_UI_Title_Var_VF_vf-1070a4fc07773d6d24b2.conf"
    assert not old_conf.exists()

    # 2. New migrated file should exist and retain settings
    new_conf = mffm_dir / "MFFMv14_Spotify_Mistu_Mix_UI_Title_Var_vf-1070a4fc07773d6d24b2.conf"
    assert new_conf.exists()
    content = new_conf.read_text(encoding="utf-8")
    assert "ENABLE_CENTERED_COLON=no" in content
    assert "METRICS_MODE=safe" in content



