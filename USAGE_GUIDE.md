# MFFMv14 — User & Configuration Guide
### Complete Handbook for Creating, Flashing, and Customizing Android Font Modules

---

> [!IMPORTANT]
> ### ⚠️ Mandatory Prerequisite: Install MFFM Runtime First!
> Before flashing any MFFMv14 font module, you **MUST** first install the standalone **`mffm-runtime-YYYY.MM.DD.zip`** module in your root manager (**Magisk**, **KernelSU**, or **APatch**).
> - **Why is it required?** The runtime supplies the on-device font transformation engine (`fontTools`, `brotli`, `cu2qu`, metrics fixers, and TTC generator).
> - **Install Once**: You only install `mffm-runtime` once. All subsequent MFFMv14 font modules utilize this shared engine.
> - **Fatal Requirement**: Font module installation will strictly abort with an alert if the MFFM Runtime is missing.
> - **Download**: Official releases are available on Telegram at **[t.me/MFFMMain](https://t.me/MFFMMain)**.

---

## ⚡ Quick Start: Creating Your Font Module

You can build an MFFMv14 font module either directly on your phone using any file manager, on your PC with standard ZIP tools, or using the PC Python build script.

---

### Method 1: On-Device / File Manager (Easiest — No Tools or Python Needed)
> **Best for:** Anyone on Android using a file manager like **MiXplorer**, **MT Manager**, **ZArchiver**, or **Solid Explorer**, or on PC/Mac using standard ZIP archive tools.

1. **Verify Runtime**: Confirm **`mffm-runtime`** is installed and active in Magisk, KernelSU, or APatch.
2. **Download Template**: Extract **`MFFMv14-Source-Template.zip`** into a folder on your phone or PC.
3. **Add Primary Font**: Place your font file(s) into the **`Files/Sans/`** directory.
   - *Supported formats:* `.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`.
   - *Single variable font:* e.g. `Files/Sans/MyFont[wght].ttf`.
   - *Static family weights:* e.g. `Files/Sans/Regular.ttf`, `Files/Sans/Bold.ttf`, `Files/Sans/Italic.ttf`, etc.
4. **Add Optional Families (Optional)**:
   - Monospace/Coding font: place into `Files/Monospace/`
   - Serif font: place into `Files/Serif/`
   - Bengali font: place into `Files/Bengali/`
5. **Customize Details (Optional)**: Open **`module.prop`** in any text editor:
   ```ini
   id=mffm14_myfont
   name=[MFFMv14] My Font Name
   version=2026.09.06
   versionCode=260906
   author=Your Name
   description=Custom font module powered by MFFMv14 engine.
   ```
6. **Package and Flash**:
   - Select all files and folders inside the extracted folder:
     `Files`, `META-INF`, `customize.sh`, `module.prop`, `service.sh`, `action.sh`, `post-mount.sh`, `uninstall.sh`.
   - Compress them into a standard **ZIP** file.
   - Flash the ZIP directly in **Magisk**, **KernelSU**, or **APatch**, then reboot!

---

### Method 2: PC Build Script (`build.py`)
> **Best for:** Font designers, power users, and developers on Windows, macOS, or Linux.

1. Clone or download this repository.
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Place your fonts in `Fonts/Sans/` (or `Files/Sans/`). Optional families go in `Fonts/Monospace/`, `Fonts/Serif/`, `Fonts/Bengali/`.
4. Run the builder:
   ```sh
   python build.py
   ```
5. Your signed, flashable module ZIP will be generated in `dist/`.

---

## 🎛️ On-Device Tuning: Customizing `/sdcard/MFFM/*.conf`

Every time you flash an MFFMv14 font module, an editable configuration file is created or updated at:
```
/sdcard/MFFM/MFFMv14_<FontFamily>_<ID>.conf
```

> [!TIP]
> **Do I have to edit this file?**
> **No!** All settings are 100% optional. The module works out of the box with safe, production-tuned defaults.
> If you wish to customize features (such as enabling a centered clock colon, slashed zero, or equalizing clock digits), edit this file with any text editor (such as MiXplorer, MT Manager, or QuickEdit) and **re-flash the font module ZIP** in your root manager.

---

### Configuration Parameters Reference

| Parameter | Default | Recommended | Description / Purpose |
| :--- | :--- | :--- | :--- |
| `ENABLE_CENTERED_COLON` | `no` | `yes` (if clock colon looks low) | Injects a vertically centered colon glyph for clock times (`12:30`) on status bars and lockscreens. |
| `COLON_ALIGNMENT` | `center` | `center` | Target height alignment: `center` (digits midpoint), `cap_height` (capitals), or `x_height` (lowercase). |
| `COLON_OFFSET` | `0` | `0` | Fine vertical offset in font units (+/-) for OEM lockscreens. |
| `COLON_RULE` | `between_digits` | `between_digits` | Rule condition: `between_digits` (`12:30`), `after_digit` (for stacked 2-line clocks `12:` / `30`), or `always`. |
| `ENABLE_TABULAR_CLOCK_DIGITS` | `no` | `yes` (if clock wobbles) | Equalizes digit widths (0–9) so lockscreen clocks never jump horizontally as minutes or seconds change. |
| `METRICS_MODE` | `safe` | `safe` | Vertical metrics: `safe` prevents accent clipping with zero monospace inflation; `compact` forces tight FFIX3; `preserve` leaves original metrics untouched. |
| `ENABLE_ZYGOTE_OPTIMIZATION` | `no` | `yes` (for size/RAM) | Prunes obsolete tables (`DSIG`, `VDMX`, `hdmx`, `LTSH`, `PCLT`, `EBDT`, Mac duplicates) to shrink font size by 10–30% and save Zygote RAM. |
| `*_FREEZE_FEATURES` | *(empty)* | `ss01,zero` (user choice) | Freezes OpenType layout features (like slashed zero `0` or stylistic sets) permanently into default characters. |
| `SANS_WGHT` / `SANS_WDTH` | *(auto)* | Leave unless custom | Explicit numeric weights (100–900) mapped to Android system font weight slots. |

---

### Detailed Feature Guides

#### 1. 🕒 Centered Clock Colon (`ENABLE_CENTERED_COLON`)
- **The Problem**: Standard fonts only provide a punctuation colon (`:`), designed to sit low near the baseline for sentence punctuation (e.g. `"Note: Hello"`). On lockscreens and status bars, clocks like `12:30` appear sunken and uneven.
- **How to Use**:
  - Set `ENABLE_CENTERED_COLON=yes` in your `.conf`.
  - `COLON_ALIGNMENT=center`: Aligns the colon dots with the vertical midpoint of numerals.
  - `COLON_OFFSET=0`: Adjust by `+20` or `-20` to fine-tune height if needed.
  - `COLON_RULE=between_digits`: Standard setting. The centered colon only triggers when typed between numbers (`12:30`), leaving normal text punctuation completely untouched.
  - `COLON_RULE=after_digit`: Use this if your phone's lockscreen displays a stacked two-line clock (where `12:` is on line 1 and `30` is on line 2).

#### 2. ⏱️ Tabular Clock Digits (`ENABLE_TABULAR_CLOCK_DIGITS`)
- **The Problem**: Proportional fonts assign different widths to different numbers (e.g., `1` is much narrower than `0` or `8`). When your lockscreen clock changes from `11:59` to `12:00`, or if you have a ticking seconds display, the digits jump horizontally and create visible jitter.
- **How to Use**:
  - Set `ENABLE_TABULAR_CLOCK_DIGITS=yes`.
  - The runtime equalizes the horizontal advance width across all digits `0` through `9` and centers their contours within the standardized bounding box.

#### 3. 🛡️ Decoupled Safe Metrics (`METRICS_MODE`)
- **The Problem**: In status bars, app toolbars, and notification headers, tall diacritics (Vietnamese `ế`, `Ậ`, Devanagari, Thai, Arabic, or display letters `Å`, `Ŵ`) can get clipped if vertical metrics are too tight. Conversely, older scripts that blindly expanded line heights caused code editors and terminal emulators to experience severe (+41%) vertical line-height ballooning.
- **Options**:
  - `METRICS_MODE=safe` (Default & Recommended): Decoupled safe metrics. Ascent and descent expand independently based on actual glyph boundaries. Tall accents never clip, descenders remain clear, and UI elements stay centered and compact.
  - `METRICS_MODE=compact`: Forces classic ultra-tight FFIX3 metrics ($2128 / -550$). Best for English-only setups desiring maximum notification compactness.
  - `METRICS_MODE=preserve`: Leaves the font designer's original metric tables unaltered.

#### 4. ⚡ Table Optimization & Zygote RAM Saver (`ENABLE_ZYGOTE_OPTIMIZATION`)
- **The Problem**: Android memory-maps `/system/fonts/DroidSans.ttf` directly into the root **Zygote** process, where it is shared across every running app and system service. Desktop fonts often bundle dead tables from the 1990s (`DSIG`, `VDMX`, `hdmx`, `LTSH`, `PCLT`, `EBDT` bitmap strikes) and duplicate Macintosh Roman name records that waste RAM and cause Minikin logcat warnings.
- **How to Use**:
  - `ENABLE_ZYGOTE_OPTIMIZATION=no` (Default): Leaves all tables byte-for-byte untouched.
  - `ENABLE_ZYGOTE_OPTIMIZATION=yes`: Strips obsolete tables, eliminates duplicate Mac Roman name records, normalizes subpixel rendering in `gasp`, and canonicalizes table ordering. Reduces font file size by 10–30% and saves memory in Zygote.

#### 5. 🎨 OpenType Feature Freezing (`*_FREEZE_FEATURES`)
- **The Problem**: Many professional fonts feature alternate characters (slashed zeros, curved lowercase `l`, single-story `a` and `g`, or geometric glyphs) hidden behind OpenType tags (`zero`, `ss01`–`ss20`, `cv01`–`cv99`). Android apps lack menus to activate these.
- **How to Use**:
  - Check the discovered features list commented directly in your `.conf` file.
  - Add desired feature tags separated by commas:
    ```sh
    SANS_FREEZE_FEATURES=ss01,zero
    MONO_FREEZE_FEATURES=zero
    ```
  - Re-flash the font module ZIP to bake these alternates into the default glyphs system-wide!

#### 6. ⚖️ Variable Font Weight Tuning
- For variable fonts, fine-tune the exact numeric weight mapped to each of Android's system weight tiers (100–900):
  ```sh
  SANS_WGHT="100 200 300 400 500 600 700 800 900"
  SANS_WDTH="100 100 100 100 100 100 100 100 100"
  ```

#### 7. 🌐 Adding Extra Fonts Directly on Your Phone
- You can augment an installed module with additional language or style families without repacking the ZIP on PC:
  - Place extra fonts into `/sdcard/MFFM/<FontFamily>/`:
    - `/sdcard/MFFM/<FontFamily>/Bengali/`
    - `/sdcard/MFFM/<FontFamily>/Monospace/`
    - `/sdcard/MFFM/<FontFamily>/Serif/`
  - Re-flash your font module — it will scan the directory, optimize the fonts, and package them into the system collection automatically!

---

## 🛡️ Anti-Google Font Update Protection

Google Play System updates silently push fonts (such as `NotoSansCJK-Regular.ttc`) to `/data/fonts/files/`, overriding user font modules without warning.

MFFMv14 provides automated dual-layer defense:
1. **Boot Daemon (`service.sh`)**: Runs early during boot to neutralize Google Font cache updates before apps launch. Operation logs are saved to `/sdcard/MFFM/font_service.log`.
2. **On-Demand Action Button (`action.sh`)**: For **KernelSU**, **APatch**, and **MMRL** users, tap the "Action" button in your root manager interface to immediately clear any newly downloaded Google Font updates without rebooting.

---

## 📦 Supported Font Formats & Technical Rules

- **Input Formats**: TrueType (`.ttf`), OpenType (`.otf`), TrueType Collection (`.ttc`), OpenType Collection (`.otc`), Web Open Font Format (`.woff`, `.woff2`).
- **Automatic Decompression**: Web fonts (`.woff`, `.woff2`) are automatically decompressed and converted into native TrueType tables.
- **Outline Conversion**: Cubic PostScript outlines (`.otf`) are automatically converted to quadratic TrueType outlines (`cu2qu`) during collection packaging.
- **Weight Resolution**: Weights are resolved through deep inspection of OS/2 `usWeightClass` and typographic name table records, ensuring accurate mapping even with arbitrary filenames.
- **Multi-400 Face Deduplication**: If multiple 400-weight normal faces exist (such as `Regular`, `Book`, `Normal`), `Regular` is strictly prioritized.

---

## ❓ Frequently Asked Questions & Troubleshooting

### Q: Why did the module installation fail with an MFFM Runtime error?
**A:** MFFMv14 modules require the standalone **`mffm-runtime`** module to be installed first. Download `mffm-runtime-YYYY.MM.DD.zip` from [t.me/MFFMMain](https://t.me/MFFMMain), flash it in Magisk/KernelSU/APatch, and then install your font module.

### Q: How do I apply my changes after editing `/sdcard/MFFM/*.conf`?
**A:** Simply flash your font module ZIP again in Magisk, KernelSU, or APatch. You do not need to uninstall it first; flashing over the existing module reads the updated configuration file and regenerates the fonts.

### Q: My clock colon is still low on a 2-line vertical lockscreen clock.
**A:** Open your `.conf` file and set `COLON_RULE=after_digit`. Standard `between_digits` requires digits on both sides (`12:30`), whereas `after_digit` supports clocks that place the hours and minutes on separate lines (`12:` on top, `30` on bottom).

### Q: Where can I find installation and error logs?
**A:** The installer retains the 3 most recent detailed diagnostic logs at:
```
/sdcard/MFFM/mffmv14_debug_<TIMESTAMP>.log
```
These logs record every command, detected weights, metric calculations, and fontTools output for easy troubleshooting.
