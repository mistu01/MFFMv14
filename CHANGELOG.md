# MFFMv14 Standalone Module — Changelog

All notable changes, releases, and architectural developments for the **MFFMv14 Standalone Module** (`build_standalone.py`, `template-standalone/`, and `MFFMv14-Standalone-Template.zip`) are documented in this file.

Dates follow the `YYYY.MM.DD` versioning format carried by the modules.

---

## 2026.09.11

### Initial Standalone Architecture Release

#### 🚀 100% Python- & fontTools-Free On-Device Architecture
- **Completely Decoupled from Python**: The standalone module installer (`template-standalone/customize.sh`) operates with **zero on-device Python, fontTools, or `mffm-runtime` dependency**.
- **Instant Installation**: All font compilation, OpenType feature freezing, metrics harmonization, TTC bundling, and system font XML fragment generation are performed upfront during build time on PC or mobile Termux. Installation on device finishes in **under 2 seconds**.
- **Binary `fvar` Axis Parser**: Built a high-speed, binary variable font table parser in pure POSIX shell and `awk` using `od -tx1`. External variable fonts dropped into `/sdcard/MFFM/` are scanned autonomously on device without Python, generating `/sdcard/MFFM/MFFMv14_<FAMILY>.conf` and full 100–900 weight XML definitions.

#### 🔤 Standardized External Static Face Standards
- When static fonts are supplied in `/sdcard/MFFM/`, the standalone installer configures standardized face counts with zero on-device TTC compilation:
  - **Serif**: **4 faces default** (`Regular` 400, `Italic` 400, `Bold` 700, `BoldItalic` 700).
  - **Bengali**: **2 faces default** (`Regular` 400, `Bold` 700).
  - **Monospace**: **1 face default** (`Regular` 400).

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
