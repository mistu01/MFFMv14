# MFFMv14 — Universal Android Font Module Builder
### User & Configuration Guide

---

> [!IMPORTANT]
> ### ⚠️ Crucial Prerequisite: Install MFFM Runtime First!
> Before flashing any MFFMv14 font module, you **MUST** first install the **`mffm-runtime-YYYY.MM.DD.zip`** module in your root manager (**Magisk**, **KernelSU**, or **APatch**).
> - The runtime provides the on-device font compiler (`fontTools`, `brotli`, metric fixers, and TTC generator).
> - You only need to install `mffm-runtime` **once**. After that, all MFFMv14 font modules will work seamlessly!
> - Download official runtime releases from **[t.me/MFFMMain](https://t.me/MFFMMain)**.

---

## ⚡ Quick Start: Creating Your Font Module

### 🌟 Method 1: Manual Module Building (Easiest — No Tools or Python Needed!)
> **Best for:** Anyone on a PC, Mac, or Android phone using a standard File Manager (ZArchiver, MiXplorer, Solid Explorer, MT Manager, Windows Explorer).

1. **Install Runtime**: Ensure **`mffm-runtime-*.zip`** is already flashed in your root manager.
2. **Extract Template**: Download and extract **`MFFMv14-Source-Template.zip`**.
3. **Add Your Fonts**: Put your font file(s) into the **`Files/Sans/`** directory.
   - *Supported formats:* `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`.
   - *Optional Families:* Put monospace/code fonts into `Files/Monospace/`, serif fonts into `Files/Serif/`, or Bengali fonts into `Files/Bengali/`.
4. **Edit Module Details (Optional)**: Open **`module.prop`** in any text editor and change `name=` or `author=`:
   ```ini
   id=mffm14_myfont
   name=[MFFMv14] My Font Name
   version=2026.08.31
   versionCode=260831
   author=Your Name
   description=Custom font module powered by MFFMv14 engine.
   ```
5. **Zip and Flash**: Select all files and folders inside the extracted folder (`Files`, `META-INF`, `customize.sh`, `module.prop`, `service.sh`, `action.sh`, `post-mount.sh`, `uninstall.sh`), compress them into a standard **ZIP** file, and flash it directly in **Magisk**, **KernelSU**, or **APatch**!

---

### 💻 Method 2: PC Build Script (`build.py`)
> **Best for:** Power users and developers with Python 3.9+ installed on Windows, macOS, or Linux.

1. Install requirements:
   ```sh
   pip install -r requirements.txt
   ```
2. Place fonts in `Fonts/Sans/` (or `Files/Sans/`).
3. Run the compiler:
   ```sh
   python build.py
   ```
   Outputs a pre-compiled, signed flashable ZIP directly to `dist/`.

---

## 🎛️ On-Device Power & Configuration: Tuning Your Fonts on Android

With MFFMv14 and the **MFFM Runtime Module**, your phone performs advanced font transformations, feature freezing, and dynamic TrueType Collection bundling right on-device!

### Step 1: Install the Runtime Once
Flash **`mffm-runtime-YYYY.MM.DD.zip`** once in Magisk, KernelSU, or APatch. This provides a self-contained, high-speed Python + fontTools engine installed to `/data/adb/mffm_runtime/`.

### Step 2: Customize Features in `/sdcard/MFFM/*.conf`
When you flash any MFFMv14 font module, a configuration file is generated at:
```
/sdcard/MFFM/MFFMv14_<FontFamily>_<ID>.conf
```

> [!TIP]
> **Do I have to edit this file?**
> **No!** All settings are 100% optional. If you like how your font looks, you don't have to touch anything. The module works out of the box with safe, optimized defaults.
> If you do decide to change something, simply edit the file in any text editor on your phone (e.g. MiXplorer, MT Manager, QuickEdit) and **re-flash the font module zip** in Magisk / KernelSU / APatch.

---

### 📖 Configuration Options Explained

| Option | Default | Recommended Choice | What It Does / When to Change |
| :--- | :--- | :--- | :--- |
| `ENABLE_CENTERED_COLON` | `no` | `yes` (if clock looks low) | Injects a vertically centered colon for clock times (`12:30`) so it doesn't look sunken. |
| `COLON_ALIGNMENT` | `center` | `center` | Sets whether the colon aligns to digits (`center`), capitals (`cap_height`), or lowercase (`x_height`). |
| `COLON_OFFSET` | `0` | `0` | Fine height adjustment in font units (+/-) for picky OEM lockscreens. |
| `COLON_RULE` | `between_digits` | `between_digits` | `between_digits` keeps normal text punctuation untouched. Use `after_digit` for stacked 2-line clocks (`12:` / `30`). |
| `ENABLE_TABULAR_CLOCK_DIGITS` | `no` | `yes` (if clock wobbles) | Equalizes digit widths (0-9) so the lockscreen clock never jumps horizontally as seconds/minutes tick. |
| `METRICS_MODE` | `safe` | `safe` | `safe` automatically prevents accents (Vietnamese, Devanagari, etc.) from clipping while keeping buttons/status bars centered. |
| `ENABLE_ZYGOTE_OPTIMIZATION` | `no` | `yes` (for size/RAM) | Prunes dead/bloat desktop tables (`DSIG`, `VDMX`, `hdmx`, `LTSH`, `PCLT`, `EBDT`, Mac Roman duplicates) to shrink font size by 10–30% and save Zygote RAM. |
| `*_FREEZE_FEATURES` | *(empty)* | `ss01,zero` (user choice) | Bakes stylistic alternates (like slashed zero `0`) into default characters system-wide. |
| `SANS_WGHT` / `SANS_WDTH` | *(auto)* | Leave unless custom | Customizes exact numeric variable weights (100–900) for variable fonts. |

---

#### Detailed Breakdown:

#### 1. 🕒 Centered Clock Colon (`ENABLE_CENTERED_COLON`)
- **The Problem**: Standard fonts only have a punctuation colon (`:`), which sits low near the bottom of letters (e.g. `"Note: Hello"`). On lockscreens and status bars, clocks like `12:30` look sunken and uneven.
- **How to decide**:
  - If your lockscreen clock colon looks too low or uneven: set `ENABLE_CENTERED_COLON=yes`.
  - If it already looks centered or you don't mind: leave it as `ENABLE_CENTERED_COLON=no`.
- **Advanced Colon Controls**:
  - `COLON_ALIGNMENT=center`: Aligns dots with the vertical midpoint of numbers. (Recommended)
  - `COLON_OFFSET=0`: Change to `+20` or `-20` if you want to shift the colon slightly higher or lower.
  - `COLON_RULE=between_digits`: Only activates between numbers (`12:30`). Sentences stay normal. If your lockscreen uses a 2-line vertical clock (`12:` on top, `30` below), change to `COLON_RULE=after_digit`.

#### 2. ⏱️ Tabular Clock Digits (`ENABLE_TABULAR_CLOCK_DIGITS`)
- **The Problem**: In proportional fonts, the number `1` is much narrower than `0` or `8`. When the lockscreen clock changes from `11:59` to `12:00` (or if your clock shows ticking seconds), the numbers shift sideways and visibly "wobble" or "jitter".
- **How to decide**:
  - If you notice clock numbers shifting horizontally or jumping sideways: set `ENABLE_TABULAR_CLOCK_DIGITS=yes`.
  - If you prefer natural proportional number spacing across your apps: leave it as `no`.

#### 3. 🛡️ Smart Metric Harmonization & Zero-Clipping (`METRICS_MODE`)
- **The Problem**: In status bars, notification popups, and app buttons, tall accents (like Vietnamese `ế`, `Ậ`, Devanagari, Thai, Arabic, or display letters `Å`, `Ŵ`) can get sliced off if the font's line box is too tight.
- **How to decide**:
  - `METRICS_MODE=safe` (Recommended): Automatically scans all characters. If any tall accents exist, it gently expands the boundaries while strictly preserving the FFIX3 baseline ratio. Buttons, status bar icons, and widgets remain perfectly centered with **zero clipping**.
  - `METRICS_MODE=compact`: Forces classic ultra-tight FFIX3 metrics ($2128 / -550$). Best for English-only users who want the absolute most compact notification padding.
  - `METRICS_MODE=preserve`: Keeps the font designer's original vertical metrics untouched.

#### 4. ⚡ Table Optimization & Zygote RAM Saver (`ENABLE_ZYGOTE_OPTIMIZATION`)
- **The Problem**: `/system/fonts/DroidSans.ttf` is memory-mapped into Android's **Zygote** root process and inherited by every single app and service. Many desktop fonts carry bloated or obsolete tables from the 1990s (`DSIG`, `VDMX`, `hdmx`, `LTSH`, `PCLT`, `EBDT`/`EBLC` bitmap strikes, and Mac Roman duplicate name records) that waste memory and can trigger Android system log warnings.
- **How to decide**:
  - `ENABLE_ZYGOTE_OPTIMIZATION=no` (Default): Leaves all original font tables byte-for-byte untouched.
  - `ENABLE_ZYGOTE_OPTIMIZATION=yes`: Automatically prunes all dead bloat tables, removes Mac Roman duplicates, normalizes subpixel anti-aliasing in `gasp`, and canonicalizes table ordering. Shrinks font file size by 10–30% and saves RAM across all running apps!

#### 5. 🎨 OpenType Feature Freezing (`*_FREEZE_FEATURES`)
- **The Problem**: Many fonts contain hidden alternate characters (such as a slashed zero `0`, curved lowercase `l`, single-story `a` or `g`). Because Android apps don't have menus to enable these, they stay hidden.
- **How to decide**:
  - Look at the discovered feature list generated directly inside your `.conf`.
  - Common favorites:
    - `zero`: Slashed zero (`0` with a slash through it).
    - `ss01` to `ss20`: Stylistic sets (alternate letter designs).
    - `cv01` to `cv99`: Character variants.
  - Enter tags separated by commas:
    ```sh
    SANS_FREEZE_FEATURES=ss01,zero
    MONO_FREEZE_FEATURES=zero
    ```
  - If you like the font as-is, leave them blank!

#### 6. ⚖️ Variable Font Weight & Width Tuning
- Customize exact numeric weights for Android's 100–900 weight classes:
  ```sh
  SANS_WGHT="100 200 300 400 500 600 700 800 900"
  SANS_WDTH="100 100 100 100 100 100 100 100 100"
  ```

#### 7. 🌐 Adding External Fonts Directly on Device
- Drop any extra font files into `/sdcard/MFFM/<FontFamily>/`:
  - `/sdcard/MFFM/<FontFamily>/Bengali/`
  - `/sdcard/MFFM/<FontFamily>/Monospace/`
  - `/sdcard/MFFM/<FontFamily>/Serif/`
- Reflash your module — it automatically discovers, optimizes, and bundles all weights into `DroidSans.ttf` on-the-fly!

#### 8. 🏷️ Intelligent Name Table Sanitization & Version Branding
- When fonts are compiled or bundled into `DroidSans.ttf`:
  - Family names automatically insert `Mistu` after the first word:
    - Single-word names become `Word Mistu` (e.g. `Roboto` -> `Roboto Mistu`, `Inter` -> `Inter Mistu`).
    - Multi-word names become `Word Mistu Other` (e.g. `Amazon Ember` -> `Amazon Mistu Ember`, `Josefa Rounded Pro` -> `Josefa Mistu Rounded Pro`).
  - The font version string (`nameID 5`) is cleanly appended with `;Mistu` (e.g. `Version 1.000;Mistu`).
  - Full Name (`nameID 4`) and PostScript Name (`nameID 6`) are automatically synchronized, and Manufacturer (`nameID 8`) is set to `Mistu @ MFFM Inc.`.

---

## 🛡️ Built-in Google Font Update Protection

Google Play System updates silently push `NotoSansCJK-Regular.ttc` and other fonts to `/data/fonts/files/`, overriding user root font modules without warning.

MFFMv14 includes comprehensive multi-layer protection:
1. **Boot Service (`service.sh`)**: Runs at boot to neutralize Google Font cache updates before apps load. Logs are mirrored to `/sdcard/MFFM/font_service.log`.
2. **On-Demand Action Button (`action.sh`)**: For **KernelSU**, **APatch**, and **MMRL**, tap the "Action" button in your root manager to instantly neutralize updates without rebooting!

---

## 📦 Supported Font Formats & Rules

- **Formats**: `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`.
- **Automatic Decompression**: Web font formats (`.woff`, `.woff2`) are decompressed and unflavored into native TrueType tables during TTC compilation.
- **Accurate Weight Detection**: OS/2 `usWeightClass` and typographic name records are inspected to resolve true weights (e.g. Linotype 400 → 900 Black).
- **Static Multi-400 Deduplication**: If multiple 400 normal faces exist (e.g. `Regular`, `Book`, `Normal`), `Regular` is always prioritized.

---

## 📚 Advanced Developer & CLI Reference

### PC Build Script (`build.py`)
```sh
python build.py [options]

  --fonts-dir <path>      Source font directory (default: ./Fonts or ./Files)
  --mode auto|static|var  Force static or variable font mode
  --name "Display Name"   Override display name in module.prop
  --output-dir <path>     Output directory for the ZIP (default: ./dist)
  --template              Package clean MFFMv14-Source-Template.zip
  --runtime               Build mffm-runtime-YYYY.MM.DD.zip
  --no-sign               Skip cryptographic signing
```

### Runtime Helper Tool (`mffm-helper`)
Located at `/data/adb/mffm_runtime/bin/mffm-helper`:
- `scan <dirs...>`: Inspects weights, styles, and variable axes.
- `ttc --out <output.ttc> <files...>`: Bundles fonts into a TrueType Collection.
- `compile-bundle --out-dir <dir> ...`: Full on-device compilation of Sans, Mono, Serif, Bengali.
- `report-features ...`: Emits categorized OpenType feature report for `.conf`.
- `check-colon <font>`: Inspects whether font has a centered clock colon.
- `inject-colon --in <font> [--out <out>] [--alignment {center,cap_height,x_height}] [--offset <dy>] [--rule {between_digits,after_digit,always}]`: Injects centered clock colon rule and `colon.case` glyph with fine height and contextual rule controls.
- `equalize-digits --in <font> [--out <out>] [--width <target_width>]`: Equalizes digit advances (0-9) and centers contours to eliminate lockscreen clock horizontal wobble.
- `freeze-features --in <font> --features <tags>`: Freezes OpenType features into font.
- `otf2ttf --in <font.otf> [--out <font.ttf>]`: Converts CFF/OTF cubic outlines to TrueType quadratic outlines using cu2qu.
- `optimize --in <font> [--out <out>] [--keep-hinting]`: Prunes bloat tables (DSIG, VDMX, hdmx, LTSH, PCLT, EBDT, Mac Roman duplicates) and optimizes for Android Zygote.
- `process-font --in <font> [--metrics-mode {safe,compact,preserve}] [--optimize-tables] ...`: Normalizes font metrics, strips hinting, sanitizes names, and optimizes tables.

#### Advanced Typography & Metrics Configuration (`/sdcard/MFFM/*.conf`):
```sh
# Centered Clock Colon
ENABLE_CENTERED_COLON=yes
COLON_ALIGNMENT=center      # center (digits), cap_height (caps), x_height (lowercase)
COLON_OFFSET=0              # Fine height adjustment in font units (+/-)
COLON_RULE=between_digits   # between_digits (12:30), after_digit (12:), always

# Tabular Clock Digits
ENABLE_TABULAR_CLOCK_DIGITS=yes  # Equalize 0-9 advance widths to prevent clock jitter

# Smart Metric Harmonization (Zero-Clipping)
METRICS_MODE=safe           # safe (auto-clamp preserving FFIX3 ratio, default), compact (fixed FFIX3), preserve (original)

# Table Optimization & Zygote RAM Saver
ENABLE_ZYGOTE_OPTIMIZATION=no   # no (default: keep all tables untouched), yes (prune dead tables for 10-30% size reduction and RAM savings)
```



