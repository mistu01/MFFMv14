# Changelog

All notable changes to MFFMv14 are documented here. Dates use the `YYYY.MM.DD`
versioning scheme the modules themselves carry.

## 2026.09.24

### Added
- **Roboto Underline Position and Thickness Harmonization Across All Metrics Modes (`runtime_helper.py`, `font_module_standalone.py`, `runtime-template/customize.sh`, `template/customize.sh`, `build.py`, `build_standalone.py`)**:
  - Harmonizes font underline metrics (`post.underlinePosition` and `post.underlineThickness`) to Android's reference Roboto measurements across **all** vertical metrics modes: `safe`, `compact`, and `intact` / `preserve`.
  - Proportional scaling applied based on target font `unitsPerEm`:
    $$\text{underlinePosition} = \text{round}\left(-150 \times \frac{\text{upem}}{2048}\right)$$
    $$\text{underlineThickness} = \max\left(1, \text{round}\left(100 \times \frac{\text{upem}}{2048}\right)\right)$$
  - Fixes misplaced, sunken, clipped, or zero-thickness underlines in Android `TextView` hyperlinks and WebViews when using custom fonts with non-standard underline metrics, while leaving designer ascender/descender line spacing completely untouched in `preserve`/`intact` mode.
  - Added `"intact"` as a recognized first-class alias for `"preserve"` across CLI flags (`--metrics-mode intact`), interactive wizard prompts, and `/sdcard/MFFM/*.conf` configurations (`METRICS_MODE=intact`).
  - Corrected on-device dynamic compilation and module metadata (`module.prop`) reporting so that all metrics modes (including `preserve` and `intact`) are properly tracked and displayed in root manager UI.

## 2026.09.23

### Added
- **Standalone SemiBold-as-Medium & SemiBoldItalic-as-MediumItalic Fallback (`template-standalone/customize.sh` & `font_module_standalone.py`)**:
  - Automatically maps SemiBold (600) to Medium (500) for external Bengali and Serif static fonts lacking a native Medium weight face.
  - For external Serif fonts, when MediumItalic (500 italic) is not present and upright Medium is also missing, SemiBoldItalic (600 italic) is automatically used as MediumItalic.
  - Expands static Bengali fallback to 3 faces (`Regular`, `SemiBold-as-Medium`, `Bold`) and static Serif fallback to up to 6 faces (`Regular`, `Italic`, `SemiBold-as-Medium`, `SemiBoldItalic-as-MediumItalic`, `Bold`, `BoldItalic`).
  - Emits corresponding `weight="500"` XML entries referencing the SemiBold / SemiBoldItalic face indices in unified TTC with zero added overhead.
- **Automated MFFM Runtime Build & Release Pipeline (`.github/workflows/runtime-auto-release.yml` & `check_runtime_updates.py`)**:
  - Automatically queries PyPI for `fonttools` updates and GitHub for `astral-sh/python-build-standalone` CPython updates on a daily schedule.
  - Automatically updates supply-chain pins, compiles static musl ABI payloads, signs the runtime module, and publishes GitHub releases.
- **Universal Font Subsetter & Runtime Optimization Engine (`runtime_helper.py`, `template/customize.sh`, `font_module.py`, `font_module_standalone.py`, `build.py`, `build_standalone.py`)**:
  - Added universal font subsetting across both standalone (`build_standalone.py`) and regular (`build.py`) builders, as well as on-device dynamic compilation via MFFM Runtime (`template/customize.sh`).
  - **Smart PUA Preservation**: Retains developer & UI glyphs including Apple logo (`0xF8FF`), Powerline status line symbols, Nerd Fonts BMP glyphs, Material Design Icons Plane 15 (`0xF0001–0xF1AF0`), and Web icons (`0xE900–0xEF50`), while eliminating proprietary Apple SF Symbols in Plane 16 (`0x100000–0x10FFFD`, 8,400+ unused glyphs) and unassigned Plane 15 ranges (`0xF1AF1–0xFFFFD`).
  - **Chinese, Japanese, and Korean (CJK) Script Removal**: Completely purges CJK ideographs (Main block `0x4E00–0x9FFF`, Ext A through H `0x3400–0x4DBF`, `0x20000–0x323AF`), Japanese Kana (Hiragana `0x3040–0x309F`, Katakana `0x30A0–0x30FF`, Kana Supplements), Korean Hangul (Syllables `0xAC00–0xD7AF`, Jamo `0x1100–0x11FF`, Extended A & B), Bopomofo, and Fullwidth forms (`0xFF00–0xFFEF`), shedding tens of thousands of unused glyphs and megabytes of memory.
  - **Android Noto Color Emoji Safe**: Automatically strips monochrome outline duplicates that conflict with Android's system `NotoColorEmoji` (Plane 1 pictographs `0x1F000–0x1FAFF`, Misc Symbols `0x2600–0x26FF`, Dingbats `0x2700–0x27BF`).
  - **Language Guard**: All non-CJK spoken languages (Latin, Cyrillic, Greek, Arabic, Hebrew, Devanagari, Bengali, Thai, Vietnamese, etc.) and diacritics are strictly guarded via Unicode category verification (`L*` letters and `M*` marks) and never dropped.
  - **Automatic Font Size Detection (> 1 MB)**:
    - In standalone and regular builders, fonts larger than 1 MB automatically trigger the subset prompt in interactive mode (`[?] Enable font subsetting? [Y/n]`) or auto-enable in non-interactive mode.
    - CLI flags `--subset` and `--no-subset` provide explicit control and are persisted in `.mffm-build.json`.
    - In on-device installer (`template/customize.sh`), `.conf` generation measures primary font size and automatically recommends `ENABLE_SUBSET_FONTS=yes` when font size > 1 MB.
- **Horizontal Font Tracking & Letter-Spacing Control (`runtime_helper.py`, `font_module.py`, `font_module_standalone.py`, `build.py`, `build_standalone.py`, `template/customize.sh`, `runtime-template/customize.sh`)**:
  - Added character tracking / letter-spacing adjustment across both regular (`build.py`) and standalone (`build_standalone.py`) builders via CLI flags (`--tracking`, `--letter-spacing`, `--sans-tracking`, `--mono-tracking`, `--serif-tracking`, `--bengali-tracking`) and `.mffm-build.json` configuration options.
  - Added on-device runtime configuration support in `/sdcard/MFFM/*.conf` via `FONT_TRACKING=...` (fallback `TRACKING=...`) to allow real-time tuning on Android devices without repacking module ZIPs.
  - Standardized tracking units to $1/1000\text{ em}$ ($\Delta W = \text{round}(tracking \times upem / 1000)$) for consistent visual spacing across different font UPMs (1000, 2048, etc.).
  - Symmetrical optical centering: adds $\Delta W / 2$ to Left Sidebearing (LSB) and Right Sidebearing (RSB) while expanding advance width by $\Delta W$, ensuring glyphs remain centered within their character cell.
  - Zero-width combining mark / diacritic safety: preserves zero-advance glyphs (`orig_adv == 0`) with zero shift, ensuring accents stay anchored to base characters.
  - TrueType composite glyph safety: recalculates composite bounding boxes (`g.recalcBounds(glyf)`) without double-shifting nested component contours.
- **Separated Module Output Folders in `dist/` (`build.py`, `build_standalone.py`, `update.py`, `termux-build.sh`)**:
  - Regular modules built with `build.py` (and updated via `update.py`) are now cleanly output to `dist/Regular/`.
  - Standalone modules built with `build_standalone.py` (and `termux-build.sh`) are now cleanly output to `dist/Standalone/`.
  - Prevents filename collisions and unintentional overwrites when building both regular and standalone packages for the same font family in the same workspace.
  - Automatically routes legacy `dist` paths from config files and CLI flags to their respective dedicated subdirectories (`dist/Regular` or `dist/Standalone`), while preserving custom paths.
  - Standalone template package includes `dist/Standalone/` skeleton out of the box.

## 2026.09.11

### Added
- **Standalone Readymade Module Builder (`build_standalone.py` & `template-standalone/`)**:
  - Re-introduced a dedicated standalone builder workflow for users who prefer pre-compiled font packages over dynamic on-device compilation.
  - All font transformations (TTC bundling, `DroidSans.ttf`, OpenType feature freezing, metrics harmonization, PUA colon, synthetic italic, and XML fragments) are executed upfront at build time on PC or Termux.
  - Generates completely self-contained modules that require **zero** on-device Python or `mffm-runtime` prerequisite and install in 1–2 seconds.
  - Backed by dedicated `template-standalone/` payload and `font_module_standalone.py`.
  - **Standardized External Static Fallback Faces**:
    - **Serif**: 4–6 faces default (`NotoSerif-Regular.ttf` 400 normal, `NotoSerif-Italic.ttf` 400 italic, `NotoSerif-Bold.ttf` 700 normal, `NotoSerif-BoldItalic.ttf` 700 italic, plus optional `Medium` 500 / SemiBold-as-Medium).
    - **Bengali**: 2–3 faces default (`NotoSansBengali-VF.ttf` / `Regular` 400, `NotoSansBengaliUI-VF.ttf` / `Bold` 700, plus optional `Medium` 500 / SemiBold-as-Medium).
    - **Monospace**: 1 face default (`DroidSansMono.ttf` / `CutiveMono.ttf` 400 normal).
    - **SemiBold-as-Medium Fallback**: If external Bengali or Serif fonts lack a Medium (500) weight but contain SemiBold (600), the standalone module maps that SemiBold face as Medium in system font configurations.
    - Pure shell execution with zero on-device TTC bundling or Python dependencies for external static fonts.
  - **100% Python & fontTools Dependency-Free Module Installer**:
    - Completely decoupled the standalone module (`template-standalone/customize.sh`) from `python`, `python3`, `pip`, and `fonttools`.
    - Implemented a high-speed, binary `fvar` table parser in pure POSIX shell and `awk` using `od -tx1`, enabling autonomous variable font axis scanning for external fonts dropped into `/sdcard/MFFM` without any runtime dependencies.
  - **Enhanced Centered Clock Colon & Build-Time Processing Parity**:
    - Integrated full feature set into `build_standalone.py` and `font_module_standalone.py`:
      - **Vertical Colon Shift**: Added `--colon-offset` / `--colon-shift` to adjust colon height upward (+) or downward (-) in font units when default optical centering needs OEM adjustment.
      - **Colon Alignment Target**: Added `--colon-alignment` (`center`, `cap_height`, `x_height`).
      - **Contextual Rule Selection**: Added `--colon-rule` (`between_digits`, `after_digit`, `always`).
      - **Digit Equalization**: Added `--equalize-digits` to eliminate lockscreen clock wobble.
      - **PUA Colon Mapping**: Added `--pua-colon` to mirror colons to `U+EE01`, `U+2236`, and `U+2982`.
      - **Interactive Prompts**: Interactive feature check now prompts for custom colon shift offset when approved.
      - **Full Config Persistence**: `.mffm-build.json` saves and restores all colon, alignment, rule, and digitization flags.
- **Mobile Termux One-Shot Builder (`termux-build.sh`)**:
  - Brought back the mobile Termux environment builder script (`termux-build.sh`).
  - Automatically provisions the Termux Python/fontTools toolchain, runs `build_standalone.py` (or `--runtime` for `build.py`), and prompts to flash the generated ZIP via `su` with Magisk, KernelSU, or APatch.
- **Standalone Template Archive Packaging (`MFFMv14-Standalone-Template.zip`)**:
  - Packaged all required standalone tools into `dist/MFFMv14-Standalone-Template.zip`.
  - Includes `build_standalone.py`, `font_module_standalone.py`, `runtime_helper.py`, `zipsigner_auto.py`, `termux-build.sh`, `requirements.txt`, convenience `build.py` wrapper, complete `template-standalone/` payload (`customize.sh`, `action.sh`, `font-config.sh`, `module.prop`, `post-mount.sh`, `service.sh`, `uninstall.sh`, `META-INF/`, `Files/`), directory skeletons with `.gitkeep` (`Fonts/Sans`, `Fonts/Monospace`, `Fonts/Serif`, `Fonts/Bengali`, `dist`), and documentation (`USAGE_GUIDE.md`, `CHANGELOG.md`, `ReadMe.md`).
  - Added `--standalone-template` flag to `build.py` and `--standalone` / `--all` flags to `package_template.py`.

### Performance & Fixes
- **Faster On-Device OTF→TTF (CFF/PostScript) Conversion** (`runtime_helper.py` & `font_module.py`):
  - **Multi-core per-glyph conversion** (`glyphs_to_quadratic`): Each glyph's cubic→quadratic (cu2qu) conversion runs concurrently in a `ThreadPoolExecutor` (up to 4 workers on mobile, 8 on PC). The CFF charstring decode step inside `glyph.draw()` releases the GIL, enabling true parallel execution across CPU cores.
  - **CFF pre-processing before cu2qu** (`otf_to_ttf`): Applies `desubroutinize()` (flattens subr call-stacks) and `remove_hints()` (strips obsolete CFF stem and counter hints) prior to curve conversion, cutting charstring bytecode by 30–50% on complex fonts.
  - **Sequential font-by-font iteration**: Restored clean sequential font-level processing in `compile_bundle()` to prevent mobile CPU thread thrashing and ensure continuous, real-time UI progression in Magisk/KernelSU terminal output.
  - **POSIX-compliant installer keepalive** (`template/customize.sh`): Replaced non-standard `\s` regex in `grep` with POSIX-standard `grep '\[\*\]'`, ensuring the active font status and elapsed time are reliably extracted on toybox shells.

## 2026.09.10

### Added
- **Live On-Device Font Compilation Progress Streaming**:
  - Replaced static heartbeat polling timer in `template/customize.sh` with a real-time progress streamer.
  - Automatically captures and prints newly emitted status lines from the background compilation helper (`compile-bundle`) directly to the root manager terminal (`ui_print`).
  - Implemented keepalive heartbeat fallback every 6 seconds during intensive per-glyph Bézier computations, including the current active font and elapsed time (e.g. `[*] Processing Sans font 3/18: SF Pro Text (300 normal) [CFF->TTF]... (24s elapsed)...`), keeping the root manager terminal pipe active and preventing Android Cached App Freezer timeouts.
- **On-Device PostScript (CFF/OTF) Conversion Notice & Step Tagging**:
  - Added automatic CFF/OTF outline detection (`is_cff`) across all font families in `runtime_helper.py`.
  - When compiling bundles containing CFF/OTF faces on-device with `convert_otf=True`, emits an immediate advisory notice informing users of intensive Bezier curve conversion on mobile CPUs (`[*] Notice: Detected X PostScript (CFF/OTF) faces...`).
  - Tags processing steps for CFF fonts with `[CFF->TTF]` in real-time logs so users have full visibility into why specific fonts take longer to convert.

### Fixed
- **Centered Colon False Positive on Fonts with `tnum` Tabular Colon Substitutions**:
  - `font_has_centered_colon()` in `runtime_helper.py` incorrectly returned `true` for fonts that only have a `tnum` GSUB `colon → colon.tf` substitution (a tabular-width colon for digit alignment), suppressing the `ENABLE_CENTERED_COLON` config option even though the font has no elevated/centered colon.
  - Root cause 1: `"tnum"` was listed alongside `"case"` and `"calt"` in the GSUB trusted-tag shortcut (L458). Only `case` (uppercase-height positional shift) and `calt` (contextual reposition) are valid indicators; `tnum` only widens advance width.
  - Root cause 2: `COLON_GLYPH_PATTERNS` included `tab|tf|tnum` as colon variant suffixes. `colon.tf` and `colon.tab` are tabular figures colons, not centered/elevated clock colons. Removed these three tokens from the pattern suffix alternation.
  - Root cause 3: `target_colons` included `"colon.tf"` and `"colon.tab"`, causing them to be treated as canonical base colon glyphs for GSUB source matching.
  - Affects any static or variable sans-serif font exposing a `tnum` feature (e.g. Circular Spotify Tx T, and potentially other Monotype/Spotify-licensed families).

## 2026.09.09

### Added
- **On-Time Synthetic Italic Engine for Sans-serif Fonts (`ENABLE_SYNTHETIC_ITALIC`)**:
  - Automatically audits the Sans-serif family during installation. If the supplied fonts lack native italic styles (both variable and static) and lack variable slant (`slnt`) or italic (`ital`) axes, exposes `ENABLE_SYNTHETIC_ITALIC=false` and `SYNTHETIC_ITALIC_ANGLE=-12` under section `# 3. SYNTHETIC ITALIC / OBLIQUE (for Sans-serif)` in `/sdcard/MFFM/*.conf`.
  - When enabled, algorithmically shears glyph outlines across TrueType quadratic `glyf` contours, variable font deltas (`gvar`), and CFF/CFF2 cubic Bezier curves.
  - Slants OpenType layout anchors (`GPOS` and `BASE` tables) to preserve optical kerning and mark-to-base attachments.
  - Updates font metadata (`post.italicAngle`, `head.macStyle |= 2`, `OS/2.fsSelection |= 1`, `hhea.caretSlopeRun`) and injects an `ital` axis into the `STAT` table.
  - Bundles the synthesized italic companion into the unified `DroidSans.ttf` collection (at index 1 for variable fonts, or companion indices for static fonts) with corresponding `<font style="italic">` mappings emitted into `sans.xml` and `condensed.xml`.
  - Strictly dedicated to the Sans-serif family; Monospace, Serif, and Bengali families remain untouched.
- **Dynamic Configuration Category Filtering & Renumbering**:
  - If native italic styles or variable slant axes are detected, the installer automatically omits the synthetic italic category from `/sdcard/MFFM/*.conf` and dynamically strips any existing synthetic italic keys.
  - Renumbers subsequent typography categories sequentially (1 to 5 or 1 to 6) without missing section numbers.
- **Build & Packaging CLI Parity**:
  - Added `--synthetic-italic`, `--no-synthetic-italic`, and `--synthetic-italic-angle` flags across `build.py`, `update.py`, and `font_module.py`.
  - Added `synthetic_italic` and `synthetic_italic_angle` to `.mffm-build.json` project configuration keys.

## 2026.09.08

### Added
- **Exhaustive Centered Colon Detection Engine**:
  - Implemented deep inspection across glyph names, Unicode codepoints (including Android lockscreen clock colon PUA `U+EE01`, `U+2236`, `U+2982`, etc.), OpenType GSUB lookups (Types 1, 3, 4, 5, 6, and 7 extension subtables), OpenType GPOS vertical placement shifts (`case`/`calt`), and glyph outline geometry (detecting native elevated colons aligned to digit centers).
  - When the primary sans-serif font already includes a centered colon feature, all centered colon configuration settings are completely omitted from the generated `/sdcard/MFFM/*.conf` file, any obsolete colon settings are pruned, and subsequent typography sections are dynamically renumbered.
- **Android Lockscreen Clock Colon PUA Mapping (`ENABLE_LOCKSCREEN_COLON_PUA`)**:
  - Automatically scans if the Sans-serif font implements Android lockscreen clock colon PUA (`U+EE01`) with valid glyph geometry.
  - If the font already implements `U+EE01`, the configuration option is omitted from `/sdcard/MFFM/*.conf`.
  - If missing, adds `ENABLE_LOCKSCREEN_COLON_PUA=false` to `.conf`. When enabled (`true`), dynamically maps the colon (or centered colon) glyph to Android lockscreen clock Private Use Area codepoints (`U+EE01`, `U+2236`, `U+2982`) across all Unicode cmap sub-tables, resolving broken glyph tofu boxes `[?]` on Pixel, HyperOS, One UI, OxygenOS, and Nothing OS lockscreens.
- **Granular On-Screen Installation Progress & Status Feedback**:
  - Replaced generic compilation messages during dynamic on-device compilation with minimal, per-feature progress indicators (`[*] Generating & injecting centered clock colon...`, `[*] Equalizing clock digits...`, `[*] Freezing OpenType features...`).
  - Added explicit per-feature success (`[OK]`) and failure (`[!]`) status indicators along with exact cause diagnostics extracted from the compilation log.
- **Dynamic Module Description Feature Reflection**:
  - Automatically updates `module.prop`'s `description` during installation (and at build time) to clearly reflect all active features (e.g. `[Active: Centered Colon, Tabular Digits, Frozen: ss03, ss04, zero]`) cleanly and idempotently across re-flashes.

### Removed
- **Completely Eliminated `font-config.sh`**:
  - Removed `font-config.sh` generation, packaging, and sourcing across `build.py`, `font_module.py`, `runtime_helper.py`, `runtime-template/customize.sh`, and `template/customize.sh`.
  - Font modules no longer require any external shell configuration crutch; the installer discovers font parameters and metadata dynamically from binaries and `module.prop`.
- **Completely Dropped Zygote RAM & Table Optimizer**:
  - Removed `optimize_font_tables()`, `ZYGOTE_BLOAT_TABLES`, and the `optimize` CLI command from `runtime_helper.py`.
  - Removed `--optimize-tables` CLI flag and logic from `compile_bundle` and `process-font`.
  - Removed `ENABLE_ZYGOTE_OPTIMIZATION` from configuration generator and runtime compiler forwarding in `template/customize.sh`.
  - Standard bytecode hinting removal (`remove_font_hinting` / `--no-hinting`) remains fully supported and intact.

### Added
- **Autonomous Multi-Category Font Detection**:
  - Implemented `detect_category_mode()` and `refresh_font_modes()` in `template/customize.sh`.
  - Directly inspects font binaries on-the-fly (`is_variable_font`) across all four categories: Sans (`SANS_MODE`), Monospace (`MONO_MODE`), Serif (`SERIF_MODE`), and Bengali (`BENGALI_MODE`).
  - Sets `FONT_MODE="variable"` if Sans is variable or if any secondary category contains variable fonts (`HAS_ANY_VARIABLE=true`).
  - Autonomously extracts `fvar` axes and populates `VF_*_AXIS_META` directly from font headers for any variable category present without external helper scripts.
  - Automatically recognizes purely static font packages (like SF Pro static) and generates appropriate configuration files without axis confusion.
- **Root Manager Anti-Freeze & Broken-Pipe Safeguards (KernelSU / Magisk / APatch)**:
  - Added `trap '' PIPE` signal ignoring and error suppression (`2>/dev/null || true`) in `mffm_ui_print` to prevent unhandled `SIGPIPE` termination when root manager UI log streams close or lag.
  - Added active 3-second heartbeat progress loop while running on-device dynamic compilation (`compile-bundle`) in the background, keeping the root manager terminal pipe fed and preventing the Android Cached App Freezer from freezing long-running font compilations.
  - Added real-time flushed font processing logs (`flush=True`) in `runtime_helper.py`.
  - Removed invalid top-level `local` declarations in `template/customize.sh` for strict POSIX shell compliance (`toybox`, `mksh`, `busybox ash`).
- **Legacy Extraction Enhancements in `update.py`**:
  - Expanded `OLD_PRIMARY_NAMES` and added automatic categorization for fonts found in legacy `system/fonts` directories, properly assigning Monospace and Serif fonts to their respective subdirectories during migration.

### Changed
- **Compact Metric Optimization Default**:
  - Switched default `METRICS_MODE` from `safe` to `compact` across the runtime compiler, configuration generator, and CLI tools for maximum UI compactness and classic tight FFIX3 vertical spacing.
  - Safe metrics auto-clamping (`METRICS_MODE=safe`) and raw metrics retention (`METRICS_MODE=preserve`) remain fully selectable options in `/sdcard/MFFM/*.conf`.

### Fixed
- **Asymmetric Whitespace Matching for Clock Colons**:
  - Expanded OpenType GSUB Format 6 contextual rules in `inject_centered_colon` to match asymmetric spacing patterns (`12: 30`, `12 :30`) in addition to standard `12:30` and `12 : 30`.
  - Added whitespace support for `after_digit` colon rules (`12 :`).
- **Primary Face Determination (`FONT_PRIMARY`)**:
  - Fixed `FONT_PRIMARY` inadvertently selecting the Italic face when sorted alphabetically (e.g. `SchibstedGrotesk-Italic...` before `SchibstedGrotesk-Variable...`).
  - Updated `font_module.py` and `template/customize.sh` to prioritize upright normal Regular faces.

## 2026.09.06

### Documentation & Public Release Architecture
- **Three-Tier Documentation Separation**:
  - Redesigned `ReadMe.md` into a modern GitHub repository frontpage and project showcase featuring compatibility badges, feature highlight summaries, architecture overview, quickstarts, and community links.
  - Refactored `USAGE_GUIDE.md` into an exhaustive end-user and theme-maker manual (step-by-step module packaging for Android file managers and PC, comprehensive `/sdcard/MFFM/*.conf` parameter guide, troubleshooting & FAQ). Packaged inside `MFFMv14-Source-Template.zip`.
  - Authored `docs/DEVELOPER.md` delivering in-depth technical documentation covering the Decoupled Safe Metrics engine mathematics, OpenType GSUB Format 6 contextual colon lookup assembly, tabular digit equalization, Zygote table pruning, dual runtime detection mechanics, and complete developer CLI tool reference.

### Improved
- **Official Runtime Download & Installer Redirect**:
  - Shifted official runtime releases and installer fallback redirect from Telegram to [GitHub Releases](https://github.com/mistu01/MFFMv14/releases).
  - Updated `template/customize.sh` missing-runtime error banner and `am start` browser intent to automatically launch the GitHub Releases page.
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
