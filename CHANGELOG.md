# Changelog

All notable changes to MFFMv14 are documented here. Dates use the `YYYY.MM.DD`
versioning scheme the modules themselves carry.

## 2026.08.27

### Fixed
- **On-device variable-axis config was not being created when the MFFM Runtime
  helper kicked in.** The build-time `prepare_variable_config` call in
  `template/customize.sh` runs *before* the on-device compiler, which then
  refreshes `font-config.sh` (and can promote `FONT_MODE` from `static` to
  `variable` plus populate new `VF_*_AXIS_META` data). The installer now
  re-evaluates the gate after the runtime helper and rebuilds the
  `/sdcard/MFFM/MFFMv14_*.conf` file from the refreshed variables. The
  build-time gate also now includes `VF_UPRIGHT_AXIS_META` and
  `VF_ITALIC_AXIS_META` so a sans-serif VF module no longer falls through.
  The post-process delete gate at end-of-install now keeps header-only
  config files (those carrying `MODULE_IDENTITY=` but no `*_WGHT`/`*_WDTH`
  keys) as an intentional "no Android axes to expose" marker, while still
  deleting truly-empty configs.
- **`serif-monospace` family incorrectly overwritten by Serif fallback.** When
  a custom Monospace font (`mono.xml`) was provided, the Serif section of the
  installer was still overwriting the `serif-monospace` XML family entry with
  the Serif font instead of the Monospace font. The Serif section now guards
  its `replace_family … serif-monospace` call with
  `if [ ! -f "$FONT_DIR/mono.xml" ]`, so a custom Monospace font always wins
  the `serif-monospace` family slot.

### Added
- **Google Font Update Neutralizer** (`template/service.sh` + `template/action.sh`):
  Automatic boot-time protection against AOSP `FontManagerService` (`/data/fonts`)
  and Google Play Services font provider overrides, plus an on-demand action
  script for KernelSU / APatch / MMRL.
  - `service.sh` — runs at late-start boot after `sys.boot_completed=1`:
    - Executes `cmd font clear` to reset `FontManagerService` to the system
      partition.
    - Recursively purges `/data/fonts`, `/data/fonts/files/`,
      `/data/fonts/config/`, and `/data/system/font_fallback.xml`.
    - Disables `com.google.android.gms.fonts.provider.FontsProvider` and
      `com.google.android.gms.fonts.update.UpdateSchedulerService` via
      `pm disable` / `pm disable-user --user 0` / `cmd package disable-user`.
    - Purges GMS downloaded font caches across `/data/data/…`, `/data/user/0/…`,
      `/data/user_de/0/…`, and `/data/data/…/app_fonts/`.
    - Spawns a **background watcher daemon** (PID saved to `$MODDIR/service.pid`)
      that polls every hour and neutralizes any newly staged Google font updates.
    - Also invocable standalone as `sh service.sh --daemon` to start only
      the watcher loop without the boot sequence.
    - Dual-writes logs to `$MODDIR/font_service.log` and
      `/sdcard/MFFM/font_service.log`.
  - `action.sh` — on-demand user-triggered neutralization:
    - Executable via the KernelSU / APatch / MMRL "Action" button, or via
      `su -c sh /data/adb/modules/<module_id>/action.sh` from any root shell.
    - Displays a diagnostic banner, runs the full neutralization routine
      (same steps as `service.sh`), then checks whether the background
      protection daemon is alive (via `$MODDIR/service.pid`). If dead or
      missing, automatically restarts it.
- **Runtime helper `compile-bundle` now exports axis metadata** into
  `font-config.sh` so `template/customize.sh` can read variable-axis
  information after on-device compilation. All `VF_*_AXIS_META` and
  `VF_*_WEIGHTS` variables are now populated correctly for every family
  (Sans upright/italic, Monospace, Serif upright/italic, Bengali).
- `tests/test_runtime_config_recovery.py` + `tests/shell/run_variable_config_recovery.sh`:
  regression coverage for the post-runtime config flow. Includes a
  `bash -n` syntax guardrail and a static check that the patch is present
  in `template/customize.sh`, so the suite fails immediately if a future
  refactor removes the recovery block.
- `tests/test_service_action.py`: automated tests verifying that
  `template/service.sh` and `template/action.sh` exist on disk, contain the
  required functional keywords (`cmd font clear`, `neutralize_google_fonts`,
  `--daemon`, `service.pid`), and are present in the template package lists
  in `font_module.py`, `build.py`, and `update.py`.
- **MFFM Runtime module (`mffm_runtime`)**: Standalone portable Python 3 +
  `fontTools` execution environment installed to `/data/adb/mffm_runtime`,
  eliminating Termux dependency for font modules.
- `prepare_runtime.py`: Downloads pinned musl-static CPython binaries from
  python-build-standalone, trims standard libraries, installs pure-python
  `fontTools`, and creates ABI payload archives with SHA-256 supply-chain
  pins in `runtime-template/manifest.json`.
- `build_runtime.py` and `build.py --runtime`: Builds and cryptographically
  signs the flashable `mffm-runtime-<version>.zip` module.
- Runtime packaging and POSIX shell syntax checks integrated into GitHub
  Actions CI (`.github/workflows/ci.yml`).
- Unit tests for runtime building, manifest verification, and stdlib pruning
  in `tests/test_runtime_build.py`.
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
- `template/service.sh` upgraded from a no-op stub to the full Google Font
  Update Neutralizer daemon (boot cleaner + background watcher).
- `template/action.sh` added to all packaging lists: `PAYLOAD_NAMES` in
  `build.py`, `TEMPLATE_COPY_ITEMS` in `font_module.py`, and `TEMPLATE_ITEMS`
  in `update.py`. Permissions set to `0755` in `template/customize.sh`.
- CI POSIX syntax check and shellcheck now cover `template/action.sh`
  alongside the other shell scripts.

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
