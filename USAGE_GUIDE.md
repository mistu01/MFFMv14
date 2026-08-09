# MFFMv14 — Complete Usage Guide

---

## Table of Contents

- [Part 1 — Module Creation on PC](#part-1--module-creation-on-pc)
- [Part 2 — Module Creation on Device (Termux)](#part-2--module-creation-on-device-termux)
- [Part 3 — Module Information, Capabilities & Usage](#part-3--module-information-capabilities--usage)

---

# Part 1 — Module Creation on PC

This section covers everything required to build a flashable font module from a Windows, macOS, or Linux desktop environment.

---

## 1.1 Prerequisites

**Python 3.9 or newer** must be installed and available in your system PATH.

Verify with:
```
python --version
```

Install all required Python packages:
```
pip install -r requirements.txt
```

### What `requirements.txt` installs

| Package | Purpose |
|---|---|
| `fonttools >= 4.55` | Font table parsing, subsetting, TTC container generation |
| `cryptography >= 43.0` | Cryptographic signing of output ZIP files |
| `brotli` | WOFF2 font decompression |
| `opentype-feature-freezer` | OpenType layout feature freezing into default glyph mappings |

---

## 1.2 Workspace Layout

After extracting `MFFMv14-Source-Template.zip`, your working directory looks like this:

```
MFFMv14/
├── Fonts/
│   ├── Sans/           ← Place Sans-Serif fonts here (MANDATORY)
│   ├── Monospace/      ← Place Monospace fonts here (optional)
│   ├── Serif/          ← Place Serif fonts here (optional)
│   └── Bengali/        ← Place Bengali fonts here (optional)
├── Old Modules/        ← Old MFFM ZIPs to upgrade (for update.py)
├── Updated Modules/    ← Output of update.py
├── dist/               ← Output compiled module ZIPs land here
├── template/           ← Module template files (do not edit manually)
├── build.py            ← Main build script
├── update.py           ← Legacy module migration script
├── termux-build.sh     ← On-device Termux build script
├── font_module.py      ← Core compilation engine
├── requirements.txt
└── USAGE_GUIDE.md
```

---

## 1.3 Placing Your Fonts

### Sans-Serif — Mandatory

Sans-serif fonts **must** be placed in `Fonts/Sans/`. Without them, the build will fail. Sans cannot be supplied later via `/sdcard/MFFM/` — it must always be compiled into the module.

```
Fonts/Sans/
    MyFont-Thin.ttf
    MyFont-Light.ttf
    MyFont-Regular.ttf
    MyFont-Medium.ttf
    MyFont-Bold.ttf
    MyFont-Black.ttf
    MyFont-Italic.ttf
    MyFont-BoldItalic.ttf
    ...
```

### Optional Families

Place fonts in the corresponding subdirectory alongside Sans:

```
Fonts/Monospace/    ← monospace family (e.g. JetBrains Mono)
Fonts/Serif/        ← serif family (e.g. Noto Serif)
Fonts/Bengali/      ← Bengali/Bangla script family
```

You may combine any of these. Building a Serif-only module (with Sans but no Mono/Bengali) is valid.

### Font Filename Rules

**Filenames do not matter for weight detection.** The compiler reads the **OS/2 `usWeightClass`** field and **`fsSelection` italic bit** directly from the font binary. Any filename is accepted — descriptive names are recommended for your own organization but are not required.

Accepted formats: `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`

---

## 1.4 Building the Module

Run the build script from the `MFFMv14` directory:

```
python build.py
```

The script will:
1. Scan all `Fonts/` subdirectories
2. Detect font mode (static or variable) from font binaries
3. Compile all faces into a single TTC payload (`DroidSans.ttf`)
4. Generate system XML patch fragments
5. Package everything into a signed, flashable ZIP in `dist/`

### Build Output

```
dist/
└── mffm14-YourFont-2026.08.08.zip    ← Flash this in your root manager
```

---

## 1.5 Build Options

```
python build.py [options]
```

| Option | Description |
|---|---|
| `--fonts-dir <path>` | Use a different source font directory (default: `./Fonts`) |
| `--mode auto\|static\|variable` | Force font mode detection (default: auto) |
| `--name "Display Name"` | Override the module display name in module.prop |
| `--version "2026.08.08"` | Override the version string |
| `--version-code <N>` | Override the numeric versionCode |
| `--output-dir <path>` | Output directory for the ZIP (default: `./dist`) |
| `--no-zip` | Prepare module files without packaging into a ZIP |
| `--no-sign` | Skip cryptographic signing (useful for debugging) |
| `--keep-hinting` | Preserve TrueType hinting instructions (not recommended) |
| `--no-prefix` | Do not prefix the internal font family name with MFFM |
| `--features ss01,zero` | Freeze OpenType features for the Sans-serif family |
| `--mono-features zero,onum` | Freeze OpenType features for the Monospace family |
| `--serif-features ss02` | Freeze OpenType features for the Serif family |
| `--bengali-features ss01` | Freeze OpenType features for the Bengali family |
| `--interactive` | Force interactive feature selection prompt |
| `--no-interactive` | Disable interactive feature selection prompt |
| `--centered-colon` | Inject a contextual centered colon for digit clock display |
| `--no-centered-colon` | Disable centered colon injection |

---

## 1.6 OpenType Feature Freezing

Feature freezing bakes OpenType layout features into the font's default glyph mappings. This allows Android to render stylistic alternates without needing app-level OpenType support.

### Interactive mode (default)

Running `python build.py` without `--no-interactive` will present a numbered list of available features found in the font and prompt you to select them.

### Flag mode

```
python build.py --features ss01,ss02,zero --mono-features zero
```

Each `--*-features` flag is applied independently to its respective family. You can freeze different features per family.

### Common feature tags

| Tag | Effect |
|---|---|
| `ss01`–`ss20` | Stylistic set alternates |
| `zero` | Slashed zero glyph |
| `tnum` | Tabular (monospaced) numerals |
| `onum` | Oldstyle numerals |
| `liga` | Standard ligatures |
| `dlig` | Discretionary ligatures |

---

## 1.7 Centered Colon Injection

For fonts where the colon `:` is not vertically centered between two digits (e.g. `12:30` on a lock screen clock appears misaligned), MFFMv14 can inject a contextual digit colon glyph automatically.

The builder detects whether the font already has such a glyph. Use `--centered-colon` to force injection or `--no-centered-colon` to disable it. In interactive mode (no `--features` flags given) you will be prompted **separately for each font family** (Sans-serif, Monospace, Serif, and Bengali) — exactly like the OpenType feature freezer — so you can enable centered colons for e.g. only the Monospace clock font. The global `--centered-colon`/`--no-centered-colon` flags override the prompts and apply to **all** families that are present.

---

## 1.8 Static vs Variable Fonts

The compiler auto-detects whether your fonts are static (separate files per weight) or variable (single file with axis ranges). You can force a mode with `--mode static` or `--mode variable` if needed.

**Static fonts:** Each weight is a separate `.ttf` file. All are packed into one TTC container (`DroidSans.ttf`), indexed and referenced in the system XML by `index=` attribute.

**Variable fonts:** A single font file with `fvar` axis table. The compiler reads axis ranges and generates per-weight `axis="wght=N"` XML entries clamped to the font's actual axis range.

---

## 1.9 Upgrading Old MFFM Modules (`update.py`)

To upgrade a module built with an older MFFM version to the MFFMv14 template:

1. Place the old module ZIP(s) in `Old Modules/`
2. Run:
   ```
   python update.py
   ```
3. Updated ZIPs are saved to `Updated Modules/`

```
python update.py [options]

  --old-dir <path>      Source folder with old ZIPs (default: ./Old Modules)
  --output-dir <path>   Output folder (default: ./Updated Modules)
  --mode auto|static|variable
  --name "Name"         Override display name for all outputs
  --no-sign             Skip signing
  --force               Overwrite existing output ZIPs
  --keep-hinting        Preserve TrueType hinting
  --features TAGS       Freeze OpenType features during rebuild
```

Supported old primary font names that `update.py` recognises: `DroidSans.ttc`, `DroidSans.ttf`, `DroidSans.otf`, `RobotoStatic-Regular.ttf`, `DroidSans-Bold.ttf`.

---

# Part 2 — Module Creation on Device (Termux)

This section covers building and flashing a module entirely on-device using Termux, without a PC.

---

## 2.1 Prerequisites

### Install Termux

Install Termux from **F-Droid** (recommended — Play Store version is outdated):
- https://f-droid.org/packages/com.termux/

After installing, open Termux and run:
```sh
termux-setup-storage
```
This grants Termux access to `/sdcard/` so it can read fonts from shared storage.

### Root access

Your device must be rooted with Magisk, KernelSU, or APatch. The flashing step uses `su` to invoke the root manager's install command.

---

## 2.2 Setting Up the Project

### Option A — Transfer from PC

Copy `MFFMv14-Source-Template.zip` to your device, then in Termux:

```sh
cd ~
cp /sdcard/Download/MFFMv14-Source-Template.zip .
unzip MFFMv14-Source-Template.zip -d MFFMv14
cd MFFMv14
```

### Option B — Clone from Git (if you have a repo)

```sh
pkg install git
git clone <your-repo-url> ~/MFFMv14
cd ~/MFFMv14
```

---

## 2.3 Placing Your Fonts

Create the font subdirectories if they don't exist:

```sh
mkdir -p Fonts/Sans Fonts/Monospace Fonts/Serif Fonts/Bengali
```

Copy fonts from shared storage into the appropriate subdirectory:

```sh
# Example: Sans font family
cp /sdcard/Download/MyFont/*.ttf Fonts/Sans/

# Example: Bengali family
cp /sdcard/Download/BengaliFont/*.ttf Fonts/Bengali/
```

Fonts can also be in `/sdcard/MFFM/` subdirectories for post-flash supply (see Part 3). For building into the module itself, use `Fonts/` subdirectories.

---

## 2.4 Building and Flashing — One Command

The `termux-build.sh` script handles everything: installs the toolchain, builds the module, and flashes it.

```sh
sh termux-build.sh
```

This single command will:
1. Check the Termux environment
2. Run `pkg install python python-pip openssl python-brotli python-cryptography`
3. Run `pip install -r requirements.txt`
4. Run `python build.py`
5. Detect your root manager (`magisk`, `ksud`, or `apd`)
6. Prompt for confirmation, then flash via `su`
7. Print "Reboot to apply the font."

---

## 2.5 Termux Build Script Options

```sh
sh termux-build.sh [options] [-- build.py options...]
```

| Option | Description |
|---|---|
| `--no-deps` | Skip package installation (environment already set up) |
| `--no-flash` | Build only, do not flash |
| `--yes` / `-y` | Skip the flash confirmation prompt |
| `--` | Everything after `--` is passed directly to `build.py` |

### Examples

**Build only, no flash:**
```sh
sh termux-build.sh --no-flash
```

**Build from a custom font directory:**
```sh
sh termux-build.sh -- --fonts-dir ~/storage/shared/Download/MyFont
```

**Build with feature freezing and auto-flash:**
```sh
sh termux-build.sh --yes -- --features ss01,zero --no-interactive
```

**Build and skip dependency installation (already installed):**
```sh
sh termux-build.sh --no-deps --yes
```

---

## 2.6 Manual Build (Without the Shell Script)

If you prefer step-by-step control:

```sh
# Step 1: Install toolchain
pkg install python python-pip openssl python-brotli python-cryptography

# Step 2: Install Python packages
pip install -r requirements.txt

# Step 3: Build
python build.py --no-interactive

# Step 4: Flash manually (pick your root manager)
su -c "magisk --install-module dist/*.zip"    # Magisk
su -c "ksud module install dist/*.zip"        # KernelSU
su -c "apd module install dist/*.zip"         # APatch
```

---

## 2.7 Flash Without Rebuild (from GUI)

If you already have the ZIP built (transferred from PC or built previously):

1. Open your root manager app (Magisk / KernelSU Manager / APatch)
2. Go to Modules
3. Tap "Install from storage"
4. Select the `.zip` from `dist/` (or wherever you placed it)
5. Reboot

---

## 2.8 Notes on Termux Environment

- **`noexec` mount warning**: If your project is on a partition mounted with `noexec`, the script cannot sign the ZIP. Move the project to `$HOME` (internal storage) to enable signing. The script detects this and warns automatically.
- **Storage permission**: Run `termux-setup-storage` once after installing Termux. Without it, `/sdcard/` is not accessible.
- **Root in Termux**: Termux does not require root for building. Root is only acquired via `su` for the flashing step.

---

# Part 3 — Module Information, Capabilities & Usage

This section describes what the module does once flashed, what capabilities it provides, and how to configure and use it.

---

## 3.1 What the Module Does

When flashed, the MFFMv14 module:

1. **Replaces the system sans-serif font** — patches `fonts.xml` and `font_fallback.xml` with the bundled font family, covering all weight slots (100 Thin through 900 Black) and italic variants.
2. **Patches Google/Pixel product fonts** — rewrites `fonts_customization.xml` on Pixel and Pixel-like ROMs to redirect Google Sans and variable font families to the new font.
3. **Applies optional external fonts** — picks up Bengali, Serif, and Monospace fonts from `/sdcard/MFFM/` subdirectories and patches the relevant system fallback entries.
4. **Runs custom scripts** — executes any `.sh` scripts found in `/sdcard/MFFM/` for post-install customization.

---

## 3.2 Supported Root Environments

| Root Manager | Detection Method | Overlay Method |
|---|---|---|
| **Magisk** | `command -v magisk` | Standard Magisk module overlay |
| **KernelSU** | `$KSU=true` or `$KSU_VER_CODE` | OverlayFS with `setfattr` opaque attr |
| **APatch** | `$APATCH=true` or `$APATCH_VER_CODE` | OverlayFS with `setfattr` opaque attr |
| **Mountify** | `$MOUNTIFY=true` or modules dir | Defers to Mountify overlay system |

The module detects the root environment automatically and applies the appropriate overlay strategy. No manual configuration is needed.

---

## 3.3 The `/sdcard/MFFM/` Directory

After flashing, the installer creates and maintains these directories:

```
/sdcard/MFFM/
├── Bengali/      ← Drop Bengali font files here
├── Serif/        ← Drop Serif font files here
├── Monospace/    ← Drop Monospace font files here
└── *.conf        ← Variable font axis configuration files (auto-generated)
```

To apply fonts placed here, **reflash the module**. The installer reads these directories at install time.

> Sans-serif fonts cannot be supplied via `/sdcard/MFFM/`. Sans must always be compiled into the module via `Fonts/Sans/`.

---

## 3.4 External Font Detection — Priority Order

For each optional family (Bengali, Serif, Monospace), the installer checks sources in this order, using the **first match found**:

| Priority | Source | Mode |
|---|---|---|
| 1 (highest) | `Files/bengali.xml` / `Files/serif.xml` / `Files/mono.xml` | Module-bundled (compiled with build.py) |
| 2 | `Files/Beng-Regular.ttf` + `Beng-Medium.ttf` + `Beng-Bold.ttf` | Module standalone 3-file (Bengali) |
| 2 | `Files/NotoSerif-Regular.ttf` + `NotoSerif-Bold.ttf` | Module standalone files (Serif) |
| 2 | `Files/CutiveMono.ttf` + `DroidSansMono.ttf` | Module standalone files (Monospace) |
| 3 | `/sdcard/MFFM/<Family>/` — Variable font detected | Auto-configured with fvar axes |
| 4 | `/sdcard/MFFM/<Family>/` — Static font(s) | Weight-mapped and TTC-bundled (or fallback) |

---

## 3.5 Static External Font Handling (Bengali / Serif / Monospace)

When static fonts are placed in the `/sdcard/MFFM/` subdirectories, the installer runs a **two-phase weight discovery**:

### Phase 1 — OS/2 `usWeightClass` scan (Python + fontTools)

If Python and fontTools are available (via Termux), the installer reads the **OS/2 `usWeightClass`** field directly from each font's binary. This correctly identifies all weight slots regardless of filename.

**Any filename works** — including Android font cache filenames like `7a4f1b0cdc12b2c1-s.p.ttf`.

### Phase 2 — Filename heuristic fallback

If Python is not available, the installer falls back to scoring filenames for weight keywords (`Bold`, `Light`, `Medium`, `Semibold`, `Black`, etc.). Files without recognizable keywords score too low and are skipped.

### TTC Bundling (Termux + fontTools required)

When multiple distinct weight faces are found, they are packed into a single **TTC (TrueType Collection)** file using `fontTools.TTCollection`. The system XML is patched with `index=N` per-face entries. Only weights actually present are written into the XML — empty slots are never padded.

**Output TTC filenames:**

| Family | TTC Filename | Also Copied As |
|---|---|---|
| Bengali | `NotoSansBengali-VF.ttf` | `NotoSerifBengali-VF.ttf`, `NotoSansBengaliUI-VF.ttf` |
| Serif | `NotoSerif-Regular.ttf` | `NotoSerif-Italic.ttf`, `NotoSerif-Bold.ttf`, `NotoSerif-BoldItalic.ttf` |
| Monospace | `DroidSansMono.ttf` | `CutiveMono.ttf` |

---

## 3.6 Termux Dependency Handling

The installer manages Python/fontTools availability at flash time:

```
Termux installed?
│
├─ YES → fontTools importable?
│         ├─ YES → Full mode: OS/2 weight scan + TTC bundling
│         └─ NO  → Auto-install fontTools via pip → retry
│                   ├─ Install OK → Full mode
│                   └─ Install failed → Warn + fallback mode
│
└─ NO → Python available from system?
          ├─ YES, but no fontTools, no Termux → fallback mode
          └─ NO → fallback mode
```

### Fallback mode (no Termux / no fontTools)

| Family | Fallback behavior |
|---|---|
| **Bengali** | 3-file install: Regular (`_r400`), Medium (`_r500`), Bold (`_r700`) |
| **Serif** | 4-file install: Regular, Italic, Bold, BoldItalic |
| **Monospace** | 1-file install: Regular only (copied to both `DroidSansMono.ttf` and `CutiveMono.ttf`) |

When multiple faces are detected but TTC bundling is impossible, the installer prints a warning and uses the fallback:
```
[--] WARNING: Multiple Bengali faces detected but Termux+Python not found.
[--] Install Termux and run: pip install fonttools  — then reflash.
[--] Falling back to 3-file install (Regular/Medium/Bold only).
```

---

## 3.7 Variable External Fonts

Variable fonts (containing an `fvar` table) placed in `/sdcard/MFFM/` subdirectories are handled entirely without fontTools:

1. **Detection** — reads the first 8 KB of the font binary for the `fvar` signature
2. **Axis extraction** — uses Python's built-in `struct` module (no fontTools) to read axis tags, min/default/max values
3. **XML generation** — generates per-weight `<font axis="wght=N">` entries clamped to the font's actual axis range
4. **Auto-config** — creates a `.conf` file in `/sdcard/MFFM/` for live axis tuning (see Section 3.8)

If Python is not available at all, axis extraction falls back to a safe default range of `wght:300:400:700`.

---

## 3.8 Variable Font Axis Tuning (`.conf` Files)

For variable-font modules (built with a variable font in `Fonts/Sans/`), a configuration file is auto-created at:

```
/sdcard/MFFM/MFFMv14_<FamilyName>_<IdentityHash>.conf
```

This file contains one entry per weight slot per axis profile. You can edit the values and reflash to apply custom axis positions:

```ini
# SANS-SERIF / UPRIGHT
# Android 100 (THIN): variable wght range 100..900
SANS_UPRIGHT_THIN_WGHT=100
SANS_UPRIGHT_LIGHT_WGHT=300
SANS_UPRIGHT_REGULAR_WGHT=400
SANS_UPRIGHT_MEDIUM_WGHT=500
SANS_UPRIGHT_BOLD_WGHT=700
...
```

### Config rules
- Values are validated against the font's actual axis range on every flash
- Out-of-range or malformed values are auto-reset to the font's default and flagged `[!!]`
- Config is **preserved across module updates** when the module identity hash matches
- Obsolete keys (from removed font profiles) are **auto-pruned** on reflash

---

## 3.9 Patched XML Files

The module patches the following system files (copies to module overlay, never modifies system directly):

| File | Purpose |
|---|---|
| `/system/etc/fonts.xml` | Primary font family definitions |
| `/system/etc/font_fallback.xml` | Script/language fallback families |
| `/system/product/etc/fonts_customization.xml` | Google Sans / Pixel product overrides |

---

## 3.10 Installation Log

Every flash writes a full debug log to:
```
/sdcard/MFFM/mffmv14_debug_<YYYYMMDD_HHMMSS>.log
```

Old logs from previous installs are deleted automatically at the start of each new flash. The log includes complete `set -x` trace output — every command executed, every variable value, every decision branch.

### Log markers

| Marker | Meaning |
|---|---|
| `[OK]` | Step completed successfully |
| `[--]` | Step skipped (font not supplied or not applicable) |
| `[!!]` | Warning — non-fatal, install continues |
| `[ERROR]` | Fatal error — installation stopped |

---

## 3.11 Custom Post-Install Scripts

Place any `.sh` scripts in `/sdcard/MFFM/` (up to 2 directory levels deep). The installer runs them at the end of Section 5/5. Scripts are run in a subshell with all module variables exported:

| Exported Variable | Value |
|---|---|
| `MODPATH` | Module directory in `/data/adb/modules_update/` |
| `FONT_DIR` | Module `Files/` directory |
| `SYS_FONT` | Module system/fonts overlay path |
| `SYS_XML` | Patched fonts.xml path |
| `SYS_FALLBACK` | Patched font_fallback.xml path |
| `MFFM_DIR` | `/sdcard/MFFM` |
| `FONT_FAMILY` | Font family name from module |
| `FONT_MODE` | `static` or `variable` |

---

## 3.12 Troubleshooting

### Bengali/Serif/Monospace fonts detected but not bundled into TTC

**Cause:** Termux is not installed or fontTools is not installed.
**Fix:** Install Termux from F-Droid, then run `pip install fonttools brotli` in Termux, then reflash.

### Fonts not applying after reboot

**Cause:** OverlayFS opacity not set correctly on KSU/APatch.
**Check:** Look in the log for `[!!] setfattr unavailable`. If present, install **Mountify** module alongside the font module.

### Variable font axis changes not taking effect

**Cause:** `.conf` file values may be out-of-range or the wrong config file is being read.
**Check:** Look for `[!!]` entries in the log near axis validation. The log shows which key was reset and to what value.

### `declare: not found` in log (old template)

**Cause:** An older version of `customize.sh` used bash-only `declare -A` associative arrays which do not exist in Android's `mksh`/`ash`.
**Fix:** This is resolved in the current MFFMv14. Rebuild using the current `MFFMv14-Source-Template.zip`.

### Module installs but font doesn't change

**Cause:** Another font module is active and takes priority, or system font cache needs clearing.
**Fix:** Disable/uninstall any other active font modules and reboot. If the issue persists, wipe the Dalvik/ART cache from recovery.
