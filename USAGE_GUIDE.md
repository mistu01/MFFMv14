# MFFMv14 Scripts Usage Guide (`build.py` & `update.py`)

This document provides a detailed command-line reference, feature description, flag argument listing, installation steps, and usage examples for the python compilation scripts in **MFFMv14**:
1. `build.py`: Main font compiler to generate flashable Magisk/KernelSU/APatch font modules from source fonts.
2. `update.py`: Batch migration utility to update legacy MFFM module ZIPs onto the MFFMv14 engine.

---

## 0. Prerequisites & Installation

Make sure Python 3.9 or newer is installed on your system. Before running any build or update scripts, install all required Python libraries by running:

```bash
pip install -r requirements.txt
```

### Included Requirements (`requirements.txt`)
- `fonttools>=4.55` (Font table parsing & manipulation)
- `cryptography>=43.0` (Key handling & ZIP signing)
- `brotli` (WOFF2 font decompression)
- `opentype-feature-freezer` (`pyftfeatfreeze` CLI tool & library for feature freezing)

*(Optional alternative using pipx)*:
```bash
pipx install opentype-feature-freezer
```

---

## 1. `build.py` — Font Module Compiler

### Overview
`build.py` compiles static or variable font files (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`) placed in the `Fonts/` directory into a flashable Android font module.

### Features
- **Auto-Detection**: Automatically detects whether input fonts are static or variable (`fvar` table present).
- **OpenType Feature Freezer (`pyftfeatfreeze`)**: Interactively lists available Stylistic Sets (`ss01`–`ss20`) and Character Variants (`cv01`–`cv99`) with human-readable descriptions, provides a visual preview link (https://www.adamjagosz.com/bulletproof/lettering), and freezes user-selected features into the font.
- **Dynamic File & Metadata Tagging**: Automatically appends applied feature tags (e.g. `(ss02, cv11)`) to the module display name in `module.prop` and the generated `.zip` output filename.
- **Auto-Signing**: Automatically signs generated ZIP packages using `zipsigner_auto.py` so they are ready to flash.

---

### Command-Line Arguments & Flags

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--fonts-dir` | `<PATH>` | Directory containing source font files (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`). | `Fonts/` |
| `--mode` | `auto`, `static`, `variable` | Font compilation mode. | `auto` |
| `--name` | `<STRING>` | Override module display name. | Extracted from font |
| `--version` | `<STRING>` | Override module version string. | `YYYY.MM.DD` |
| `--version-code` | `<NUMBER>` | Override numeric `versionCode` property. | `YYYYMMDDHHMM` |
| `--output-dir` | `<PATH>` | Destination directory for output `.zip` files. | `dist/` |
| `--features` | `<TAGS>` | Comma-separated list of OpenType features to freeze (e.g., `'ss01,cv01'`). | None |
| `--interactive` | *Flag* | Force interactive feature selection prompt regardless of TTY status. | False |
| `--no-interactive` | *Flag* | Disable interactive feature selection prompt. | False |
| `--keep-hinting` | *Flag* | Keep original TrueType hinting tables (`cvt`, `fpgm`, `prep`, etc.). | False (hints removed) |
| `--no-prefix` | *Flag* | Do not prefix internal font family metadata with `MFFM`. | False (`MFFM` added) |
| `--no-zip` | *Flag* | Compile and stage module payload in `Files/` without creating a ZIP file. | False |
| `--no-sign` | *Flag* | Create an unsigned debugging ZIP file. | False (signed) |

---

### `build.py` Usage Examples

#### Example 1: Standard Interactive Build
Install dependencies, then run without flags to enter the interactive OpenType feature freezer workflow:
```bash
pip install -r requirements.txt
python build.py
```
**Interactive Prompt Output:**
```text
------------------------------------------------------------
OpenType Feature Freezer Tool Integration
------------------------------------------------------------
Do you want to use any Stylistic Sets (for example ss01 Open digits), or Character Variants (for example cv01 Alternate One)? (y/N): y

Available Stylistic Sets and Character Variants:
  cv01  -  Alternate one
  cv11  -  Single-story a
  ss01  -  Open digits
  ss02  -  Disambiguation

[Visual Preview]
For visual representation of available sets, visit:
https://www.adamjagosz.com/bulletproof/lettering and upload your font.
------------------------------------------------------------

Enter your desired entries (comma or space separated, e.g. ss01, cv01): ss02, cv11
Selected features to freeze: ss02, cv11
Successfully froze features [ss02,cv11] in InterVariable.ttf
Detected mode : variable
Font family   : Inter Variable
Freezer sets  : ss02, cv11
Source faces  : 2
Payload fonts : DroidSans.ttf, DroidSans-Bold.ttf
Signature     : verified
Output        : C:\Users\Admin\Desktop\MFFMv14\dist\mffm14-Inter-Variable-VF-ss02-cv11-2026.07.30.zip
```

#### Example 2: Non-Interactive Build with Specific Features
Pass `--features` directly for headless execution or automated scripts:
```bash
python build.py --features "ss02,ss03,cv11"
```
**Output File:** `dist/mffm14-Inter-Variable-VF-ss02-ss03-cv11-YYYY.MM.DD.zip`

#### Example 3: Custom Module Name, Version & Unsigned Output
```bash
python build.py --name "Custom Sans" --version "1.0.0" --version-code 100 --no-sign
```

---

## 2. `update.py` — Legacy Module Migration Utility

### Overview
`update.py` batch processes older MFFM module ZIP files located in the `Old Modules/` directory, extracts their primary font assets, re-compiles them using the latest MFFMv14 template core, and outputs signed ZIPs into `Updated Modules/`.

---

### Command-Line Arguments & Flags

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--old-dir` | `<PATH>` | Input directory containing legacy MFFM module ZIP files. | `Old Modules/` |
| `--output-dir` | `<PATH>` | Output directory for migrated MFFMv14 ZIP modules. | `Updated Modules/` |
| `--mode` | `auto`, `static`, `variable` | Font compilation mode. | `auto` |
| `--name` | `<STRING>` | Override display name for all updated modules. | Extracted from old module |
| `--version` | `<STRING>` | Override version string for updated modules. | Current date |
| `--version-code` | `<NUMBER>` | Override numeric `versionCode`. | Current timestamp |
| `--no-sign` | *Flag* | Create unsigned debugging ZIP modules. | False (signed) |
| `--keep-hinting` | *Flag* | Do not strip TrueType hinting from source fonts. | False |
| `--no-prefix` | *Flag* | Do not prefix internal font family metadata with `MFFM`. | False |
| `--force` | *Flag* | Overwrite existing output ZIP files in the output directory. | False |
| `--keep-temp` | *Flag* | Preserve temporary extraction and build workspace directories for diagnostics. | False |

---

### `update.py` Usage Examples

#### Example 1: Standard Batch Migration
Place your legacy module `.zip` files in `Old Modules/` and run:
```bash
python update.py
```
**Output:**
```text
Updated old-font-module.zip
  mode   : variable
  family : Roboto Flex VF
  output : C:\Users\Admin\Desktop\MFFMv14\Updated Modules\mffm14-Roboto-Flex-VF-2026.07.30.zip
Updated 1 module(s).
```

#### Example 2: Force Overwrite Existing Updated Modules
```bash
python update.py --force
```

#### Example 3: Batch Update with Custom Destination and Debugging Output
```bash
python update.py --old-dir "./my_old_zips" --output-dir "./migrated_zips" --no-sign --keep-temp
```

---

## 3. Workflow Summary & Quick Reference

```bash
# 0. Install all required dependencies
pip install -r requirements.txt

# 1. Standard interactive build from Fonts/ directory
python build.py

# 2. Freeze specific features non-interactively
python build.py --features "ss01,cv01"

# 3. Create unsigned debug build
python build.py --no-sign

# 4. Migrate old MFFM ZIPs in Old Modules/ to Updated Modules/
python update.py
```
