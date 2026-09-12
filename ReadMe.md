# MFFMv14 — Universal Android Font Module Framework

<div align="center">

[![Android](https://img.shields.io/badge/Android-8.0_to_15+-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![Magisk](https://img.shields.io/badge/Magisk-v20.4+-B0BEC5?style=for-the-badge&logo=android&logoColor=black)](https://github.com/topjohnwu/Magisk)
[![KernelSU](https://img.shields.io/badge/KernelSU-v0.9.4+-80CBC4?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/tiann/KernelSU)
[![APatch](https://img.shields.io/badge/APatch-v0.11.0+-90CAF9?style=for-the-badge&logo=android&logoColor=black)](https://github.com/bmax121/APatch)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-MFFMMain-0088CC?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/MFFMMain)

**The easy, universal system font engine for rooted Android devices.**  
*Use any font you love system-wide on Magisk, KernelSU, and APatch — with automatic fixes for lockscreens, clocks, and accents.*

</div>

---

## 📖 What is MFFMv14?

**MFFMv14** turns your favorite fonts into clean, flashable root modules. 

Unlike traditional font modules that only copy static files, MFFMv14 harmonizes font metrics, aligns lockscreen clock colons, equalizes clock digit widths, prevents accent clipping, and maps OEM-specific lockscreen PUA codepoints.

MFFMv14 provides **two distinct builder workflows** tailored to your preference:

1. **Regular Edition (`build.py` / `MFFMv14-Source-Template.zip`)**:  
   Uses a shared on-device engine ([`mffm-runtime`](https://github.com/mistu01/MFFMv14/releases)) to dynamically compile, adjust, and re-tune your fonts directly on your phone using `/sdcard/MFFM/*.conf` configuration files. Can be built on PC or entirely on your phone via a file manager.
2. **Standalone Edition (`build_standalone.py` / `MFFMv14-Standalone-Template.zip`)**:  
   Performs all font transformations upfront during build time (on PC or in mobile Termux). The resulting module is **100% readymade** and **completely Python-free** — it flashes in **under 2 seconds** with zero on-device dependencies.

---

## ⚖️ Builder Workflow Comparison

| Feature | 🔄 Regular Edition (Shared Runtime) | ⚡ Standalone Edition (100% Python-Free) |
| :--- | :--- | :--- |
| **Primary Build Script** | `python build.py` | `python build_standalone.py` *(or `termux-build.sh`)* |
| **Flashing Speed on Device** | ~10–30 seconds | **< 2 seconds** (Instant flash) |
| **Phone Prerequisites** | Requires `mffm-runtime` module installed once | **Zero prerequisites** (no Python, no runtime) |
| **Creation on Android** | Any File Manager (MiXplorer, MT Manager, ZArchiver) | Mobile Termux one-shot script (`termux-build.sh`) |
| **Template ZIP Asset** | `MFFMv14-Source-Template.zip` | `MFFMv14-Standalone-Template.zip` |
| **On-Device Customization** | Full `.conf` support (colons, italics, features, metrics) | Native variable font axis control via `.conf` |
| **Detailed Handbook** | 📖 **[Regular User Guide](USAGE_GUIDE.md)** | ⚡ **[Standalone User Guide](USAGE_GUIDE_STANDALONE.md)** |
| **Version History** | 📜 **[Regular Changelog](CHANGELOG.md)** | 📋 **[Standalone Changelog](CHANGELOG_STANDALONE.md)** |

---

## ✨ Universal Typography Features

- 🕒 **Centered Lockscreen Clock Colon**  
  Standard fonts place the colon (`:`) low on the baseline. MFFM lifts the colon in `12:30` on your lockscreen and status bar to be vertically centered while preserving normal punctuation in body text.
- 📱 **Lockscreen Colon Missing Glyph Fix (PUA `U+EE01`)**  
  Resolves broken tofu boxes (`[?]`) on OEM lockscreens (Google Pixel, Xiaomi HyperOS, Samsung One UI, OnePlus OxygenOS, Nothing OS) by mapping the colon to Android system clock Private Use Area codepoints.
- 📐 **Synthetic Italic Companion Generator**  
  If your favorite font only has upright weights, MFFM can algorithmically synthesize slanted italic companion faces on-the-fly.
- ⏱️ **Jitter-Free Clock Numbers**  
  Equalizes digit widths (`0`–`9`) so your lockscreen clock doesn't wobble or jump sideways as time ticks.
- 🛡️ **Zero Text Clipping (Safe Metrics)**  
  Ensures tall accents (e.g., Vietnamese `ế`, `Ậ`, Devanagari, Thai, Arabic, or `Å`) fit comfortably without inflating line spacing or breaking app layouts.
- 🎨 **Slashed Zeros & Style Alternates**  
  Freeze OpenType features system-wide (e.g. slashed zero `zero`, alternate `cv01`, stylistic sets `ss01`–`ss20`).
- 🛑 **Anti-Google Font Override Shield**  
  Built-in protection that blocks Google Play System updates from silently reverting your font back to Roboto.
- 🌐 **Multi-Family Support**  
  Apply custom fonts for your main system font (**Sans**), coding/terminal font (**Monospace**), book font (**Serif**), and **Bengali** script in the same module.

---

## 🚀 Workflow 1: Regular Edition (Shared Runtime)

> Detailed guide: 📖 **[USAGE_GUIDE.md](USAGE_GUIDE.md)**

### Step 1: Install MFFM Runtime (One-Time Setup)
Before flashing any regular font module, install the standalone **MFFM Runtime** module once in your root manager:
```
mffm-runtime-YYYY.MM.DD.zip
```
*Download the latest runtime from **[GitHub Releases](https://github.com/mistu01/MFFMv14/releases)**.*

### Step 2: Build & Flash
* **Option A (On PC via `build.py`)**:
  ```sh
  pip install -r requirements.txt
  # Put fonts in Fonts/Sans/
  python build.py
  ```
  Flash the generated ZIP from `dist/` in Magisk, KernelSU, or APatch.
* **Option B (On Phone via File Manager)**:
  Extract **`MFFMv14-Source-Template.zip`**, place your fonts in `Files/Sans/`, compress the folder contents back into a ZIP, and flash!

---

## ⚡ Workflow 2: Standalone Edition (100% Python-Free)

> Detailed guide: ⚡ **[USAGE_GUIDE_STANDALONE.md](USAGE_GUIDE_STANDALONE.md)**

### On PC (Windows / Linux / macOS)
1. Install Python dependencies:
   ```sh
   pip install -r requirements.txt
   ```
2. Place your source fonts into `Fonts/Sans/` *(optional: `Fonts/Monospace/`, `Fonts/Serif/`, `Fonts/Bengali/`)*.
3. Run the standalone builder:
   ```sh
   python build_standalone.py
   ```
4. Transfer the flashable ZIP from `dist/` to your phone and flash it. **No runtime or Python required on device!**

### On Android Phone (via Termux)
1. Extract `MFFMv14-Standalone-Template.zip` in Termux.
2. Put your fonts into `Fonts/Sans/`.
3. Run the automated one-shot script:
   ```sh
   sh termux-build.sh
   ```
   *Automatically installs Termux dependencies, compiles the module, and optionally flashes it directly with root (`su`).*

---

## 📚 Documentation Index

| Document | Purpose |
| :--- | :--- |
| 📖 **[Regular User Guide (USAGE_GUIDE.md)](USAGE_GUIDE.md)** | Complete handbook for the dynamic shared-runtime workflow, on-device module creation, and `.conf` options. |
| ⚡ **[Standalone User Guide (USAGE_GUIDE_STANDALONE.md)](USAGE_GUIDE_STANDALONE.md)** | Complete handbook for building readymade, Python-free standalone modules on PC & Termux. |
| 📜 **[Regular Changelog (CHANGELOG.md)](CHANGELOG.md)** | Version history and release notes for the regular runtime framework. |
| 📋 **[Standalone Changelog (CHANGELOG_STANDALONE.md)](CHANGELOG_STANDALONE.md)** | Version history and architectural notes for the standalone module builder. |
| ⚖️ **[License (LICENSE)](LICENSE)** | Full MIT License text. |

---

## 📂 Repository Structure

```
MFFMv14/
├── build.py                  # Regular module builder (dynamic runtime packaging)
├── build_standalone.py       # Standalone module builder (100% readymade payload)
├── font_module.py            # Regular font compilation and packaging engine
├── font_module_standalone.py # Standalone font compilation engine
├── build_runtime.py          # MFFM Runtime module builder
├── prepare_runtime.py        # Runtime payload assembler
├── package_template.py       # Template ZIP packager (Source & Standalone templates)
├── runtime_helper.py         # On-device helper CLI & font tools
├── termux-build.sh           # Mobile Termux one-shot builder and installer
├── zipsigner_auto.py         # Automatic ZIP signer
├── template/                 # Dynamic runtime module template
├── template-standalone/      # 100% Python-free standalone module template
├── runtime-template/         # Standalone MFFM Runtime module skeleton
├── USAGE_GUIDE.md            # Comprehensive user manual (Regular Edition)
├── USAGE_GUIDE_STANDALONE.md # Comprehensive user manual (Standalone Edition)
├── CHANGELOG.md              # Version history (Regular Edition)
├── CHANGELOG_STANDALONE.md   # Version history (Standalone Edition)
├── LICENSE                   # MIT License
└── ReadMe.md                 # Project frontpage
```

---

## 📱 Compatibility

- **Root Managers**: Magisk v20.4+, KernelSU v0.9.4+, APatch v0.11.0+, MMRL.
- **Android Versions**: Android 8.0 (Oreo) through Android 15.
- **Architectures**: ARM64 (`arm64-v8a`) and x86_64.

---

## ⚖️ License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

```text
Copyright (c) 2026 Mistu (@MFFMMain)
```

---

## 💬 Community & Support

- **Official Releases**: [GitHub Releases](https://github.com/mistu01/MFFMv14/releases)
- **Telegram Community**: [t.me/MFFMMain](https://t.me/MFFMMain)
- **Author**: Mistu (@MFFMMain)
- **Feedback & Issues**: Bug reports and feature suggestions are welcome on GitHub Issues!
