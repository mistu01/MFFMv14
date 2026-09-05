# Changelog

All notable changes to MFFMv14 are documented here. Dates use the `YYYY.MM.DD`
versioning scheme the modules themselves carry.

## 2026.09.06

### Documentation & Public Release Architecture
- **Three-Tier Documentation Separation**:
  - Redesigned `ReadMe.md` into a modern GitHub repository frontpage and project showcase featuring compatibility badges, feature highlight summaries, architecture overview, quickstarts, and community links.
  - Refactored `USAGE_GUIDE.md` into an exhaustive end-user and theme-maker manual (step-by-step module packaging for Android file managers and PC, comprehensive `/sdcard/MFFM/*.conf` parameter guide, troubleshooting & FAQ). Packaged inside `MFFMv14-Source-Template.zip`.
  - Authored `docs/DEVELOPER.md` delivering in-depth technical documentation covering the Decoupled Safe Metrics engine mathematics, OpenType GSUB Format 6 contextual colon lookup assembly, tabular digit equalization, Zygote table pruning, dual runtime detection mechanics, and complete developer CLI tool reference.

### Improved
- **Module Migration Utility (`update.py`) Modernization**:
  - Upgraded font discovery (`find_categorized_sources`) to use recursive `rglob` and `classify_source_path()`, providing native support for both legacy flat modules and modern structured subdirectories (`Files/Sans/`, `Files/Monospace/`, etc.).
  - Added single-file input support (`--input` / `-i`), allowing direct migration of individual module ZIPs.
  - Synchronized output ZIP filename slug generation with `build.py` to include applied OpenType features.
  - Pruned obsolete, unused `TEMPLATE_ITEMS` constant.

## 2026.09.03

### Added
- **On-Device CFF/OTF Conversion (`otf2ttf`) & `cu2qu`**:
  - Implemented pure-Python cubic-to-quadratic Bezier conversion on-device using `fontTools.pens.cu2quPen.Cu2QuPen`.
  - Converts OpenType PostScript fonts (`.otf`, `.otc`, `sfntVersion == 'OTTO'`) to TrueType quadratic tables (`glyf`, `loca`, `maxp` v1.0).
  - Automatically converts CFF/OTF fonts to TrueType before bundling into `/system/fonts/DroidSans.ttf`, preventing font engine crashes on OEM Android skins (Samsung OneUI, Xiaomi HyperOS) and enabling centered colon injection for OTF fonts.
  - New standalone CLI command: `mffm-helper otf2ttf --in <font.otf> [--out <font.ttf>]`.
- **Advanced Lockscreen Typography: Tabular Digits & Flexible Colon Controls**:
  - **Tabular Digit Equalization (`equalize_clock_digits`)**: Dynamically equalizes horizontal advance widths across digits `0`–`9` and centers contours/composites. Eliminates lockscreen clock number jumping and horizontal wobble when ticking between digits.
  - **Flexible Clock Colon Positioning**: Added `alignment` (`center` on digits, `cap_height` on caps, `x_height` on lowercase) and fine-tuned vertical `offset` (+/- font units).
  - **Contextual Colon Rules**: Added `rule` options: `between_digits` (single-line clocks `12:30`), `after_digit` (for stacked 2-line clocks `12:` / `30`), and `always`.
  - New standalone CLI command: `mffm-helper equalize-digits --in <font> [--out <out>] [--width <width>]`.
- **Smart Metric Harmonization & Zero-Clipping Engine (`METRICS_MODE`)**:
  - **Proportional FFIX3 Ratio Auto-Clamping (`safe` mode)**: Audits actual glyph bounding boxes (`actual_yMax`, `actual_yMin`) and calculates the expansion factor $k = \max(1.0, \, k_{\text{ascent}}, \, k_{\text{descent}})$. Expands ascent and descent proportionally, guaranteeing zero accent/diacritic clipping for multilingual scripts (Vietnamese `ế`, `Ậ`, Devanagari, Thai, Arabic, tall capitals `Å`, `Ŵ`) while strictly preserving the FFIX3 baseline ratio ($\approx 3.869$).
  - Full multi-table synchronization across `hhea` (ascent/descent/lineGap), `OS/2` (sTypoAscender/Descender/LineGap, usWinAscent/Descent), and `head` (yMax/yMin).
  - Selectable modes: `safe` (default, auto-clamp), `compact` (classic fixed FFIX3), and `preserve` (original font metrics).
- **Table Optimization & Dead Table Pruning for Android Zygote (`optimize_font_tables`)**:
  - Implemented automatic pruning of dead and bloat tables (`DSIG`, `VDMX`, `hdmx`, `LTSH`, `PCLT`, `EBDT`/`EBLC`, `FFTM`, Apple AAT tables, and Macintosh Roman duplicate name records).
  - Eliminates `logcat` warnings on Android caused by dummy digital signatures (`DSIG`) and reduces TTC size by 10–30%, directly saving memory in Android's Zygote process across every running app.
  - Normalizes `gasp` table for clean subpixel anti-aliasing across all point sizes.
  - Fully configurable via `ENABLE_ZYGOTE_OPTIMIZATION=no` (default: false, preserving original font tables; set to `yes` for maximum size and RAM savings).
  - New standalone CLI command: `mffm-helper optimize --in <font> [--out <out>] [--keep-hinting]`.
- **Name Table Sanitization & Version Pinning**:
  - Automatically inserts `Mistu` after the first word of the font family name: single-word families become `Word Mistu` (e.g. `Roboto` -> `Roboto Mistu`), while multi-word families become `Word Mistu Other` (e.g. `Amazon Ember` -> `Amazon Mistu Ember`, `Josefa Rounded Pro` -> `Josefa Mistu Rounded Pro`).
  - Appends `;Mistu` to the font's version string in `nameID 5` (e.g. `Version 1.000;Mistu`).
  - Synchronizes Full Name (`nameID 4`), PostScript Name (`nameID 6`), and sets Manufacturer (`nameID 8`) to `Mistu @ MFFM Inc.`.
- **Enforced Fatal Abort When MFFM Runtime is Missing**:
  - `template/customize.sh` now strictly enforces that the companion MFFM Runtime module is installed before allowing any font module to install.
  - If `mffm-runtime` is missing, the installer immediately halts execution via `fail`, displays a prominent error banner directing the user to the Telegram download link (`https://t.me/MFFMMain`), and aborts the flash so no broken/unprocessed font files are installed into root.
- **Decoupled Safe Metrics Engine (Ascender Bloat Prevention)**:
  - Decoupled ascent and descent expansion in `safe` metrics mode: ascent only expands when tall accents exceed `base_ascent` (`1039` at 1000 UPM), and descent expands independently when descenders exceed `base_descent` (`-269`).
  - Eliminates line height inflation on monospace and display fonts with deep descenders (like `SpotifyMixMono`), dropping line height from `1702` back down to `1389` and restoring standard terminal log text size and window proportions.
- **Comprehensive Configuration & Onboarding Guidance**:
  - Re-architected `/sdcard/MFFM/*.conf` generation in `template/customize.sh` with beginner-friendly explanations, option breakdowns, and clear defaults.
  - Added dedicated Configuration Options cheat sheet and guide in `USAGE_GUIDE.md`.
- **Variable Font Config Isolation, Clean Categorization & Automatic Section Ordering**:
  - Variable font axis configuration is now strictly positioned at the top of `/sdcard/MFFM/*.conf` directly below the module header, beautifully categorized with distinct section headers (`# SANS-SERIF / UPRIGHT`, `# CONDENSED / UPRIGHT`, `# MONOSPACE / UPRIGHT`, etc.) and clean spacing.
  - Implemented `reformat_config_file()` in `template/customize.sh`: dynamically reorders legacy or scrambled configs, sorting axes sections to the top and `# ADVANCED TYPOGRAPHY & LOCKSCREEN CLOCK SETTINGS` to the bottom while preserving 100% of user customization values.
  - Exported variable font axis metadata (`VF_*_AXIS_META`, `VF_*_WEIGHTS`) into `font-config.sh` and packaged into module zips by `build.py`, eliminating pre-compilation axis discovery misses.
  - Added early on-the-fly axis detection in `prepare_variable_config()` for manual modules, guaranteeing profile keys are generated with full categorization headers even before runtime bundle compilation.

## 2026.08.31

### Added
- **On-Device Centered Clock Colon Detection & Injection**:
  - `mffm-helper` scans the Sans-serif font at install time. If missing, automatically adds an `ENABLE_CENTERED_COLON=no` block with instructions to `/sdcard/MFFM/*.conf`.
  - When enabled by the user (`ENABLE_CENTERED_COLON=yes` or `true`), the installer dynamically generates a `colon.case` glyph contour and injects a contextual substitution rule (`[0-9] + colon + [0-9] -> [0-9] + colon.case + [0-9]`) into `calt` on-device.
- **On-Device OpenType Feature Discovery, Reporting & Freezing**:
  - `mffm-helper` scans all available fonts across Sans, Monospace, Serif, and Bengali (internal and `/sdcard/MFFM/`).
  - Generates a categorized report (`[RECOMMENDED / SAFE TO FREEZE]`, `[CAUTION]`, `[SYSTEM / NOT RECOMMENDED]`) directly into `.conf` with `SANS_FREEZE_FEATURES=`, `MONO_FREEZE_FEATURES=`, `SERIF_FREEZE_FEATURES=`, `BENGALI_FREEZE_FEATURES=`.
  - On reflash, executes pure-Python `fontTools` 1-to-1 `cmap` remapping (`SingleSubst`/`AlternateSubst`) and contextual lookup promotion (`calt`/`liga`) on-the-fly without requiring external binary tools.
- **On-Device Name Table Sanitization**:
  - `mffm-helper` automatically cleans brand noise, standardizes family names, sets Full Name (`nameID` 4), PostScript Name (`nameID` 6), Version (`nameID` 5), and Manufacturer (`nameID` 8) during compilation.
- **New CLI Subcommands in `mffm-helper`**:
  - `report-features`: Discovers and formats available OpenType layout features per category.
  - `check-colon`: Inspects whether a font has a centered colon feature.
  - `inject-colon`: Injects a centered colon into a standalone font file.
  - `freeze-features`: Freezes specified feature tags into a standalone font file.
  - `compile-bundle`: Added `--enable-centered-colon`, `--freeze-sans`, `--freeze-mono`, `--freeze-serif`, `--freeze-bengali`, `--no-sanitize-names`.
- **Full WOFF & WOFF2 Web Font Support On-Device & in Builder**:
  - `mffm-helper` and `template/customize.sh` now discover and compile `.woff` and `.woff2` files (in addition to `.ttf`, `.otf`, `.ttc`, `.otc`).
  - Web font containers are automatically unflavored and decompressed into native TrueType tables when bundled into the unified `DroidSans.ttf` TTC.
- **Static Multi-400 Face Preference Scoring (`face_preference_score`)**:
  - Implemented `face_preference_score()` in `runtime_helper.py` to match `build.py`'s scoring hierarchy. When multiple 400 normal faces are present (e.g. `Regular`, `Book`, `Normal`), `Regular` is consistently prioritized as the primary face and the deduplicated slot choice.
- **Pure Plug-and-Play Template Architecture**:
  - Eliminated the separate `font-config.sh` placeholder requirement from the template — `customize.sh` now initializes dynamically and derives metadata from `module.prop` and font binaries on-the-fly.
  - Users can create modules manually by simply dropping fonts into `Files/Sans/` and zipping the folder with any standard file manager.
- **MFFM Runtime Check & Telegram Download Trigger**:
  - Added install-time verification in `template/customize.sh` that checks for `mffm-runtime`. If missing, it outputs an informative warning banner and automatically opens the official Telegram channel (`https://t.me/MFFMMain`) to download the runtime.

### Fixed
- **Google Font Protection Boot Logging (`service.sh` & `action.sh`)**:
  - Added dynamic storage path resolution (`get_mffm_dir()`) probing across `/storage/emulated/0`, `/data/media/0`, `/mnt/pass_through/0/emulated/0`, and `/sdcard`.
  - Added a readiness wait loop for decrypted user storage at boot so `font_service.log` is reliably mirrored to `/sdcard/MFFM/font_service.log`.
- **Debug & Action Log Cleanup**:
  - Installer now automatically purges all stale historical debug and action logs (`mffmv14_debug_*.log`, `mffmv14_runtime_*.log`, `action.log`, etc.) from `/sdcard/MFFM`, keeping only the current run's log.
- **Dynamic Centered Colon Glyph Bounds**:
  - Fixed `KeyError: 'xMin'` during TTCollection saving by invoking `new_glyph.recalcBounds(glyf)` on dynamically generated `colon.case` glyph contours.
- **Installer Compilation Error Logging**:
  - Removed silent `>/dev/null 2>&1` suppression from `compile-bundle` in `template/customize.sh`, redirecting full output to `$LOG_FILE` with exit code verification.
- **Output Target Exclusion in Scanner**:
  - Excluded generated output targets (`DroidSans.ttf`, `DroidSans.ttc`, etc.) from input face collection in `runtime_helper.py` to prevent recursive re-ingestion of previously compiled TTC files.

### Changed
- **Streamlined Public Distribution**:
  - Removed `termux-build.sh` in favor of zero-tool manual ZIP creation.
  - `MFFMv14-Source-Template.zip` now distributes the clean, standalone template directly at root.
- **Automated Test Suite**:
  - Test suite covers centered colon detection/injection, name sanitization, feature reporting/freezing, WOFF/WOFF2 compilation, multi-400 deduplication, and POSIX shell syntax guards.

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
