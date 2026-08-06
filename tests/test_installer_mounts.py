"""Tests for the mount-view helpers in fontlib.sh.

The installer has to read the ROM's untouched fonts.xml while another font module may already have
an overlay in the way. These tests drive the helpers with a fake /proc/mounts, so they cover which
paths are considered pristine and which mounts the installer is willing to tear down.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

FONTLIB = Path(__file__).resolve().parents[1] / "fontlib.sh"

# A booted KernelSU device: the ROM's own /system, another module's overlay over /system, an
# unrelated module's overlay over /product, and a font module bind-mounted over fonts.xml.
MOUNTS = """\
/dev/block/dm-4 /system erofs ro,seclabel 0 0
/dev/block/dm-6 /system_ext ext4 ro,seclabel 0 0
overlay /system overlay ro,lowerdir=/data/adb/modules/other/system:/system 0 0
overlay /product overlay ro,lowerdir=/data/adb/modules/tweaks/product:/product 0 0
/dev/block/dm-4 /system_ext/etc/fonts.xml erofs ro,seclabel 0 0
"""


def run(script: str, mounts: Path, roots: str = "") -> subprocess.CompletedProcess[str]:
    stubs = f"""
ui_print() {{ echo "$*"; }}
status_warn() {{ echo "WARN: $*" >&2; }}
status_ok() {{ :; }}
status_skip() {{ :; }}
fail() {{ echo "FAIL: $*" >&2; exit 1; }}
. "{FONTLIB}"
MFFM_MOUNTS="{mounts}"
{f'MFFM_MODULE_ROOTS="{roots}"' if roots else ""}
{script}
"""
    return subprocess.run(["sh", "-c", stubs], capture_output=True, text=True)


@pytest.fixture
def mounts(tmp_path: Path) -> Path:
    path = tmp_path / "mounts"
    path.write_text(MOUNTS, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("path", "covered"),
    [
        ("/system/etc/fonts.xml", True),  # /system carries another module's overlay
        ("/product/etc/fonts_customization.xml", True),
        ("/system_ext/etc/fonts.xml", False),  # only the ROM's own erofs mounts above it
        ("/vendor/etc/fonts.xml", False),
    ],
)
def test_covered_by_module_overlay_only_matches_module_mounts(
    mounts: Path, path: str, covered: bool
) -> None:
    result = run(f'covered_by_module_overlay "{path}"', mounts)
    assert (result.returncode == 0) is covered


def test_pristine_file_skips_candidates_under_an_overlay(tmp_path: Path, mounts: Path) -> None:
    overlaid = tmp_path / "overlaid.xml"
    overlaid.write_text("x", encoding="utf-8")
    clean = tmp_path / "clean.xml"
    clean.write_text("x", encoding="utf-8")
    # Pretend the first candidate lives under a mount an unrelated module owns.
    mounts.write_text(f"overlay {tmp_path} overlay ro,lowerdir=/system 0 0\n", encoding="utf-8")
    assert run(f'pristine_file "{overlaid}" "{clean}"', mounts).stdout.strip() == ""

    mounts.write_text(MOUNTS, encoding="utf-8")
    assert run(f'pristine_file "{overlaid}" "{clean}"', mounts).stdout.strip() == str(overlaid)


def test_pristine_file_ignores_missing_candidates(tmp_path: Path, mounts: Path) -> None:
    present = tmp_path / "present.xml"
    present.write_text("x", encoding="utf-8")
    result = run(f'pristine_file "{tmp_path}/absent.xml" "{present}"', mounts)
    assert result.stdout.strip() == str(present)


def test_snapshot_file_finds_a_previous_installs_untouched_copy(
    tmp_path: Path, mounts: Path
) -> None:
    modules = tmp_path / "modules"
    saved = modules / "mffm14" / "mffm" / "original"
    saved.mkdir(parents=True)
    (saved / "fonts.xml").write_text("pristine", encoding="utf-8")

    result = run("snapshot_file fonts.xml", mounts, roots=str(modules))
    assert result.stdout.strip() == str(saved / "fonts.xml")
    assert run("snapshot_file font_fallback.xml", mounts, roots=str(modules)).returncode == 1
    assert run("snapshot_file fonts.xml", mounts, roots=str(tmp_path / "empty")).returncode == 1


def test_refresh_mount_view_only_unmounts_the_font_xml_files(mounts: Path) -> None:
    # umount is stubbed out: what matters is that nothing but the six font XML paths is attempted.
    result = run(
        'umount() { echo "UMOUNT $*"; }\nrefresh_mount_view',
        mounts,
    )
    attempted = [line.split()[-1] for line in result.stdout.splitlines() if "UMOUNT" in line]
    assert attempted == ["/system_ext/etc/fonts.xml"]
    assert "/system" not in attempted
    assert "/product" not in attempted
