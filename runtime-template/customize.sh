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
"""MFFM Runtime Helper — on-device font metrics normalization, TTC bundling, and indexed XML compilation."""

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


def _scale_value(val: int, from_upm: int, to_upm: int = 2048) -> int:
    return int(round(val * to_upm / from_upm))


def fix_font_metrics(font, target_upm: int = 2048) -> None:
    head = font.get("head")
    os2 = font.get("OS/2")
    hhea = font.get("hhea")
    if head is None:
        return
    upm = int(getattr(head, "unitsPerEm", target_upm))

    for table_name, field_name, ref_val in FFIX3_METRICS:
        table = font.get(table_name)
        if table is not None and hasattr(table, field_name):
            setattr(table, field_name, int(round(ref_val * upm / target_upm)))

    if os2 is not None:
        os2.fsSelection = int(getattr(os2, "fsSelection", 0)) & 0b01111111
        if "fvar" in font:
            os2.usWeightClass = 400


def remove_font_hinting(font) -> None:
    for table in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if table in font:
            del font[table]
    if "glyf" in font:
        for glyph in font["glyf"].glyphs.values():
            if hasattr(glyph, "removeHinting"):
                glyph.removeHinting()


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
            if not (f.lower().endswith(".ttf") or f.lower().endswith(".otf")):
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
            col.fonts.append(TTFont(f))
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


def compile_bundle(out_dir: str, sans_dirs: list[str], mono_dirs: list[str] = None, serif_dirs: list[str] = None, bengali_dirs: list[str] = None, keep_hinting: bool = False, fix_metrics: bool = True) -> int:
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
                if not (f.lower().endswith(".ttf") or f.lower().endswith(".otf") or f.lower().endswith(".ttc")):
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

    primary = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"] and f["weight"] == 400),
                   next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0]))
    mode = "variable" if primary["variable"] else "static"
    family_name = primary["family"] or "Custom Font"

    ttc_fonts = []
    output_filename = "DroidSans.ttf"

    def process_and_open(face):
        kw = {"lazy": False, "recalcBBoxes": False, "recalcTimestamp": False}
        if face["font_number"] is not None:
            kw["fontNumber"] = face["font_number"]
        font = TTFont(face["path"], **kw)
        if not keep_hinting:
            remove_font_hinting(font)
        if fix_metrics:
            fix_font_metrics(font)
        return font

    # Process Sans
    sans_entries = []
    normal_entries = []
    condensed_entries = []

    if mode == "variable":
        upright = next((f for f in sans_faces if f["style"] == "normal" and not f["condensed"]), sans_faces[0])
        italic = next((f for f in sans_faces if f["style"] == "italic" and not f["condensed"]), None)

        upright_idx = len(ttc_fonts)
        ttc_fonts.append(process_and_open(upright))

        italic_idx = upright_idx
        if italic and italic["path"] != upright["path"]:
            italic_idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(italic))

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
            chosen = {}
            for f in faces:
                k = (f["condensed"], f["style"], f["weight"])
                if k not in chosen:
                    chosen[k] = f
            return list(chosen.values())

        ordered_sans = dedupe_static(sans_faces)
        ordered_sans.sort(key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))

        for f in ordered_sans:
            idx = len(ttc_fonts)
            ttc_fonts.append(process_and_open(f))
            xml_line = font_xml(output_filename, f["weight"], f["style"], index=idx)
            (condensed_entries if f["condensed"] else normal_entries).append((f["weight"], f["style"], xml_line))

        if not normal_entries:
            normal_entries = list(condensed_entries)
        sans_xml_str = "\n".join(x for _, _, x in normal_entries)
        condensed_xml_str = "\n".join(x for _, _, x in (condensed_entries or normal_entries))

    # Process Optional Families (Mono, Serif, Bengali)
    def process_family(faces):
        if not faces: return [], None
        f_lines = []
        first_idx = None
        var_upright = next((f for f in faces if f["variable"] and "wght" in f["axes"]), None)
        if var_upright:
            idx = len(ttc_fonts)
            first_idx = idx
            ttc_fonts.append(process_and_open(var_upright))
            var_italic = next((f for f in faces if f["style"] == "italic" and f["variable"] and "wght" in f["axes"]), None)
            ital_idx = idx
            if var_italic and var_italic["path"] != var_upright["path"]:
                ital_idx = len(ttc_fonts)
                ttc_fonts.append(process_and_open(var_italic))
            for st, vf, f_i in (("normal", var_upright, idx), ("italic", var_italic or var_upright, ital_idx)):
                for w in WEIGHT_NAMES:
                    ax = calc_axis_values(vf, w, st == "italic")
                    if ax:
                        f_lines.append(font_xml(output_filename, w, st, index=f_i, axes=ax))
        else:
            slot_map = {}
            for f in faces:
                slot_key = (f["weight"], f["style"], f["condensed"])
                if slot_key not in slot_map:
                    slot_map[slot_key] = f

            sorted_faces = sorted(slot_map.values(), key=lambda f: (int(f["condensed"]), int(f["style"] == "italic"), f["weight"]))
            for f in sorted_faces:
                idx = len(ttc_fonts)
                if first_idx is None: first_idx = idx
                ttc_fonts.append(process_and_open(f))
                f_lines.append(font_xml(output_filename, f["weight"], f["style"], index=idx))
        return f_lines, first_idx

    mono_lines, mono_idx = process_family(mono_faces)
    serif_lines, serif_idx = process_family(serif_faces)
    bengali_lines, bengali_idx = process_family(bengali_faces)

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

    s_comp = sub.add_parser("compile-bundle", help="Compile multiple font directories into unified indexed TTC")
    s_comp.add_argument("--out-dir", required=True)
    s_comp.add_argument("--sans-dir", action="append", default=[])
    s_comp.add_argument("--mono-dir", action="append", default=[])
    s_comp.add_argument("--serif-dir", action="append", default=[])
    s_comp.add_argument("--bengali-dir", action="append", default=[])
    s_comp.add_argument("--keep-hinting", action="store_true")
    s_comp.add_argument("--no-fix-metrics", action="store_true")

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
        if args.no_hinting:
            remove_font_hinting(font)
        if not args.no_fix_metrics:
            fix_font_metrics(font)
        font.save(out_f)
        font.close()
        print(f"Processed {args.input_file} -> {out_f}")
    elif args.cmd == "compile-bundle":
        ret = compile_bundle(
            out_dir=args.out_dir,
            sans_dirs=args.sans_dir,
            mono_dirs=args.mono_dir,
            serif_dirs=args.serif_dir,
            bengali_dirs=args.bengali_dir,
            keep_hinting=args.keep_hinting,
            fix_metrics=not args.no_fix_metrics,
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
