"""Tests for MFFM Runtime module building, manifest verification, and CLI flags."""

import json
import zipfile
from pathlib import Path

import pytest
from build import ROOT
from build_runtime import RUNTIME_TEMPLATE, build_runtime, parse_args, sha256_file, verify_manifest


def test_build_runtime_zip(tmp_path):
    class Args:
        output_dir = tmp_path
        version = "1.5"
        version_code = "150"
        no_sign = True
        no_zip = False
        inspect = False

    output = build_runtime(Args())
    assert output is not None
    assert output.is_file()
    assert output.name == "mffm-runtime-1.5.zip"

    with zipfile.ZipFile(output, "r") as archive:
        names = archive.namelist()
        assert "module.prop" in names
        assert "customize.sh" in names
        assert "service.sh" in names
        assert "post-mount.sh" in names
        assert "uninstall.sh" in names
        assert "manifest.json" in names
        assert "META-INF/com/google/android/update-binary" in names

        # Check permissions
        for info in archive.infolist():
            perms = oct(info.external_attr >> 16)
            if info.filename.endswith(".sh") or info.filename.endswith("update-binary") or info.filename in ("python3", "mffm-helper"):
                assert perms == "0o755", f"{info.filename} should be 0o755, got {perms}"
            elif not info.is_dir():
                assert perms == "0o644", f"{info.filename} should be 0o644, got {perms}"

        # Verify module.prop contains overridden version
        prop_content = archive.read("module.prop").decode("utf-8")
        assert "version=1.5" in prop_content
        assert "versionCode=150" in prop_content
        assert "id=mffm_runtime" in prop_content


def test_build_py_runtime_flag(tmp_path):
    class Args:
        runtime = True
        template = False
        inspect = False
        fonts_dir = None
        mode = None
        name = None
        version = "2.0"
        version_code = "200"
        output_dir = tmp_path
        no_zip = False
        no_sign = True
        keep_hinting = False
        no_prefix = False
        features = None
        mono_features = None
        serif_features = None
        bengali_features = None
        interactive = False
        centered_colon = None
        config = None
        no_config = True
        save_config = False

    output = build_runtime(Args())
    assert output is not None
    assert output.is_file()
    assert output.name == "mffm-runtime-2.0.zip"


def test_verify_manifest_validation(tmp_path):
    # Verify the real template manifest passes
    real_manifest = RUNTIME_TEMPLATE / "manifest.json"
    data = verify_manifest(real_manifest)
    assert "version" in data and len(data["version"]) > 0

    # Verify SHA mismatch triggers SystemExit
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text(json.dumps({
        "version": "1.0",
        "sha256": {
            "aarch64": "0000000000000000000000000000000000000000000000000000000000000000"
        }
    }), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        verify_manifest(bad_manifest)
    assert "SHA256 mismatch" in str(exc_info.value)


def test_prepare_runtime_helpers(tmp_path):
    from prepare_runtime import _trim_stdlib

    lib = tmp_path / "lib" / "python3.11"
    lib.mkdir(parents=True)
    (lib / "test").mkdir()
    (lib / "test" / "dummy.py").write_text("test")
    (lib / "math.py").write_text("import os")
    (lib / "__pycache__").mkdir()
    (lib / "__pycache__" / "math.pyc").write_text("cache")

    sp = lib / "site-packages"
    sp.mkdir()
    (sp / "pip").mkdir()
    (sp / "pip" / "__init__.py").write_text("")
    (sp / "custom_pkg").mkdir()
    (sp / "custom_pkg" / "__init__.py").write_text("")

    _trim_stdlib(lib)

    assert not (lib / "test").exists()
    assert not (lib / "__pycache__").exists()
    assert not (sp / "pip").exists()
    assert (lib / "math.py").exists()
    assert (sp / "custom_pkg").exists()
