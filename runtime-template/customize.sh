#!/system/bin/sh
# MFFM Runtime Installer - shared Python + fontTools for all MFFMv14 font modules
# Installs portable runtime to /data/adb/mffm_runtime

# --- Termux paths (for bootstrap fallback) ---
if [ -d "/data/data/com.termux/files/usr/bin" ]; then
  export PATH="/data/data/com.termux/files/usr/bin:$PATH"
  export LD_LIBRARY_PATH="/data/data/com.termux/files/usr/lib:$LD_LIBRARY_PATH"
  export HOME="/data/data/com.termux/files/home"
  export TMPDIR="/data/data/com.termux/files/usr/tmp"
  mkdir -p "$TMPDIR" 2>/dev/null
fi

# --- ui_print shim ---
if ! command -v ui_print >/dev/null 2>&1; then
  ui_print() { echo "$1"; }
fi
if ! command -v abort >/dev/null 2>&1; then
  abort() { ui_print "$1"; exit 1; }
fi

# --- Logging (reuse font-module log dir) ---
LOG_DIR=${LOG_DIR:-/sdcard/MFFM}
LOG_FILE=${LOG_FILE:-"$LOG_DIR/mffmv14_runtime_$(date '+%Y%m%d_%H%M%S' 2>/dev/null || echo current).log"}
mkdir -p "$LOG_DIR" 2>/dev/null

if [ -d "$LOG_DIR" ]; then
  for old_log in "$LOG_DIR"/mffmv14_debug_*.log "$LOG_DIR"/mffmv14_runtime_*.log "$LOG_DIR"/mffm_debug_*.log "$LOG_DIR"/action.log "$LOG_DIR"/action_*.log; do
    [ -f "$old_log" ] || continue
    [ "$old_log" != "$LOG_FILE" ] && rm -f "$old_log" 2>/dev/null
  done
fi

if [ -d "$LOG_DIR" ] && : >> "$LOG_FILE" 2>/dev/null; then
  exec 2>> "$LOG_FILE"
  PS4='+ [${0##*/}:${LINENO:-?}] '
  set -x
fi

mffm_log_line() { [ -n "$LOG_FILE" ] || return 0; printf '%s\n' "$1" >> "$LOG_FILE" 2>/dev/null; }
mffm_ui_print() {
  local msg=$1; mffm_log_line "$msg"
  if [ "${BOOTMODE:-false}" = "true" ]; then printf '%s\n' "$msg";
  else case "$OUTFD" in ''|*[!0-9]*) printf '%s\n' "$msg";; *) printf 'ui_print %s\nui_print\n' "$msg" >&$OUTFD;; esac; fi
}
ui_print() { mffm_ui_print "$1"; }
fail() { ui_print ""; ui_print "  [ERROR] $1"; ui_print "  Runtime installation stopped."; ui_print ""; exit 1; }
section() { ui_print ""; ui_print "  [$1] $2"; ui_print "  ----------------------------------------"; }
status_ok() { ui_print "    [OK] $1"; }
status_skip() { ui_print "    [--] $1"; }
status_warn() { ui_print "    [!!] $1"; }

# --- Paths ---
MODPATH=${MODPATH:-$1}
[ -n "$MODPATH" ] || MODPATH="$(dirname "$0")"
RUNTIME_DEST="/data/adb/mffm_runtime"
RUNTIME_VERSION=""
if [ -f "$MODPATH/module.prop" ]; then
  RUNTIME_VERSION=$(grep '^version=' "$MODPATH/module.prop" 2>/dev/null | cut -d= -f2)
fi
[ -z "$RUNTIME_VERSION" ] && RUNTIME_VERSION="1.0"

# Resolve MFFM storage (same logic as font module customize.sh)
MFFM_STORAGE=""
for _sbase in /sdcard /storage/emulated/0 /data/media/0 /mnt/pass_through/0/emulated/0; do
  if [ -d "$_sbase/MFFM" ]; then MFFM_STORAGE="$_sbase"; break; fi
done
[ -z "$MFFM_STORAGE" ] && MFFM_STORAGE=/sdcard
MFFM_DIR="$MFFM_STORAGE/MFFM"
TMP_EXTRACT="/dev/.mffm_runtime_extract_$$"

# --- ABI detection (arm64 > armv7 > x64 > x86) ---
detect_abi() {
  local abi=""
  # 1. Android property (most reliable)
  if command -v getprop >/dev/null 2>&1; then
    abi=$(getprop ro.product.cpu.abi 2>/dev/null)
    case "$abi" in
      arm64-v8a|arm64) printf 'aarch64\n'; return 0;;
      armeabi-v7a|armeabi|armv7*) printf 'armv7\n'; return 0;;
      x86_64|x64) printf 'x64\n'; return 0;;
      x86) printf 'x86\n'; return 0;;
    esac
  fi
  # 2. uname
  abi=$(uname -m 2>/dev/null | tr '[:upper:]' '[:lower:]')
  case "$abi" in
    aarch64|arm64) printf 'aarch64\n'; return 0;;
    armv7l|armv7|arm) printf 'armv7\n'; return 0;;
    x86_64|amd64) printf 'x64\n'; return 0;;
    i686|i386|x86) printf 'x86\n'; return 0;;
  esac
  # 3. fallback
  printf 'aarch64\n'
}
ABI=$(detect_abi)
ui_print ""
ui_print "  +----------------------------------------+"
ui_print "  |       MFFM RUNTIME INSTALLER           |"
ui_print "  |   Shared Python + fontTools v$RUNTIME_VERSION  |"
ui_print "  +----------------------------------------+"
ui_print "    ABI          : $ABI"
ui_print "    Module path  : $MODPATH"
ui_print "    Dest (exec)  : $RUNTIME_DEST"

# --- Manifest handling (SHA256 pin, like zipsigner_auto.py) ---
MANIFEST="$MODPATH/manifest.json"
# Also allow manifest in runtime/ subdir for legacy
[ -f "$MANIFEST" ] || MANIFEST="$MODPATH/runtime/manifest.json"

# --- Locate embedded runtime tarball ---
RUNTIME_TAR=""
for cand in \
  "$MODPATH/runtime/$ABI/python.tar.xz" \
  "$MODPATH/runtime/$ABI/runtime.tar.xz" \
  "$MODPATH/runtime/$ABI.tar.xz" \
  "$MODPATH/python-$ABI.tar.xz" \
; do
  [ -f "$cand" ] && { RUNTIME_TAR="$cand"; break; }
done

# Also accept .tar.gz
if [ -z "$RUNTIME_TAR" ]; then
  for cand in \
    "$MODPATH/runtime/$ABI/python.tar.gz" \
    "$MODPATH/runtime/$ABI/runtime.tar.gz" \
  ; do [ -f "$cand" ] && { RUNTIME_TAR="$cand"; break; }; done
fi

# --- Helper: sha256 check ---
verify_sha256() {
  local file=$1 expected=$2 actual=""
  [ -z "$expected" ] && return 0
  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1)
  elif command -v sha256 >/dev/null 2>&1; then
    actual=$(sha256 "$file" 2>/dev/null | cut -d' ' -f1)
  else
    status_warn "sha256sum not available, skipping verification for $file"
    return 0
  fi
  if [ "$actual" != "$expected" ]; then
    ui_print "  [ERROR] SHA256 mismatch for $file"
    ui_print "          expected: $expected"
    ui_print "          actual  : $actual"
    return 1
  fi
  return 0
}

get_manifest_sha() {
  local abi=$1
  [ -f "$MANIFEST" ] || return 1
  # Very small JSON parser: extract "abi": "sha"
  # manifest format: {"version":"1.0","sha256":{"aarch64":"...","armv7":"..."}}
  grep -o "\"$abi\"[[:space:]]*:[[:space:]]*\"[a-fA-F0-9]*\"" "$MANIFEST" 2>/dev/null | grep -o "[a-fA-F0-9]\{64\}" | head -n1
}

# --- Installation ---
section "1/3" "Preparing destination"

# Ensure clean extract dir
rm -rf "$RUNTIME_DEST" 2>/dev/null
mkdir -p "$RUNTIME_DEST" || fail "Could not create $RUNTIME_DEST"

installed_via=""

if [ -n "$RUNTIME_TAR" ] && [ -f "$RUNTIME_TAR" ]; then
  section "2/3" "Installing embedded runtime ($ABI)"
  ui_print "    Archive : $RUNTIME_TAR"

  expected_sha=$(get_manifest_sha "$ABI")
  if [ -n "$expected_sha" ]; then
    ui_print "    Verifying SHA256..."
    verify_sha256 "$RUNTIME_TAR" "$expected_sha" || fail "Archive failed SHA256 pin — possible tamper or stale manifest.json. Update manifest.json SHA."
    status_ok "SHA256 verified"
  else
    status_skip "No SHA pin for $ABI in manifest.json — skipping verification"
  fi

  mkdir -p "$TMP_EXTRACT"
  case "$RUNTIME_TAR" in
    *.tar.xz)
      tar -xJf "$RUNTIME_TAR" -C "$TMP_EXTRACT" 2>/dev/null || \
      (xz -dc "$RUNTIME_TAR" 2>/dev/null | tar -xf - -C "$TMP_EXTRACT" 2>/dev/null) || \
      (busybox tar -xJf "$RUNTIME_TAR" -C "$TMP_EXTRACT" 2>/dev/null) || \
      (busybox unxz -c "$RUNTIME_TAR" 2>/dev/null | tar -xf - -C "$TMP_EXTRACT" 2>/dev/null) || \
      fail "Failed to extract $RUNTIME_TAR (xz)"
      ;;
    *.tar.gz)
      tar -xzf "$RUNTIME_TAR" -C "$TMP_EXTRACT" 2>/dev/null || \
      (gzip -dc "$RUNTIME_TAR" 2>/dev/null | tar -xf - -C "$TMP_EXTRACT" 2>/dev/null) || \
      (busybox tar -xzf "$RUNTIME_TAR" -C "$TMP_EXTRACT" 2>/dev/null) || \
      fail "Failed to extract $RUNTIME_TAR (gz)"
      ;;
    *) fail "Unknown archive format: $RUNTIME_TAR";;
  esac

  # Tar is expected to contain bin/python3, lib/, etc at top level, but handle single top-dir case
  if [ -f "$TMP_EXTRACT/bin/python3" ] || [ -f "$TMP_EXTRACT/bin/python" ]; then
    cp -a "$TMP_EXTRACT"/* "$RUNTIME_DEST"/ 2>/dev/null
  else
    # Find nested dir containing bin/
    nested=$(find "$TMP_EXTRACT" -maxdepth 2 -type d -name bin 2>/dev/null | head -n1)
    if [ -n "$nested" ]; then
      cp -a "$(dirname "$nested")"/* "$RUNTIME_DEST"/ 2>/dev/null
    else
      cp -a "$TMP_EXTRACT"/* "$RUNTIME_DEST"/ 2>/dev/null
    fi
  fi
  rm -rf "$TMP_EXTRACT" 2>/dev/null
  installed_via="embedded tarball"

elif command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  # --- Bootstrap via Termux/host python ---
  section "2/3" "No embedded tarball, bootstrapping via pip"
  py_bin=""
  command -v python3 >/dev/null 2>&1 && py_bin="python3"
  [ -z "$py_bin" ] && command -v python >/dev/null 2>&1 && py_bin="python"

  if [ -n "$py_bin" ] && $py_bin -c "import sys" 2>/dev/null; then
    ui_print "    Python : $($py_bin --version 2>&1) ($py_bin)"
    # Try pip install directly to RUNTIME_DEST
    mkdir -p "$RUNTIME_DEST/lib" "$RUNTIME_DEST/bin"

    # Copy host python binary if possible
    py_path=$(command -v "$py_bin" 2>/dev/null)
    if [ -n "$py_path" ] && [ -f "$py_path" ]; then
      cp -f "$py_path" "$RUNTIME_DEST/bin/python3" 2>/dev/null
      cp -f "$py_path" "$RUNTIME_DEST/bin/python" 2>/dev/null
      chmod 755 "$RUNTIME_DEST/bin/python3" 2>/dev/null
      chmod 755 "$RUNTIME_DEST/bin/python" 2>/dev/null
    fi

    # Determine pip
    pip_bin=""
    if [ -x "/data/data/com.termux/files/usr/bin/pip" ]; then pip_bin="/data/data/com.termux/files/usr/bin/pip"
    elif command -v pip3 >/dev/null 2>&1; then pip_bin="pip3"
    elif command -v pip >/dev/null 2>&1; then pip_bin="pip"
    fi

    if [ -n "$pip_bin" ]; then
      ui_print "    Pip    : $pip_bin"
      # Install fontTools + brotli to runtime lib
      PYTHONPATH="" PIP_TARGET="$RUNTIME_DEST/lib" $pip_bin install --no-deps --target "$RUNTIME_DEST/lib" fonttools brotli 2>&1 | mffm_log_line
      if [ $? -eq 0 ] && [ -d "$RUNTIME_DEST/lib/fontTools" ]; then
        status_ok "Bootstrapped fontTools via pip to $RUNTIME_DEST/lib"
        installed_via="pip bootstrap"
      else
        # Fallback: try pip install fonttools without target then copy
        $pip_bin install fonttools brotli 2>&1 | mffm_log_line
        if $py_bin -c "import fontTools" 2>/dev/null; then
          status_ok "fontTools available via system pip"
          # Still record runtime dest for discovery
          printf '# runtime bootstrapped via system pip\n' > "$RUNTIME_DEST/.pip_bootstrap"
          installed_via="system pip"
        else
          status_warn "pip install did not provide fontTools, runtime will be limited"
        fi
      fi
    else
      status_warn "pip not found — cannot bootstrap, runtime will be limited"
    fi
  else
    status_warn "No python found for bootstrap"
  fi
else
  section "2/3" "No embedded tarball and no bootstrap python"
  status_warn "No runtime archive for $ABI and no host python — runtime will be empty"
  status_warn "Place python.tar.xz for $ABI under runtime/$ABI/ and reflash, or install Termux+python"
  # Create placeholder so font modules can detect missing runtime gracefully
  mkdir -p "$RUNTIME_DEST/bin"
  printf '# placeholder - runtime archive missing for %s\n' "$ABI" > "$RUNTIME_DEST/README"
fi

# --- Common: helper wrapper + helper.py ---
section "3/3" "Finalizing runtime"

# Create helper.py that font modules will invoke (mirrors font_module _py_scan_font_weights + TTC)
mkdir -p "$RUNTIME_DEST/bin" 2>/dev/null
cat > "$RUNTIME_DEST/helper.py" <<'PYEOF'
#!/usr/bin/env python3
"""MFFM Runtime Helper — on-device font metrics normalization, TTC bundling, OpenType feature freezing, centered colon injection, and indexed XML compilation."""

import argparse
import os
import re
import sys
from pathlib import Path

FFIX3_REFERENCE_UPM = 2048
FFIX3_METRICS = (
    ("hhea", "ascent", 2128),
    ("hhea", "descent", -550),
    ("hhea", "lineGap", 0),
    ("OS/2", "sTypoAscender", 2128),
    ("OS/2", "sTypoDescender", -550),
    ("OS/2", "sTypoLineGap", 0),
    ("OS/2", "sCapHeight", 1456),
    ("OS/2", "sxHeight", 1082),
    ("head", "yMax", 2163),
    ("head", "yMin", -555),
)

WEIGHT_NAMES = {
    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular",
    500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black",
}

SUPPORTED_EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2")

WEIGHT_LABELS = (
    (r"extra[\s_-]*black|ultra[\s_-]*black", 900),
    (r"extra[\s_-]*bold|ultra[\s_-]*bold", 800),
    (r"semi[\s_-]*bold|demi[\s_-]*bold", 600),
    (r"extra[\s_-]*light|ultra[\s_-]*light", 200),
    (r"thin|hairline", 100),
    (r"black|heavy", 900),
    (r"bold", 700),
    (r"medium", 500),
    (r"light", 300),
    (r"regular|normal|book|roman", 400),
)

STANDARD_FEATURE_NAMES = {
    "aalt": "Access All Alternates",
    "calt": "Contextual Alternates",
    "case": "Case-Sensitive Forms",
    "ccmp": "Glyph Composition / Decomposition",
    "cpsp": "Capital Spacing",
    "dlig": "Discretionary Ligatures",
    "dnom": "Denominators",
    "frac": "Fractions",
    "kern": "Kerning",
    "liga": "Standard Ligatures",
    "locl": "Localized Forms",
    "lnum": "Lining Figures",
    "numr": "Numerators",
    "onum": "Oldstyle Figures",
    "ordn": "Ordinals",
    "pnum": "Proportional Figures",
    "salt": "Stylistic Alternates",
    "sinf": "Scientific Inferiors",
    "subs": "Subscript",
    "sups": "Superscript",
    "tnum": "Tabular Figures",
    "zero": "Slashed Zero",
}

UNSAFE_FEATURES = {
    "aalt": "UNSAFE: Enables multiple/all alternate glyphs simultaneously across font",
    "calt": "Enabled by default in font layout engines (Contextual)",
    "ccmp": "System layout feature",
    "locl": "System script/language feature",
    "kern": "System layout feature",
    "liga": "Standard Ligature (Enabled by default in font layout engines)",
}

CAUTION_FEATURES = {
    "frac": "NOT RECOMMENDED TO FREEZE: Alters normal number sequences (e.g. 123456 -> 1²3456) system-wide!",
    "numr": "Numerators (Shrinks letters/numbers into superior position)",
    "dnom": "Denominators (Shrinks letters/numbers into inferior position)",
    "subs": "Subscript (Shrinks/lowers letters/numbers into subscript)",
    "sups": "Superscript (Shrinks/raises letters/numbers into superscript)",
    "sinf": "Scientific Inferiors (Shrinks numbers into inferior position)",
    "ordn": "Ordinals (Shrinks letters into ordinal position)",
    "onum": "Changes default numbers to oldstyle height",
}


def _scale_value(val: int, from_upm: int, to_upm: int = 2048) -> int:
    return int(round(val * to_upm / from_upm))


def _name(font, *ids: int) -> str:
    if "name" not in font:
        return ""
    for name_id in ids:
        records = [record for record in font["name"].names if record.nameID == name_id]
        records.sort(key=lambda record: (record.platformID != 3, record.langID not in (0x409, 0)))
        for record in records:
            try:
                value = record.toUnicode().strip()
            except Exception:
                continue
            if value:
                return value
    return ""


def _set_name(font, name_id: int, value: str) -> None:
    name_table = font.get("name")
    if name_table is None:
        return
    records = [record for record in name_table.names if record.nameID == name_id]
    if records:
        for record in records:
            record.string = value.encode("utf-16be" if record.platformID == 3 else "latin1", errors="replace")
    else:
        name_table.setName(value, name_id, 3, 1, 0x409)


def sanitize_name_table(font, prefix: str = "") -> None:
    raw_family = _name(font, 16, 1) or "Font"
    cleaned = re.sub(r"(?i)\b(?:MFFM|Mistu|Variable)\b", "", raw_family).strip(" -_")
    cleaned = re.sub(r"\s+", " ", cleaned).strip() or "Font"
    if prefix:
        cleaned = f"{prefix} {cleaned}".strip()

    words = cleaned.split()
    if len(words) >= 2:
        new_family = f"{words[0]} Mistu {' '.join(words[1:])}".strip()
    else:
        new_family = f"{words[0]} Mistu".strip()

    style = _name(font, 17, 2) or "Regular"
    full_name = f"{new_family} {style}".strip()
    postscript = re.sub(r"[^A-Za-z0-9-]", "", f"{new_family.replace(' ', '')}-{style.replace(' ', '')}")[:63]

    for name_id in (1, 16):
        _set_name(font, name_id, new_family)
    _set_name(font, 4, full_name)
    _set_name(font, 6, postscript)

    ver = (_name(font, 5) or "Version 1.000").strip()
    if not ver.endswith(";Mistu"):
        if ver.endswith(";"):
            ver = f"{ver}Mistu"
        else:
            ver = f"{ver};Mistu"
    _set_name(font, 5, ver)
    _set_name(font, 8, "Mistu @ MFFM Inc.")


def fix_font_metrics(font, target_upm: int = 2048, mode: str = "safe") -> None:
    head = font.get("head")
    os2 = font.get("OS/2")
    hhea = font.get("hhea")
    if head is None:
        return
    upm = int(getattr(head, "unitsPerEm", target_upm))
    mode_lower = (mode or "safe").strip().lower()

    if mode_lower == "preserve":
        if os2 is not None:
            os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
            if "fvar" in font:
                os2.usWeightClass = 400
        return

    base_ascent = int(round(2128 * upm / target_upm))
    base_descent = int(round(-550 * upm / target_upm))

    actual_y_max = None
    actual_y_min = None

    if mode_lower == "safe":
        if "glyf" in font and hasattr(font["glyf"], "glyphs"):
            for g in font["glyf"].glyphs.values():
                if hasattr(g, "numberOfContours") and g.numberOfContours != 0:
                    if hasattr(g, "yMax"):
                        if actual_y_max is None or g.yMax > actual_y_max:
                            actual_y_max = g.yMax
                    if hasattr(g, "yMin"):
                        if actual_y_min is None or g.yMin < actual_y_min:
                            actual_y_min = g.yMin

        head_y_max = getattr(head, "yMax", None)
        head_y_min = getattr(head, "yMin", None)
        if head_y_max is not None:
            if actual_y_max is None or head_y_max > actual_y_max:
                actual_y_max = head_y_max
        if head_y_min is not None:
            if actual_y_min is None or head_y_min < actual_y_min:
                actual_y_min = head_y_min

        k_ascent = (actual_y_max / base_ascent) if (actual_y_max is not None and base_ascent > 0) else 1.0
        k_descent = (abs(actual_y_min) / abs(base_descent)) if (actual_y_min is not None and base_descent < 0) else 1.0
        ascent = int(round(max(1.0, k_ascent) * base_ascent))
        descent = int(round(-max(1.0, k_descent) * abs(base_descent)))
    else:  # compact mode
        ascent = base_ascent
        descent = base_descent

    # 1. hhea
    if hhea is not None:
        hhea.ascent = ascent
        hhea.descent = descent
        hhea.lineGap = 0

    # 2. OS/2
    if os2 is not None:
        os2.sTypoAscender = ascent
        os2.sTypoDescender = descent
        os2.sTypoLineGap = 0

        win_ascent = max(ascent, actual_y_max) if actual_y_max is not None else ascent
        win_descent = max(abs(descent), abs(actual_y_min)) if actual_y_min is not None else abs(descent)
        os2.usWinAscent = int(win_ascent)
        os2.usWinDescent = int(win_descent)

        if hasattr(os2, "sCapHeight"):
            os2.sCapHeight = int(round(1456 * upm / target_upm))
        if hasattr(os2, "sxHeight"):
            os2.sxHeight = int(round(1082 * upm / target_upm))

        os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
        if "fvar" in font:
            os2.usWeightClass = 400

    # 3. head
    if hasattr(head, "yMax"):
        curr_max = getattr(head, "yMax", 0)
        head.yMax = max(curr_max, ascent, actual_y_max if actual_y_max is not None else ascent)
    if hasattr(head, "yMin"):
        curr_min = getattr(head, "yMin", 0)
        head.yMin = min(curr_min, descent, actual_y_min if actual_y_min is not None else descent)


def remove_font_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()


ZYGOTE_BLOAT_TABLES = (
    "DSIG", "LTSH", "VDMX", "hdmx", "PCLT", "EBDT", "EBLC", "EBSC",
    "bdat", "bloc", "bhed", "JSTF", "Feat", "Glat", "Gloc", "Silf",
    "Sill", "FFTM", "TSI0", "TSI1", "TSI2", "TSI3", "TSI5", "prop",
    "opbd", "kerx", "morx", "mort", "meta",
)


def optimize_font_tables(font, keep_hinting: bool = False) -> bool:
    """Optimize font tables for Android Zygote memory footprint and rendering speed."""
    modified = False

    # 1. Drop bloat tables
    for tag in ZYGOTE_BLOAT_TABLES:
        if tag in font:
            del font[tag]
            modified = True

    # 2. Hinting removal (if not keep_hinting)
    if not keep_hinting:
        hint_tables = ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX")
        for tag in hint_tables:
            if tag in font:
                del font[tag]
                modified = True
        if "glyf" in font:
            for glyph in font["glyf"].glyphs.values():
                if hasattr(glyph, "removeHinting"):
                    glyph.removeHinting()
                    modified = True

    # 3. Clean and normalize gasp table for smooth subpixel anti-aliasing (0x000F)
    if "gasp" in font:
        try:
            gasp_table = font["gasp"]
            gasp_table.gaspRange = {0xFFFF: 0x000F}
            modified = True
        except Exception:
            pass

    # 4. Prune obsolete Macintosh Roman (platformID 1) duplicate name records if Windows Unicode (platformID 3) exists
    if "name" in font and hasattr(font["name"], "names"):
        has_win_records = any(rec.platformID == 3 for rec in font["name"].names)
        if has_win_records:
            initial_count = len(font["name"].names)
            font["name"].names = [
                rec for rec in font["name"].names
                if rec.platformID != 1
            ]
            if len(font["name"].names) != initial_count:
                modified = True

    return modified


def glyphs_to_quadratic(glyphs, max_err: float = 1.0, reverse_direction: bool = True) -> dict:
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    quad_glyphs = {}
    for gname in glyphs.keys():
        glyph = glyphs[gname]
        tt_pen = TTGlyphPen(glyphs)
        cu2qu_pen = Cu2QuPen(tt_pen, max_err, reverse_direction=reverse_direction)
        glyph.draw(cu2qu_pen)
        quad_glyphs[gname] = tt_pen.glyph()
    return quad_glyphs


def update_hmtx_lsb(tt_font, glyf) -> None:
    if "hmtx" not in tt_font:
        return
    hmtx = tt_font["hmtx"]
    metrics = getattr(hmtx, "metrics", {})
    for glyph_name, glyph in glyf.glyphs.items():
        if hasattr(glyph, "xMin") and glyph_name in metrics:
            advance = metrics[glyph_name][0]
            metrics[glyph_name] = (advance, glyph.xMin)


def otf_to_ttf(tt_font, post_format: float = 2.0, max_err: float = 1.0, reverse_direction: bool = True) -> bool:
    """Convert CFF/OTF cubic outlines to TrueType quadratic outlines."""
    from fontTools.ttLib import newTable

    is_cff = "CFF " in tt_font or "CFF2" in tt_font or getattr(tt_font, "sfntVersion", None) == "OTTO"
    if not is_cff:
        return False

    glyph_order = tt_font.getGlyphOrder()
    tt_font["loca"] = newTable("loca")
    tt_font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = glyph_order
    glyf.glyphs = glyphs_to_quadratic(tt_font.getGlyphSet(), max_err=max_err, reverse_direction=reverse_direction)
    for glyph in glyf.glyphs.values():
        glyph.recalcBounds(glyf)

    if "CFF " in tt_font:
        del tt_font["CFF "]
    if "CFF2" in tt_font:
        del tt_font["CFF2"]
    if "VORG" in tt_font:
        del tt_font["VORG"]

    glyf.compile(tt_font)
    update_hmtx_lsb(tt_font, glyf)

    tt_font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.recalc(tt_font)
    maxp.compile(tt_font)

    if "post" in tt_font:
        post = tt_font["post"]
        post.formatType = post_format
        post.extraNames = []
        post.mapping = {}
        post.glyphOrder = glyph_order
        try:
            post.compile(tt_font)
        except OverflowError:
            post.formatType = 3
    else:
        tt_font["post"] = post = newTable("post")
        post.formatType = 3

    tt_font.sfntVersion = "\000\001\000\000"
    return True


def font_has_centered_colon(font_or_path) -> bool:
    from fontTools.ttLib import TTFont
    should_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path), lazy=True)
            should_close = True
        except Exception:
            return True
    else:
        font = font_or_path

    try:
        glyph_order = font.getGlyphOrder()
        for name in ("colon.case", "colon.centered", "colon.cap", "colon.case.tf", "colon.centered.tf"):
            if name in glyph_order:
                return True
        if "GSUB" in font and font["GSUB"].table is not None:
            gsub = font["GSUB"].table
            if gsub.FeatureList and gsub.FeatureList.FeatureRecord:
                records = {rec.FeatureTag: rec.Feature for rec in gsub.FeatureList.FeatureRecord if rec.FeatureTag}
                if "case" in records:
                    lookups = getattr(gsub.LookupList, "Lookup", [])
                    for lidx in records["case"].LookupListIndex:
                        if lidx < len(lookups):
                            for st in getattr(lookups[lidx], "SubTable", []):
                                mapping = getattr(st, "mapping", {})
                                if "colon" in mapping:
                                    return True
    finally:
        if should_close:
            font.close()
    return False


def equalize_clock_digits(font_or_path, target_width: int | None = None) -> bool:
    """Equalize advance widths of digits (0-9) and center their contours for wobble-free clocks."""
    from fontTools.ttLib import TTFont

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        if getattr(font, "flavor", None) is not None:
            font.flavor = None

        if "CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO":
            otf_to_ttf(font)

        if "glyf" not in font or "hmtx" not in font:
            if should_save_and_close:
                font.close()
            return False

        glyph_order = font.getGlyphOrder()
        cmap = font.getBestCmap() or {}
        digit_set = set()
        for cp in range(0x30, 0x3A):
            if cp in cmap:
                digit_set.add(cmap[cp])
        exact_digit_bases = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
        for g in glyph_order:
            if g.split(".")[0].lower() in exact_digit_bases:
                digit_set.add(g)

        hmtx = font["hmtx"]
        glyf = font["glyf"]
        metrics = getattr(hmtx, "metrics", {})
        digits = [g for g in glyph_order if g in digit_set and g in metrics]
        if not digits:
            if should_save_and_close:
                font.close()
            return False

        advances = [metrics[d][0] for d in digits]
        w_target = int(target_width) if target_width is not None else max(advances)
        if target_width is None and len(set(advances)) == 1:
            if should_save_and_close:
                font.close()
            return False

        modified = False
        for d in digits:
            g = glyf[d]
            orig_adv, orig_lsb = metrics[d]
            if hasattr(g, "numberOfContours") and g.numberOfContours > 0:
                glyph_w = g.xMax - g.xMin
                new_lsb = round((w_target - glyph_w) / 2)
                dx = new_lsb - g.xMin
                if dx != 0:
                    coords = g.coordinates
                    for i in range(len(coords)):
                        coords[i] = (coords[i][0] + dx, coords[i][1])
                    g.recalcBounds(glyf)
                    modified = True
                metrics[d] = (w_target, g.xMin)
                if orig_adv != w_target or orig_lsb != g.xMin:
                    modified = True
            elif hasattr(g, "components") and g.components:
                glyph_w = g.xMax - g.xMin
                new_lsb = round((w_target - glyph_w) / 2)
                dx = new_lsb - g.xMin
                if dx != 0:
                    for comp in g.components:
                        if hasattr(comp, "x"):
                            comp.x += dx
                    g.recalcBounds(glyf)
                    modified = True
                metrics[d] = (w_target, g.xMin)
                if orig_adv != w_target or orig_lsb != g.xMin:
                    modified = True
            else:
                if orig_adv != w_target:
                    metrics[d] = (w_target, orig_lsb)
                    modified = True

        if modified and "OS/2" in font:
            try:
                font["OS/2"].recalc(font)
            except Exception:
                pass

        if should_save_and_close:
            if modified:
                font.save(str(font_or_path))
            font.close()
        return modified
    except Exception as exc:
        sys.stderr.write(f"equalize_clock_digits error: {exc}\n")
        if should_save_and_close:
            try:
                font.close()
            except Exception:
                pass
        return False


def inject_centered_colon(
    font_or_path,
    alignment: str = "center",
    offset: int = 0,
    rule: str = "between_digits",
) -> bool:
    from fontTools.ttLib import TTFont, newTable
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables.otTables import (
        ChainContextSubst, Coverage, DefaultLangSys, Feature, FeatureList,
        FeatureRecord, GSUB, Lookup, LookupList, Script, ScriptList,
        ScriptRecord, SingleSubst, SubstLookupRecord
    )

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        glyph_order = font.getGlyphOrder()
        if "colon" not in glyph_order:
            return False

        centered_glyph = None
        for candidate in ("colon.case.tf", "colon.case", "colon.centered", "colon.cap", "colon.centered.tf"):
            if candidate in glyph_order:
                centered_glyph = candidate
                break

        if not centered_glyph and "glyf" not in font:
            if "CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO":
                otf_to_ttf(font)
                glyph_order = font.getGlyphOrder()

        if not centered_glyph and "glyf" in font:
            glyf = font["glyf"]
            hmtx = font["hmtx"]
            coords, _, _ = glyf["colon"].getCoordinates(glyf)
            if coords:
                y_coords = [y for _, y in coords]
                colon_center = (min(y_coords) + max(y_coords)) / 2

                cap_height = getattr(font.get("OS/2"), "sCapHeight", None) or 1400
                x_height = getattr(font.get("OS/2"), "sxHeight", None) or 1000
                align_lower = (alignment or "center").strip().lower()

                if align_lower in ("cap_height", "capheight", "caps"):
                    target_center = cap_height / 2
                elif align_lower in ("x_height", "xheight", "lowercase"):
                    target_center = x_height / 2
                else:
                    digit_y_maxes = []
                    digit_y_mins = []
                    for d in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3"):
                        if d in glyph_order:
                            try:
                                d_coords, _, _ = glyf[d].getCoordinates(glyf)
                                if d_coords:
                                    digit_y_maxes.append(max(y for _, y in d_coords))
                                    digit_y_mins.append(min(y for _, y in d_coords))
                            except Exception:
                                pass
                    if digit_y_maxes:
                        d_min = min(digit_y_mins) if digit_y_mins else 0
                        d_max = max(digit_y_maxes)
                        target_center = (d_min + d_max) / 2
                    else:
                        target_center = cap_height / 2

                dy = round(target_center - colon_center) + int(offset or 0)
                pen = TTGlyphPen(font.getGlyphSet())
                tpen = TransformPen(pen, (1, 0, 0, 1, 0, dy))
                font.getGlyphSet()["colon"].draw(tpen)
                centered_glyph = "colon.case"
                font.setGlyphOrder(glyph_order + [centered_glyph])
                new_glyph = pen.glyph()
                new_glyph.recalcBounds(glyf)
                glyf[centered_glyph] = new_glyph
                hmtx[centered_glyph] = hmtx["colon"]
                if "vmtx" in font:
                    vmtx = font["vmtx"]
                    if "colon" in getattr(vmtx, "metrics", {}):
                        vmtx[centered_glyph] = vmtx["colon"]
                    else:
                        vmtx[centered_glyph] = (0, 0)
                glyph_order = font.getGlyphOrder()

        if not centered_glyph:
            return False

        if "GSUB" not in font or font["GSUB"].table is None:
            gsub_wrapper = newTable("GSUB")
            gsub = GSUB()
            gsub.Version = 0x00010000
            gsub.ScriptList = ScriptList()
            gsub.FeatureList = FeatureList()
            gsub.LookupList = LookupList()
            gsub.ScriptList.ScriptRecord = []
            gsub.FeatureList.FeatureRecord = []
            gsub.LookupList.Lookup = []
            gsub_wrapper.table = gsub
            font["GSUB"] = gsub_wrapper

        gsub = font["GSUB"].table
        if gsub.FeatureList is None: gsub.FeatureList = FeatureList()
        if gsub.FeatureList.FeatureRecord is None: gsub.FeatureList.FeatureRecord = []
        if gsub.LookupList is None: gsub.LookupList = LookupList()
        if gsub.LookupList.Lookup is None: gsub.LookupList.Lookup = []

        calt_rec_idx = None
        for idx, rec in enumerate(gsub.FeatureList.FeatureRecord):
            if rec.FeatureTag == "calt":
                calt_rec_idx = idx
                target_feat = rec.Feature
                break

        if calt_rec_idx is None:
            new_rec = FeatureRecord()
            new_rec.FeatureTag = "calt"
            new_rec.Feature = Feature()
            new_rec.Feature.LookupListIndex = []
            new_rec.Feature.FeatureParams = None
            gsub.FeatureList.FeatureRecord.append(new_rec)
            calt_rec_idx = len(gsub.FeatureList.FeatureRecord) - 1
            target_feat = new_rec.Feature

        if gsub.ScriptList and gsub.ScriptList.ScriptRecord:
            for srec in gsub.ScriptList.ScriptRecord:
                script = srec.Script
                lang_sys_list = []
                if script.DefaultLangSys: lang_sys_list.append(script.DefaultLangSys)
                if script.LangSysRecord:
                    for lrec in script.LangSysRecord: lang_sys_list.append(lrec.LangSys)
                for lsys in lang_sys_list:
                    if calt_rec_idx not in lsys.FeatureIndex:
                        lsys.FeatureIndex.append(calt_rec_idx)
        elif gsub.ScriptList is not None:
            for script_tag in ("DFLT", "latn"):
                srec = ScriptRecord()
                srec.ScriptTag = script_tag
                srec.Script = Script()
                srec.Script.DefaultLangSys = DefaultLangSys()
                srec.Script.DefaultLangSys.ReqFeatureIndex = 0xFFFF
                srec.Script.DefaultLangSys.FeatureIndex = [calt_rec_idx]
                srec.Script.LangSysRecord = []
                gsub.ScriptList.ScriptRecord.append(srec)

        rule_lower = (rule or "between_digits").strip().lower()

        s_lookup = Lookup()
        s_lookup.LookupType = 1
        s_lookup.LookupFlag = 0
        st1 = SingleSubst()
        st1.Format = 1
        st1.mapping = {}
        if "colon" in glyph_order:
            st1.mapping["colon"] = centered_glyph
        if "colon.tf" in glyph_order and "colon.case.tf" in glyph_order:
            st1.mapping["colon.tf"] = "colon.case.tf"
        st1.mapping = dict(sorted(st1.mapping.items(), key=lambda item: font.getGlyphID(item[0])))
        s_lookup.SubTable = [st1]
        gsub.LookupList.Lookup.append(s_lookup)
        s_lidx = len(gsub.LookupList.Lookup) - 1

        if rule_lower == "always":
            if s_lidx not in target_feat.LookupListIndex:
                target_feat.LookupListIndex.append(s_lidx)
        else:
            pure_digits = set()
            cmap = font.getBestCmap() or {}
            for codepoint, gname in cmap.items():
                if (0x0030 <= codepoint <= 0x0039) or (0xFF10 <= codepoint <= 0xFF19) or (0x0660 <= codepoint <= 0x0669) or (0x0966 <= codepoint <= 0x096F):
                    pure_digits.add(gname)
            exact_digit_bases = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
            for g in glyph_order:
                if g.split(".")[0].lower() in exact_digit_bases:
                    pure_digits.add(g)
            sorted_digits = sorted(list(pure_digits), key=lambda g: font.getGlyphID(g))

            bcov = Coverage(); bcov.glyphs = sorted_digits
            icov = Coverage(); icov.glyphs = sorted([g for g in ("colon", "colon.tf") if g in glyph_order], key=lambda g: font.getGlyphID(g))
            lcov = Coverage(); lcov.glyphs = sorted_digits

            c_lookup = Lookup()
            c_lookup.LookupType = 6
            c_lookup.LookupFlag = 0

            st6 = ChainContextSubst()
            st6.Format = 3
            st6.BacktrackGlyphCount = 1
            st6.BacktrackCoverage = [bcov]
            st6.InputGlyphCount = 1
            st6.InputCoverage = [icov]

            if rule_lower in ("after_digit", "trailing", "after"):
                st6.LookAheadGlyphCount = 0
                st6.LookAheadCoverage = []
            else:
                st6.LookAheadGlyphCount = 1
                st6.LookAheadCoverage = [lcov]

            srec = SubstLookupRecord()
            srec.SequenceIndex = 0
            srec.LookupListIndex = s_lidx
            st6.SubstLookupRecord = [srec]
            c_lookup.SubTable = [st6]

            space_glyphs = [g for g in ("space", "uni0020", "u0020", "thinspace", "uni2009", "u2009") if g in glyph_order]
            if space_glyphs:
                scov = Coverage(); scov.glyphs = sorted(space_glyphs, key=lambda g: font.getGlyphID(g))
                if rule_lower in ("after_digit", "trailing", "after"):
                    # digit + space + colon ("12 :")
                    st_after_space = ChainContextSubst()
                    st_after_space.Format = 3
                    st_after_space.BacktrackGlyphCount = 2
                    st_after_space.BacktrackCoverage = [scov, bcov]
                    st_after_space.InputGlyphCount = 1
                    st_after_space.InputCoverage = [icov]
                    st_after_space.LookAheadGlyphCount = 0
                    st_after_space.LookAheadCoverage = []
                    st_after_space.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_after_space)
                else:
                    # 1. digit + space + colon + space + digit ("12 : 30")
                    st_space = ChainContextSubst()
                    st_space.Format = 3
                    st_space.BacktrackGlyphCount = 2
                    st_space.BacktrackCoverage = [scov, bcov]
                    st_space.InputGlyphCount = 1
                    st_space.InputCoverage = [icov]
                    st_space.LookAheadGlyphCount = 2
                    st_space.LookAheadCoverage = [scov, lcov]
                    st_space.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_space)

                    # 2. digit + colon + space + digit ("12: 30")
                    st_lead = ChainContextSubst()
                    st_lead.Format = 3
                    st_lead.BacktrackGlyphCount = 1
                    st_lead.BacktrackCoverage = [bcov]
                    st_lead.InputGlyphCount = 1
                    st_lead.InputCoverage = [icov]
                    st_lead.LookAheadGlyphCount = 2
                    st_lead.LookAheadCoverage = [scov, lcov]
                    st_lead.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_lead)

                    # 3. digit + space + colon + digit ("12 :30")
                    st_trail = ChainContextSubst()
                    st_trail.Format = 3
                    st_trail.BacktrackGlyphCount = 2
                    st_trail.BacktrackCoverage = [scov, bcov]
                    st_trail.InputGlyphCount = 1
                    st_trail.InputCoverage = [icov]
                    st_trail.LookAheadGlyphCount = 1
                    st_trail.LookAheadCoverage = [lcov]
                    st_trail.SubstLookupRecord = [srec]
                    c_lookup.SubTable.append(st_trail)

            gsub.LookupList.Lookup.append(c_lookup)
            c_lidx = len(gsub.LookupList.Lookup) - 1

            if c_lidx not in target_feat.LookupListIndex:
                target_feat.LookupListIndex.append(c_lidx)

        if should_save_and_close:
            font.save(str(font_or_path))
            font.close()
        return True
    except Exception as exc:
        sys.stderr.write(f"inject_centered_colon error: {exc}\n")
        return False


def extract_opentype_features(font_or_path) -> dict[str, str]:
    from fontTools.ttLib import TTFont
    should_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path), lazy=True)
            should_close = True
        except Exception:
            return {}
    else:
        font = font_or_path

    features = {}
    try:
        if "GSUB" not in font or font["GSUB"].table is None or font["GSUB"].table.FeatureList is None:
            return features
        gsub = font["GSUB"].table
        name_table = font.get("name")
        for record in gsub.FeatureList.FeatureRecord:
            tag = record.FeatureTag
            if not tag:
                continue
            ui_name = ""
            params = getattr(record.Feature, "FeatureParams", None)
            if params and name_table:
                name_id = (
                    getattr(params, "UINameID", None)
                    or getattr(params, "FeatUILabelNameID", None)
                    or getattr(params, "featUINameID", None)
                    or getattr(params, "FirstParamUILabelNameID", None)
                )
                if name_id:
                    for nrec in name_table.names:
                        if nrec.nameID == name_id:
                            try: ui_name = nrec.toUnicode().strip()
                            except Exception: pass
                            if ui_name: break
            if not ui_name:
                if tag in STANDARD_FEATURE_NAMES:
                    ui_name = STANDARD_FEATURE_NAMES[tag]
                elif tag.startswith("ss") and tag[2:].isdigit():
                    ui_name = f"Stylistic Set {int(tag[2:])}"
                elif tag.startswith("cv") and tag[2:].isdigit():
                    ui_name = f"Character Variant {int(tag[2:])}"
            features[tag] = ui_name
    finally:
        if should_close:
            font.close()
    return features


def extract_features_from_dirs(dirs: list[str]) -> dict[str, str]:
    from fontTools.ttLib import TTCollection
    aggregated = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not any(f.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                continue
            fp = os.path.join(d, f)
            try:
                col = TTCollection(fp, lazy=True)
                for font in col.fonts:
                    for tag, name in extract_opentype_features(font).items():
                        if tag not in aggregated or (not aggregated[tag] and name):
                            aggregated[tag] = name
                col.close()
            except Exception:
                for tag, name in extract_opentype_features(fp).items():
                    if tag not in aggregated or (not aggregated[tag] and name):
                        aggregated[tag] = name
    return dict(sorted(aggregated.items()))


def format_category_feature_report(category_name: str, features: dict[str, str]) -> list[str]:
    lines = [f"# {category_name.upper()} AVAILABLE FEATURES:"]
    if not features:
        lines.append("#   (none detected)")
        return lines

    safe = {k: v for k, v in features.items() if k not in UNSAFE_FEATURES and k not in CAUTION_FEATURES}
    caution = {k: v for k, v in features.items() if k in CAUTION_FEATURES}
    unsafe = {k: v for k, v in features.items() if k in UNSAFE_FEATURES}

    if safe:
        lines.append("#   [RECOMMENDED / SAFE TO FREEZE]:")
        for tag, name in sorted(safe.items()):
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            lines.append(f"#{label}")
    if caution:
        lines.append("#   [CAUTION - USE WITH CARE]:")
        for tag, name in sorted(caution.items()):
            note = CAUTION_FEATURES.get(tag, "")
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            if note: label += f" ({note})"
            lines.append(f"#{label}")
    if unsafe:
        lines.append("#   [SYSTEM / NOT RECOMMENDED]:")
        for tag, name in sorted(unsafe.items()):
            note = UNSAFE_FEATURES.get(tag, "")
            label = f"    {tag:<6} - {name}" if name else f"    {tag}"
            if note: label += f" ({note})"
            lines.append(f"#{label}")
    return lines


def freeze_font_features(font_or_path, features: list[str] | str) -> bool:
    from fontTools.ttLib import TTFont
    if isinstance(features, str):
        feature_list = [f.strip().lower() for f in features.split(",") if f.strip()]
    else:
        feature_list = [f.strip().lower() for f in features if f.strip()]

    if not feature_list:
        return False

    should_save_and_close = False
    if isinstance(font_or_path, (str, Path)):
        try:
            font = TTFont(str(font_or_path))
            should_save_and_close = True
        except Exception:
            return False
    else:
        font = font_or_path

    try:
        if "GSUB" not in font or font["GSUB"].table is None:
            return False
        gsub = font["GSUB"].table
        if not gsub.FeatureList or not gsub.FeatureList.FeatureRecord:
            return False

        contextual_candidates = {"dlig", "hlig", "clig", "rvrn"}
        contextual_feats = [f for f in feature_list if f in contextual_candidates]
        single_feats = [f for f in feature_list if f not in contextual_candidates]

        modified = False

        if single_feats and gsub.LookupList and gsub.LookupList.Lookup:
            target_tags = set(single_feats)
            lookup_indices = []
            for rec in gsub.FeatureList.FeatureRecord:
                if rec.FeatureTag in target_tags and rec.Feature:
                    lookup_indices.extend(rec.Feature.LookupListIndex)
            lookup_indices = sorted(set(lookup_indices))

            glyph_order = font.getGlyphOrder()
            subs = {g: g for g in glyph_order}

            for lidx in lookup_indices:
                if lidx >= len(gsub.LookupList.Lookup):
                    continue
                lookup = gsub.LookupList.Lookup[lidx]
                for st in getattr(lookup, "SubTable", []):
                    mapping = {}
                    alternates = {}
                    if getattr(st, "LookupType", None) == 1:
                        mapping = getattr(st, "mapping", {})
                    elif getattr(st, "LookupType", None) == 3:
                        alternates = getattr(st, "alternates", {})
                    elif getattr(st, "LookupType", None) == 7:
                        ext = getattr(st, "ExtSubTable", None)
                        if ext and getattr(ext, "LookupType", None) == 1:
                            mapping = getattr(ext, "mapping", {})
                        elif ext and getattr(ext, "LookupType", None) == 3:
                            alternates = getattr(ext, "alternates", {})

                    for in_g, out_g in mapping.items():
                        for k, v in subs.items():
                            if v == in_g: subs[k] = out_g
                    for in_g, out_list in alternates.items():
                        if out_list:
                            out_first = out_list[0]
                            for k, v in subs.items():
                                if v == in_g: subs[k] = out_first

            if "cmap" in font and font["cmap"].tables:
                for cmaptable in font["cmap"].tables:
                    if not getattr(cmaptable, "cmap", None): continue
                    for cp, gname in list(cmaptable.cmap.items()):
                        target = subs.get(gname, gname)
                        if target != gname:
                            cmaptable.cmap[cp] = target
                            modified = True

        if contextual_feats and gsub.FeatureList and gsub.LookupList:
            records = {rec.FeatureTag: rec.Feature for rec in gsub.FeatureList.FeatureRecord if rec.FeatureTag}
            target_feat = records.get("calt") or records.get("liga")
            if not target_feat:
                from fontTools.ttLib.tables.otTables import FeatureRecord, Feature
                new_rec = FeatureRecord()
                new_rec.FeatureTag = "calt"
                new_rec.Feature = Feature()
                new_rec.Feature.LookupListIndex = []
                new_rec.Feature.FeatureParams = None
                gsub.FeatureList.FeatureRecord.append(new_rec)
                target_feat = new_rec.Feature

            def collect_lookups(lidx: int, collected: set[int]):
                if lidx in collected or lidx >= len(gsub.LookupList.Lookup): return
                collected.add(lidx)
                lk = gsub.LookupList.Lookup[lidx]
                for st in getattr(lk, "SubTable", []):
                    for sr in getattr(st, "SubstLookupRecord", []) or []:
                        collect_lookups(sr.LookupListIndex, collected)

            to_promote = set()
            for tag in contextual_feats:
                if tag in records:
                    for idx in records[tag].LookupListIndex:
                        collect_lookups(idx, to_promote)

            for idx in sorted(to_promote):
                if idx not in target_feat.LookupListIndex:
                    target_feat.LookupListIndex.append(idx)
                    modified = True

        if should_save_and_close:
            font.save(str(font_or_path))
            font.close()
        return modified
    except Exception as exc:
        sys.stderr.write(f"freeze_font_features error: {exc}\n")
        return False


def inspect_face(path: str, font_num: int | None = None) -> dict:
    from fontTools.ttLib import TTFont
    kwargs = {"lazy": True}
    if font_num is not None:
        kwargs["fontNumber"] = font_num
    with TTFont(path, **kwargs) as font:
        os2 = font.get("OS/2")
        head = font.get("head")
        name = font.get("name")
        family = (name.getDebugName(16) or name.getDebugName(1) or os.path.splitext(os.path.basename(path))[0]) if name else ""
        sub = (name.getDebugName(17) or name.getDebugName(2) or "") if name else ""
        full = (name.getDebugName(4) or "") if name else ""
        label = f"{sub} {family} {full} {os.path.splitext(os.path.basename(path))[0]}".lower()

        italic = bool(
            "italic" in label or "oblique" in label
            or (os2 is not None and int(getattr(os2, "fsSelection", 0)) & 1)
            or (head is not None and int(getattr(head, "macStyle", 0)) & 2)
        )
        width_class = int(getattr(os2, "usWidthClass", 5)) if os2 is not None else 5
        condensed = width_class <= 4 or "condensed" in label or "narrow" in label
        os2_w = int(getattr(os2, "usWeightClass", 0)) if os2 is not None else 0

        name_wt = None
        for pattern, w in WEIGHT_LABELS:
            if re.search(rf"(?i)(?:^|[\s_-])(?:{pattern})(?:$|[\s_-])", label):
                name_wt = w
                break

        if os2_w in WEIGHT_NAMES and os2_w != 400:
            if name_wt and name_wt != os2_w and abs(name_wt - 400) > abs(os2_w - 400):
                weight = name_wt
            else:
                weight = os2_w
        elif name_wt:
            weight = name_wt
        elif os2_w in WEIGHT_NAMES:
            weight = os2_w
        else:
            weight = min(WEIGHT_NAMES, key=lambda w: (abs(w - (os2_w or 400)), w))

        axes = {}
        if "fvar" in font:
            for axis in font["fvar"].axes:
                axes[axis.axisTag] = (float(axis.minValue), float(axis.defaultValue), float(axis.maxValue))

        return {
            "path": path,
            "font_number": font_num,
            "family": family,
            "style_name": sub,
            "weight": weight,
            "style": "italic" if italic else "normal",
            "condensed": condensed,
            "variable": bool(axes),
            "axes": axes,
        }


def format_num(val: float) -> str:
    return str(int(val)) if float(val).is_integer() else f"{val:g}"


def font_xml(filename: str, weight: int, style: str, index: int | None = None, axes: dict[str, float] | None = None) -> str:
    attrs = f' weight="{weight}" style="{style}"'
    if index is not None:
        attrs += f' index="{index}"'
    if not axes:
        return f"    <font{attrs}>{filename}</font>"
    lines = [f"    <font{attrs}>{filename}"]
    for tag, val in axes.items():
        lines.append(f'      <axis tag="{tag}" stylevalue="{format_num(val)}"/>')
    lines.append("    </font>")
    return "\n".join(lines)


def calc_axis_values(face: dict, weight: int, italic: bool) -> dict[str, float] | None:
    if "wght" not in face["axes"]:
        return None
    min_w, def_w, max_w = face["axes"]["wght"]
    if not min_w <= weight <= max_w:
        return None
    values = {}
    for tag, (a_min, a_def, a_max) in face["axes"].items():
        if tag == "wght":
            v = float(weight)
        elif tag == "ital":
            v = 1.0 if italic else 0.0
        elif tag == "slnt":
            v = (a_min if a_min < 0 else a_max) if italic else (0.0 if a_min <= 0 <= a_max else a_def)
        else:
            v = a_def
        values[tag] = max(a_min, min(a_max, v))
    return values


def scan_weights(dirs: list[str]) -> None:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.stderr.write("fontTools not available\n"); sys.exit(1)
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not any(f.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                continue
            path = os.path.join(d, f)
            try:
                face = inspect_face(path)
                print(f"{face['weight']}:{face['style']}:{face['path']}")
            except Exception as e:
                sys.stderr.write(f"scan skip {path}: {e}\n")


def build_ttc(out_path: str, files: list[str]) -> None:
    try:
        from fontTools.ttLib import TTFont, TTCollection
    except ImportError:
        sys.stderr.write("fontTools not available for TTC\n"); sys.exit(1)
    if not files:
        sys.stderr.write("no input files for TTC\n"); sys.exit(1)
    col = TTCollection()
    for f in files:
        f = f.strip()
        if not f: continue
        try:
            font = TTFont(f)
            if getattr(font, "flavor", None) is not None:
                font.flavor = None
            col.fonts.append(font)
        except Exception as e:
            sys.stderr.write(f"Error loading {f}: {e}\n")
    if not col.fonts:
        sys.stderr.write("no fonts loaded\n"); sys.exit(1)
    col.save(out_path)
    print(f"TTC saved {out_path} with {len(col.fonts)} fonts")


def format_axis_meta(face: dict, italic: bool = False) -> str:
    if not face.get("axes"): return ""
    default_vals = calc_axis_values(face, int(face["axes"]["wght"][1]), italic) or {} if "wght" in face["axes"] else {}
    parts = []
    for tag, (a_min, a_def, a_max) in face["axes"].items():
        val = default_vals.get(tag, a_def)
        parts.append(f"{tag}|{format_num(a_min)}|{format_num(val)}|{format_num(a_max)}")
    return " ".join(parts)


def supported_weights_str(face: dict) -> str:
    if "wght" not in face.get("axes", {}): return ""
    a_min, _, a_max = face["axes"]["wght"]
    return " ".join(str(w) for w in WEIGHT_NAMES if a_min <= w <= a_max)


def face_preference_score(face: dict) -> int:
    name = Path(face["path"]).stem.lower()
    score = 0
    if "hairline" in name: score -= 10
    if "thin" in name: score += 10
    if "extralight" in name: score += 10
    if "ultralight" in name: score -= 5
    if "regular" in name: score += 20
    if "normal" in name: score += 15
    if "book" in name: score -= 5
    if "medium" in name: score += 10
    if "semibold" in name: score += 10
    if "demibold" in name: score -= 5
    if "extrabold" in name: score += 10
    if "ultrabold" in name: score -= 5
    if "black" in name: score += 10
    if "heavy" in name: score -= 5
    if face.get("font_number") is None:
        score += 5
    return score


def compile_bundle(
    out_dir: str,
    sans_dirs: list[str],
    mono_dirs: list[str] = None,
    serif_dirs: list[str] = None,
    bengali_dirs: list[str] = None,
    keep_hinting: bool = False,
    fix_metrics: bool = True,
    sanitize_names: bool = True,
    enable_centered_colon: bool = False,
    convert_otf: bool = True,
    enable_tabular_digits: bool = False,
    colon_alignment: str = "center",
    colon_offset: int = 0,
    colon_rule: str = "between_digits",
    metrics_mode: str = "safe",
    optimize_tables: bool = False,
    freeze_sans: list[str] | str | None = None,
    freeze_mono: list[str] | str | None = None,
    freeze_serif: list[str] | str | None = None,
    freeze_bengali: list[str] | str | None = None,
) -> int:
    from fontTools.ttLib import TTFont, TTCollection
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    def collect_faces(dirs):
        faces = []
        seen_files = set()
        if not dirs: return faces
        for d in dirs:
            if not d or not os.path.isdir(d): continue
            for f in sorted(os.listdir(d)):
                if not any(f.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    continue
                if os.path.abspath(d) == os.path.abspath(out_dir) and f.lower() in ("droidsans.ttf", "droidsans.ttc", "droidsans.otf", "droidsans.otc", "droidsans.woff", "droidsans.woff2"):
                    continue
                fp = os.path.join(d, f)
                try:
                    real_fp = os.path.realpath(fp)
                except Exception:
                    real_fp = fp
                file_key = (os.path.normcase(real_fp), f.lower())
                if file_key in seen_files:
                    continue
                seen_files.add(file_key)
                try:
                    col = TTCollection(fp, lazy=True)
                    for i in range(len(col.fonts)):
                        faces.append(inspect_face(fp, i))
                    col.close()
                except Exception:
                    try:
                        faces.append(inspect_face(fp, None))
                    except Exception as e:
                        sys.stderr.write(f"skip {fp}: {e}\n")
        return faces

    sans_faces = collect_faces(sans_dirs)
    mono_faces = collect_faces(mono_dirs)
    serif_faces = collect_faces(serif_dirs)
    bengali_faces = collect_faces(bengali_dirs)

    if not sans_faces:
        sys.stderr.write("No Sans fonts found to compile\n")
        return 1

    candidates_400 = [f for f in sans_faces if f["style"] == "normal" and not f["condensed"] and f["weight"] == 400]
    if candidates_400:
        primary = max(candidates_400, key=face_preference_score)
    else:
        normal_candidates = [f for f in sans_faces if f["style"] == "normal" and not f["condensed"]]
        if normal_candidates:
            primary = max(normal_candidates, key=face_preference_score)
        else:
            primary = max(sans_faces, key=face_preference_score)

    mode = "variable" if primary["variable"] else "static"
    family_name = primary["family"] or "Custom Font"

    ttc_fonts = []
    output_filename = "DroidSans.ttf"

    def process_and_open(face, category: str = "sans"):
        kw = {"lazy": False, "recalcBBoxes": False, "recalcTimestamp": False}
        if face["font_number"] is not None:
            kw["fontNumber"] = face["font_number"]
        font = TTFont(face["path"], **kw)
        if getattr(font, "flavor", None) is not None:
            font.flavor = None

        # 0. Convert CFF/OTF outlines to TrueType
        if convert_otf and ("CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO"):
            otf_to_ttf(font)

        # 1. Table optimization / Hinting stripping (clean font tables first)
        if optimize_tables:
            optimize_font_tables(font, keep_hinting=keep_hinting)
        elif not keep_hinting:
            remove_font_hinting(font)

        # 2. Equalize clock digits (0-9)
        if enable_tabular_digits:
            equalize_clock_digits(font)

        # 3. Feature freezing
        feat_target = None
        if category == "sans": feat_target = freeze_sans
        elif category == "mono": feat_target = freeze_mono
        elif category == "serif": feat_target = freeze_serif
        elif category == "bengali": feat_target = freeze_bengali
        if feat_target:
            freeze_font_features(font, feat_target)

        # 4. Centered colon (Sans only)
        if category == "sans" and enable_centered_colon:
            inject_centered_colon(
                font,
                alignment=colon_alignment,
                offset=colon_offset,
                rule=colon_rule,
            )

        # 5. Name table sanitization
        if sanitize_names:
            sanitize_name_table(font)

        # 6. Metrics normalization
        if fix_metrics:
            fix_font_metrics(font, mode=metrics_mode)

        return font

    # Process Sans
    sans_entries = []
    normal_entries = []
    condensed_entries = []

    if mode == "variable":
        upright = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0])
        italic = next((f for f in sans_faces if f["style"] == "italic" and not f["condensed"]), None)

        upright_idx = len(ttc_fonts)
        ttc_fonts.append(process_and_open(upright, "sans"))

        italic_idx = upright_idx
        if italic and italic["path"] != upright["path"]:
            italic_idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(italic, "sans"))

        for st, f_face, f_idx in (("normal", upright, upright_idx), ("italic", italic or upright, italic_idx)):
            for w in WEIGHT_NAMES:
                ax = calc_axis_values(f_face, w, st == "italic")
                if ax:
                    sans_entries.append((w, st, font_xml(output_filename, w, st, index=f_idx, axes=ax)))
        sans_entries.sort(key=lambda item: (item[1] == "italic", item[0]))
        sans_xml_str = "\n".join(x for _, _, x in sans_entries)
        condensed_xml_str = sans_xml_str
    else:
        def dedupe_static(faces):
            grouped = {}
            for f in faces:
                k = (f["condensed"], f["style"], f["weight"])
                grouped.setdefault(k, []).append(f)
            return [max(group, key=face_preference_score) for group in grouped.values()]

        ordered_sans = dedupe_static(sans_faces)
        ordered_sans.sort(key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))

        for f in ordered_sans:
            idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(f, "sans"))
            xml_line = font_xml(output_filename, f["weight"], f["style"], index=idx)
            (condensed_entries if f["condensed"] else normal_entries).append((f["weight"], f["style"], xml_line))

        if not normal_entries:
            normal_entries = list(condensed_entries)
        sans_xml_str = "\n".join(x for _, _, x in normal_entries)
        condensed_xml_str = "\n".join(x for _, _, x in (condensed_entries or normal_entries))

    # Process Optional Families (Mono, Serif, Bengali)
    def process_family(faces, cat_name):
        if not faces: return [], None
        f_lines = []
        first_idx = None
        var_upright = next((f for f in faces if f["variable"] and "wght" in f["axes"]), None)
        if var_upright:
            idx = len(ttc_fonts)
            first_idx = idx
            ttc_fonts.append(process_and_open(var_upright, cat_name))
            var_italic = next((f for f in faces if f["style"] == "italic" and f["variable"] and "wght" in f["axes"]), None)
            ital_idx = idx
            if var_italic and var_italic["path"] != var_upright["path"]:
                ital_idx = len(ttc_fonts)
                ttc_fonts.append(process_and_open(var_italic, cat_name))
            for st, vf, f_i in (("normal", var_upright, idx), ("italic", var_italic or var_upright, ital_idx)):
                for w in WEIGHT_NAMES:
                    ax = calc_axis_values(vf, w, st == "italic")
                    if ax:
                        f_lines.append(font_xml(output_filename, w, st, index=f_i, axes=ax))
        else:
            grouped_static = {}
            for f in faces:
                slot_key = (f["weight"], f["style"], f["condensed"])
                grouped_static.setdefault(slot_key, []).append(f)

            deduped = [max(group, key=face_preference_score) for group in grouped_static.values()]
            sorted_faces = sorted(deduped, key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))
            for f in sorted_faces:
                idx = len(ttc_fonts)
                if first_idx is None: first_idx = idx
                ttc_fonts.append(process_and_open(f, cat_name))
                f_lines.append(font_xml(output_filename, f["weight"], f["style"], index=idx))
        return f_lines, first_idx

    mono_lines, mono_idx = process_family(mono_faces, "mono")
    serif_lines, serif_idx = process_family(serif_faces, "serif")
    bengali_lines, bengali_idx = process_family(bengali_faces, "bengali")

    # Save TTCollection
    ttc = TTCollection()
    ttc.fonts = ttc_fonts
    ttc.save(str(out_path / output_filename))
    for f in ttc_fonts:
        f.close()

    # Write XML fragments
    (out_path / "sans.xml").write_text(sans_xml_str + "\n", encoding="utf-8", newline="\n")
    (out_path / "condensed.xml").write_text(condensed_xml_str + "\n", encoding="utf-8", newline="\n")

    if serif_lines:
        (out_path / "serif.xml").write_text("\n".join(serif_lines) + "\n", encoding="utf-8", newline="\n")
    else:
        serif_fallback = []
        for w, s in ((400, "normal"), (700, "normal"), (400, "italic"), (700, "italic")):
            match = next((x for item_w, item_s, x in (sans_entries if mode == "variable" else normal_entries) if item_w == w and item_s == s), None)
            if match and match not in serif_fallback:
                serif_fallback.append(match)
        (out_path / "serif.xml").write_text("\n".join(serif_fallback) + "\n", encoding="utf-8", newline="\n")

    if mono_lines:
        (out_path / "mono.xml").write_text("\n".join(mono_lines) + "\n", encoding="utf-8", newline="\n")
    if bengali_lines:
        (out_path / "bengali.xml").write_text("\n".join(bengali_lines) + "\n", encoding="utf-8", newline="\n")

    conf_lines = [
        f'FONT_MODE="{mode}"',
        f'FONT_FAMILY="{family_name}"',
        f'HAS_CUSTOM_MONO="{"true" if mono_lines else "false"}"',
        f'HAS_CUSTOM_SERIF="{"true" if serif_lines else "false"}"',
        f'HAS_CUSTOM_BENGALI="{"true" if bengali_lines else "false"}"',
        f'TTC_TOTAL_FONTS="{len(ttc_fonts)}"',
    ]

    if mode == "variable":
        upright = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0])
        italic = next((f for f in sans_faces if f["style"] == "italic" and not f["condensed"]), None)
        if upright and upright.get("axes") and "wght" in upright["axes"]:
            conf_lines.append(f'VF_UPRIGHT_AXIS_META="{format_axis_meta(upright, False)}"')
            conf_lines.append(f'VF_UPRIGHT_WEIGHTS="{supported_weights_str(upright)}"')
        if italic and italic.get("axes") and "wght" in italic["axes"] and italic["path"] != upright["path"]:
            conf_lines.append(f'VF_ITALIC_AXIS_META="{format_axis_meta(italic, True)}"')
            conf_lines.append(f'VF_ITALIC_WEIGHTS="{supported_weights_str(italic)}"')

    mono_var = next((f for f in mono_faces if f["variable"] and "wght" in f.get("axes", {})), None)
    if mono_var:
        conf_lines.append(f'VF_MONO_AXIS_META="{format_axis_meta(mono_var, False)}"')
        conf_lines.append(f'VF_MONO_WEIGHTS="{supported_weights_str(mono_var)}"')

    serif_var_upright = next((f for f in serif_faces if f["variable"] and f["style"] == "normal" and "wght" in f.get("axes", {})), None)
    if serif_var_upright:
        conf_lines.append(f'VF_SERIF_UPRIGHT_AXIS_META="{format_axis_meta(serif_var_upright, False)}"')
        conf_lines.append(f'VF_SERIF_UPRIGHT_WEIGHTS="{supported_weights_str(serif_var_upright)}"')
    serif_var_italic = next((f for f in serif_faces if f["variable"] and f["style"] == "italic" and "wght" in f.get("axes", {})), None)
    if serif_var_italic:
        conf_lines.append(f'VF_SERIF_ITALIC_AXIS_META="{format_axis_meta(serif_var_italic, True)}"')
        conf_lines.append(f'VF_SERIF_ITALIC_WEIGHTS="{supported_weights_str(serif_var_italic)}"')

    beng_var = next((f for f in bengali_faces if f["variable"] and "wght" in f.get("axes", {})), None)
    if beng_var:
        conf_lines.append(f'VF_BENGALI_AXIS_META="{format_axis_meta(beng_var, False)}"')
        conf_lines.append(f'VF_BENGALI_WEIGHTS="{supported_weights_str(beng_var)}"')

    (out_path / "font-config.sh").write_text("\n".join(conf_lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Compiled unified TTC ({output_filename}) with {len(ttc_fonts)} fonts -> {out_dir}")
    return 0


def main():
    p = argparse.ArgumentParser(prog="mffm-helper", description="MFFM runtime font helper")
    sub = p.add_subparsers(dest="cmd")

    s_scan = sub.add_parser("scan", help="Scan directories and print OS/2 weights & styles")
    s_scan.add_argument("dirs", nargs="+")

    s_ttc = sub.add_parser("ttc", help="Bundle input fonts into TTC collection")
    s_ttc.add_argument("--out", required=True, help="Output TTC path")
    s_ttc.add_argument("files", nargs="*", help="Input font files")

    s_proc = sub.add_parser("process-font", help="Normalize font metrics and strip hinting")
    s_proc.add_argument("--in", dest="input_file", required=True)
    s_proc.add_argument("--out", dest="output_file")
    s_proc.add_argument("--no-hinting", action="store_true")
    s_proc.add_argument("--no-fix-metrics", action="store_true")
    s_proc.add_argument("--metrics-mode", choices=["safe", "compact", "preserve"], default="safe", help="Metrics mode (safe=auto-clamp FFIX3 ratio, compact=fixed FFIX3, preserve=keep original)")
    s_proc.add_argument("--sanitize-names", action="store_true")
    s_proc.add_argument("--inject-colon", action="store_true")
    s_proc.add_argument("--colon-alignment", choices=["center", "cap_height", "x_height"], default="center")
    s_proc.add_argument("--colon-offset", type=int, default=0)
    s_proc.add_argument("--colon-rule", choices=["between_digits", "after_digit", "always"], default="between_digits")
    s_proc.add_argument("--equalize-digits", action="store_true", help="Equalize advance widths of digits (0-9)")
    s_proc.add_argument("--digit-width", type=int, help="Target advance width for digits")
    s_proc.add_argument("--freeze-features")
    s_proc.add_argument("--convert-otf", action="store_true", help="Convert CFF/OTF outlines to TrueType")
    s_proc.add_argument("--no-convert-otf", action="store_true", help="Skip OTF to TTF conversion")
    s_proc.add_argument("--optimize-tables", action="store_true", help="Optimize tables and prune bloat for Zygote")

    s_comp = sub.add_parser("compile-bundle", help="Compile multiple font directories into unified indexed TTC")
    s_comp.add_argument("--out-dir", required=True)
    s_comp.add_argument("--sans-dir", action="append", default=[])
    s_comp.add_argument("--mono-dir", action="append", default=[])
    s_comp.add_argument("--serif-dir", action="append", default=[])
    s_comp.add_argument("--bengali-dir", action="append", default=[])
    s_comp.add_argument("--keep-hinting", action="store_true")
    s_comp.add_argument("--no-fix-metrics", action="store_true")
    s_comp.add_argument("--metrics-mode", choices=["safe", "compact", "preserve"], default="safe", help="Metrics mode (safe=auto-clamp FFIX3 ratio, compact=fixed FFIX3, preserve=keep original)")
    s_comp.add_argument("--no-sanitize-names", action="store_true")
    s_comp.add_argument("--enable-centered-colon", action="store_true")
    s_comp.add_argument("--colon-alignment", choices=["center", "cap_height", "x_height"], default="center")
    s_comp.add_argument("--colon-offset", type=int, default=0)
    s_comp.add_argument("--colon-rule", choices=["between_digits", "after_digit", "always"], default="between_digits")
    s_comp.add_argument("--enable-tabular-digits", action="store_true", help="Equalize digit advance widths for wobble-free clock")
    s_comp.add_argument("--no-convert-otf", action="store_true", help="Do not convert CFF/OTF outlines to TrueType")
    s_comp.add_argument("--optimize-tables", action="store_true", help="Optimize tables and prune bloat for Zygote")
    s_comp.add_argument("--freeze-sans")
    s_comp.add_argument("--freeze-mono")
    s_comp.add_argument("--freeze-serif")
    s_comp.add_argument("--freeze-bengali")

    s_opt = sub.add_parser("optimize", help="Optimize font tables and prune bloat for Android Zygote")
    s_opt.add_argument("--in", dest="input_file", required=True, help="Input font file")
    s_opt.add_argument("--out", dest="output_file", help="Output font file (default overwrites input)")
    s_opt.add_argument("--keep-hinting", action="store_true", help="Preserve TrueType bytecode hinting")

    s_otf2ttf = sub.add_parser("otf2ttf", help="Convert CFF/OTF font to TrueType font using cu2qu")
    s_otf2ttf.add_argument("--in", dest="input_file", required=True, help="Input OTF font")
    s_otf2ttf.add_argument("--out", dest="output_file", help="Output TTF font (default replaces .otf with .ttf)")
    s_otf2ttf.add_argument("--max-err", type=float, default=1.0, help="Maximum approximation error for cu2qu (default: 1.0)")
    s_otf2ttf.add_argument("--post-format", type=float, default=2.0, help="Post table format (default: 2.0)")

    s_eq_digits = sub.add_parser("equalize-digits", help="Equalize digit advance widths and center contours for clocks")
    s_eq_digits.add_argument("--in", dest="input_file", required=True, help="Input font file")
    s_eq_digits.add_argument("--out", dest="output_file", help="Output font file (default overwrites input)")
    s_eq_digits.add_argument("--width", type=int, help="Target advance width for digits (default: max digit advance)")

    s_colon = sub.add_parser("check-colon", help="Check if font has centered colon")
    s_colon.add_argument("file", help="Path to font file")

    s_inj_col = sub.add_parser("inject-colon", help="Inject centered colon into font")
    s_inj_col.add_argument("--in", dest="input_file", required=True)
    s_inj_col.add_argument("--out", dest="output_file")
    s_inj_col.add_argument("--alignment", choices=["center", "cap_height", "x_height"], default="center")
    s_inj_col.add_argument("--offset", type=int, default=0)
    s_inj_col.add_argument("--rule", choices=["between_digits", "after_digit", "always"], default="between_digits")

    s_freeze = sub.add_parser("freeze-features", help="Freeze OpenType features into font")
    s_freeze.add_argument("--in", dest="input_file", required=True)
    s_freeze.add_argument("--features", required=True, help="Comma-separated feature tags (e.g. ss01,zero)")
    s_freeze.add_argument("--out", dest="output_file")

    s_report = sub.add_parser("report-features", help="Discover and report available OpenType features per category")
    s_report.add_argument("--sans-dir", action="append", default=[])
    s_report.add_argument("--mono-dir", action="append", default=[])
    s_report.add_argument("--serif-dir", action="append", default=[])
    s_report.add_argument("--bengali-dir", action="append", default=[])
    s_report.add_argument("--out", help="Write report to output file")

    args = p.parse_args()
    if args.cmd == "scan":
        scan_weights(args.dirs)
    elif args.cmd == "ttc":
        files = args.files
        if not files:
            files = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
        build_ttc(args.out, files)
    elif args.cmd == "process-font":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        if getattr(font, "flavor", None) is not None:
            font.flavor = None
        if not args.no_convert_otf and (args.convert_otf or args.inject_colon or "CFF " in font or "CFF2" in font or getattr(font, "sfntVersion", None) == "OTTO"):
            otf_to_ttf(font)
        if args.optimize_tables:
            optimize_font_tables(font, keep_hinting=not args.no_hinting)
        elif args.no_hinting:
            remove_font_hinting(font)
        if args.equalize_digits:
            equalize_clock_digits(font, target_width=args.digit_width)
        if args.freeze_features:
            freeze_font_features(font, args.freeze_features)
        if args.inject_colon:
            inject_centered_colon(
                font,
                alignment=args.colon_alignment,
                offset=args.colon_offset,
                rule=args.colon_rule,
            )
        if args.sanitize_names:
            sanitize_name_table(font)
        if not args.no_fix_metrics:
            fix_font_metrics(font, mode=args.metrics_mode)
        font.save(out_f)
        font.close()
        print(f"Processed {args.input_file} -> {out_f}")
    elif args.cmd == "optimize":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        if getattr(font, "flavor", None) is not None:
            font.flavor = None
        ok = optimize_font_tables(font, keep_hinting=args.keep_hinting)
        font.save(out_f)
        font.close()
        if ok:
            print(f"Optimized font tables: {args.input_file} -> {out_f}")
        else:
            print(f"No bloat tables found in {args.input_file}")
    elif args.cmd == "otf2ttf":
        from fontTools.ttLib import TTFont
        in_path = Path(args.input_file)
        out_path = Path(args.output_file) if args.output_file else in_path.with_suffix(".ttf")
        font = TTFont(str(in_path))
        if getattr(font, "flavor", None) is not None:
            font.flavor = None
        ok = otf_to_ttf(font, post_format=args.post_format, max_err=args.max_err)
        if ok or in_path != out_path:
            font.save(str(out_path))
            font.close()
            print(f"Converted {in_path} -> {out_path}")
        else:
            font.close()
            print(f"{in_path} is already TrueType and input equals output")
    elif args.cmd == "equalize-digits":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = equalize_clock_digits(font, target_width=args.width)
        font.save(out_f)
        font.close()
        if ok:
            print(f"Equalized clock digits in {out_f}")
        else:
            print(f"Clock digits already tabular or not modified in {args.input_file}")
    elif args.cmd == "check-colon":
        has_col = font_has_centered_colon(args.file)
        print("true" if has_col else "false")
    elif args.cmd == "inject-colon":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = inject_centered_colon(
            font,
            alignment=args.alignment,
            offset=args.offset,
            rule=args.rule,
        )
        if ok:
            font.save(out_f)
            font.close()
            print(f"Injected centered colon into {out_f}")
        else:
            font.close()
            print(f"Centered colon already present or not applicable in {args.input_file}")
    elif args.cmd == "freeze-features":
        from fontTools.ttLib import TTFont
        out_f = args.output_file or args.input_file
        font = TTFont(args.input_file)
        ok = freeze_font_features(font, args.features)
        font.save(out_f)
        font.close()
        print(f"Froze features [{args.features}] -> {out_f}")
    elif args.cmd == "report-features":
        report_lines = []
        if args.sans_dir:
            f_sans = extract_features_from_dirs(args.sans_dir)
            report_lines.extend(format_category_feature_report("Sans-serif", f_sans))
            report_lines.append("")
        if args.mono_dir:
            f_mono = extract_features_from_dirs(args.mono_dir)
            report_lines.extend(format_category_feature_report("Monospace", f_mono))
            report_lines.append("")
        if args.serif_dir:
            f_serif = extract_features_from_dirs(args.serif_dir)
            report_lines.extend(format_category_feature_report("Serif", f_serif))
            report_lines.append("")
        if args.bengali_dir:
            f_beng = extract_features_from_dirs(args.bengali_dir)
            report_lines.extend(format_category_feature_report("Bengali", f_beng))
            report_lines.append("")

        report_txt = "\n".join(report_lines).rstrip() + "\n"
        if args.out:
            Path(args.out).write_text(report_txt, encoding="utf-8")
        else:
            sys.stdout.write(report_txt)
    elif args.cmd == "compile-bundle":
        ret = compile_bundle(
            out_dir=args.out_dir,
            sans_dirs=args.sans_dir,
            mono_dirs=args.mono_dir,
            serif_dirs=args.serif_dir,
            bengali_dirs=args.bengali_dir,
            keep_hinting=args.keep_hinting,
            fix_metrics=not args.no_fix_metrics,
            metrics_mode=args.metrics_mode,
            sanitize_names=not args.no_sanitize_names,
            enable_centered_colon=args.enable_centered_colon,
            convert_otf=not args.no_convert_otf,
            enable_tabular_digits=args.enable_tabular_digits,
            optimize_tables=args.optimize_tables,
            colon_alignment=args.colon_alignment,
            colon_offset=args.colon_offset,
            colon_rule=args.colon_rule,
            freeze_sans=args.freeze_sans,
            freeze_mono=args.freeze_mono,
            freeze_serif=args.freeze_serif,
            freeze_bengali=args.freeze_bengali,
        )
        sys.exit(ret)
    else:
        p.print_help(); sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF
chmod 644 "$RUNTIME_DEST/helper.py" 2>/dev/null

# Create wrapper shell that sets PYTHONPATH correctly
cat > "$RUNTIME_DEST/bin/mffm-helper" <<'SHEOF'
#!/system/bin/sh
# Wrapper ensures fontTools on PYTHONPATH
HERE=$(dirname "$0")
RUNTIME_ROOT=$(dirname "$HERE")
export PYTHONPATH="$RUNTIME_ROOT/lib/python3.11/site-packages:$RUNTIME_ROOT/lib/python3.11:$RUNTIME_ROOT/lib:$RUNTIME_ROOT:$PYTHONPATH"
export LD_LIBRARY_PATH="$RUNTIME_ROOT/lib:$LD_LIBRARY_PATH"
# Prefer runtime python, fallback to system
if [ -x "$RUNTIME_ROOT/bin/python3" ]; then exec "$RUNTIME_ROOT/bin/python3" "$RUNTIME_ROOT/helper.py" "$@"
elif [ -x "$RUNTIME_ROOT/bin/python" ]; then exec "$RUNTIME_ROOT/bin/python" "$RUNTIME_ROOT/helper.py" "$@"
elif command -v python3 >/dev/null 2>&1; then exec python3 "$RUNTIME_ROOT/helper.py" "$@"
elif command -v python >/dev/null 2>&1; then exec python "$RUNTIME_ROOT/helper.py" "$@"
else echo "mffm-helper: no python found" >&2; exit 1
fi
SHEOF
chmod 755 "$RUNTIME_DEST/bin/mffm-helper" 2>/dev/null

# Also provide direct python shim if runtime provided real binary
if [ -f "$RUNTIME_DEST/bin/python3" ]; then chmod 755 "$RUNTIME_DEST/bin/python3" 2>/dev/null; fi
if [ -f "$RUNTIME_DEST/bin/python" ]; then chmod 755 "$RUNTIME_DEST/bin/python" 2>/dev/null; fi

# Write version/manifest for font modules to check
cat > "$RUNTIME_DEST/version" <<EOF
$RUNTIME_VERSION
EOF
if [ -f "$MANIFEST" ]; then cp -f "$MANIFEST" "$RUNTIME_DEST/manifest.json" 2>/dev/null; fi
printf '%s\n' "$ABI" > "$RUNTIME_DEST/arch" 2>/dev/null
printf 'installed_via=%s\n' "$installed_via" > "$RUNTIME_DEST/install.log" 2>/dev/null
date >> "$RUNTIME_DEST/install.log" 2>/dev/null

# --- Permissions ---
chmod -R 755 "$RUNTIME_DEST" 2>/dev/null

# --- Verify ---
if [ -x "$RUNTIME_DEST/bin/mffm-helper" ]; then
  if "$RUNTIME_DEST/bin/mffm-helper" scan /system/etc 2>&1 | head -n1 | mffm_log_line; then
    status_ok "Runtime helper self-test passed"
  else
    status_warn "Runtime helper installed but scan test had no output (may be normal)"
  fi
  # Also test fontTools import via helper
  if "$RUNTIME_DEST/bin/mffm-helper" 2>&1 | grep -q "usage"; then status_ok "Helper CLI available"; fi
else
  status_warn "Helper not executable"
fi

if [ -x "$RUNTIME_DEST/bin/python3" ] && "$RUNTIME_DEST/bin/python3" -c "import fontTools" 2>/dev/null; then
  status_ok "fontTools import: OK ($RUNTIME_DEST/bin/python3)"
elif python3 -c "import fontTools" 2>/dev/null; then
  status_ok "fontTools import: OK (system python3)"
else
  status_warn "fontTools import failed — TTC bundling will fallback to single-file. Reflash with valid tarballs or install Termux pip."
fi

ui_print ""
ui_print "  Runtime installed: $RUNTIME_DEST"
ui_print "  Helper         : $RUNTIME_DEST/bin/mffm-helper (scan, ttc)"
ui_print "  Version        : $RUNTIME_VERSION ($installed_via)"
ui_print ""
ui_print "  Font modules will auto-detect this runtime at flash time."
ui_print "  No need to reflash runtime unless updating."
ui_print ""

# Clean up heavy archive payloads from module directory to save device storage
rm -rf "$MODPATH/runtime" "$MODPATH"/python-*.tar.* "$MODPATH"/runtime-*.tar.* 2>/dev/null

# Keep MODPATH skeleton for Magisk/KernelSU/APatch module tracking (empty overlay is fine)
mkdir -p "$MODPATH/system" 2>/dev/null
set_perm_recursive "$MODPATH" 0 0 0755 0644 2>/dev/null || chmod -R 755 "$MODPATH" 2>/dev/null
# Restore execution permissions for boot scripts and update binaries
chmod 755 "$MODPATH/service.sh" "$MODPATH/post-mount.sh" "$MODPATH/uninstall.sh" "$MODPATH/customize.sh" 2>/dev/null
[ -f "$MODPATH/META-INF/com/google/android/update-binary" ] && chmod 755 "$MODPATH/META-INF/com/google/android/update-binary" 2>/dev/null
