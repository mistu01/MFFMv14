"""The module ZIP has to carry every file customize.sh refuses to install without."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import build
import update

ROOT = Path(__file__).resolve().parents[1]
# customize.sh calls fail() when these are absent, so a ZIP without them cannot be installed.
REQUIRED = ("customize.sh", "fontlib.sh", "font-config", "font-config.sh")


def test_customize_requires_the_files_the_installer_checks() -> None:
    source = (ROOT / "customize.sh").read_text(encoding="utf-8")
    checked = set(re.findall(r'\[ -f "\$MODPATH/([\w.-]+)" \] \|\| fail', source))
    assert checked <= set(REQUIRED)


def test_build_payload_covers_every_required_file() -> None:
    assert set(REQUIRED) <= set(build.PAYLOAD_NAMES)


def test_update_template_covers_every_required_file() -> None:
    # font-config.sh is generated per build, so update.py stages the rest of the template.
    assert set(REQUIRED) - {"font-config.sh"} <= set(update.TEMPLATE_ITEMS)


def test_write_zip_marks_the_runtime_tool_executable(tmp_path: Path) -> None:
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    for name in REQUIRED:
        (module_dir / name).write_text("#!/system/bin/sh\n", encoding="utf-8")
    output = tmp_path / "module.zip"

    build.write_zip(module_dir, output)

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert set(REQUIRED) <= names
        assert archive.getinfo("font-config").external_attr >> 16 == 0o755
