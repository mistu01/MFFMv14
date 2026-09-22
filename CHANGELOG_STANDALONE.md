# MFFMv14 Standalone Module — Changelog

All notable changes, releases, and architectural developments for the **MFFMv14 Standalone Module** (`build_standalone.py`, `template-standalone/`, and `MFFMv14-Standalone-Template.zip`) are documented in this file.

Dates follow the `YYYY.MM.DD` versioning format carried by the modules.

---

## 2026.09.23

### Added
- **SemiBold-as-Medium & SemiBoldItalic-as-MediumItalic Fallback for External Static Fonts (`template-standalone/customize.sh` & `font_module_standalone.py`)**:
  - Automatically maps SemiBold (600) to Medium (500) when external static Bengali or Serif fonts provide SemiBold but lack a native Medium weight face.
  - For external Serif fonts, when MediumItalic (500 italic) is not present and upright Medium is also missing, SemiBoldItalic (600 italic) is automatically used as MediumItalic.
  - Expands static Bengali fallback to 3 faces (`Regular`, `SemiBold-as-Medium`, `Bold`) and static Serif fallback to up to 6 faces (`Regular`, `Italic`, `SemiBold-as-Medium`, `SemiBoldItalic-as-MediumItalic`, `Bold`, `BoldItalic`).
  - Emits `<font weight="500">` XML definitions pointing directly to the SemiBold / SemiBoldItalic face indices in `DroidSans.ttf` or standalone font files with zero overhead.
- **3-Mode Vertical Metrics Harmonization (`--metrics-mode`) (`build_standalone.py`, `build.py`, `font_module_standalone.py`)**:
  - Added full parity with runtime metrics modes: `compact` (default tight FFIX3), `safe` (decoupled zero-clipping bounds calculation from `glyf`/`head`), and `preserve` (intact designer metrics with HWUI bugfixes).
  - Integrated into interactive wizard prompts (`prompt_metrics_mode`), build configuration persistence (`.mffm-build.json`), build summary banners, and standalone module runtime configuration (`font-config.sh`).
- **Universal Font Subsetter & Plane 16 Bloat Pruning (`build_standalone.py`, `font_module_standalone.py`, `runtime_helper.py`)**:
  - Integrated universal font subsetter into standalone font compilation.
  - **Smart PUA Preservation**: Preserves Apple logo (`0xF8FF`), Powerline, Nerd Fonts BMP, Material Design Icons (`0xF0001–0xF1AF0`), and Web icons (`0xE900–0xEF50`), while dropping Apple SF Symbols Plane 16 (`0x100000–0x10FFFD`, 8,400+ unused glyphs) and unassigned Plane 15 bloat (`0xF1AF1–0xFFFFD`).
  - **Chinese, Japanese, and Korean (CJK) Script Removal**: Completely purges CJK ideographs (Main block `0x4E00–0x9FFF`, Ext A through H `0x3400–0x4DBF`, `0x20000–0x323AF`), Japanese Kana (Hiragana `0x3040–0x309F`, Katakana `0x30A0–0x30FF`, Kana Supplements), Korean Hangul (Syllables `0xAC00–0xD7AF`, Jamo `0x1100–0x11FF`, Extended A & B), Bopomofo, and Fullwidth forms (`0xFF00–0xFFEF`).
  - **Android Noto Color Emoji Safe**: Drops monochrome emoji outlines that shadow Android's system `NotoColorEmoji`.
  - **Language Guard**: All non-CJK spoken languages (Latin, Cyrillic, Greek, Arabic, Hebrew, Devanagari, Bengali, Thai, Vietnamese, etc.) and diacritics are strictly guarded via Unicode category verification (`L*` letters and `M*` marks) and never dropped.
  - **Automatic Font Size Detection (> 1 MB)**: Automatically prompts or activates when source fonts exceed 1 MB, slashing font memory footprint and package size.
  - Added `--subset` and `--no-subset` CLI flags with `.mffm-build.json` persistence.

## 2026.09.11

### Initial Standalone Architecture Release

#### 🚀 100% Python- & fontTools-Free On-Device Architecture
- **Completely Decoupled from Python**: The standalone module installer (`template-standalone/customize.sh`) operates with **zero on-device Python, fontTools, or `mffm-runtime` dependency**.
- **Instant Installation**: All font compilation, OpenType feature freezing, metrics harmonization, TTC bundling, and system font XML fragment generation are performed upfront during build time on PC or mobile Termux. Installation on device finishes in **under 2 seconds**.
- **Binary `fvar` Axis Parser**: Built a high-speed, binary variable font table parser in pure POSIX shell and `awk` using `od -tx1`. External variable fonts dropped into `/sdcard/MFFM/` are scanned autonomously on device without Python, generating `/sdcard/MFFM/MFFMv14_<FAMILY>.conf` and full 100–900 weight XML definitions.

#### 🔤 Standardized External Static Face Standards
- When static fonts are supplied in `/sdcard/MFFM/`, the standalone installer configures standardized face counts with zero on-device TTC compilation:
  - **Serif**: **4–6 faces default** (`Regular` 400, `Italic` 400, `Bold` 700, `BoldItalic` 700, plus `Medium` 500 / SemiBold-as-Medium).
  - **Bengali**: **2–3 faces default** (`Regular` 400, `Bold` 700, plus `Medium` 500 / SemiBold-as-Medium).
  - **Monospace**: **1 face default** (`Regular` 400).
  - **SemiBold-as-Medium Fallback**: For Bengali and Serif external fonts that do not contain a Medium (500) face but include a SemiBold (600) face, the module automatically leverages that SemiBold face as Medium in system typography mappings.

#### ⏰ Enhanced Centered Clock Colon Suite
- **Vertical Colon Shift / Offset** (`--colon-offset` / `--colon-shift`): Allows fine-grained height adjustment (+/- font units) of the centered clock colon for OEM-specific lockscreen clock widgets.
- **Colon Alignment Reference** (`--colon-alignment`): Supports `center` (mathematical digit box center), `cap_height` (cap-height alignment), and `x_height` (lowercase x-height alignment).
- **Contextual Substitution Rules** (`--colon-rule`): Choose between `between_digits` (e.g. `12:30`), `after_digit` (e.g. `12:`), or `always`.
- **Digit Equalization** (`--equalize-digits`): Automatically equalizes advance widths across all digits (`0`–`9`) and centers contours to eliminate clock number wobbling.
- **Lockscreen PUA Colon** (`--pua-colon`): Mirrors colon glyph to Android PUA (`U+EE01`) and math ratio symbols (`U+2236`, `U+2982`) for OEM lockscreen clock compatibility.

#### 📱 Mobile Termux One-Shot Builder (`termux-build.sh`)
- Standalone-first terminal builder for Android Termux.
- Automatically installs required toolchain dependencies (`python`, `fonttools`, `brotli`, `cryptography`), compiles the module with `build_standalone.py`, and prompts for immediate installation via root (`su`) with Magisk, KernelSU, or APatch.

#### 📦 Self-Contained Distribution Template (`MFFMv14-Standalone-Template.zip`)
- Packaged full standalone toolchain into `dist/MFFMv14-Standalone-Template.zip`.
- Contains `build_standalone.py`, `font_module_standalone.py`, `runtime_helper.py`, `zipsigner_auto.py`, `termux-build.sh`, `requirements.txt`, convenience wrapper `build.py`, `template-standalone/` payload, directory skeletons (`Fonts/Sans/`, `Monospace/`, `Serif/`, `Bengali/`, `dist/`), and standalone documentation (`USAGE_GUIDE_STANDALONE.md`, `CHANGELOG_STANDALONE.md`).
