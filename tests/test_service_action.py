"""Tests for Google font update blocker service (service.sh) and fallback action (action.sh)."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "template"


def test_service_and_action_files_exist():
    service_sh = TEMPLATE_DIR / "service.sh"
    action_sh = TEMPLATE_DIR / "action.sh"
    assert service_sh.is_file(), "template/service.sh missing"
    assert action_sh.is_file(), "template/action.sh missing"


def test_service_sh_content():
    content = (TEMPLATE_DIR / "service.sh").read_text(encoding="utf-8")
    assert "cmd font clear" in content
    assert "/data/fonts" in content
    assert "com.google.android.gms.fonts.provider.FontsProvider" in content
    assert "com.google.android.gms.fonts.update.UpdateSchedulerService" in content
    assert "service.pid" in content
    assert "--daemon" in content


def test_action_sh_content():
    content = (TEMPLATE_DIR / "action.sh").read_text(encoding="utf-8")
    assert "cmd font clear" in content
    assert "/data/fonts" in content
    assert "com.google.android.gms.fonts.provider.FontsProvider" in content
    assert "com.google.android.gms.fonts.update.UpdateSchedulerService" in content
    assert "Google Font Update Neutralizer" in content
    assert "service.pid" in content


def test_template_and_font_module_packaging(tmp_path):
    # Test that action.sh and service.sh are included across all module packaging configs
    from build import PAYLOAD_NAMES
    from font_module import TEMPLATE_COPY_ITEMS
    from update import TEMPLATE_ITEMS
    from package_template import build_template_zip

    assert "action.sh" in PAYLOAD_NAMES
    assert "service.sh" in PAYLOAD_NAMES
    assert "action.sh" in TEMPLATE_COPY_ITEMS
    assert "service.sh" in TEMPLATE_COPY_ITEMS
    assert "action.sh" in TEMPLATE_ITEMS
    assert "service.sh" in TEMPLATE_ITEMS

    out_zip = build_template_zip(tmp_path)
    with zipfile.ZipFile(out_zip, "r") as z:
        names = z.namelist()
        assert "service.sh" in names
        assert "action.sh" in names
        assert "customize.sh" in names
        assert "module.prop" in names
        assert "USAGE_GUIDE.md" in names
        assert "CHANGELOG.md" in names
