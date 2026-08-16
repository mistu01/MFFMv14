"""Tests for build.py's config-file loading, merging and saving."""

import argparse
import json

import pytest

from build import (
    ROOT,
    apply_build_config,
    load_build_config,
    save_build_config,
)


def make_args(**overrides):
    defaults = dict(
        fonts_dir=None, mode=None, name=None, version=None, version_code=None,
        output_dir=None, no_zip=None, no_sign=None, keep_hinting=None,
        no_prefix=None, features=None, mono_features=None, serif_features=None,
        bengali_features=None, interactive=None, centered_colon=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_load_rejects_unknown_keys(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"bogus": 1}), encoding="utf-8")
    with pytest.raises(SystemExit, match="Unknown keys"):
        load_build_config(path)


def test_load_rejects_non_object(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="JSON object"):
        load_build_config(path)


def test_config_fills_unset_options(tmp_path):
    config = {
        "fonts_dir": "MyFonts",
        "features": "ss01",
        "keep_hinting": True,
        "centered_colon": False,
    }
    args = make_args()
    apply_build_config(args, config, "cfg.json")
    assert args.fonts_dir == ROOT / "MyFonts"
    assert args.features == "ss01"
    assert args.keep_hinting is True
    assert args.centered_colon is False
    assert args.mode == "auto"
    assert args.output_dir == ROOT / "dist"


def test_cli_flags_beat_config(tmp_path):
    config = {"features": "ss01", "fonts_dir": "Configured"}
    args = make_args(features="zero")
    apply_build_config(args, config, "cfg.json")
    assert args.features == "zero"
    assert args.fonts_dir == ROOT / "Configured"


def test_save_and_roundtrip(tmp_path):
    args = make_args(
        features="ss01,zero", centered_colon=True, interactive=False,
        fonts_dir=ROOT / "Fonts", output_dir=ROOT / "dist",
        keep_hinting=None,
    )
    path = tmp_path / "cfg.json"
    save_build_config(path, args)

    data = load_build_config(path)
    assert data["features"] == "ss01,zero"
    assert data["centered_colon"] is True
    assert data["interactive"] is False
    assert data["keep_hinting"] is False  # unset tri-state normalizes to False
    assert data["fonts_dir"] == "Fonts"   # stored relative to the project root

    restored = make_args()
    apply_build_config(restored, data, None)
    assert restored.features == "ss01,zero"
    assert restored.centered_colon is True
    assert restored.fonts_dir == ROOT / "Fonts"


def test_absolute_font_dir_roundtrips(tmp_path):
    outside = tmp_path / "elsewhere" / "Fonts"
    args = make_args(fonts_dir=outside, output_dir=ROOT / "dist")
    path = tmp_path / "cfg.json"
    save_build_config(path, args)
    data = load_build_config(path)
    assert data["fonts_dir"] == str(outside)
    restored = make_args()
    apply_build_config(restored, data, None)
    assert restored.fonts_dir == outside
