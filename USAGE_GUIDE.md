# MFFMv14 Standalone Module — User & Configuration Guide
### Complete Handbook for Building, Flashing, and Customizing Readymade Android Font Modules (Zero On-Device Dependencies)

---

> [!NOTE]
> ### ⚡ 100% Dependency-Free Experience
> Unlike the dynamic runtime workflow, the **MFFMv14 Standalone Module** requires **NO on-device Python**, **NO fontTools**, and **NO `mffm-runtime` prerequisite** on your Android device.
> - All font processing, TrueType Collection (TTC) bundling, OpenType feature freezing, metrics harmonization, and system XML fragment generation are performed **upfront at build time** on your PC or in mobile Termux.
> - The generated module installs in **under 2 seconds** and is ready immediately upon reboot.

---

## 📑 Table of Contents
1. [Quick Start: Building Your Standalone Module](#-quick-start-building-your-standalone-module)
   - [Method 1: PC Builder (Recommended)](#method-1-pc-builder-recommended)
   - [Method 2: Mobile Termux One-Shot Builder](#method-2-mobile-termux-one-shot-builder)
2. [Font Directory Structure & Categories](#-font-directory-structure--categories)
3. [Compiler CLI Options & Customization](#-compiler-cli-options--customization)
   - [Clock Colon Customization & Shift](#clock-colon-customization--shift)
   - [Digit Equalization (Wobble-Free Clocks)](#digit-equalization-wobble-free-clocks)
   - [Lockscreen Clock PUA Colon](#lockscreen-clock-pua-colon)
   - [OpenType Feature Freezing](#opentype-feature-freezing)
   - [Synthetic Italics](#synthetic-italics)
4. [External Fonts on Device (`/sdcard/MFFM/`)](#-external-fonts-on-device-sdcardmffm)
   - [Standard Face Counts for External Static Fonts](#standard-face-counts-for-external-static-fonts)
   - [External Variable Font Tuning (`.conf`)](#external-variable-font-tuning-conf)
5. [Root Manager Compatibility](#-root-manager-compatibility)
6. [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 🚀 Quick Start: Building Your Standalone Module

You can compile a standalone MFFMv14 module on a PC (Windows, macOS, Linux) or directly on an Android device using the Termux terminal.

---

### Method 1: PC Builder (Recommended)
> **Best for:** Designers and users who want high compilation speed, advanced CLI switches, and automated zip signing.

1. **Prerequisites**: Ensure Python 3.8+ is installed on your system.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Installs `fonttools`, `cryptography`, `brotli`, and `opentype-feature-freezer`).*
3. **Add Your Fonts**: Place your font files into the **`Fonts/Sans/`** directory.
   - *Variable Font:* e.g. `Fonts/Sans/Inter[opsz,wght].ttf`
   - *Static Family:* e.g. `Fonts/Sans/Regular.ttf`, `Fonts/Sans/Bold.ttf`, `Fonts/Sans/Italic.ttf`, etc.
   - *Optional Categories:*
     - Monospace / Coding font: place in `Fonts/Monospace/`
     - Serif font: place in `Fonts/Serif/`
     - Bengali font: place in `Fonts/Bengali/`
4. **Compile the Module**:
   ```bash
   python build.py
   # or: python build_standalone.py
   ```
5. **Flash the Output**:
   The signed, flashable ZIP is written to `dist/` (e.g., `dist/mffm14-inter-2026.09.11.zip`). Transfer it to your device and flash it directly in **Magisk**, **KernelSU**, or **APatch**, then reboot.

---

### Method 2: Mobile Termux One-Shot Builder
> **Best for:** Users building directly on Android without access to a computer.

1. Install [Termux](https://github.com/termux/termux-app/releases) from GitHub or F-Droid.
2. Extract `MFFMv14-Standalone-Template.zip` into your Termux home directory:
   ```bash
   cd ~
   unzip MFFMv14-Standalone-Template.zip -d MFFMv14
   cd MFFMv14
   ```
3. Copy your font files into `Fonts/Sans/` (e.g., from `/sdcard/Download/`):
   ```bash
   cp ~/storage/shared/Download/MyFont*.ttf Fonts/Sans/
   ```
4. Run the builder script:
   ```bash
   sh termux-build.sh
   ```
   - Automatically installs the required Python and fontTools packages in Termux.
   - Builds the standalone font module.
   - Prompts to install the module directly via root (`su`) with Magisk, KernelSU, or APatch.

---

## 📂 Font Directory Structure & Categories

The builder automatically categorizes and routes fonts based on their folder or file naming:

```
MFFMv14/
├── Fonts/
│   ├── Sans/         <-- Primary system font (Required)
│   ├── Monospace/    <-- Terminal & code font (Optional)
│   ├── Serif/        <-- Serif / news font (Optional)
│   └── Bengali/      <-- Regional Bengali font (Optional)
├── dist/             <-- Output flashable ZIP modules
├── build.py          <-- CLI entrypoint
├── build_standalone.py
├── termux-build.sh
└── requirements.txt
```

### Supported Font Formats
The standalone builder natively accepts:
- TrueType fonts (`.ttf`)
- OpenType fonts (`.otf` — CFF/PostScript outlines are automatically converted to TrueType quadratics)
- TrueType Collections (`.ttc`, `.otc`)
- Web fonts (`.woff`, `.woff2`)

---

## ⚙️ Compiler CLI Options & Customization

The standalone builder provides powerful options to customize font rendering and behavior:

```bash
python build.py [OPTIONS]
# or: python build_standalone.py [OPTIONS]
```

### General Options
- `--fonts-dir DIR`: Path to custom fonts directory (default: `./Fonts`).
- `--mode {auto,static,variable}`: Force font mode detection (default: `auto`).
- `--name NAME`: Override module display name.
- `--version VER`: Override module version string (default: `YYYY.MM.DD`).
- `--version-code CODE`: Override numeric `versionCode` (default: `YYMMDD`).
- `--output-dir DIR`: Custom directory for generated ZIP (default: `./dist`).
- `--no-sign`: Create an unsigned ZIP (skips ZipSignerust).
- `--keep-hinting`: Preserve TrueType hinting instructions (by default, hinting is stripped for cleaner rendering and smaller file size).
- `--no-prefix`: Do not prepend `MFFM` or `Mistu` to internal font family names.
- `--inspect`: Report detected fonts, weights, and axes without building.

---

### Clock Colon Customization & Shift

Many modern clock widgets (lockscreen, status bar, and always-on display) display the time as `12:30`. MFFMv14 can automatically generate and inject an optically centered colon between digits (`between_digits`).

- **Vertical Colon Shift / Offset**:
  If the default centered colon sits slightly too high or too low for your device's clock layout:
  ```bash
  python build.py --colon-offset 25   # Shift colon UP by 25 font units
  python build.py --colon-offset -30  # Shift colon DOWN by 30 font units
  ```
  *(Alias: `--colon-shift`)*
- **Colon Alignment Reference**:
  ```bash
  python build.py --colon-alignment center      # Mathematical center of digit bounding box (default)
  python build.py --colon-alignment cap_height  # Aligned to font Cap Height
  python build.py --colon-alignment x_height    # Aligned to font x-Height
  ```
- **Contextual Rule**:
  ```bash
  python build.py --colon-rule between_digits   # Replace only between numbers (e.g. 12:30) (default)
  python build.py --colon-rule after_digit      # Replace after any number (e.g. 12:)
  python build.py --colon-rule always           # Always replace colon everywhere
  ```
- **Disable Centered Colon**:
  ```bash
  python build.py --no-centered-colon
  ```

---

### Digit Equalization (Wobble-Free Clocks)

Some proportional fonts have digits with differing advance widths (for instance, `1` is much narrower than `8`). As the clock ticks from `11:59` to `12:00`, the clock numbers can wobble or shift horizontally.

To solve this, enable digit equalization:
```bash
python build.py --equalize-digits
```
- Equalizes advance widths of all digits (`0`–`9`) to the widest digit.
- Centers each digit outline optically within its new advance slot.
- Ensures stable, wobble-free lockscreen and status bar clocks.

---

### Lockscreen Clock PUA Colon

Certain OEM custom skins (HyperOS, One UI, OxygenOS, Nothing OS, Google Pixel) query Private Use Area (PUA) codepoints (`U+EE01`) or ratio symbols (`U+2236`, `U+2982`) for lockscreen clocks.

Enable PUA colon mapping:
```bash
python build.py --pua-colon
```
This maps the colon glyph across all font cmap tables to `U+EE01`, `U+2236`, and `U+2982`.

---

### OpenType Feature Freezing

Permanently freeze OpenType features into the font glyph tables (e.g., slashed zero `zero`, tabular numbers `tnum`, stylistic sets `ss01`, `cv01`):

```bash
python build.py --features zero,ss01
```

Family-specific feature freezing:
- `--mono-features TAGS`: Monospace font family.
- `--serif-features TAGS`: Serif font family.
- `--bengali-features TAGS`: Bengali font family.

---

### Synthetic Italics

If your primary Sans-serif font only provides upright weights and lacks italic faces:
```bash
python build.py --synthetic-italic
```
- Automatically generates slanted companion italic faces for all available upright weights.
- Adjust angle using `--synthetic-italic-angle` (default: `-12.0` degrees).

---

### Saving and Loading Build Configurations

Save your favorite build options into `.mffm-build.json` for repeated builds:
```bash
python build.py --features zero,tnum --colon-offset 20 --equalize-digits --save-config
```
Future runs will automatically read `.mffm-build.json` without needing CLI arguments.

---

## 📱 External Fonts on Device (`/sdcard/MFFM/`)

Even though the standalone module is pre-compiled, you can dynamically override fonts after installation by placing custom font files directly into `/sdcard/MFFM/` on your phone!

### Standard Face Counts for External Static Fonts
When the standalone installer detects external static fonts in `/sdcard/MFFM/`, it configures them using standardized face counts without requiring any on-device Python or TTC bundling:

| Category | Target Directory | Standard Face Count | Selected Faces |
| :--- | :--- | :--- | :--- |
| **Serif** | `/sdcard/MFFM/Serif/` | **4 faces** | `Regular` (400 normal), `Italic` (400 italic), `Bold` (700 normal), `BoldItalic` (700 italic) |
| **Bengali** | `/sdcard/MFFM/Bengali/` | **2 faces** | `Regular` (400 normal), `Bold` (700 normal) |
| **Monospace**| `/sdcard/MFFM/Monospace/` | **1 face** | `Regular` (400 normal) |

---

### External Variable Font Tuning (`.conf`)

When an external variable font is placed in `/sdcard/MFFM/`, the standalone installer automatically scans its variation axes (`fvar`) using an ultra-fast, binary table parser written in **pure shell and `awk`** (100% Python-free).

It automatically creates an axis configuration file at:
```
/sdcard/MFFM/MFFMv14_<FAMILY_SLUG>.conf
```

You can open this `.conf` file in any text editor on Android to adjust weights:
```sh
# MFFMv14 Standalone Variable Font Axis Configuration
VF_SANS_AXIS_TAG="wght"
VF_SANS_AXIS_MIN="100"
VF_SANS_AXIS_MAX="900"
VF_SANS_AXIS_DEF="400"

# Target weight coordinates
WEIGHT_THIN="100"
WEIGHT_LIGHT="300"
WEIGHT_REGULAR="400"
WEIGHT_MEDIUM="500"
WEIGHT_BOLD="700"
WEIGHT_BLACK="900"
```

Re-flashing the standalone module instantly applies your custom weight mapping in seconds!

---

## 🛡️ Root Manager Compatibility

The standalone module payload (`template-standalone/`) is engineered for universal compatibility across all modern Android root solutions:

- **Magisk**: v20.4 to v28+
- **KernelSU**: v0.9.0 to v1.0+
- **APatch**: v0.10.0 to v0.11+
- **Action WebUI**: Trigger font reconfiguration directly from the KernelSU/APatch WebUI action button (`action.sh`).

---

## ❓ Troubleshooting & FAQ

### Q: Does the standalone module require `mffm-runtime`?
**A:** No. Standalone modules are 100% independent. You do **NOT** need `mffm-runtime` installed on your device.

### Q: Why did the build script say "OTF to TTF conversion"?
**A:** Android's native font rendering stack requires TrueType (`glyf` / quadratic) outlines for variable font variation tables and proper lockscreen clock scaling. The builder automatically converts PostScript (`CFF`) outlines to TrueType curves during the build.

### Q: Why is my lockscreen clock colon not centered?
**A:** Re-build the module with `--colon-offset` (e.g. `python build.py --colon-offset 20` or `-20`) to tune the height to your OEM's specific lockscreen layout.

### Q: Where are installation logs stored?
**A:** The standalone installer stores detailed installation logs at:
```
/sdcard/MFFM/mffmv14_debug_<TIMESTAMP>.log
```
