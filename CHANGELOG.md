# Changelog

All notable changes to MFFMv14 are documented here. Dates use the `YYYY.MM.DD`
versioning scheme the modules themselves carry.

## Unreleased

### Added
- Regression test suite (`tests/`) with synthetic fontTools-generated fixtures —
  no binary test fonts needed. Covers weight detection, TTC packing, XML
  fragment generation, config handling and reproducible archives.
- Shared weight-resolution test vectors (`tests/weight_vectors.json`) consumed
  by both the Python engine tests and a shell harness that extracts
  `find_best_face` live from `template/customize.sh`, so the build-time and
  flash-time weight engines cannot silently drift apart.
- Build configuration file support: `.mffm-build.json` is auto-loaded when
  present, `--config <path>` loads an explicit file, `--no-config` ignores
  configs, and `--save-config` persists the effective options for one-keystroke
  repeat builds. Explicit CLI flags always beat config values.
- `--inspect` flag for `build.py`: reports detected faces, weights, styles,
  axes, per-family modes and warnings without building anything.
- Reproducible build output: `write_zip` honours `SOURCE_DATE_EPOCH`
  (clamped to the 1980 ZIP epoch), enabling byte-identical rebuilds.
- GitHub Actions CI (`.github/workflows/ci.yml`): pytest matrix, POSIX syntax
  checks, advisory shellcheck, reproducible fixture-module build and source
  template artifact.
- `tests/make_fixture_fonts.py` for smoke builds in CI or manual testing.
- `requirements-dev.txt` with the test dependencies.

### Changed
- ZipSignerust downloads are now supply-chain pinned: exact release tag plus
  SHA-256 digests for every platform binary, verified after download and for
  cached copies. A re-published release fails the check instead of executing.
- Font categories (Sans/Monospace/Serif/Bengali) are driven by a data
  registry (`FONT_CATEGORIES`) in `font_module.py` instead of hard-coded
  if/elif chains; adding a script family on the build side is now mostly a
  table entry.
- Template copying unified: `build.py` and `update.py` share one
  `copy_template()` implementation instead of two drifting variants.
- The installer now keeps the three most recent `mffmv14_debug_*.log` files
  (configurable via `MFFM_LOG_KEEP`) instead of deleting every previous log,
  and no longer touches unrelated `*.log` files in `/sdcard/MFFM/`.
- `template/font-config.sh` placeholder neutralized (was carrying stale
  values from an old Amazon Ember build) and documents that it is regenerated
  at build time.

### Removed
- Ghost entries (`MFFMv14_DISTRIBUTION_GUIDE.txt`, `RELEASE_NOTES.txt`) from
  `package_template.py`'s include list.

## 2026.08.14

- Improved weight detection (hybrid OS/2 + name-table resolution), templating
  and installer bundling.
- Neutral template placeholders and refreshed documentation.

## 2026.08.09

- Per-family centered-colon prompts and GSUB creation fix.

## 2026.08.08

- Documentation overhaul and enhanced installer bundling.

## 2026.08.07

- Smart `find_best_face` weight & style resolution engine in `customize.sh`;
  external fonts in `/sdcard/MFFM/` subdirectories accepted with any filename.
- Static external Bengali fonts bundled into the `NotoSansBengali-VF.ttf` TTC
  container with per-weight `index=` XML entries (100–900).
- Variable axis configurations saved for Bengali, Monospace and Serif in
  `/sdcard/MFFM/*.conf`, with obsolete profile keys pruned on reflash.
- Native variable-font binary parsing in the installer (no fontTools needed
  for external variable fonts).

## 2026.08.06

- Initial v14 template: full 100–900 weight-class support for Bengali,
  auto-created MFFM subdirectories, TTC payload compilation and signed
  flashable ZIP output.
