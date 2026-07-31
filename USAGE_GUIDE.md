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

## 1. `build.py` — Universal Font Module Compiler

### Overview
`build.py` compiles static or variable font files (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`) from **any font family** placed in the `Fonts/` directory into a flashable Android font module.

### Features
- **Universal Font Support**: Automatically parses, converts, and compiles static (`.ttf`, `.otf`) and variable (`fvar` axes) fonts from any typeface (Roboto, Google Sans, Inter, Fira Code, JetBrains Mono, Atkinson, SF Pro, etc.).
- **Comprehensive OpenType Feature Freezer (`pyftfeatfreeze`)**: Discovers **all** available OpenType Layout features (Stylistic Sets `ss01`–`ss20`, Character Variants `cv01`–`cv99`, `zero` Slashed Zero, `tnum` Tabular Figures, `pnum`, `salt`, `case`, `dlig`, etc.) present in your font. Features are dynamically categorized with safety recommendations (`[RECOMMENDED/SAFE]`, `[CAUTION]`, `[NOT RECOMMENDED/UNSAFE]`), provides visual preview links (https://www.adamjagosz.com/bulletproof/lettering & https://wakamaifondue.com/), and freezes user-selected features into default glyph mappings.
- **Feature Safety Guidance**:
  - **[SAFE TO FREEZE]**: Stylistic Sets (`ss01`..`ss20`), Character Variants (`cv01`..`cv99`), Slashed Zero (`zero`), Tabular Figures (`tnum`), Proportional Figures (`pnum`), Stylistic Alternates (`salt`), Case-Sensitive Forms (`case`), Discretionary Ligatures (`dlig`).
  - **[CAUTION - USE WITH CARE]**: Position/Layout features (`frac`, `numr`, `dnom`, `subs`, `sups`, `sinf`, `ordn`) which shrink or reposition numbers globally across all text.
  - **[NOT RECOMMENDED / UNSAFE]**: Master override features like `aalt` (Access All Alternates - enables all alternate glyphs simultaneously) and default engine features (`calt`, `kern`, `liga`, `ccmp`, `locl`).
- **Centered Colon Feature Detection & Generation**: Automatically inspects input fonts to check if a centered colon feature (`colon.case` for clock `12:30` time display) exists. If missing, prompts the user interactively to generate & inject a vertically centered colon for digit displays.
- **Dynamic File & Metadata Tagging**: Automatically appends applied feature tags (e.g. `(ss02, cv11)`, `(zero, tnum)`) to the module display name in `module.prop` and the generated `.zip` output filename.
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
| `--features` | `<TAGS>` | Comma-separated list of OpenType features to freeze (e.g., `'zero,tnum,ss01,cv01'`). | None |
| `--centered-colon` | *Flag* | Force centered colon generation/injection for digits (`12:30` time display). | False |
| `--no-centered-colon` | *Flag* | Disable centered colon injection. | False |
| `--interactive` | *Flag* | Force interactive feature selection prompt regardless of TTY status. | False |
| `--no-interactive` | *Flag* | Disable interactive feature selection prompt. | False |
| `--keep-hinting` | *Flag* | Keep original TrueType hinting tables (`cvt`, `fpgm`, `prep`, etc.). | False (hints removed) |
| `--no-prefix` | *Flag* | Do not prefix internal font family metadata with `MFFM`. | False (`MFFM` added) |
| `--no-zip` | *Flag* | Compile and stage module payload in `Files/` without creating a ZIP file. | False |
| `--no-sign` | *Flag* | Create an unsigned debugging ZIP file. | False (signed) |

---

### `build.py` Usage Examples

#### Example 1: Standard Interactive Build
Install dependencies, place your font in `Fonts/`, and run:
```bash
pip install -r requirements.txt
python build.py
```
**Interactive Prompt Output:**
```text
------------------------------------------------------------
OpenType Feature Freezer Tool Integration
------------------------------------------------------------
Do you want to freeze any OpenType layout features (Stylistic Sets, Character Variants, Slashed Zero, Tabular Figures, etc.)? (y/N): y

Available OpenType Layout Features:

  [RECOMMENDED / SAFE TO FREEZE] (Stylistic & Character Alternates, Digit Toggles):
    case   - Case-Sensitive Forms
    cv01   - Alternate one
    cv11   - Single-story a
    ss01   - Open digits
    ss02   - Disambiguation
    tnum   - Tabular Figures
    zero   - Slashed Zero

  [CAUTION - USE WITH CARE] (Layout/Position features - shrinks/repositions text globally):
    dnom   - Denominators (Shrinks all numbers into denominators)
    frac   - Fractions (Shrinks and repositions all numbers into fraction form)

  [NOT RECOMMENDED / SYSTEM & MASTER ALTERNATE FEATURES]:
    aalt   - Access All Alternates (UNSAFE: Enables multiple/all alternate glyphs simultaneously across font)
    calt   - Contextual Alternates (Enabled by default in font layout engines)

[Visual Preview]
For visual representation of available sets, visit:
https://www.adamjagosz.com/bulletproof/lettering and upload your font.
------------------------------------------------------------

Enter your desired entries (comma or space separated, e.g. ss01, cv01, zero, tnum): zero, tnum, ss01
Selected features to freeze: zero, tnum, ss01
Successfully froze features [zero,tnum,ss01] in YourFont.ttf
Detected mode : variable
Font family   : Your Font Family
Freezer sets  : zero, tnum, ss01
Source faces  : 1
Payload fonts : DroidSans.ttf
Signature     : verified
Output        : dist/mffm14-Your-Font-Family-zero-tnum-ss01-YYYY.MM.DD.zip
```

#### Example 2: Non-Interactive Build with Specific Features
Pass `--features` directly for headless execution or automated scripts:
```bash
python build.py --features "zero,tnum,ss01"
```
**Output File:** `dist/mffm14-Your-Font-Family-zero-tnum-ss01-YYYY.MM.DD.zip`

---

## 2. `update.py` — Legacy Module Migration Utility

### Overview
`update.py` batch processes older MFFM module ZIP files located in the `Old Modules/` directory, extracts their primary font assets, re-compiles them using the latest MFFMv14 template core, and outputs signed ZIPs into `Updated Modules/`.

---

## 3. Workflow Summary & Quick Reference

```bash
# 0. Install all required dependencies
pip install -r requirements.txt

# 1. Standard interactive build from Fonts/ directory
python build.py

# 2. Freeze specific features for any font (e.g. slashed zero, tabular figures, stylistic sets)
python build.py --features "zero,tnum,ss01,cv01"

# 3. Create unsigned debug build
python build.py --no-sign

# 4. Migrate old MFFM ZIPs in Old Modules/ to Updated Modules/
python update.py
```
