"""Reproducible-archive tests for write_zip / SOURCE_DATE_EPOCH handling."""

import hashlib

import pytest

from build import write_zip, zip_timestamp


def sha256(path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def make_module(tmp_path):
    module = tmp_path / "module"
    (module / "Files").mkdir(parents=True)
    (module / "module.prop").write_text("id=fixture\n", encoding="utf-8", newline="\n")
    (module / "customize.sh").write_text("#!/system/bin/sh\n", encoding="utf-8", newline="\n")
    (module / "Files" / "sans.xml").write_text("<font/>\n", encoding="utf-8", newline="\n")
    return module


def test_same_epoch_produces_identical_zips(tmp_path, monkeypatch):
    module = make_module(tmp_path)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1723680000")
    first = tmp_path / "a.zip"
    second = tmp_path / "b.zip"
    write_zip(module, first)
    write_zip(module, second)
    assert sha256(first) == sha256(second)


def test_different_epochs_produce_different_zips(tmp_path, monkeypatch):
    module = make_module(tmp_path)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1723680000")
    first = tmp_path / "a.zip"
    write_zip(module, first)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    second = tmp_path / "b.zip"
    write_zip(module, second)
    assert sha256(first) != sha256(second)


def test_epoch_clamped_to_zip_era(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1")
    assert zip_timestamp()[0] == 1980


def test_invalid_epoch_rejected(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
    with pytest.raises(SystemExit, match="SOURCE_DATE_EPOCH"):
        zip_timestamp()
