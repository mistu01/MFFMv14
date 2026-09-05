# MFFMv14 — Universal Android Font Module Framework

<div align="center">

[![Android](https://img.shields.io/badge/Android-8.0_to_15+-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![Magisk](https://img.shields.io/badge/Magisk-v20.4+-B0BEC5?style=for-the-badge&logo=android&logoColor=black)](https://github.com/topjohnwu/Magisk)
[![KernelSU](https://img.shields.io/badge/KernelSU-v0.9.4+-80CBC4?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/tiann/KernelSU)
[![APatch](https://img.shields.io/badge/APatch-v0.11.0+-90CAF9?style=for-the-badge&logo=android&logoColor=black)](https://github.com/bmax121/APatch)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Telegram](https://img.shields.io/badge/Telegram-MFFMMain-0088CC?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/MFFMMain)

**The next-generation, universal Android system font module engine.**  
*Transform any static or variable font into a production-grade, flashable root module with on-device typography intelligence.*

</div>

---

## 📖 Overview

**MFFMv14** is a modern, cross-platform Android font framework that compiles, packages, and tunes system fonts across **Magisk**, **KernelSU**, and **APatch**.

Unlike legacy font modules that merely swap static TTF files, MFFMv14 introduces a **split-architecture engine**: a lightweight font module works in tandem with a standalone, on-device Python + `fontTools` runtime (`mffm-runtime`). Together, they perform intelligent bounding-box metric clamping, contextual centered clock colons, tabular digit advance equalization, OpenType feature freezing, and dynamic TrueType Collection (`.ttc`) packaging directly on your phone.

---

## ✨ Key Highlights

- 🛡️ **Zero-Clipping Decoupled Safe Metrics Engine**  
  Positive $y$-axis (ascent) and negative $y$-axis (descent) expand independently based on actual glyph extremes. Accents (Vietnamese `ế`, `Ậ`, Devanagari, Thai, Arabic, Polish) never clip, while button heights and status bar icons stay centered with **zero monospace line-height inflation**.
- 🕒 **Contextual Centered Clock Colon (GSUB Format 6)**  
  Injects an OpenType Chaining Contextual Substitution rule so clock times (`12:30`) display a vertically centered colon, without distorting normal text punctuation.
- ⏱️ **Tabular Lockscreen Clock Digits**  
  Equalizes numeral advance widths (0–9) to stop lockscreen clocks from wobbling horizontally when minutes or seconds tick.
- ⚡ **Zygote RAM & Table Optimizer**  
  Prunes obsolete tables (`DSIG`, `VDMX`, `hdmx`, `LTSH`, `PCLT`, `EBDT`) and removes duplicate Macintosh Roman name records, shrinking font sizes by 10–30% and reducing memory usage in Android's root Zygote process.
- 🎨 **OpenType Feature Freezing**  
  Bakes stylistic sets (`ss01`–`ss20`), slashed zero (`zero`), and character variants permanently into default glyphs system-wide.
- 🛑 **Anti-Google Font Update Shield**  
  A background boot daemon (`service.sh`) and an on-demand Action button (`action.sh`) neutralize silent Google Play System font overrides (`/data/fonts/files/`).
- 🌐 **Multi-Family & Multi-Script Architecture**  
  Full first-class support for **Sans-serif**, **Monospace**, **Serif**, and **Bengali** script font families within a single module.
- 📦 **Universal Format Ingestion**  
  Accepts `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, and `.woff2` fonts, with automatic decompression and CFF-to-TrueType curve conversion (`cu2qu`).

---

## ⚠️ Mandatory Prerequisite: MFFM Runtime

MFFMv14 uses a modular architecture. Before flashing any MFFMv14 font module, you **MUST** install the standalone runtime module once:

```
mffm-runtime-YYYY.MM.DD.zip
```

- **What it is**: A standalone module providing embedded Python 3.12/3.14, `fontTools`, `brotli`, and the `mffm-helper` CLI at `/data/adb/mffm_runtime/`.
- **Install Once**: You only flash the runtime once. After that, any MFFMv14 font module will execute instantly.
- **Download**: Grab official runtime releases from **[GitHub Releases](https://github.com/mistu01/MFFMv14/releases)**.

---

## 🚀 Quick Start

### Option 1: Create a Module on Your Phone (No Python Needed)
1. Ensure **`mffm-runtime`** is installed in your root manager.
2. Extract **`MFFMv14-Source-Template.zip`** using your favorite file manager (MiXplorer, MT Manager, ZArchiver).
3. Put your font file(s) into **`Files/Sans/`** (optionally add fonts to `Files/Monospace/`, `Files/Serif/`, or `Files/Bengali/`).
4. Edit **`module.prop`** with your font name and author.
5. Compress the template contents into a standard **ZIP** and flash it in **Magisk**, **KernelSU**, or **APatch**!

### Option 2: Build with the PC Script (`build.py`)
1. Clone the repository and install requirements:
   ```sh
   git clone https://github.com/mistu01/MFFMv14.git
   cd MFFMv14
   pip install -r requirements.txt
   ```
2. Place fonts into `Fonts/Sans/`.
3. Run the compiler:
   ```sh
   python build.py
   ```
   Outputs a cryptographically signed flashable ZIP directly to `dist/`.

---

## 🎛️ On-Device Customization (`/sdcard/MFFM/*.conf`)

Every installed font module generates an editable settings file at:
```
/sdcard/MFFM/MFFMv14_<FontFamily>_<ID>.conf
```

All settings are optional and pre-tuned with safe defaults:
```sh
# Centered Clock Colon for 12:30
ENABLE_CENTERED_COLON=yes
COLON_ALIGNMENT=center
COLON_OFFSET=0
COLON_RULE=between_digits

# Wobble-free lockscreen clock digits
ENABLE_TABULAR_CLOCK_DIGITS=yes

# Zero-clipping safe vertical metrics
METRICS_MODE=safe

# Zygote RAM saver and table optimizer
ENABLE_ZYGOTE_OPTIMIZATION=yes

# OpenType feature freezing (slashed zero, stylistic sets)
SANS_FREEZE_FEATURES=ss01,zero
MONO_FREEZE_FEATURES=zero
```
*To apply changes, simply edit the file and re-flash your font module ZIP.*

---

## 📚 Documentation Index

For detailed documentation, refer to the specialized guides:

| Document | Purpose & Contents |
| :--- | :--- |
| 📖 **[User & Configuration Guide](USAGE_GUIDE.md)** | Step-by-step module creation, full `/sdcard/MFFM/*.conf` parameter guide, on-device font additions, Google font update defense, and FAQ. |
| 🛠️ **[Developer & Architecture Guide](docs/DEVELOPER.md)** | Internal architecture, typography mathematics (Decoupled Safe Metrics, GSUB Format 6 colon, tabular digits, Zygote pruning), and full CLI tool reference. |
| 📜 **[Changelog](CHANGELOG.md)** | Complete version history, release notes, and milestone tracking. |

---

## 📂 Repository Structure

```
MFFMv14/
├── build.py                  # PC module compiler and packaging engine
├── build_runtime.py          # Standalone MFFM Runtime module builder
├── update.py                 # Module migration utility (legacy and modern)
├── package_template.py       # Builder for MFFMv14-Source-Template.zip
├── font_module.py            # Core font compiler & metadata engine
├── runtime_helper.py         # On-device mffm-helper CLI & typography tools
├── zipsigner_auto.py         # Automatic cryptographic ZIP signer
├── template/                 # Shared font module skeleton & orchestrator
│   ├── customize.sh          # On-device installer orchestrator
│   ├── service.sh            # Boot daemon neutralizing Google Font updates
│   ├── action.sh             # On-demand Action button for KSU / APatch / MMRL
│   └── META-INF/             # Standard Android update binary
├── runtime-template/         # Standalone MFFM Runtime module skeleton
├── docs/
│   └── DEVELOPER.md          # Architecture, metric math & developer guide
├── USAGE_GUIDE.md            # Comprehensive user handbook & .conf manual
├── CHANGELOG.md              # Version release history
└── ReadMe.md                 # Public repository frontpage
```

---

## 📱 Compatibility

- **Root Environments**: Magisk v20.4+, KernelSU v0.9.4+, APatch v0.11.0+, MMRL.
- **Android Versions**: Android 8.0 (Oreo / API 26) through Android 15 (Vanilla Ice Cream / API 35).
- **Architectures**: `arm64-v8a` (aarch64), `x86_64`.
- **Python**: Python 3.9+ (on PC), embedded Python 3.12/3.14 (on device runtime).

---

## 💬 Community & Support

- **Official Releases**: [GitHub Releases](https://github.com/mistu01/MFFMv14/releases)
- **Telegram Community**: [t.me/MFFMMain](https://t.me/MFFMMain)
- **Author**: Mistu (@MFFMMain)
- **Issues & Contributions**: Pull requests and issue reports are welcome via GitHub!

---

<div align="center">
<b>MFFMv14</b> — Crafted with precision for Android typography enthusiasts.
</div>
