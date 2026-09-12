# MFFMv14 — Universal Android Font Module Framework

<div align="center">

[![Android](https://img.shields.io/badge/Android-8.0_to_15+-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://android.com)
[![Magisk](https://img.shields.io/badge/Magisk-v20.4+-B0BEC5?style=for-the-badge&logo=android&logoColor=black)](https://github.com/topjohnwu/Magisk)
[![KernelSU](https://img.shields.io/badge/KernelSU-v0.9.4+-80CBC4?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/tiann/KernelSU)
[![APatch](https://img.shields.io/badge/APatch-v0.11.0+-90CAF9?style=for-the-badge&logo=android&logoColor=black)](https://github.com/bmax121/APatch)
[![Telegram](https://img.shields.io/badge/Telegram-MFFMMain-0088CC?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/MFFMMain)

**The easy, universal system font engine for rooted Android devices.**  
*Use any font you love system-wide on Magisk, KernelSU, and APatch — with automatic fixes for lockscreens, clocks, and accents.*

</div>

---

## 📖 What is MFFMv14?

**MFFMv14** turns your favorite fonts into clean, flashable root modules. 

Unlike old font modules that only copy static font files, MFFMv14 automatically tunes your fonts directly on your phone. It fixes the common annoyances of custom fonts on Android — such as sunken clock colons, jittery lockscreen numbers, and cut-off accents — without requiring any technical knowledge.

---

## ✨ Why Use MFFMv14?

- 🕒 **Centered Lockscreen Clock Colon**  
  Standard fonts place the colon (`:`) low on the baseline for sentences. MFFM automatically lifts the colon in `12:30` on your lockscreen and status bar to look perfectly centered, while keeping normal sentence punctuation untouched.
- 📱 **Lockscreen Colon Missing Glyph Fix (PUA `U+EE01`)**  
  Resolves broken tofu boxes (`[?]`) on OEM lockscreens (Google Pixel, Xiaomi HyperOS, Samsung One UI, OnePlus OxygenOS, Nothing OS) by mapping the colon to Android system clock Private Use Area codepoints.
- 📐 **Synthetic Italic Companion Generator**  
  If your favorite font only comes in upright styles and has no italics, MFFM can algorithmically synthesize and bundle slanted italic companion faces on-the-fly, keeping variable axes, glyph outlines, and layout anchors intact.
- ⏱️ **Jitter-Free Clock Numbers**  
  Numbers in many fonts have different widths (for example, `1` is narrower than `0`). MFFM equalizes digit widths so your lockscreen clock doesn't wobble or jump sideways every time a second ticks or a minute changes.
- 🛡️ **Zero Text Clipping (Safe Metrics)**  
  Tall accents (like Vietnamese `ế`, `Ậ`, Devanagari, Thai, Arabic, or `Å`) often get cut off at the top or bottom of notifications and status bars. MFFM ensures all characters fit comfortably without inflating line spacing or breaking app layouts.
- 🎨 **Slashed Zeros & Style Alternates**  
  Easily activate font features you want system-wide, like slashed zeros (`0`), curved lowercase `l`, or alternate letter designs.
- 🛑 **Anti-Google Font Override Shield**  
  Android often silently overrides custom fonts during Google Play System updates. MFFM includes a built-in shield that blocks Google from reverting your font back to stock Roboto.
- 🌐 **Multi-Family Support**  
  Apply custom fonts for your main system font (**Sans**), coding/terminal font (**Monospace**), book font (**Serif**), and **Bengali** script all in the same module.
- 📦 **Works with Any Font File**  
  Accepts `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, and `.woff2`, including variable and static fonts.

---

## ⚠️ Step 1: Install MFFM Runtime First (One-Time Setup)

Before flashing any MFFMv14 font module, install the standalone **MFFM Runtime** module once in your root manager:

```
mffm-runtime-YYYY.MM.DD.zip
```

- **Why is it needed?** It gives your phone the tools required to adjust metrics, align clock colons, and package fonts on-device.
- **Install Once**: You only flash it once. All your current and future MFFMv14 font modules will use it automatically.
- **Download**: Grab the latest `mffm-runtime-*.zip` from **[GitHub Releases](https://github.com/mistu01/MFFMv14/releases)**.

---

## 🚀 Step 2: Create & Flash Your Font

### Method 1: On PC using Python (`build.py`) — Recommended
1. Clone this repository:
   ```sh
   git clone https://github.com/mistu01/MFFMv14.git
   cd MFFMv14
   pip install -r requirements.txt
   ```
2. Put your source fonts into `Fonts/Sans/`  
   *(Optional: put coding fonts into `Fonts/Monospace/`, serif fonts into `Fonts/Serif/`, or Bengali fonts into `Fonts/Bengali/`)*.
3. Run the builder:
   ```sh
   python build.py
   ```
4. Transfer the flashable ZIP generated in `dist/` to your phone and flash it in **Magisk**, **KernelSU**, or **APatch**!

### Method 2: On Your Phone (No PC Needed)
1. Download and extract **`MFFMv14-Source-Template.zip`** from [GitHub Releases](https://github.com/mistu01/MFFMv14/releases) using any file manager (like MiXplorer, MT Manager, or ZArchiver).
2. Put your font file(s) into the **`Files/Sans/`** folder.  
   *(Optional: put coding fonts into `Files/Monospace/`, serif fonts into `Files/Serif/`, or Bengali fonts into `Files/Bengali/`)*.
3. Open **`module.prop`** and customize the font name/author if you wish.
4. Select all files inside the template folder, compress them into a standard **ZIP**, and flash it in **Magisk**, **KernelSU**, or **APatch**!
5. Reboot to enjoy your new system font!

> [!NOTE]
> **Looking for the Standalone (100% Python-Free) Edition?**  
> If you prefer readymade modules that flash in under 2 seconds without requiring `mffm-runtime` on your device, check out the dedicated **[`standalone`](https://github.com/mistu01/MFFMv14/tree/standalone)** branch.

---

## 🎛️ How to Customize Your Font (`.conf`)

Whenever you install a font module, a simple settings file is created on your internal storage at:
```
/sdcard/MFFM/MFFMv14_<FontFamily>_<ID>.conf
```

> [!TIP]
> **Do you have to change anything?**  
> **No!** Everything works out of the box with safe, beautiful defaults.

If you want to tweak settings, open the file in any text editor, change what you want, and re-flash your module ZIP:

```sh
# 1. Centered colon for lockscreen & status bar clocks (12:30)
ENABLE_CENTERED_COLON=yes

# 2. Fix broken glyph box [?] on OEM lockscreen clocks (PUA U+EE01)
ENABLE_LOCKSCREEN_COLON_PUA=false

# 3. Synthesize italic companion faces if the font lacks them (Sans-serif only)
ENABLE_SYNTHETIC_ITALIC=false
SYNTHETIC_ITALIC_ANGLE=-12

# 4. Equalize clock numbers so the clock doesn't wobble
ENABLE_TABULAR_CLOCK_DIGITS=yes

# 5. Metric mode: compact (default tight UI), safe (zero accent clipping), or preserve
METRICS_MODE=compact

# 6. Activate cool font features (like slashed zero or stylistic sets)
SANS_FREEZE_FEATURES=ss01,zero
```

---

## 📚 Documentation Index

| Document | Description |
| :--- | :--- |
| 📖 **[User & Configuration Guide](USAGE_GUIDE.md)** | Detailed handbook covering on-device module creation, full configuration settings guide, adding extra fonts directly on phone, and FAQ. |
| 📜 **[Changelog](CHANGELOG.md)** | Complete release notes and version history. |
| ⚡ **[Standalone Edition](https://github.com/mistu01/MFFMv14/tree/standalone)** | Dedicated branch for building readymade standalone modules with zero on-device dependencies. |

---

## 📂 Repository Structure

```
MFFMv14/ (main branch)
├── build.py                  # PC module builder and packaging script
├── font_module.py            # Core font inspection and compilation engine
├── build_runtime.py          # MFFM Runtime module builder
├── prepare_runtime.py        # Runtime payload assembler
├── package_template.py       # Source template packager (MFFMv14-Source-Template.zip)
├── runtime_helper.py         # On-device helper CLI & font tools
├── zipsigner_auto.py         # Automatic ZIP signer
├── template/                 # Dynamic runtime module template
├── runtime-template/         # Standalone MFFM Runtime module skeleton
├── USAGE_GUIDE.md            # Comprehensive user manual
├── CHANGELOG.md              # Full version history
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



