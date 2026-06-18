# MFFMv14 Font Module Template

One template builds and updates both static and variable Android font modules. The compiler detects the font model from OpenType tables and generates the correct installer XML:

- **Static:** multiple faces are compiled into one TTC-backed `DroidSans.ttf`; XML entries use collection `index` values. The `.ttf` extension is intentional and preserves the established Android compatibility/spoofing convention.
- **Variable:** one upright font and an optional italic font are kept variable; XML entries use each font's real `fvar` axes.

For the established Android spoofing convention, a separate variable italic
face is intentionally packaged as `DroidSans-Bold.ttf`. Its generated XML still
declares `style="italic"`, so the filename disguise does not change its role.

When the static input contains only one face, `DroidSans.ttf` is an ordinary
standalone TTF rather than a collection, and its XML uses the detected weight
and style. This applies equally to inputs such as `Regular.ttf`, `Bold.ttf`, or
`Italic.ttf`.

The flashable payload supports Magisk, KernelSU, and APatch. KernelSU users may still need their manager's mounting metamodule.

Variable builds receive a single `VF` suffix in both the module display name
and output ZIP filename. Static module names are left unchanged.

## Setup

```powershell
python -m pip install -r requirements.txt
```

ZipSignerust is downloaded on the first signed build. Its binary and the reusable signing key pair are stored in `.mffm-signer/`, which is excluded from module ZIPs and Git.

## Build a static module

Clear `Fonts/`, then add one file per face. Metadata is the primary classifier, so filenames can be descriptive; conventional names remain easiest to audit:

```text
Fonts/
  Thin.ttf
  Regular.ttf
  Medium.ttf
  Bold.ttf
  Italic.ttf
  BoldItalic.ttf
  Condensed-Regular.ttf
```

Build:

```powershell
python build.py
```

Duplicate weight/style/width combinations are rejected instead of silently choosing the wrong face.

## Build a variable module

Clear `Fonts/`, then add exactly one upright variable font and optionally one separate italic variable font. A single font with an `ital` or `slnt` axis can serve both styles.

```text
Fonts/
  Family[opsz,wdth,wght].ttf
  Family-Italic[opsz,wdth,wght].ttf   # optional
```

Build with the same command:

```powershell
python build.py
```

The compiler keeps every non-weight axis at its declared default. It selects `ital`/`slnt` appropriately for italic XML and emits only weights supported by the font's `wght` range.

### On-device variable-axis configuration

The first time a variable module is flashed, the installer creates an editable,
font-specific configuration in `/sdcard/MFFM`:

```text
/sdcard/MFFM/MFFMv14_<Font_Name>_vf-<unique_identity>.conf
```

This user configuration is never included in the module ZIP. It persists on
shared storage across module updates and reinstalls. The identity is a
deterministic fingerprint of the module's font payload and axis schema, keeping
different variable modules isolated even when their family names are similar.
A typical file looks like:

```ini
CONFIG_SCHEMA=2
MODULE_IDENTITY=vf-0123456789abcdefabcd

# SANS-SERIF / UPRIGHT
SANS_UPRIGHT_REGULAR_WGHT=400
SANS_UPRIGHT_MEDIUM_WGHT=500
SANS_UPRIGHT_WDTH=100

# SANS-SERIF / ITALIC
SANS_ITALIC_REGULAR_WGHT=400
SANS_ITALIC_WDTH=100
SANS_ITALIC_SLNT=-10

# CONDENSED / UPRIGHT
CONDENSED_UPRIGHT_REGULAR_WGHT=400
CONDENSED_UPRIGHT_WDTH=75

# CONDENSED / ITALIC
CONDENSED_ITALIC_REGULAR_WGHT=400
CONDENSED_ITALIC_WDTH=75
CONDENSED_ITALIC_SLNT=-10
```

The generated file contains a usage guide and valid ranges. Named weight keys
target one Android face, so setting `SANS_UPRIGHT_REGULAR_WGHT=450` changes only
Regular. Sans and condensed profiles are independent, allowing condensed width
without narrowing the normal family. Italic profiles receive explicit `ital`
or `slnt` values when those axes exist. `AUTO` remains available as an optional
way to restore the compiler-generated value for an individual key.

After editing, save and reflash the same module. The installer validates every
value and targets the exact family profile, style, and named weight in Android's
XML. Empty, non-numeric, and out-of-range values produce a warning and are
rewritten in the saved configuration using that field's compiled default.

Do not edit `CONFIG_SCHEMA` or `MODULE_IDENTITY`. On reflash, the installer
checks both before reading any axis value. A missing, outdated, or incorrect
value causes the incompatible file to be replaced with fresh defaults.

## Useful compiler options

```powershell
python build.py --mode auto --name "My Font" --version 2026.06.18
python build.py --no-sign              # unsigned debugging ZIP
python build.py --no-zip               # prepare Files/ and config only
python build.py --keep-hinting         # preserve TrueType instructions
python build.py --no-prefix            # preserve internal family names
python build.py --fonts-dir D:\Fonts  # external source folder
```

`--mode auto` is the default. Mixed static and variable inputs are rejected because silently flattening or mixing them can produce invalid Android family mappings.

## Update old modules

Create `Old Modules/`, place old v12 static and/or v13 variable ZIPs inside it, then run:

```powershell
python update.py
```

Updated ZIPs are written to `Updated Modules/`. The updater:

1. safely extracts each ZIP;
2. locates legacy `DroidSans.ttf`, `RobotoStatic-Regular.ttf`, or v13 upright/italic payloads;
3. detects static collections versus variable fonts from their tables;
4. recovers legacy face weights from names when old OS/2 metadata is stale;
5. rebuilds the font config on the current template;
6. preserves optional `Beng*`, `Serif*`, and `Mono*` assets;
7. signs and verifies the result.

For a dry/debug migration:

```powershell
python update.py --no-sign --keep-temp
```

## Generated contract

The compiler produces `font-config.sh` and four XML fragments under `Files/`:

- `sans.xml` — primary family entries;
- `condensed.xml` — dedicated condensed entries or primary fallback;
- `serif.xml` — regular/bold/italic fallback selections;
- `clock.xml` — Google Sans Clock entry.

`customize.sh` reads this contract. It does not inspect or guess font axes on-device. The `FONT_MODE` value is also printed during installation, which makes static/variable behavior visible in recovery logs.

For variable builds, the internal contract also carries axis names and ranges
so the installer can create and validate the external `/sdcard/MFFM` user
configuration. The editable configuration itself is not packaged.

## Optional assets

The installer accepts the conventions retained from both source templates:

- `Beng*.zip` containing `Beng-Regular.ttf`, `Beng-Medium.ttf`, and `Beng-Bold.ttf`;
- `Serif*.zip` containing the four `Serif-*.ttf` faces;
- `Mono*.ttf`.

Assets may be bundled in `Files/` before building or placed in `/sdcard/MFFM` on the device.

## Installation logs

Each flash saves a detailed shell debug log in the MFFM folder:

```text
/sdcard/MFFM/mffmv14_debug_YYYYMMDD_HHMMSS.log
```

Debug logging is enabled automatically. The file contains the shell execution trace,
expanded commands, command errors, root-manager installer messages, MFFMv14 progress,
configuration warnings, and fatal errors. It can be shared as-is for troubleshooting
without enabling a separate debug option before flashing.
