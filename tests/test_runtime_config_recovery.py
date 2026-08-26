"""Regression test for the on-device variable-axis config recovery.

When the MFFM Runtime on-device compiler (``mffm_runtime_helper``) regenerates
``font-config.sh`` mid-install, the build-time ``prepare_variable_config`` call
has already run against the *pre-compile* state. Without a re-evaluation the
``/sdcard/MFFM/MFFMv14_*.conf`` config file is either never created (static
build + user-dropped VF fonts) or carries stale weight keys that the
post-process cleanup gate later deletes.

This test exercises two behaviours of the patched ``template/customize.sh``:

1. The build-time / post-runtime gate now triggers on **any** VF_*_AXIS_META
   (including the previously-missing VF_UPRIGHT / VF_ITALIC axes for sans-serif
   variable fonts).
2. The post-process delete gate at end-of-install keeps **header-only** config
   files (those with a ``MODULE_IDENTITY=`` line but no ``*_WGHT``/``*_WDTH``
   keys) as an intentional marker, while still deleting truly-empty configs.

A static guardrail in the Python module also verifies the patch is in place so
the harness cannot pass on a vanilla customize.sh.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CUSTOMIZE_SH = ROOT / "template" / "customize.sh"
HARNESS = Path(__file__).parent / "shell" / "run_variable_config_recovery.sh"


def _find_usable_bash() -> str | None:
    for cand in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
        shutil.which("sh"),
    ):
        if cand and Path(cand).is_file():
            if "system32" in str(cand).lower():
                continue
            return str(cand)
    found = shutil.which("bash")
    return found if found and "system32" not in str(found).lower() else None


USABLE_BASH = _find_usable_bash()


def _run(
    tmp_path: Path,
    *,
    font_mode: str,
    vf_upright: str = "",
    vf_mono: str = "",
    config_has_wght: int = 0,
    config_has_identity: int = 1,
) -> dict:
    assert USABLE_BASH is not None
    mffm_dir = tmp_path / "MFFM"
    mffm_dir.mkdir()
    env = os.environ.copy()
    env["CONFIG_HAS_WGHT"] = str(config_has_wght)
    env["CONFIG_HAS_IDENTITY"] = str(config_has_identity)
    proc = subprocess.run(
        [USABLE_BASH, HARNESS.as_posix(), font_mode, vf_upright, vf_mono, mffm_dir.as_posix()],
        capture_output=True,
        env=env,
    )
    out = proc.stdout.decode("utf-8")
    err = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"harness failed:\n{err}\n--- stdout ---\n{out}"
    return {
        "stdout": out,
        "stderr": err,
        "files": sorted(p.name for p in mffm_dir.glob("MFFMv14_*.conf")),
    }


# ── Patch guardrails (always run, even without bash) ────────────────────────


def test_patched_customize_sh_has_post_runtime_re_evaluation():
    """Static guardrail: the patched customize.sh must contain the new block."""
    text = CUSTOMIZE_SH.read_text(encoding="utf-8")
    runtime_idx = text.find('"$_helper" compile-bundle')
    assert runtime_idx > 0, "runtime helper not found in customize.sh"
    re_eval_idx = text.find("Re-evaluate the variable-axis config after the on-device compiler")
    assert re_eval_idx > 0, "post-runtime re-evaluation block missing"
    assert re_eval_idx > runtime_idx, "re-evaluation must run after the runtime helper"
    # The build-time gate must now also include VF_UPRIGHT_AXIS_META and
    # VF_ITALIC_AXIS_META so a sans-serif VF module does not fall through.
    assert '"$VF_UPRIGHT_AXIS_META"' in text
    assert '"$VF_ITALIC_AXIS_META"' in text
    # The post-process delete gate must keep header-only config files.
    assert "header-only config files" in text
    assert "MODULE_IDENTITY[[:space:]]*=" in text


def test_patched_customize_sh_passes_bash_syntax_check():
    """The patched customize.sh must remain syntactically valid bash."""
    assert USABLE_BASH is not None, "no usable bash"
    proc = subprocess.run(
        [USABLE_BASH, "-n", CUSTOMIZE_SH.as_posix()],
        capture_output=True,
    )
    assert proc.returncode == 0, f"bash -n failed:\n{proc.stderr.decode('utf-8', errors='replace')}"


# ── Behavioural tests (require bash) ────────────────────────────────────────


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_build_time_gate_fires_on_vf_upright_axis_meta(tmp_path):
    """Sans-serif VF build with VF_UPRIGHT_AXIS_META only must trigger the gate."""
    result = _run(
        tmp_path,
        font_mode="static",   # build was static
        vf_upright="wght|300|400|700",  # but sans has VF axes
    )
    assert "GATE_TRIGGERED=1" in result["stdout"]


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_build_time_gate_fires_on_vf_mono_axis_meta(tmp_path):
    """Mono VF build must still trigger the gate (regression check)."""
    result = _run(
        tmp_path,
        font_mode="static",
        vf_mono="wght|300|400|700",
    )
    assert "GATE_TRIGGERED=1" in result["stdout"]


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_post_runtime_gate_fires_after_runtime_sets_variable_mode(tmp_path):
    """Static build + runtime that promoted FONT_MODE to variable must re-trigger."""
    result = _run(
        tmp_path,
        font_mode="runtime_variable",  # mocks runtime upgrading FONT_MODE
    )
    assert "POST_RUNTIME_GATE=1" in result["stdout"]


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_post_process_gate_keeps_header_only_config(tmp_path):
    """Header-only config (MODULE_IDENTITY but no *_WGHT) must be kept."""
    result = _run(
        tmp_path,
        font_mode="variable",
        config_has_wght=0,
        config_has_identity=1,
    )
    assert "POST_GATE_KEPT=1" in result["stdout"]
    assert "POST_GATE_DELETED=1" not in result["stdout"]
    assert result["files"], "config file should still exist after post-process gate"


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_post_process_gate_keeps_config_with_wght_keys(tmp_path):
    """Config with *_WGHT keys is always kept (regression check)."""
    result = _run(
        tmp_path,
        font_mode="variable",
        config_has_wght=1,
        config_has_identity=1,
    )
    assert "POST_GATE_KEPT=1" in result["stdout"]
    assert "POST_GATE_DELETED=1" not in result["stdout"]


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_post_process_gate_deletes_truly_empty_config(tmp_path):
    """Config with neither MODULE_IDENTITY nor *_WGHT is still deleted."""
    result = _run(
        tmp_path,
        font_mode="variable",
        config_has_wght=0,
        config_has_identity=0,
    )
    assert "POST_GATE_DELETED=1" in result["stdout"]
    assert "POST_GATE_KEPT=1" not in result["stdout"]
    assert not result["files"], "config file should be deleted"
