# MFFMv14 — Standalone Font Module Builder

<div align="center">

[![Android](https://img.shields.io/badge/Android-8.0_to_15+-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![Magisk](https://img.shields.io/badge/Magisk-v20.4+-B0BEC5?style=for-the-badge&logo=android&logoColor=black)](https://github.com/topjohnwu/Magisk)
[![KernelSU](https://img.shields.io/badge/KernelSU-v0.9.4+-80CBC4?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/tiann/KernelSU)
[![APatch](https://img.shields.io/badge/APatch-v0.11.0+-90CAF9?style=for-the-badge&logo=android&logoColor=black)](https://github.com/bmax121/APatch)
[![Telegram](https://img.shields.io/badge/Telegram-MFFMMain-0088CC?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/MFFMMain)

**100% Python-free, instant-flashing font modules for rooted Android devices.**  
*Compile custom fonts on PC or mobile Termux into self-contained root modules that flash in under 2 seconds with zero on-device dependencies.*

</div>

---

## 📖 What is MFFMv14 Standalone?

The **MFFMv14 Standalone Edition** performs all heavy typography processing, metric harmonization, outline conversion, and font packaging during build time (on your PC or in Termux).

The resulting flashable module is **100% readymade**:
- ⚡ **Installs in < 2 seconds** on Magisk, KernelSU, and APatch.
- 🚫 **Zero Python / fontTools requirements** on your phone (no `mffm-runtime` module needed).
- 🎛️ **Full Variable Font Axis Control** via `/sdcard/MFFM/*.conf` using native shell-level fvar table parsing.
- 🕒 **Centered Lockscreen Clock Colon & Typography Enhancements** baked directly into the font payload during build.

---

## 🚀 Quick Start: Building a Module

### On PC (Windows / Linux / macOS)
1. Install Python dependencies:
   ```sh
   pip install -r requirements.txt
   ```
2. Place your source fonts into `Fonts/Sans/`  
   *(Optional: coding fonts into `Fonts/Monospace/`, serif fonts into `Fonts/Serif/`, or Bengali fonts into `Fonts/Bengali/`)*.
3. Run the builder:
   ```sh
   python build.py
   ```
4. Transfer the flashable ZIP generated in `dist/` to your phone and flash it in **Magisk**, **KernelSU**, or **APatch**!

### On Android Phone (via Termux)
1. Install Termux and clone this branch:
   ```sh
   git clone -b standalone https://github.com/mistu01/MFFMv14.git
   cd MFFMv14
   ```
2. Put your fonts into `Fonts/Sans/` (or pass `--fonts-dir /sdcard/Download/MyFont`).
3. Run the automated Termux builder:
   ```sh
   sh termux-build.sh
   ```
   *The script automatically installs required packages, builds the module, and optionally flashes it directly using root permissions (`su`).*

---

## 🎛️ Variable Font Customization (`.conf`)

For variable font modules, an axis configuration file is generated upon installation at:
```
/sdcard/MFFM/<ModuleName>_axes.conf
```
You can edit font weights, optical sizes, and design axes directly in any text editor, then re-flash to apply your changes!

---

## 📚 Documentation

| Document | Description |
| :--- | :--- |
| ⚡ **[User & Configuration Guide](USAGE_GUIDE.md)** | Complete handbook for building readymade standalone modules, command-line arguments, typography features, and FAQs. |
| 📜 **[Changelog](CHANGELOG.md)** | Standalone module release history and architectural notes. |

---

## 📂 Repository Structure

```
MFFMv14/ (standalone branch)
├── build.py                  # Standalone module compiler (main build entry point)
├── font_module.py            # Standalone font compilation engine & typography processor
├── runtime_helper.py         # TrueType outline conversion & font tools
├── termux-build.sh           # Termux one-shot builder and installer
├── zipsigner_auto.py         # Automatic ZIP signer
├── package_template.py       # Standalone template packager (MFFMv14-Standalone-Template.zip)
├── template/                 # Lightweight 100% Python-free module template
├── USAGE_GUIDE.md            # Standalone user & configuration manual
├── CHANGELOG.md              # Standalone version history
└── ReadMe.md                 # Project frontpage
```


---

## 📱 Compatibility

- **Root Managers**: Magisk v20.4+, KernelSU v0.9.4+, APatch v0.11.0+, MMRL.
- **Android Versions**: Android 8.0 (Oreo) through Android 15.
- **Architectures**: ARM64 (`arm64-v8a`) and x86_64.

---

## 💬 Community & Support

- **Official Releases**: [GitHub Releases](https://github.com/mistu01/MFFMv14/releases)
- **Telegram Community**: [t.me/MFFMMain](https://t.me/MFFMMain)
- **Author**: Mistu (@MFFMMain)
- **Feedback & Issues**: Bug reports and feature suggestions are welcome on GitHub Issues!



