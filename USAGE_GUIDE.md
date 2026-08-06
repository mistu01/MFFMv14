# MFFMv14 Master User & Architecture Guide

This guide provides a comprehensive technical reference for creating, flashing, configuring, and debugging font modules built with the **MFFMv14** engine.

---

## Table of Contents

1. [Prerequisites & Environment Setup](#1-prerequisites--environment-setup)
2. [Module Creation (`build.py`)](#2-module-creation-buildpy)
   - [Font Discovery & Categorization](#font-discovery--categorization)
   - [Single TTC Collection Architecture (`DroidSans.ttf`)](#single-ttc-collection-architecture-droidsans-ttf)
   - [OpenType Feature Freezing](#opentype-feature-freezing)
   - [Centered Colon Injection](#centered-colon-injection)
   - [Command-Line Options & Flags](#command-line-options--flags)
3. [On-Device Building & Flashing with Termux (`termux-build.sh`)](#3-on-device-building--flashing-with-termux-termux-buildsh)
   - [Storage Setup & Permission](#storage-setup--permission)
   - [Setup & Unpacking](#setup--unpacking)
   - [Placing Font Files](#placing-font-files)
   - [Running `termux-build.sh`](#running-termux-buildsh)
   - [Advanced Command Features](#advanced-command-features)
   - [Termux Troubleshooting](#termux-troubleshooting)
4. [Module Flashing & Root Installation Workflow (`customize.sh`)](#4-module-flashing--root-installation-workflow-customizesh)
   - [Supported Root Environments](#supported-root-environments)
   - [Installer Section-by-Section Breakdown](#installer-section-by-section-breakdown)
5. [The `/sdcard/MFFM` Directory & Runtime Configuration](#5-the-sdcardmffm-directory--runtime-configuration)
   - [Monospace Font Priority Rules](#monospace-font-priority-rules)
   - [Serif Font Priority Rules](#serif-font-priority-rules)
   - [Variable Font Dynamic Axis Tuning (`.conf` files)](#variable-font-dynamic-axis-tuning-conf-files)
6. [Legacy Module Migration (`update.py`)](#6-legacy-module-migration-updatepy)
7. [Debugging & Troubleshooting](#7-debugging--troubleshooting)

---

## 1. Prerequisites & Environment Setup

Ensure Python 3.9 or newer is installed on your system. Before compiling fonts or running migration scripts, install all required dependencies:

```bash
pip install -r requirements.txt
```

### Dependencies Included in `requirements.txt`
- `fonttools>=4.55` — Font table parsing, subsetting, and TTC container generation.
- `cryptography>=43.0` — Cryptographic signing of generated module ZIP files.
- `brotli` — WOFF2 font decompression.
- `opentype-feature-freezer` — `pyftfeatfreeze` library for freezing OpenType layout features into default glyph mappings.

---

## 2. Module Creation (`build.py`)

`build.py` parses all font files placed inside the `Fonts/` directory and compiles them into a signed, flashable Android font module.

### Font Discovery & Folder Categorization
The compiler scans `Fonts/` and its subdirectories for `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, and `.woff2` files. Fonts are categorized automatically via folder paths or filename fallbacks:
- **Primary Sans-Serif Family**: Fonts placed in `Fonts/` or `Fonts/Sans/`.
- **Monospace Family**: Fonts placed in `Fonts/Monospace/` or `Fonts/Mono/` (or matching filename tags `mono`, `code`, `consolas`).
- **Serif Family**: Fonts placed in `Fonts/Serif/` (or matching filename tags `serif`).
- **Bengali Family**: Fonts placed in `Fonts/Bengali/` or `Fonts/Beng/` (or matching filename tags `bengali`, `beng`).

Using dedicated subdirectories (`Fonts/Sans/`, `Fonts/Monospace/`, `Fonts/Serif/`, `Fonts/Bengali/`) guarantees 100% accurate classification even if font filenames or internal font metadata do not contain keyword tags!

### Single TTC Collection Architecture (`DroidSans.ttf`)
All discovered font faces (Sans-serif static or variable, Monospace static or variable, Serif static or variable, and Bengali static or variable) are compiled into **ONE single `DroidSans.ttf` TTC container**:
- **Indices 0..S**: Sans-serif font faces.
- **Indices M1..Mn**: Monospace font faces.
- **Indices R1..Rn**: Serif font faces.
- **Indices B1..Bn**: Bengali font faces.

Corresponding XML configuration fragments (`sans.xml`, `condensed.xml`, `mono.xml`, `serif.xml`, `bengali.xml`, `clock.xml`) are generated in `Files/` referencing `DroidSans.ttf` at their respective TTC face indices with full 100-900 weight class mappings (100 Thin..900 Black).

### Per-Family OpenType Feature Freezing
`build.py` integrates `pyftfeatfreeze` for interactive or headless OpenType feature freezing.
When running interactively:
1. **Sans-serif Prompt**: Prompts to freeze features for the primary Sans-serif font family.
2. **Monospace Prompt**: If Monospace fonts are supplied (in `Fonts/Monospace/` or `Fonts/Mono/`), additionally prompts to select and freeze features specifically for the Monospace family.
3. **Serif Prompt**: If Serif fonts are supplied (in `Fonts/Serif/`), additionally prompts to select and freeze features specifically for the Serif family.
4. **Bengali Prompt**: If Bengali fonts are supplied (in `Fonts/Bengali/` or `Fonts/Beng/`), additionally prompts to select and freeze features specifically for the Bengali family.

- **[SAFE TO FREEZE]**: Stylistic Sets (`ss01`–`ss20`), Character Variants (`cv01`–`cv99`), Slashed Zero (`zero`), Tabular Figures (`tnum`), Proportional Figures (`pnum`), Stylistic Alternates (`salt`), Case-Sensitive Forms (`case`).
- **[CAUTION]**: Repositioning features (`frac`, `numr`, `dnom`, `subs`, `sups`) that alter number layout globally.
- **[UNSAFE / NOT RECOMMENDED]**: Master alternates like `aalt` and default layout features (`calt`, `kern`, `liga`, `ccmp`).

### Centered Colon Injection
Inspects input fonts for contextual centered colon support (displaying `: ` vertically centered between digits for `12:30` clock displays). If missing, `build.py` can generate and inject contextual layout rules automatically.

### Command-Line Options & Flags

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--fonts-dir` | `<PATH>` | Directory containing source font files. | `Fonts/` |
| `--mode` | `auto`, `static`, `variable` | Font compilation mode. | `auto` |
| `--keep-hinting` | *Flag* | Preserve original TrueType hinting instructions. | False (hints stripped) |
| `--no-prefix` | *Flag* | Disable `Mistu` family name transformation. | False |
| `--no-zip` | *Flag* | Stage files in `Files/` without compressing into ZIP. | False |
| `--no-sign` | *Flag* | Output unsigned ZIP file. | False (signed) |

---

## 3. On-Device Building & Flashing with Termux (`termux-build.sh`)

`termux-build.sh` is an automated one-shot script designed to run natively inside **Termux** on Android devices. It handles dependency setup, font compilation, and root flashing seamlessly.

### Storage Setup & Permission
1. Grant Termux access to your phone's internal storage:
   ```bash
   termux-setup-storage
   ```
2. Tap **ALLOW** on the Android permission prompt.

*(On Android 11+, if no pop-up appears, navigate to **Android Settings → Apps → Termux → Permissions → Files and media** and enable **"Allow management of all files"**).*

### Setup & Unpacking
1. Download `MFFMv14-Source-Template.zip` to your device (e.g. `/sdcard/Download/` or `/sdcard/Download/Nekogram/`).
2. Open Termux and extract the package into your home directory:
   ```bash
   unzip /sdcard/Download/MFFMv14-Source-Template.zip -d ~/MFFMv14
   cd ~/MFFMv14
   ```

### Placing Font Files
Copy your `.ttf`, `.otf`, `.ttc`, or `.woff2` font files into the `Fonts/` folder:
```bash
cp /sdcard/Download/*.ttf Fonts/
```

Or organize multi-family setups into dedicated folders:
- `Fonts/Sans/` — Primary sans-serif body fonts
- `Fonts/Monospace/` — Monospace / code fonts
- `Fonts/Serif/` — Serif fonts

### Running `termux-build.sh`

- **Interactive Build & Flash (Default)**:
  ```bash
  sh termux-build.sh
  ```
  *Installs dependencies via `pkg`/`pip`, prompts for OpenType feature choices, compiles the ZIP, and prompts to flash via `su`.*

- **Non-Interactive Auto-Flash (`--yes`)**:
  ```bash
  sh termux-build.sh --yes
  ```

- **Build-Only Mode (No Root / No Flash)**:
  ```bash
  sh termux-build.sh --no-flash
  ```

### Advanced Command Features
Pass custom flags directly to `build.py` after `--`:

- **Read fonts from a custom directory**:
  ```bash
  sh termux-build.sh -- --fonts-dir /sdcard/Download/Nekogram
  ```
- **Force Variable Font mode**:
  ```bash
  sh termux-build.sh -- --mode variable
  ```
- **Freeze OpenType features**:
  ```bash
  sh termux-build.sh -- --features "tnum,ss01"
  ```

### Termux Troubleshooting

| Issue | Solution |
| :--- | :--- |
| `error: no fonts in ~/MFFMv14/Fonts` | Copy your `.ttf` or `.otf` font files into `Fonts/` before running `termux-build.sh`. |
| `pkg install failed` | Run `pkg update && pkg upgrade -y` first to refresh repository mirrors. |
| `no root shell available` | Build-only mode will still output the signed ZIP in `dist/`. Copy it to Downloads: `cp dist/*.zip /sdcard/Download/` and flash manually via your root app. |

---

## 4. Module Flashing & Root Installation Workflow (`customize.sh`)

### Supported Root Environments
The module installer (`customize.sh`) is fully compatible with:
- **Magisk** (v20.4+)
- **KernelSU**
- **APatch**
- **Mountify** / OverlayFS environments

### Installer Section-by-Section Breakdown

When flashed in Magisk / KernelSU / APatch, `customize.sh` executes 5 distinct steps:

1. **Section 1/5: Installing primary font payload**
   - Copies `DroidSans.ttf` from `Files/` to `/system/fonts/DroidSans.ttf`.
2. **Section 2/5: Patching Android font families**
   - Patches `/system/etc/fonts.xml` and `font_fallback.xml` for `sans-serif`, `sans-serif-condensed`, `roboto-flex`, `serif`, `noto-serif`.
   - On ROMs with `/product/etc/fonts_customization.xml` (e.g. Google Pixel), copies `DroidSans.ttf` as `Rubik-Regular.ttf` / `Rubik-Italic.ttf` into `/product/fonts` and patches product XML entries.
3. **Section 3/5: Applying optional font resources**
   - Evaluates **Monospace** and **Serif** priority rules (see Section 5).
   - Installs Bengali font overlays if supplied (`Beng-*.ttf`).
4. **Section 4/5: Finalizing root integration**
   - Sets SELinux `trusted.overlay.opaque` extended attributes (`setfattr`) on KernelSU/APatch for overlay directory mount stability.
5. **Section 5/5: Variable font axis configuration**
   - Creates or loads schema v2 axis configuration files (`.conf`) in `/sdcard/MFFM/`.

---

## 5. The `/sdcard/MFFM` Directory & Runtime Configuration

The `/sdcard/MFFM` folder on internal storage allows user customizations and external font fallbacks without modifying module files.

### Monospace Font Priority Rules

When installing monospace fonts, `customize.sh` checks in two tiers:

1. **Priority 1 (Module Native Monospace - Highest Priority)**:
   - If the module contains native monospace fonts (bundled into `DroidSans.ttf` via `Files/mono.xml`), the installer uses `mono.xml` to patch `fonts.xml` for `monospace`, `cutive-mono`, and `droidsans-mono`.
   - **Any external `/sdcard/MFFM/Mono.ttf` file is IGNORED.**
2. **Priority 2 (External Monospace Fallback)**:
   - If the module has NO native monospace font (`Files/mono.xml` absent):
   - The installer searches `/sdcard/MFFM/Mono.ttf` and copies it directly to `/system/fonts/CutiveMono.ttf` and `/system/fonts/DroidSansMono.ttf`.

### Serif Font Priority Rules

1. **Priority 1 (Module Native Serif - Highest Priority)**:
   - If the module contains native serif fonts (bundled into `DroidSans.ttf` via `Files/serif.xml`), the installer uses `serif.xml` to patch `fonts.xml` for `serif` and `noto-serif`.
   - **Any external `/sdcard/MFFM/Serif-*.ttf` files are IGNORED.**
2. **Priority 2 (External Serif Fallback)**:
   - If the module has NO native serif font (`Files/serif.xml` absent):
   - The installer searches `/sdcard/MFFM/` for `Serif-Regular.ttf`, `Serif-Italic.ttf`, `Serif-Bold.ttf`, `Serif-BoldItalic.ttf` and copies them directly to `/system/fonts/NotoSerif-*.ttf`.

### Variable Font Dynamic Axis Tuning (`.conf` files)

For Variable Font modules, a configuration file is created at:
`/sdcard/MFFM/MFFMv14_<Family>_<ID>.conf`

Users can edit this `.conf` file to adjust variable font weights and axis values (e.g. `wght`, `opsz`, `wdth`, `grad`) without re-flashing:
```ini
CONFIG_SCHEMA=2
MODULE_IDENTITY=vf-a1b2c3d4e5f678901234

# SANS-SERIF / UPRIGHT
SANS_UPRIGHT_REGULAR_WGHT=400
SANS_UPRIGHT_MEDIUM_WGHT=500
SANS_UPRIGHT_BOLD_WGHT=700
SANS_UPRIGHT_OPSZ=20
```

To re-apply updated axis values live without re-flashing:
Run `/system/bin/font-config` from a root terminal, or simply reboot the device.

---

## 6. Legacy Module Migration (`update.py`)

To upgrade old MFFM module ZIP files to the latest MFFMv14 core:

1. Place legacy MFFM module ZIP files into `Old Modules/`.
2. Run:
   ```bash
   python update.py
   ```
3. Updated, signed MFFMv14 modules will be saved to `Updated Modules/`.

---

## 7. Debugging & Troubleshooting

### Diagnostic Logs
- **Build Logs**: Stored in standard terminal output during `build.py` execution.
- **Flashing Logs**: Viewable inside Magisk / KernelSU / APatch installation screen, or logged to `/data/adb/modules/mffm14-*/`.

### Common Issues & Solutions

1. **System UI Crashes or Missing Fonts**:
   - Check `/system/etc/fonts.xml` to verify that `<family name="sans-serif">` points to `<font index="...">DroidSans.ttf</font>`.
   - Ensure the module ZIP was properly signed using `zipsigner_auto.py`.

2. **Monospace / Serif Font Not Changing**:
   - Remember Priority 1: If the module contains a native Mono or Serif font in `Fonts/`, external files in `/sdcard/MFFM` are ignored. Remove native mono/serif files from `Fonts/` before building if you want to use external `/sdcard/MFFM` fonts.

3. **Centered Colon Not Centered**:
   - Build with `--centered-colon` flag to force injection of contextual digit rules.

4. **Variable Font Axis Reset**:
   - If you modify font files, the module identity changes. The installer will clean up old configuration files and generate a new matching `.conf` file automatically.
