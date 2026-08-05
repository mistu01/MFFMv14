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
3. [Module Flashing & Root Installation Workflow](#3-module-flashing--root-installation-workflow)
   - [Supported Root Environments](#supported-root-environments)
   - [Installer Section-by-Section Breakdown](#installer-section-by-section-breakdown)
4. [The `/sdcard/MFFM` Directory & Runtime Configuration](#4-the-sdcardmffm-directory--runtime-configuration)
   - [Monospace Font Priority Rules](#monospace-font-priority-rules)
   - [Serif Font Priority Rules](#serif-font-priority-rules)
   - [Variable Font Dynamic Axis Tuning (`.conf` files)](#variable-font-dynamic-axis-tuning-conf-files)
5. [Legacy Module Migration (`update.py`)](#5-legacy-module-migration-updatepy)
6. [Debugging & Troubleshooting](#6-debugging--troubleshooting)
7. [Development & Tests](#7-development--tests)
8. [Building on Android with Termux](#8-building-on-android-with-termux)
   - [One-Command Build (`termux-build.sh`)](#one-command-build-termux-buildsh)
   - [Python & Dependency Setup](#python--dependency-setup)
   - [Where to Keep the Repository](#where-to-keep-the-repository)
   - [Building & Flashing from the Phone](#building--flashing-from-the-phone)
   - [Termux Troubleshooting](#termux-troubleshooting)

---

## 1. Prerequisites & Environment Setup

Ensure Python 3.9 or newer is installed on your system. Before compiling fonts or running migration scripts, install all required dependencies:

Building on the phone itself is supported — see [section 8](#8-building-on-android-with-termux) for Termux.

```bash
pip install -r requirements.txt
```

### Dependencies Included in `requirements.txt`
- `fonttools>=4.55` — Font table parsing, subsetting, and TTC container generation.
- `cryptography>=43.0` — Cryptographic signing of generated module ZIP files.
- `brotli` — WOFF2 font decompression.
- `opentype-feature-freezer` — `pyftfeatfreeze` library for freezing OpenType layout features into default glyph mappings.

The test suite needs `pytest` as well: `pip install -r requirements-dev.txt`.

---

## 2. Module Creation (`build.py`)

`build.py` parses all font files placed inside the `Fonts/` directory and compiles them into a signed, flashable Android font module.

### Font Discovery & Folder Categorization
The compiler scans `Fonts/` and its subdirectories for `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, and `.woff2` files. Fonts are categorized automatically via folder paths or filename fallbacks:
- **Primary Sans-Serif Family**: Fonts placed in `Fonts/` or `Fonts/Sans/`.
- **Monospace Family**: Fonts placed in `Fonts/Monospace/` or `Fonts/Mono/` (or matching filename tags `mono`, `code`, `consolas`).
- **Serif Family**: Fonts placed in `Fonts/Serif/` (or matching filename tags `serif`).

Using dedicated subdirectories (`Fonts/Monospace/` and `Fonts/Serif/`) guarantees 100% accurate classification even if font filenames or internal font metadata do not contain keyword tags!

### Single TTC Collection Architecture (`DroidSans.ttf`)
All discovered font faces (Sans-serif static or variable, Monospace static or variable, and Serif static or variable) are compiled into **ONE single `DroidSans.ttf` TTC container**:
- **Indices 0..S**: Sans-serif font faces.
- **Indices M1..Mn**: Monospace font faces.
- **Indices R1..Rn**: Serif font faces.

Corresponding XML configuration fragments (`sans.xml`, `condensed.xml`, `mono.xml`, `serif.xml`) are generated in `Files/` referencing `DroidSans.ttf` at their respective TTC face indices.

If only Monospace or only Serif fonts are supplied, those faces also act as the primary family: they are embedded once, and `sans.xml` points at the same indices as `mono.xml` / `serif.xml`.

### Per-Family OpenType Feature Freezing
`build.py` integrates `pyftfeatfreeze` for interactive or headless OpenType feature freezing.
When running interactively:
1. **Sans-serif Prompt**: Prompts to freeze features for the primary Sans-serif font family.
2. **Monospace Prompt**: If Monospace fonts are supplied (in `Fonts/Monospace/` or `Fonts/Mono/`), additionally prompts to select and freeze features specifically for the Monospace family.
3. **Serif Prompt**: If Serif fonts are supplied (in `Fonts/Serif/`), additionally prompts to select and freeze features specifically for the Serif family.

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
| `--name` | `<STRING>` | Override module display name in `module.prop`. | Extracted from font |
| `--version` | `<STRING>` | Override version string. | `YYYY.MM.DD` |
| `--version-code` | `<NUMBER>` | Override numeric `versionCode`. | `YYYYMMDDHHMM` |
| `--output-dir` | `<PATH>` | Target directory for generated ZIPs. | `dist/` |
| `--features` | `<TAGS>` | Comma-separated OpenType features to freeze for Sans-serif (or default for all families). | None |
| `--mono-features` | `<TAGS>` | Comma-separated OpenType features to freeze specifically for Monospace family. | None |
| `--serif-features` | `<TAGS>` | Comma-separated OpenType features to freeze specifically for Serif family. | None |
| `--centered-colon` | *Flag* | Force centered colon generation for clock displays. | False |
| `--no-centered-colon` | *Flag* | Disable centered colon injection. | False |
| `--interactive` | *Flag* | Force interactive feature selection prompt. | False |
| `--no-interactive` | *Flag* | Disable interactive prompts. | False |
| `--keep-hinting` | *Flag* | Preserve original TrueType hinting instructions. | False (hints stripped) |
| `--no-prefix` | *Flag* | Disable `Mistu` family name transformation. | False |
| `--no-zip` | *Flag* | Stage files in `Files/` without compressing into ZIP. | False |
| `--no-sign` | *Flag* | Output unsigned ZIP file. | False (signed) |

---

## 3. Module Flashing & Root Installation Workflow

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
   - On ROMs with `/product/etc/fonts_customization.xml` (e.g. Google Pixel), installs `DroidSans.ttf` as `Rubik-Regular.ttf` into `/product/fonts` and patches product XML entries. A separate `Rubik-Italic.ttf` is written only when the module ships a dedicated italic payload file; otherwise the italic entries reference `Rubik-Regular.ttf` by face index. Every payload path is hard-linked where the filesystem allows it, so the collection is stored once regardless of how many overlay paths need it.
3. **Section 3/5: Applying optional font resources**
   - Evaluates **Monospace** and **Serif** priority rules (see Section 4).
   - Installs Bengali font overlays if supplied (`Beng-*.ttf`).
4. **Section 4/5: Finalizing root integration**
   - Sets SELinux `trusted.overlay.opaque` extended attributes (`setfattr`) on KernelSU/APatch for overlay directory mount stability.
5. **Section 5/5: Running custom local scripts**
   - Sources every `/sdcard/MFFM/*.sh` file **as root**, in alphabetical order, exporting the installer paths (`MODPATH`, `FONT_DIR`, `SYS_FONT`, `SYS_XML`, `PRODUCT_XML`, …) for them to use. A failing script aborts the installation.
   - Because any app with storage permission can write to `/sdcard`, this step is **opt-in**: create an empty `/sdcard/MFFM/allow-custom-scripts` file to enable it. Without that marker the scripts are listed and skipped.

Variable-font axis configuration (schema v2 `.conf` files in `/sdcard/MFFM/`) is created or loaded before section 1/5.

---

## 4. The `/sdcard/MFFM` Directory & Runtime Configuration

The `/sdcard/MFFM` folder on internal storage allows user customizations and external font fallbacks without modifying module files.

### Monospace Font Priority Rules

When installing monospace fonts, `customize.sh` checks in two tiers:

1. **Priority 1 (Module Native Monospace - Highest Priority)**:
   - If the module contains native monospace fonts (bundled into `DroidSans.ttf` via `Files/mono.xml`), the installer uses `mono.xml` to patch `fonts.xml` for `monospace`, `cutive-mono`, and `droidsans-mono`.
   - **Any external `/sdcard/MFFM/Mono*.ttf` file is IGNORED.**
2. **Priority 2 (External Monospace Fallback)**:
   - If the module has NO native monospace font (`Files/mono.xml` absent):
   - The installer takes the first `/sdcard/MFFM/Mono*.ttf` match (e.g. `Mono.ttf`, `Mono-Regular.ttf`) and copies it directly to `/system/fonts/CutiveMono.ttf` and `/system/fonts/DroidSansMono.ttf`.

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

Variable mode requires the source font to expose a `wght` axis (Android selects weights through it); a variable font without `wght` is rejected at build time.

Users can edit this `.conf` file to adjust variable font weights and axis values (e.g. `wght`, `opsz`, `wdth`, `grad`):
```ini
CONFIG_SCHEMA=2
MODULE_IDENTITY=vf-a1b2c3d4e5f678901234

# SANS-SERIF / UPRIGHT
SANS_UPRIGHT_REGULAR_WGHT=400
SANS_UPRIGHT_MEDIUM_WGHT=500
SANS_UPRIGHT_BOLD_WGHT=700
SANS_UPRIGHT_OPSZ=20
```

After editing the values, apply them with either:

* **On device, without re-flashing** — a variable module installs `/system/bin/font-config`:
  ```bash
  su -c font-config
  ```
  It rebuilds the module's `fonts.xml`, `font_fallback.xml` and `fonts_customization.xml` from the axis metadata and the pristine XML fragments saved under `/data/adb/modules/mffm14/mffm/`, using the same `fontlib.sh` implementation the installer uses. Fonts are cached per process, so **reboot** afterwards for running apps to pick up the new values.
* **Re-flashing the ZIP** — the installer reads the same `.conf` file, so the values are preserved (the `.conf` is kept as long as the module identity matches).

Static modules have no axis values to change and therefore do not install `font-config`; changing a static module means rebuilding it.

Because `/sdcard` is readable and writable by any app holding storage permission, `font-config` treats the `.conf` as untrusted input: every value must be a plain decimal number inside the axis range declared by the build, and anything else is reported and reset to the compiled default. Paths are fixed rather than taken from the environment; `--module-path` and `--config-dir` exist for non-standard install roots and for the test suite.

---

## 5. Legacy Module Migration (`update.py`)

To upgrade old MFFM module ZIP files to the latest MFFMv14 core:

1. Place legacy MFFM module ZIP files into `Old Modules/`.
2. Run:
   ```bash
   python update.py
   ```
3. Updated, signed MFFMv14 modules will be saved to `Updated Modules/`.

---

## 6. Debugging & Troubleshooting

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

5. **`Refusing to run zipsignerust-…: expected SHA-256 …`**:
   - The signer binary is pinned by digest in `SIGNER_DIGESTS` (`zipsigner_auto.py`), and upstream republishes its assets under the same rolling `latest` tag. Review the new release, then update the digest for your platform (`gh api repos/MrCarb0n/zipsignerust/releases/latest --jq '.assets[] | "\(.name) \(.digest)"'`). Use `--no-sign` to build in the meantime.

---

## 7. Development & Tests

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/` builds the fonts it needs with fontTools (`tests/conftest.py`), so no font binaries are
committed. Coverage is split into three parts:

- `test_font_module.py` — categorization, duplicate-face selection, axis/XML emission helpers.
- `test_compile.py` — end-to-end `compile_fonts` runs asserting the TTC face count and the `index=`
  values in each generated fragment, plus the `update.py` migration round-trip.
- `test_installer_xml.py` — sources `fontlib.sh` and runs `replace_family` / `replace_beng_family`
  with `sh` against a captured `fonts.xml`, asserting the result still parses as XML.
- `test_font_config_runtime.py` — axis substitution plus `font-config` end-to-end against a fake
  module tree, asserting the rebuilt XML, idempotency and the static-module refusal.

The same commands run in CI (`.github/workflows/ci.yml`), together with `shellcheck -s sh` over the
installer scripts and one `build.py --no-interactive --no-sign` build.

---

## 8. Building on Android with Termux

The whole toolchain runs on the phone: MFFMv14 is pure Python plus POSIX shell, and the signer has a
native `aarch64` build, so no PC is required. Install Termux from
[F-Droid](https://f-droid.org/packages/com.termux/) or
[GitHub](https://github.com/termux/termux-app/releases) — the Play Store build is outdated and
cannot install current packages.

### One-Command Build (`termux-build.sh`)

`termux-build.sh` performs everything in this section — dependency installation, the build, and
installing the module through your root manager:

```bash
cd ~/MFFMv14
sh termux-build.sh
```

Run it as the **normal Termux user, not as root**: `pkg` corrupts its own file ownership when run as
root, so the script refuses to start under `su` and instead invokes `su` itself for the single step
that needs it (flashing). It asks before installing anything into your system.

| Option | Effect |
|---|---|
| `--no-deps` | Skip `pkg`/`pip` installation and use the environment as it is. |
| `--no-flash` | Build only, and print the flashing commands instead of running them. |
| `--yes` | Do not ask for confirmation before installing the module. |
| `-- …` | Everything after `--` is passed to `build.py`. |

```bash
sh termux-build.sh --yes -- --mode variable --fonts-dir ~/storage/shared/Download/MyFont
```

It degrades instead of failing: if the checkout is on `noexec` shared storage it builds unsigned, and
if there is no root shell or no `magisk`/`ksud`/`apd` it stops after the build and tells you how to
flash the ZIP by hand. The rest of this section documents the same steps manually.

### Python & Dependency Setup

```bash
pkg update && pkg upgrade
# git is only needed if you clone instead of unpacking a release archive.
pkg install python python-pip git openssl python-brotli python-cryptography
pip install --upgrade pip
```

Install `brotli` and `cryptography` with `pkg`, **not** `pip`: both are C/Rust extensions, and the
Termux packages ship prebuilt binaries while `pip` would try to compile them (`cryptography` needs a
full Rust toolchain). With those two already present, the remaining requirements are pure Python:

```bash
pip install -r requirements.txt   # resolves to fonttools + opentype-feature-freezer
```

Grant access to your font files once, which creates `~/storage/`:

```bash
termux-setup-storage
```

### Where to Keep the Repository

**Keep the project inside Termux' own home directory** (`~/MFFMv14`), not under
`~/storage/shared` (`/sdcard`):

```bash
cd ~ && git clone https://github.com/mistu01/MFFMv14.git && cd MFFMv14
```

Signing downloads the pinned `zipsignerust-android-arm64` binary into `<project>/.mffm-signer/bin/`
and executes it. Shared storage is mounted `noexec`, so a project placed there fails at the signing
step with a permission error even though every other step works.

Source fonts may live anywhere — point the builder at them instead of moving them:

```bash
python build.py --fonts-dir ~/storage/shared/Download/MyFont
```

### Building & Flashing from the Phone

```bash
python build.py --no-interactive
```

The ZIP lands in `dist/`. Install it without leaving the terminal, using the CLI of your root
manager (each needs root, so run it under `su`):

```bash
su -c "magisk --install-module $PWD/dist/mffm14-*.zip"    # Magisk
su -c "ksud module install $PWD/dist/mffm14-*.zip"        # KernelSU
su -c "apd module install $PWD/dist/mffm14-*.zip"         # APatch
```

Then reboot. Alternatively copy the ZIP to shared storage and flash it from the manager app:

```bash
cp dist/mffm14-*.zip ~/storage/shared/Download/
```

For a variable module you can tune the axes and re-apply them from the same shell — no re-flash:

```bash
nano ~/storage/shared/MFFM/MFFMv14_*.conf
su -c font-config
```

(see [Variable Font Dynamic Axis Tuning](#variable-font-dynamic-axis-tuning-conf-files); a reboot is
still needed for running apps to pick up new values.)

### Termux Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `Could not obtain ZipSignerust` | No network, or GitHub is unreachable. Build with `--no-sign` and flash from the manager app, which does not verify the signature. |
| Permission denied when signing | The project sits on shared storage (`noexec`). Move it to `~/`. |
| `Signing keys are missing` | `openssl` is not installed and `cryptography` is unavailable — `pkg install openssl python-cryptography`. |
| `pip` tries to build `cryptography`/`brotli` and fails | The Termux packages were not installed first: `pkg install python-brotli python-cryptography`, then re-run `pip install -r requirements.txt`. |
| `No supported ZipSignerust binary for Linux …` | A 32-bit Termux on a 64-bit phone reports `armv7l`; that asset is pinned too, so upgrade Termux rather than forcing the build. |
| Fonts in `~/storage/shared` are not found | `termux-setup-storage` has not been run, or the Android storage permission was denied. |
