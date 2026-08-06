# MFFMv14

Builds a systemless Android font module from a folder of font files. Point it at your fonts and it
produces a flashable ZIP that replaces the ROM's sans-serif, monospace and serif families for
Magisk, KernelSU, APatch, Mountify and OverlayFS-based root implementations.

The full reference — every CLI flag, the installer's behaviour section by section, the on-device
configuration files and troubleshooting — is in **[USAGE_GUIDE.md](USAGE_GUIDE.md)**
([বাংলা](USAGE_GUIDE_BN.md)).

## What it does

- Compiles static or variable fonts into one `DroidSans.ttf` TTC holding every face, and generates
  the matching `fonts.xml` fragments that index into it.
- Normalises vertical metrics across faces so line spacing does not change per weight.
- Optionally freezes OpenType features (`ss01`, `zero`, `tnum`, …) into the default glyph mappings.
- Injects contextual centered-colon rules for clock displays when the font lacks them.
- Rewrites the ROM's `fonts.xml`, `font_fallback.xml` and `fonts_customization.xml` at install time
  without touching the ROM's own copies.
- For variable fonts, installs `/system/bin/font-config`, which re-applies the axis values from
  `/sdcard/MFFM/MFFMv14_*.conf` on the next reboot without re-flashing.

## Quick start

```bash
pip install -r requirements.txt
cp /path/to/*.ttf Fonts/            # Fonts/Monospace/ and Fonts/Serif/ for those families
python build.py
```

The signed ZIP lands in `dist/`; flash it from your root manager. Useful flags:

| Flag | Effect |
|---|---|
| `--mode static\|variable\|auto` | Force a font model instead of detecting it. |
| `--fonts-dir DIR` | Build from a different folder. |
| `--name`, `--version` | Override the module name and version. |
| `--features ss01,zero` | Freeze features headlessly instead of being prompted. |
| `--no-interactive` | Never prompt (for scripts and CI). |
| `--no-sign` | Skip ZIP signing when the signer cannot run. |

Building on the phone itself is supported: run `sh termux-build.sh` in Termux and it installs the
toolchain, builds and flashes in one step. See
[section 8 of the guide](USAGE_GUIDE.md#8-building-on-android-with-termux).

Already have an older MFFM module? `python update.py` migrates it to the v14 layout.

## Repository layout

| Path | Purpose |
|---|---|
| `build.py`, `font_module.py` | The compiler: font discovery, TTC assembly, XML generation, packaging. |
| `update.py` | Migrates legacy modules to the v14 template. |
| `zipsigner_auto.py` | Fetches and verifies the ZipSignerust binary used to sign the ZIP. |
| `customize.sh`, `fontlib.sh` | The on-device installer and its shared XML/axis routines. |
| `font-config` | Installed to `system/bin` by variable modules to re-apply axis values. |
| `service.sh`, `post-mount.sh`, `uninstall.sh` | Boot-time and removal hooks. |
| `tests/` | Pytest suite covering the compiler and the shell rewriters. |

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
shellcheck -S warning -s sh -e SC3043,SC3021,SC1090,SC1091 \
  customize.sh fontlib.sh font-config termux-build.sh service.sh post-mount.sh uninstall.sh \
  META-INF/com/google/android/update-binary
```

CI runs the same checks plus an end-to-end build on every push.

---

© 2026 MFFM / Mistu
