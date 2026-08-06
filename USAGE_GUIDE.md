# MFFMv14 Master User & Architecture Guide

This guide provides a comprehensive technical reference for creating, flashing, configuring, and debugging font modules built with the **MFFMv14** engine.

---

## Table of Contents

1. [Prerequisites & Environment Setup](#1-prerequisites--environment-setup)
2. [Workspace Architecture & Organization](#2-workspace-architecture--organization)
3. [Module Creation (`build.py`)](#3-module-creation-buildpy)
   - [Font Discovery & Folder Categorization](#font-discovery--folder-categorization)
   - [Any-Family Module Compilation](#any-family-module-compilation)
   - [Single TTC Collection Architecture (`DroidSans.ttf`)](#single-ttc-collection-architecture-droidsans-ttf)
   - [Bengali Full 100–900 Weight Class Engine](#bengali-full-100900-weight-class-engine)
   - [OpenType Feature Freezing](#opentype-feature-freezing)
   - [Centered Colon Injection](#centered-colon-injection)
   - [Command-Line Options & Flags](#command-line-options--flags)
4. [On-Device Building & Flashing with Termux (`termux-build.sh`)](#4-on-device-building--flashing-with-termux-termux-buildsh)
   - [Storage Setup & Permission](#storage-setup--permission)
   - [Setup & Unpacking](#setup--unpacking)
   - [Placing Font Files](#placing-font-files)
   - [Running `termux-build.sh`](#running-termux-buildsh)
   - [Advanced Command Features](#advanced-command-features)
   - [Termux Troubleshooting](#termux-troubleshooting)
5. [Module Flashing & Root Installation Workflow (`customize.sh`)](#5-module-flashing--root-installation-workflow-customizesh)
   - [Supported Root Environments](#supported-root-environments)
   - [Installer Section-by-Section Breakdown](#installer-section-by-section-breakdown)
6. [The `/sdcard/MFFM` Directory & Runtime Configuration](#6-the-sdcardmffm-directory--runtime-configuration)
   - [Subdirectory Auto-Creation & Folder Separation](#subdirectory-auto-creation--folder-separation)
   - [Universal Font Family Priority Rules](#universal-font-family-priority-rules)
   - [Native Binary Variable Font Parsing & XML Patching](#native-binary-variable-font-parsing--xml-patching)
   - [Variable Font Dynamic Axis Tuning (`.conf` files)](#variable-font-dynamic-axis-tuning-conf-files)
7. [Legacy Module Migration (`update.py`)](#7-legacy-module-migration-updatepy)
8. [Debugging & Troubleshooting](#8-debugging--troubleshooting)

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

## 2. Workspace Architecture & Organization

The MFFMv14 workspace is structured into dedicated directories for modular maintainability:

- **`template/`**: Contains clean module payload templates (`customize.sh`, `module.prop`, `service.sh`, `uninstall.sh`, `post-mount.sh`, `font-config.sh`, `META-INF/`, `Files/`).
- **`Fonts/`**: Source font directory with subdirectories `Sans/`, `Monospace/`, `Serif/`, and `Bengali/`.
- **`dist/`**: Target directory where compiled, signed module ZIP files and `MFFMv14-Source-Template.zip` are saved.
- **`Old Modules/`**: Folder for legacy MFFM ZIP packages to be updated by `update.py`.
- **`Updated Modules/`**: Output folder for upgraded MFFMv14 module packages.

*Compilation in `build.py` runs inside isolated temporary directories (`tempfile.mkdtemp()`), keeping the repository root completely clean of transient files.*

---

## 3. Module Creation (`build.py`)

`build.py` parses font files placed inside `Fonts/` subdirectories and compiles them into a signed, flashable Android font module.

### Font Discovery & Folder Categorization
The compiler scans `Fonts/` subdirectories for `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, and `.woff2` files. Strict folder separation guarantees 100% accurate classification:
- **Sans-Serif**: Fonts placed in `Fonts/Sans/` (or `Fonts/` root).
- **Monospace**: Fonts placed in `Fonts/Monospace/` or `Fonts/Mono/`.
- **Serif**: Fonts placed in `Fonts/Serif/`.
- **Bengali**: Fonts placed in `Fonts/Bengali/` or `Fonts/Beng/`.

*Note: Loose font files placed directly in `Fonts/` root are automatically flagged; users are guided to place them into the appropriate family folder.*

### Any-Family Module Compilation
MFFMv14 allows building modules with **any combination of supplied font families**:
- You can create a module containing **only Bengali fonts**, **only Serif fonts**, **only Monospace fonts**, or **only Sans fonts**.
- Sans-serif is no longer mandatory. `build.py` extracts family metadata from whichever faces are supplied and builds a valid, working module package.

### Single TTC Collection Architecture (`DroidSans.ttf`)
All discovered font faces across all supplied categories are packed into **ONE single `DroidSans.ttf` TTC container**:
- **Indices 0..S**: Sans-serif font faces.
- **Indices M1..Mn**: Monospace font faces.
- **Indices R1..Rn**: Serif font faces.
- **Indices B1..Bn**: Bengali font faces.

XML configuration fragments (`sans.xml`, `condensed.xml`, `mono.xml`, `serif.xml`, `bengali.xml`, `clock.xml`) reference `DroidSans.ttf` at their respective TTC face indices.

### Bengali Full 100–900 Weight Class Engine
Bengali fonts placed in `Fonts/Bengali/` are processed with full weight class support:
- Static faces are mapped across the full **100–900 weight spectrum** (100 Thin, 200 ExtraLight, 300 Light, 400 Regular, 500 Medium, 600 SemiBold, 700 Bold, 800 ExtraBold, 900 Black).
- Variable faces extract axis bounds (`wght`, etc.) to generate precise `bengali.xml` fragments.
- Automatically patches `und-Beng` and `bn` language family entries in system font XMLs.

### Per-Family OpenType Feature Freezing
`build.py` integrates `pyftfeatfreeze` for interactive or headless OpenType feature freezing:
- **Sans-serif Prompt**: Prompts to freeze features for Sans-serif fonts.
- **Monospace Prompt**: Prompts to freeze features for Monospace fonts.
- **Serif Prompt**: Prompts to freeze features for Serif fonts.
- **Bengali Prompt**: Prompts to freeze features for Bengali fonts (`--bengali-features`).

- **[SAFE TO FREEZE]**: Stylistic Sets (`ss01`–`ss20`), Character Variants (`cv01`–`cv99`), Slashed Zero (`zero`), Tabular Figures (`tnum`), Proportional Figures (`pnum`), Stylistic Alternates (`salt`), Case-Sensitive Forms (`case`).
- **[CAUTION]**: Repositioning features (`frac`, `numr`, `dnom`, `subs`, `sups`).
- **[UNSAFE]**: Master alternates (`aalt`) and default layout features (`calt`, `kern`, `liga`, `ccmp`).

### Centered Colon Injection
Inspects input fonts for contextual centered colon support (`: ` vertically centered between digits for `12:30` clock displays). If missing, `build.py` can generate and inject contextual layout rules automatically (`--centered-colon`).

### Command-Line Options & Flags

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--fonts-dir` | `<PATH>` | Directory containing source font files. | `Fonts/` |
| `--mode` | `auto`, `static`, `variable` | Font compilation mode. | `auto` |
| `--bengali-features` | `<LIST>` | OpenType feature list for Bengali fonts (e.g. `"ss01,zero"`). | None |
| `--features` | `<LIST>` | OpenType feature list for Sans fonts. | None |
| `--mono-features` | `<LIST>` | OpenType feature list for Monospace fonts. | None |
| `--serif-features` | `<LIST>` | OpenType feature list for Serif fonts. | None |
| `--keep-hinting` | *Flag* | Preserve original TrueType hinting instructions. | False (hints stripped) |
| `--no-prefix` | *Flag* | Disable `Mistu` family name transformation. | False |
| `--no-zip` | *Flag* | Stage files in `Files/` without compressing into ZIP. | False |
| `--no-sign` | *Flag* | Output unsigned ZIP file. | False (signed) |

---

## 4. On-Device Building & Flashing with Termux (`termux-build.sh`)

`termux-build.sh` is an automated one-shot script designed to run natively inside **Termux** on Android devices.

### Storage Setup & Permission
1. Grant Termux storage permissions:
   ```bash
   termux-setup-storage
   ```
2. Enable "Allow management of all files" in Android Settings if prompted.

### Setup & Unpacking
1. Download `MFFMv14-Source-Template.zip` to your device (e.g. `/sdcard/Download/`).
2. Open Termux and extract:
   ```bash
   unzip /sdcard/Download/MFFMv14-Source-Template.zip -d ~/MFFMv14
   cd ~/MFFMv14
   ```

### Placing Font Files
Organize source font files into dedicated folders:
- `Fonts/Sans/` — Primary sans-serif body fonts
- `Fonts/Monospace/` — Monospace / code fonts
- `Fonts/Serif/` — Serif fonts
- `Fonts/Bengali/` — Bengali language fonts

### Running `termux-build.sh`

- **Interactive Build & Flash (Default)**:
  ```bash
  sh termux-build.sh
  ```
- **Non-Interactive Auto-Flash (`--yes`)**:
  ```bash
  sh termux-build.sh --yes
  ```
- **Build-Only Mode (No Root / No Flash)**:
  ```bash
  sh termux-build.sh --no-flash
  ```

---

## 5. Module Flashing & Root Installation Workflow (`customize.sh`)

### Supported Root Environments
The module installer (`customize.sh`) is fully compatible with **Magisk** (v20.4+), **KernelSU**, **APatch**, and **Mountify** / OverlayFS environments.

### Installer Section-by-Section Breakdown

1. **Section 1/5: Installing primary font payload**
   - Copies `DroidSans.ttf` (and standalone payload files) to `/system/fonts/`.
2. **Section 2/5: Patching Android font families**
   - Evaluates Sans-serif priority rules. Patches `/system/etc/fonts.xml` and `font_fallback.xml` for `sans-serif`, `sans-serif-condensed`, `roboto-flex`.
   - On Pixel ROMs with `/product/etc/fonts_customization.xml`, pattern-patches Google Sans families.
3. **Section 3/5: Applying optional font resources**
   - Evaluates **Monospace**, **Serif**, and **Bengali** priority rules.
   - Natively extracts variable font variation axes for external fonts if present.
4. **Section 4/5: Finalizing root integration**
   - Sets SELinux `trusted.overlay.opaque` extended attributes (`setfattr`) for OverlayFS mount stability.
5. **Section 5/5: Variable font axis configuration**
   - Creates or retains schema v2 axis configuration files (`.conf`) in `/sdcard/MFFM/`.

---

## 6. The `/sdcard/MFFM` Directory & Runtime Configuration

The `/sdcard/MFFM` directory on internal storage allows runtime user customizations and external font fallbacks.

### Subdirectory Auto-Creation & Folder Separation
When any MFFMv14 module is flashed, `customize.sh` automatically creates dedicated subdirectories:
- `/sdcard/MFFM/Sans/`
- `/sdcard/MFFM/Serif/`
- `/sdcard/MFFM/Monospace/`
- `/sdcard/MFFM/Bengali/`

### Universal Font Family Priority Rules

For **every** font category (Sans, Serif, Monospace, Bengali), the installer enforces a 3-tier priority:

1. **Priority 1 (Module Inbuilt Supplied Font — Highest Priority)**:
   - If the module payload contains native XML fragments (`sans.xml`, `serif.xml`, `mono.xml`, `bengali.xml`), the installer uses the native bundled fonts.
   - **External `/sdcard/MFFM/` files for that family are ignored.**
2. **Priority 2 (External Fallback from `/sdcard/MFFM` Subdirectories)**:
   - If the module does NOT contain that font family, the installer checks `/sdcard/MFFM/<Family>/` (and root `/sdcard/MFFM/`).
   - **Static Fonts**: Copied to `/system/fonts/` and patched into system XMLs.
   - **Variable Fonts**: Natively parsed via `extract_fvar_axes` to extract variation axes and patch system XMLs with 100–900 weight class axis attributes.
3. **Priority 3 (No Fonts Supplied Anywhere)**:
   - If no font is supplied for a category, installation skips that category cleanly (`status_skip`) without errors. If no fonts are supplied anywhere, the module installs 100% cleanly without patching system XMLs.

### Native Binary Variable Font Parsing & XML Patching

`customize.sh` includes native binary parsing capabilities (`extract_fvar_axes` and `generate_vf_xml_fragment`):
- Reads the SFNT table directory directly from `.ttf`/`.otf` binaries to locate `fvar` (Font Variations) tables.
- Extracts `wght`, `opsz`, `ital`, `slnt`, and `wdth` axis ranges.
- Natively generates full 100–900 weight class XML fragments (`axis="wght=..."`) in recovery without requiring external custom scripts or Python dependencies!

### Variable Font Dynamic Axis Tuning (`.conf` files)

For Variable Font modules, a configuration file is maintained at:
`/sdcard/MFFM/MFFMv14_<Family>_<ID>.conf`

Users can edit axis weights (`wght`, `opsz`, `wdth`, `grad`) without re-flashing:
```ini
CONFIG_SCHEMA=2
MODULE_IDENTITY=vf-a1b2c3d4e5f678901234

# SANS-SERIF / UPRIGHT
SANS_UPRIGHT_REGULAR_WGHT=400
SANS_UPRIGHT_MEDIUM_WGHT=500
SANS_UPRIGHT_BOLD_WGHT=700
SANS_UPRIGHT_OPSZ=20
```

*Updating or re-installing the same font module automatically preserves existing `.conf` settings and user customizations.*

---

## 7. Legacy Module Migration (`update.py`)

To upgrade old MFFM module ZIP files to the latest MFFMv14 core:

1. Place legacy MFFM module ZIP files into `Old Modules/`.
2. Run:
   ```bash
   python update.py
   ```
3. Updated, signed MFFMv14 modules will be saved to `Updated Modules/`.

---

## 8. Debugging & Troubleshooting

### Diagnostic Logs
- **Build Logs**: Terminal output during `build.py` or `termux-build.sh`.
- **Flashing Logs**: Viewable inside Magisk / KernelSU / APatch installation screens, or logged to `/data/adb/modules/mffm14-*/`.

### Common Issues & Solutions

1. **System UI Crashes or Missing Fonts**:
   - Check `/system/etc/fonts.xml` to verify `<family name="sans-serif">` references valid font targets.
   - Ensure the module ZIP was properly signed.

2. **External Monospace / Serif / Bengali Fonts Ignored**:
   - Check Priority 1: If the module payload contains a native font for that category, external `/sdcard/MFFM/` files are ignored. Build a module with only the desired categories if you want to rely on external fallbacks.

3. **Variable Font Config Retention**:
   - Re-installing the same module retains `/sdcard/MFFM/*.conf` settings. If you change font families, the installer automatically cleans up mismatched legacy `.conf` files and generates a new configuration.

