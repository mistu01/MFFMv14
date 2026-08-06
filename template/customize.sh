#!/system/bin/sh
# MFFMv14 Font Module Installer

if ! command -v ui_print >/dev/null 2>&1; then
  ui_print() { echo "$1"; }
fi
if ! command -v set_perm >/dev/null 2>&1; then
  set_perm() { chown "$2:$3" "$1" 2>/dev/null; chmod "$4" "$1" 2>/dev/null; }
fi
if ! command -v set_perm_recursive >/dev/null 2>&1; then
  set_perm_recursive() {
    chown -R "$2:$3" "$1" 2>/dev/null
    find "$1" -type d -exec chmod "$4" {} \; 2>/dev/null
    find "$1" -type f -exec chmod "$5" {} \; 2>/dev/null
  }
fi

LOG_DIR=${LOG_DIR:-/sdcard/MFFM}
LOG_FILE=${LOG_FILE:-"$LOG_DIR/mffmv14_debug_$(date '+%Y%m%d_%H%M%S' 2>/dev/null || echo current).log"}
mkdir -p "$LOG_DIR" 2>/dev/null

# Clean old log files from previous installations in LOG_DIR before initializing fresh log
if [ -d "$LOG_DIR" ]; then
  for old_log in "$LOG_DIR"/mffmv14_debug_*.log "$LOG_DIR"/*.log; do
    [ -f "$old_log" ] && [ "$old_log" != "$LOG_FILE" ] && rm -f "$old_log" 2>/dev/null
  done
fi

DEBUG=${DEBUG:-1}
if [ "$DEBUG" = "1" ] && [ -d "$LOG_DIR" ] && : >> "$LOG_FILE" 2>/dev/null; then
  exec 2>> "$LOG_FILE"
  PS4='+ [${0##*/}:${LINENO:-?}] '
  set -x
fi

mffm_log_line() {
  [ -n "$LOG_FILE" ] || return 0
  printf '%s\n' "$1" >> "$LOG_FILE" 2>/dev/null
}

mffm_ui_print() {
  local message=$1
  mffm_log_line "$message"
  if [ "${BOOTMODE:-false}" = "true" ]; then
    printf '%s\n' "$message"
  else
    case "$OUTFD" in
      ''|*[!0-9]*) printf '%s\n' "$message" ;;
      *) printf 'ui_print %s\nui_print\n' "$message" >&$OUTFD ;;
    esac
  fi
}

ui_print() { mffm_ui_print "$1"; }

fail() {
  ui_print ""
  ui_print "  [ERROR] $1"
  ui_print "  Installation stopped."
  ui_print ""
  exit 1
}

section() {
  ui_print ""
  ui_print "  [$1] $2"
  ui_print "  ----------------------------------------"
}

status_ok() { ui_print "    [OK] $1"; }
status_skip() { ui_print "    [--] $1"; }
status_warn() { ui_print "    [!!] $1"; }

first_dir() {
  for item in "$@"; do
    [ -n "$item" ] && [ -d "$item" ] && { printf '%s\n' "$item"; return 0; }
  done
  return 1
}

first_file() {
  for item in "$@"; do
    [ -n "$item" ] && [ -f "$item" ] && { printf '%s\n' "$item"; return 0; }
  done
  return 1
}

find_first() {
  local pattern=$1 match dir
  shift
  for dir in "$@"; do
    [ -n "$dir" ] && [ -d "$dir" ] || continue
    match=$(find "$dir" -maxdepth 1 -type f -name "$pattern" 2>/dev/null | head -n 1)
    [ -n "$match" ] && { printf '%s\n' "$match"; return 0; }
  done
  return 1
}

find_best_face() {
  local target_weight=$1 target_style=$2
  shift 2
  local dir file name name_lower is_ital score best_score=0 best_file=""

  for dir in "$@"; do
    [ -n "$dir" ] && [ -d "$dir" ] || continue
    for file in "$dir"/*.ttf "$dir"/*.otf; do
      [ -f "$file" ] || continue
      name=${file##*/}
      name_lower=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')

      case "$name_lower" in
        *ital*|*oblique*|*slanted*) is_ital="italic" ;;
        *) is_ital="normal" ;;
      esac
      [ "$is_ital" = "$target_style" ] || continue

      score=10
      case "$target_weight" in
        100)
          case "$name_lower" in
            *thin*|*100*) score=100 ;;
            *hairline*) score=80 ;;
          esac
          ;;
        200)
          case "$name_lower" in
            *extralight*|*ultralight*|*200*) score=100 ;;
            *light*) score=50 ;;
          esac
          ;;
        300)
          case "$name_lower" in
            *light*|*300*) score=100 ;;
            *extralight*) score=40 ;;
          esac
          ;;
        400)
          case "$name_lower" in
            *regular*|*400*) score=100 ;;
            *rg.ttf|*rg.otf|*-rg*) score=95 ;;
            *book*) score=90 ;;
            *normal*) score=80 ;;
            *medium*|*bold*|*black*|*thin*|*light*) score=10 ;;
            *) score=50 ;;
          esac
          ;;
        500)
          case "$name_lower" in
            *medium*|*500*) score=100 ;;
            *md.ttf|*md.otf|*-md*) score=95 ;;
            *semibold*|*demibold*) score=60 ;;
          esac
          ;;
        600)
          case "$name_lower" in
            *semibold*|*demibold*|*600*) score=100 ;;
            *medium*) score=50 ;;
            *bold*) score=50 ;;
          esac
          ;;
        700)
          case "$name_lower" in
            *bold*|*700*) score=100 ;;
            *bd.ttf|*bd.otf|*-bd*) score=95 ;;
            *heavy*) score=70 ;;
            *semibold*) score=40 ;;
          esac
          ;;
        800)
          case "$name_lower" in
            *extrabold*|*ultrabold*|*800*) score=100 ;;
            *black*|*heavy*) score=70 ;;
            *bold*) score=50 ;;
          esac
          ;;
        900)
          case "$name_lower" in
            *black*|*heavy*|*900*) score=100 ;;
            *extrabold*) score=70 ;;
            *bold*) score=40 ;;
          esac
          ;;
      esac

      if [ $score -gt $best_score ]; then
        best_score=$score
        best_file=$file
      fi
    done
  done

  [ -n "$best_file" ] && [ $best_score -ge 40 ] && printf '%s\n' "$best_file"
}

is_variable_font() {
  local font_file=$1
  [ -f "$font_file" ] || return 1
  head -c 8192 "$font_file" 2>/dev/null | grep -q 'fvar'
}

extract_fvar_axes() {
  local font_file=$1
  [ -f "$font_file" ] || return 1

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$font_file" <<'EOF' 2>/dev/null
import sys, struct
with open(sys.argv[1], 'rb') as f:
    data = f.read()
pos = data.find(b'fvar')
if pos != -1 and len(data) >= pos + 16:
    _, _, t_offset, _ = struct.unpack('>4sIII', data[pos:pos+16])
    if len(data) >= t_offset + 12:
        _, _, a_off, _, count, size = struct.unpack('>HHHHHH', data[t_offset:t_offset+12])
        curr = t_offset + a_off
        res = []
        for _ in range(count):
            if len(data) >= curr + 16:
                tag, min_v, def_v, max_v = struct.unpack('>4siii', data[curr:curr+16])
                t_str = tag.decode('ascii', errors='ignore')
                res.append(f"{t_str}:{int(min_v/65536)}:{int(def_v/65536)}:{int(max_v/65536)}")
                curr += size
        print(" ".join(res))
EOF
    return 0
  elif command -v python >/dev/null 2>&1; then
    python - "$font_file" <<'EOF' 2>/dev/null
import sys, struct
with open(sys.argv[1], 'rb') as f:
    data = f.read()
pos = data.find(b'fvar')
if pos != -1 and len(data) >= pos + 16:
    _, _, t_offset, _ = struct.unpack('>4sIII', data[pos:pos+16])
    if len(data) >= t_offset + 12:
        _, _, a_off, _, count, size = struct.unpack('>HHHHHH', data[t_offset:t_offset+12])
        curr = t_offset + a_off
        res = []
        for _ in range(count):
            if len(data) >= curr + 16:
                tag, min_v, def_v, max_v = struct.unpack('>4siii', data[curr:curr+16])
                t_str = tag.decode('ascii', errors='ignore')
                res.append(f"{t_str}:{int(min_v/65536)}:{int(def_v/65536)}:{int(max_v/65536)}")
                curr += size
        print(" ".join(res))
EOF
    return 0
  fi

  printf '%s\n' "wght:300:400:700"
}

generate_vf_xml_fragment() {
  local font_file=$1 font_sys_name=$2 axes_str=$3
  local wght_min=300 wght_def=400 wght_max=700
  local has_wght=0 item tag min_v def_v max_v

  for item in $axes_str; do
    tag=$(printf '%s' "$item" | cut -d: -f1)
    min_v=$(printf '%s' "$item" | cut -d: -f2)
    def_v=$(printf '%s' "$item" | cut -d: -f3)
    max_v=$(printf '%s' "$item" | cut -d: -f4)
    if [ "$tag" = "wght" ]; then
      [ -n "$min_v" ] && wght_min=$min_v
      [ -n "$def_v" ] && wght_def=$def_v
      [ -n "$max_v" ] && wght_max=$max_v
      has_wght=1
    fi
  done

  local w w_clamp
  for w in 100 200 300 400 500 600 700 800 900; do
    w_clamp=$w
    [ $w_clamp -lt $wght_min ] && w_clamp=$wght_min
    [ $w_clamp -gt $wght_max ] && w_clamp=$wght_max
    if [ "$has_wght" = "1" ]; then
      printf '    <font weight="%d" style="normal" axis="wght=%d">%s</font>\n' "$w" "$w_clamp" "$font_sys_name"
    else
      printf '    <font weight="%d" style="normal">%s</font>\n' "$w" "$font_sys_name"
    fi
  done
}

has_custom_script_for() {
  local font_file=$1 dir
  dir=$(dirname "$font_file")
  if [ -n "$dir" ] && [ -d "$dir" ]; then
    find "$dir" -maxdepth 1 -type f -name '*.sh' 2>/dev/null | grep -q '.' && return 0
  fi
  find "$MFFM_DIR" -maxdepth 2 -type f -name '*.sh' 2>/dev/null | grep -q '.' && return 0
  return 1
}

run_custom_scripts() {
  local custom_script custom_list custom_output custom_status custom_trace line
  custom_list="$MFFM_DIR/.mffmv14-custom-scripts.$$"
  custom_output="$MFFM_DIR/.mffmv14-custom-output.$$"

  find "$MFFM_DIR" -maxdepth 2 -type f -name '*.sh' 2>/dev/null | sort > "$custom_list"
  if [ ! -s "$custom_list" ]; then
    rm -f "$custom_list"
    status_skip "No custom local scripts"
    return 0
  fi

  export MODPATH FONT_DIR SYS_FONT SYS_ETC SYS_XML SYS_FALLBACK
  export PRODUCT_FONT PRODUCT_ETC PRODUCT_XML MFFM_DIR
  export FONT_MODE FONT_FAMILY FONT_FILES FONT_PRIMARY CLOCK_FONT
  export LOG_DIR LOG_FILE
  MFFM="$MFFM_DIR"
  FONTDIR="$FONT_DIR"
  SYSFONT="$SYS_FONT"
  SYSETC="$SYS_ETC"
  SYSXML="$SYS_XML"
  SYSFALLBACK="$SYS_FALLBACK"
  PRODUCTFONT="$PRODUCT_FONT"
  PRODUCTETC="$PRODUCT_ETC"
  PRODUCTXML="$PRODUCT_XML"
  export MFFM FONTDIR SYSFONT SYSETC SYSXML SYSFALLBACK
  export PRODUCTFONT PRODUCTETC PRODUCTXML

  while IFS= read -r custom_script || [ -n "$custom_script" ]; do
    [ -f "$custom_script" ] || continue
    status_ok "Script: ${custom_script##*/}"

    case $- in
      *x*) custom_trace=1; set +x ;;
      *) custom_trace=0 ;;
    esac
    (
      cd "$MFFM_DIR" || exit 1
      . "$custom_script"
    ) > "$custom_output" 2>&1
    custom_status=$?
    [ "$custom_trace" = "1" ] && set -x

    if [ -s "$custom_output" ]; then
      while IFS= read -r line || [ -n "$line" ]; do
        ui_print "    $line"
      done < "$custom_output"
    fi
    rm -f "$custom_output"

    [ "$custom_status" -eq 0 ] || {
      rm -f "$custom_list"
      fail "Custom local script failed (${custom_script##*/}, exit $custom_status)"
    }
    status_ok "Completed: ${custom_script##*/}"
  done < "$custom_list"
  rm -f "$custom_list"
}

copy_if_exists() {
  [ -f "$1" ] || return 1
  cp -f "$1" "$2"
}

ROOT_IMPL=Unknown
if [ "$KSU" = "true" ] || [ -n "$KSU_VER_CODE" ]; then
  ROOT_IMPL=KernelSU
elif [ "$APATCH" = "true" ] || [ -n "$APATCH_VER_CODE" ]; then
  ROOT_IMPL=APatch
elif command -v magisk >/dev/null 2>&1; then
  ROOT_IMPL=Magisk
fi

MIRROR=
if command -v magisk >/dev/null 2>&1; then
  MAGISK_PATH=$(magisk --path 2>/dev/null)
  [ -n "$MAGISK_PATH" ] && [ -d "$MAGISK_PATH/.magisk/mirror" ] && MIRROR="$MAGISK_PATH/.magisk/mirror"
fi
[ -n "$MIRROR" ] || MIRROR=$(first_dir /sbin/.magisk/mirror /debug_ramdisk/.magisk/mirror 2>/dev/null)

refresh_mount_view() {
  local dev mnt fs opt dump fsck file
  ui_print "- Refreshing live system mount view for XML discovery."
  for file in \
    /system/etc/fonts.xml \
    /system/etc/font_fallback.xml \
    /system/product/etc/fonts_customization.xml \
    /product/etc/fonts_customization.xml \
    /system_ext/etc/fonts.xml \
    /system_ext/etc/font_fallback.xml
  do
    if grep -q " $file " /proc/mounts 2>/dev/null; then
      ui_print "  Unmounting overlay at $file"
      umount "$file" 2>/dev/null || umount -l "$file" 2>/dev/null || :
    fi
  done

  while read -r dev mnt fs opt dump fsck; do
    [ -z "$mnt" ] && continue
    case "$mnt" in
      /system|/system/*|/product|/product/*|/system_ext|/system_ext/*)
        case "$dev $mnt $fs $opt" in
          *overlay*|*magisk*|*ksu*|*apatch*)
            ui_print "  Unmounting overlay directory at $mnt"
            umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || :
            ;;
        esac
        ;;
    esac
  done < /proc/mounts
}

find_original_xmls() {
  ORIGINAL_SYSTEM=$(first_dir "$MIRROR/system" /system /system_root/system 2>/dev/null)
  ORIGINAL_PRODUCT=$(first_dir "$MIRROR/product" "$MIRROR/system/product" /product /system/product /system_root/system/product 2>/dev/null)
  ORIGINAL_FONTS_XML=$(first_file "$ORIGINAL_SYSTEM/etc/fonts.xml" /system/etc/fonts.xml /system_root/system/etc/fonts.xml 2>/dev/null)
  ORIGINAL_FALLBACK_XML=$(first_file "$ORIGINAL_SYSTEM/etc/font_fallback.xml" /system/etc/font_fallback.xml /system_root/system/etc/font_fallback.xml 2>/dev/null)
  ORIGINAL_PRODUCT_XML=$(first_file "$ORIGINAL_PRODUCT/etc/fonts_customization.xml" /product/etc/fonts_customization.xml /system/product/etc/fonts_customization.xml 2>/dev/null)
}

[ -z "$MIRROR" ] && refresh_mount_view
find_original_xmls
if [ -z "$ORIGINAL_FONTS_XML" ]; then
  refresh_mount_view
  find_original_xmls
fi

FONT_DIR="$MODPATH/Files"
SYS_FONT="$MODPATH/system/fonts"
SYS_ETC="$MODPATH/system/etc"
SYS_XML="$SYS_ETC/fonts.xml"
SYS_FALLBACK="$SYS_ETC/font_fallback.xml"
PRODUCT_FONT="$MODPATH/system/product/fonts"
PRODUCT_ETC="$MODPATH/system/product/etc"
PRODUCT_XML="$PRODUCT_ETC/fonts_customization.xml"
MFFM_DIR=/sdcard/MFFM

[ -f "$MODPATH/font-config.sh" ] || fail "font-config.sh is missing"
. "$MODPATH/font-config.sh"
[ "$FONT_MODE" = "static" ] || [ "$FONT_MODE" = "variable" ] || fail "Unknown FONT_MODE: $FONT_MODE"
[ -n "$FONT_FILES" ] || fail "FONT_FILES is empty"

mkdir -p "$SYS_FONT" "$SYS_ETC" "$PRODUCT_FONT" "$PRODUCT_ETC" || fail "Could not create module overlay directories"
if [ "$MOUNTIFY" != "true" ] && [ ! -d "/data/adb/modules/mountify" ]; then
  mkdir -p "$MODPATH/product/fonts" "$MODPATH/product/etc" || fail "Could not create root product overlay directories"
fi
mkdir -p "$MFFM_DIR" || fail "Could not create $MFFM_DIR for variable-font settings"
for mffm_sub in Sans Serif Monospace Bengali; do
  mkdir -p "$MFFM_DIR/$mffm_sub" 2>/dev/null
done
[ -f "$ORIGINAL_FONTS_XML" ] || fail "Could not locate the live system fonts.xml"
cp -f "$ORIGINAL_FONTS_XML" "$SYS_XML" || fail "Could not copy system fonts.xml"
[ -f "$ORIGINAL_FALLBACK_XML" ] && cp -f "$ORIGINAL_FALLBACK_XML" "$SYS_FALLBACK"

replace_family() {
  xml=$1
  family=$2
  fragment_file=$3
  mode=${4:-"replace"}
  [ -f "$xml" ] || return 0
  [ -f "$fragment_file" ] || return 0
  grep -q "<family[^>]*name=\"$family\"" "$xml" 2>/dev/null || return 0
  fragment=$(cat "$fragment_file")
  awk -v target="$family" -v replacement="$fragment" -v mode="$mode" '
    !inside && index($0, "<family") > 0 && index($0, "name=\"" target "\"") > 0 {
      if (target == "sans-serif" || mode == "split") {
        print
        print replacement
        print "  </family>"
        print "  <family>"
      } else {
        print
        print replacement
      }
      inside=1
      next
    }
    inside {
      if (target == "sans-serif" || mode == "split" || mode == "prepend") {
        print
        if (index($0, "</family>") > 0) { inside=0 }
      } else {
        if (index($0, "</family>") > 0) { print; inside=0 }
      }
      next
    }
    { print }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"
}

replace_lang_family() {
  xml=$1
  lang=$2
  fragment_file=$3
  [ -f "$xml" ] || return 0
  [ -f "$fragment_file" ] || return 0
  grep -q "lang=\"$lang\"" "$xml" 2>/dev/null || return 0
  fragment=$(cat "$fragment_file")
  awk -v target="$lang" -v replacement="$fragment" '
    !inside && index($0, "<family") > 0 && index($0, "lang=\"" target "\"") > 0 {
      print $0
      print replacement
      inside=1
      next
    }
    inside {
      if (index($0, "</family>") > 0) {
        print $0
        inside=0
      }
      next
    }
    { print }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"
}

PRODUCT_RUBIK_REGULAR="Rubik-Regular.ttf"
PRODUCT_RUBIK_ITALIC="Rubik-Italic.ttf"

is_google_sans_product_name() {
  case "$1" in
    sans-serif|google-sans|google-sans-*|variable-*) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_product_rubik_sources() {
  PRODUCT_HAS_DEDICATED_ITALIC=0
  PRODUCT_RUBIK_REGULAR_SRC=$FONT_PRIMARY
  PRODUCT_RUBIK_ITALIC_SRC=

  set -- $FONT_FILES
  if [ -n "$1" ]; then
    PRODUCT_RUBIK_REGULAR_SRC=$1
  fi
  [ -n "$PRODUCT_RUBIK_REGULAR_SRC" ] || fail "No primary font available for product Rubik spoof"

  if [ "$FONT_MODE" = "variable" ] && [ -n "$2" ] && [ "$2" != "$1" ]; then
    PRODUCT_RUBIK_ITALIC_SRC=$2
    PRODUCT_HAS_DEDICATED_ITALIC=1
  fi
}

install_product_font_payload() {
  local dest=$1
  [ -n "$dest" ] || return 1
  mkdir -p "$dest" || fail "Could not create $dest"
  resolve_product_rubik_sources "$FONT_DIR/sans.xml"

  if [ -f "$FONT_DIR/DroidSans.ttf" ]; then
    cp -f "$FONT_DIR/DroidSans.ttf" "$dest/$PRODUCT_RUBIK_REGULAR" || fail "Could not install $PRODUCT_RUBIK_REGULAR into $dest"
    cp -f "$FONT_DIR/DroidSans.ttf" "$dest/$PRODUCT_RUBIK_ITALIC" || fail "Could not install $PRODUCT_RUBIK_ITALIC into $dest"
  else
    for font_file in $FONT_FILES; do
      [ -f "$FONT_DIR/$font_file" ] || fail "Product font payload missing: $font_file"
      cp -f "$FONT_DIR/$font_file" "$dest/$font_file" || fail "Could not install $font_file into $dest"
    done
  fi
}

patch_product_fonts_customization() {
  local xml=${1:-"$PRODUCT_XML"}
  local sans_fragment="$FONT_DIR/sans.xml"

  [ -f "$ORIGINAL_PRODUCT_XML" ] || return 0
  [ -f "$sans_fragment" ] || fail "Generated sans.xml is missing"

  if ! grep -qE '<(family-list|familyset|family)[^A-Za-z0-9_-][^>]*name="(sans-serif|google-sans|google-sans-[^"]*|variable-[^"]*)"' \
    "$ORIGINAL_PRODUCT_XML" 2>/dev/null; then
    PRODUCT_GS_PATCHED=0
    return 0
  fi

  resolve_product_rubik_sources "$sans_fragment"
  cp -f "$ORIGINAL_PRODUCT_XML" "$xml" || fail "Could not copy product fonts_customization.xml"

  awk -v sans_file="$sans_fragment" \
      -v rubik_regular="$PRODUCT_RUBIK_REGULAR" \
      -v rubik_italic="$PRODUCT_RUBIK_ITALIC" \
      -v has_dedicated_italic="$PRODUCT_HAS_DEDICATED_ITALIC" '
    function abs(v) { return v < 0 ? -v : v }
    function is_open_tag(line, open_tag) {
      return match(line, "<" open_tag "[^A-Za-z0-9_-]")
    }
    function open_count(line, open_tag,   n, rest) {
      n = 0; rest = line
      while (match(rest, "<" open_tag "[^A-Za-z0-9_-]")) {
        n++
        rest = substr(rest, RSTART + RLENGTH)
      }
      return n
    }
    function close_count(line, open_tag,   n, rest) {
      n = 0; rest = line
      while (match(rest, "</" open_tag ">")) {
        n++
        rest = substr(rest, RSTART + RLENGTH)
      }
      return n
    }
    function extract_name(line) {
      if (match(line, /name="[^"]+"/)) {
        return substr(line, RSTART + 6, RLENGTH - 7)
      }
      return ""
    }
    function is_gs_name(name) {
      return name == "sans-serif" || name ~ /^google-sans($|-)/ || name ~ /^variable-/
    }
    function attr_value(text, key,   pat) {
      pat = key "=\"[^\"]+\""
      if (match(text, pat)) {
        return substr(text, RSTART + length(key) + 2, RLENGTH - length(key) - 3)
      }
      return ""
    }
    function store_face(weight, style, index_attr, axes,   key) {
      if (weight == "") weight = "400"
      if (style == "") style = "normal"
      key = weight SUBSEP style
      face_weight[key] = weight + 0
      face_index[key] = index_attr
      face_axes[key] = axes
      if (style == "italic") {
        italic_weights[++italic_count] = weight + 0
        italic_key[weight + 0] = key
      } else {
        normal_weights[++normal_count] = weight + 0
        normal_key[weight + 0] = key
      }
    }
    function load_sans(path,   line, in_font, style, weight, index_attr, axes, file) {
      in_font = 0
      while ((getline line < path) > 0) {
        if (!in_font && line ~ /<font[[:space:]]/) {
          in_font = 1
          style = attr_value(line, "style")
          weight = attr_value(line, "weight")
          index_attr = attr_value(line, "index")
          axes = ""
          file = ""
          if (match(line, /[A-Za-z0-9._-]+\.(ttf|otf|ttc|otc)/)) {
            file = substr(line, RSTART, RLENGTH)
          }
          if (line ~ /<\/font>/) {
            store_face(weight, style, index_attr, axes)
            in_font = 0
          }
          continue
        }
        if (in_font) {
          if (match(line, /<axis[^>]*\/?>/)) {
            if (axes != "") axes = axes "\n"
            axes = axes line
          }
          if (file == "" && match(line, /[A-Za-z0-9._-]+\.(ttf|otf|ttc|otc)/)) {
            file = substr(line, RSTART, RLENGTH)
          }
          if (line ~ /<\/font>/) {
            store_face(weight, style, index_attr, axes)
            in_font = 0
          }
        }
      }
      close(path)
    }
    function closest_key(want_weight, want_style,   i, best, best_diff, w, use_italic) {
      use_italic = (want_style == "italic" && italic_count > 0)
      if (use_italic) {
        best = italic_key[italic_weights[1]]
        best_diff = abs(italic_weights[1] - want_weight)
        for (i = 2; i <= italic_count; i++) {
          w = italic_weights[i]
          if (abs(w - want_weight) < best_diff) {
            best = italic_key[w]
            best_diff = abs(w - want_weight)
          }
        }
        return best
      }
      if (normal_count == 0) return ""
      best = normal_key[normal_weights[1]]
      best_diff = abs(normal_weights[1] - want_weight)
      for (i = 2; i <= normal_count; i++) {
        w = normal_weights[i]
        if (abs(w - want_weight) < best_diff) {
          best = normal_key[w]
          best_diff = abs(w - want_weight)
        }
      }
      return best
    }
    function choose_file(want_style) {
      if (want_style == "italic" && has_dedicated_italic == "1" && italic_count > 0) {
        return rubik_italic
      }
      return rubik_regular
    }
    function emit_font(indent, stock_weight, stock_style,   key, out, idx, n, i, axes_line) {
      if (stock_weight == "") stock_weight = "400"
      if (stock_style == "") stock_style = "normal"
      key = closest_key(stock_weight + 0, stock_style)
      if (key == "") {
        print indent "<font weight=\"" stock_weight "\" style=\"" stock_style "\">" rubik_regular "</font>"
        return
      }
      out = indent "<font weight=\"" stock_weight "\" style=\"" stock_style "\""
      idx = face_index[key]
      if (idx != "") out = out " index=\"" idx "\""
      out = out ">" choose_file(stock_style)
      if (face_axes[key] != "") {
        print out
        n = split(face_axes[key], axis_lines, "\n")
        for (i = 1; i <= n; i++) {
          axes_line = axis_lines[i]
          sub(/^[[:space:]]+/, "", axes_line)
          if (axes_line != "") print indent "  " axes_line
        }
        print indent "</font>"
      } else {
        print out "</font>"
      }
    }
    function flush_font(   weight, style) {
      if (!in_font_block) return
      weight = attr_value(font_open, "weight")
      style = attr_value(font_open, "style")
      if (weight == "") weight = "400"
      if (style == "") style = "normal"
      if (font_indent == "") font_indent = "    "
      emit_font(font_indent, weight, style)
      in_font_block = 0
      font_open = ""
    }
    function maybe_enter_gs(line,   nm) {
      if (gs_active) return
      if (is_open_tag(line, "family-list")) {
        nm = extract_name(line)
        if (nm != "" && is_gs_name(nm)) {
          gs_active = 1; gs_tag = "family-list"
          gs_depth = open_count(line, gs_tag) - close_count(line, gs_tag)
          if (gs_depth <= 0) gs_active = 0
          return
        }
      }
      if (is_open_tag(line, "familyset")) {
        nm = extract_name(line)
        if (nm != "" && is_gs_name(nm)) {
          gs_active = 1; gs_tag = "familyset"
          gs_depth = open_count(line, gs_tag) - close_count(line, gs_tag)
          if (gs_depth <= 0) gs_active = 0
          return
        }
      }
      if (is_open_tag(line, "family")) {
        nm = extract_name(line)
        if (nm != "" && is_gs_name(nm)) {
          gs_active = 1; gs_tag = "family"
          gs_depth = open_count(line, gs_tag) - close_count(line, gs_tag)
          if (gs_depth <= 0) gs_active = 0
        }
      }
    }
    BEGIN {
      normal_count = 0
      italic_count = 0
      gs_active = 0
      gs_depth = 0
      in_font_block = 0
      entered_this_line = 0
      load_sans(sans_file)
    }
    {
      line = $0
      entered_this_line = 0

      if (!gs_active && !in_font_block) {
        maybe_enter_gs(line)
        if (gs_active) entered_this_line = 1
      }

      if (gs_active && !in_font_block && line ~ /<font([[:space:]>])/) {
        in_font_block = 1
        font_open = line
        if (match(line, /^[[:space:]]*/)) font_indent = substr(line, RSTART, RLENGTH)
        else font_indent = "    "
        if (line ~ /<\/font>/) flush_font()
      } else if (in_font_block) {
        if (line ~ /<\/font>/) flush_font()
      } else {
        print line
      }

      if (gs_active && !in_font_block && !entered_this_line) {
        gs_depth += open_count(line, gs_tag) - close_count(line, gs_tag)
        if (gs_depth <= 0) {
          gs_active = 0
          gs_tag = ""
          gs_depth = 0
        }
      }
    }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"

  PRODUCT_GS_PATCHED=$(grep -cE '<(family-list|familyset|family)[^A-Za-z0-9_-][^>]*name="(sans-serif|google-sans|google-sans-[^"]*|variable-[^"]*)"' "$xml" 2>/dev/null || echo 0)
  if ! grep -q "$PRODUCT_RUBIK_REGULAR" "$xml" 2>/dev/null; then
    PRODUCT_GS_PATCHED=0
  fi
  return 0
}

config_value() {
  local key=$1
  sed -n "s/^[[:space:]]*$key[[:space:]]*=[[:space:]]*//p" "$VF_CONFIG_FILE" 2>/dev/null |
    tail -n 1 |
    sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//'
}

weight_label() {
  case "$1" in
    100) printf 'THIN' ;;
    200) printf 'EXTRALIGHT' ;;
    300) printf 'LIGHT' ;;
    400) printf 'REGULAR' ;;
    500) printf 'MEDIUM' ;;
    600) printf 'SEMIBOLD' ;;
    700) printf 'BOLD' ;;
    800) printf 'EXTRABOLD' ;;
    900) printf 'BLACK' ;;
    *) printf 'WEIGHT_%s' "$1" ;;
  esac
}

profile_title() {
  case "$1" in
    SANS_UPRIGHT) printf 'SANS-SERIF / UPRIGHT' ;;
    SANS_ITALIC) printf 'SANS-SERIF / ITALIC' ;;
    CONDENSED_UPRIGHT) printf 'CONDENSED / UPRIGHT' ;;
    CONDENSED_ITALIC) printf 'CONDENSED / ITALIC' ;;
    BENGALI_UPRIGHT) printf 'BENGALI / UPRIGHT' ;;
    MONOSPACE_UPRIGHT) printf 'MONOSPACE / UPRIGHT' ;;
    SERIF_UPRIGHT) printf 'SERIF / UPRIGHT' ;;
    SERIF_ITALIC) printf 'SERIF / ITALIC' ;;
    *) printf '%s' "$1" ;;
  esac
}

ensure_profile_keys() {
  local profile=$1 axis_meta=$2 weights=$3
  local title=$(profile_title "$profile")
  local axis_record axis_tag remainder axis_min axis_default axis_max
  local config_key axis_key weight label wght_min wght_max

  if [ "$VF_CONFIG_CREATED" = "1" ]; then
    {
      printf '\n# ------------------------------------------------------------------------------\n'
      printf '# %s\n' "$title"
      printf '# ------------------------------------------------------------------------------\n'
    } >> "$VF_CONFIG_FILE"
  fi

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    [ "$axis_tag" = "wght" ] && { wght_min=$axis_min; wght_max=$axis_max; }
  done

  for weight in $weights; do
    label=$(weight_label "$weight")
    config_key="${profile}_${label}_WGHT"
    if ! grep -q "^[[:space:]]*$config_key[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
      {
        printf '# Android %s (%s): variable wght range %s..%s\n' "$weight" "$label" "$wght_min" "$wght_max"
        printf '%s=%s\n' "$config_key" "$weight"
      } >> "$VF_CONFIG_FILE"
    fi
  done

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    [ "$axis_tag" = "wght" ] && continue
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    axis_key=$(printf '%s' "$axis_tag" | tr '[:lower:]' '[:upper:]')
    config_key="${profile}_${axis_key}"
    if ! grep -q "^[[:space:]]*$config_key[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
      {
        printf '# %s axis range %s..%s; compiled value %s\n' "$axis_tag" "$axis_min" "$axis_max" "$axis_default"
        printf '%s=%s\n' "$config_key" "$axis_default"
      } >> "$VF_CONFIG_FILE"
    fi
  done
}

reset_config_value() {
  local config_key=$1 reset_value=$2
  awk -v wanted_key="$config_key" -v wanted_value="$reset_value" '
    $0 ~ "^[[:space:]]*" wanted_key "[[:space:]]*=" {
      print wanted_key "=" wanted_value
      replaced=1
      next
    }
    { print }
    END {
      if (!replaced) print wanted_key "=" wanted_value
    }
  ' "$VF_CONFIG_FILE" > "$VF_CONFIG_FILE.tmp" && mv -f "$VF_CONFIG_FILE.tmp" "$VF_CONFIG_FILE"
}

validate_axis_value() {
  local config_key=$1 axis_value=$2 axis_min=$3 axis_max=$4 reset_value=$5
  case "$axis_value" in
    AUTO|Auto|auto) return 1 ;;
    "")
      status_warn "$config_key was empty; reset to $reset_value"
      reset_config_value "$config_key" "$reset_value"
      return 1
      ;;
  esac
  if ! printf '%s\n' "$axis_value" | grep -Eq '^-?([0-9]+([.][0-9]*)?|[.][0-9]+)$'; then
    status_warn "$config_key='$axis_value' is invalid; reset to $reset_value"
    reset_config_value "$config_key" "$reset_value"
    return 1
  fi
  if ! awk -v value="$axis_value" -v minimum="$axis_min" -v maximum="$axis_max" \
    'BEGIN { exit !(value >= minimum && value <= maximum) }'; then
    status_warn "$config_key=$axis_value is outside $axis_min..$axis_max; reset to $reset_value"
    reset_config_value "$config_key" "$reset_value"
    return 1
  fi
  return 0
}

apply_axis_value() {
  local style_name=$1 declared_weight=$2 axis_tag=$3 axis_value=$4 fragment_file
  shift 4
  for fragment_file in "$@"; do
    [ -f "$fragment_file" ] || continue
    awk -v wanted_style="$style_name" -v wanted_weight="$declared_weight" \
      -v wanted_tag="$axis_tag" -v wanted_value="$axis_value" '
      /<font[[:space:]]/ {
        active = index($0, "style=\"" wanted_style "\"") > 0
        if (wanted_weight != "") {
          active = active && index($0, "weight=\"" wanted_weight "\"") > 0
        }
      }
      active && index($0, "<axis tag=\"" wanted_tag "\"") > 0 {
        sub(/stylevalue="[^"]*"/, "stylevalue=\"" wanted_value "\"")
      }
      { print }
      /<\/font>/ { active=0 }
    ' "$fragment_file" > "$fragment_file.tmp" && mv -f "$fragment_file.tmp" "$fragment_file"
  done
}

apply_profile() {
  local profile=$1 xml_style=$2 axis_meta=$3 weights=$4
  shift 4
  local fragment_list="$*"
  local axis_record axis_tag remainder axis_min axis_default axis_max axis_key config_key axis_value weight label wght_min wght_max

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    [ "$axis_tag" = "wght" ] && { wght_min=$axis_min; wght_max=$axis_max; }
  done

  for weight in $weights; do
    label=$(weight_label "$weight")
    config_key="${profile}_${label}_WGHT"
    axis_value=$(config_value "$config_key")
    validate_axis_value "$config_key" "$axis_value" "$wght_min" "$wght_max" "$weight" || continue
    apply_axis_value "$xml_style" "$weight" wght "$axis_value" $fragment_list
  done

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    [ "$axis_tag" = "wght" ] && continue
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    axis_key=$(printf '%s' "$axis_tag" | tr '[:lower:]' '[:upper:]')
    config_key="${profile}_${axis_key}"
    axis_value=$(config_value "$config_key")
    validate_axis_value "$config_key" "$axis_value" "$axis_min" "$axis_max" "$axis_default" || continue
    apply_axis_value "$xml_style" "" "$axis_tag" "$axis_value" $fragment_list
  done
}

configure_variable_family_profile() {
  local profile=$1 font_file=$2 xml_style=$3 weights=$4
  shift 4
  local fragment_list="$*"
  [ -f "$font_file" ] || return 0
  [ -n "$VF_CONFIG_FILE" ] && [ -f "$VF_CONFIG_FILE" ] || return 0

  local axes_meta
  axes_meta=$(extract_fvar_axes "$font_file" | tr ' ' '\n' | awk -F: '{print $1 "|" $2 "|" $3 "|" $4}' | tr '\n' ' ')
  [ -n "$axes_meta" ] || axes_meta="wght|300|400|700"

  ensure_profile_keys "$profile" "$axes_meta" "$weights"
  apply_profile "$profile" "$xml_style" "$axes_meta" "$weights" $fragment_list
}

prune_obsolete_profile_keys() {
  local profile=$1
  [ -n "$VF_CONFIG_FILE" ] && [ -f "$VF_CONFIG_FILE" ] || return 0

  awk -v prefix="${profile}_" '
    $0 ~ "^[[:space:]]*#" && index($0, prefix) > 0 { next }
    $0 ~ "^[[:space:]]*" prefix { next }
    { print }
  ' "$VF_CONFIG_FILE" > "$VF_CONFIG_FILE.tmp" && mv -f "$VF_CONFIG_FILE.tmp" "$VF_CONFIG_FILE"
}

prepare_variable_config() {
  safe_family=$(printf '%s' "$FONT_FAMILY" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_*//;s/_*$//')
  [ -n "$safe_family" ] || safe_family=Variable_Font
  [ -n "$VF_CONFIG_ID" ] || fail "Variable module identity is missing"
  [ "$VF_CONFIG_SCHEMA" = "2" ] || fail "Unsupported variable config schema: $VF_CONFIG_SCHEMA"
  if ! printf '%s\n' "$VF_CONFIG_ID" | grep -Eq '^vf-[a-f0-9]{20}$'; then
    fail "Variable module identity is invalid: $VF_CONFIG_ID"
  fi
  VF_CONFIG_FILE="$MFFM_DIR/MFFMv14_${safe_family}_${VF_CONFIG_ID}.conf"
  VF_LEGACY_CONFIG="$MFFM_DIR/MFFMv14_${safe_family}_VF.conf"
  VF_CONFIG_RESET=0

  # Preserve existing configuration when updating the same module family or identity
  if [ -d "$MFFM_DIR" ]; then
    local candidate saved_identity
    if [ ! -f "$VF_CONFIG_FILE" ]; then
      # Search for existing config file from previous installation of the same module
      for candidate in "$MFFM_DIR"/MFFMv14_${safe_family}_*.conf "$VF_LEGACY_CONFIG"; do
        [ -f "$candidate" ] || continue
        saved_identity=$(sed -n 's/^[[:space:]]*MODULE_IDENTITY[[:space:]]*=[[:space:]]*//p' "$candidate" 2>/dev/null |
          tail -n 1 | sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//')
        if [ "$saved_identity" = "$VF_CONFIG_ID" ] || [ -z "$saved_identity" ]; then
          # Found matching config from previous update -> migrate it to VF_CONFIG_FILE
          cp -f "$candidate" "$VF_CONFIG_FILE" 2>/dev/null && rm -f "$candidate" 2>/dev/null
          ui_print "  [OK] Retained existing configuration for $FONT_FAMILY"
          break
        fi
      done
    fi
  fi

  if [ ! -f "$VF_CONFIG_FILE" ]; then
    cat > "$VF_CONFIG_FILE" <<EOF
# ==============================================================================
# MFFMv14 VARIABLE FONT CONFIGURATION
# ==============================================================================
# Font: $FONT_FAMILY
# Module identity: $VF_CONFIG_ID
CONFIG_SCHEMA=$VF_CONFIG_SCHEMA
MODULE_IDENTITY=$VF_CONFIG_ID
EOF
    VF_CONFIG_CREATED=1
  else
    VF_CONFIG_CREATED=0
    if ! grep -q "^[[:space:]]*MODULE_IDENTITY[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
      printf 'MODULE_IDENTITY=%s\n' "$VF_CONFIG_ID" >> "$VF_CONFIG_FILE"
    fi
    ui_print "  [OK] Retained existing configuration for $FONT_FAMILY"
  fi
  [ -f "$VF_CONFIG_FILE" ] || fail "Could not create variable-axis configuration: $VF_CONFIG_FILE"
  ensure_profile_keys SANS_UPRIGHT "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS"
  ensure_profile_keys SANS_ITALIC "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS"
  ensure_profile_keys CONDENSED_UPRIGHT "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS"
  ensure_profile_keys CONDENSED_ITALIC "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS"

  apply_profile SANS_UPRIGHT normal "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS" \
    "$FONT_DIR/sans.xml" "$FONT_DIR/serif.xml"
  apply_profile SANS_ITALIC italic "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS" \
    "$FONT_DIR/sans.xml" "$FONT_DIR/serif.xml"
  apply_profile CONDENSED_UPRIGHT normal "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS" \
    "$FONT_DIR/condensed.xml"
  apply_profile CONDENSED_ITALIC italic "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS" \
    "$FONT_DIR/condensed.xml"
}

ui_print ""
ui_print ""
ui_print "  +----------------------------------------+"
ui_print "  |          MFFMv14 FONT MODULE           |"
ui_print "  |          MFFM / Mistu - 2026           |"
ui_print "  +----------------------------------------+"
ui_print ""
ui_print "    Root manager : $ROOT_IMPL"
ui_print "    Font model   : $FONT_MODE"
ui_print "    Font family  : $FONT_FAMILY"

if [ "$FONT_MODE" = "variable" ]; then
  prepare_variable_config
  ui_print "    Axis config  : $VF_CONFIG_FILE"
  if [ "$VF_CONFIG_CREATED" = "1" ]; then
    if [ "$VF_CONFIG_RESET" = "1" ]; then
      status_warn "Replaced a legacy or mismatched axis configuration"
    fi
    status_ok "Created identity-bound variable-axis configuration"
  else
    status_ok "Loaded matching identity-bound axis configuration"
  fi
fi

section "1/5" "Installing primary font payload"

for font_file in $FONT_FILES; do
  [ -f "$FONT_DIR/$font_file" ] || fail "Payload font is missing: $font_file"
  cp -f "$FONT_DIR/$font_file" "$SYS_FONT/$font_file" || fail "Could not install $font_file"
  status_ok "$font_file"
done

section "2/5" "Patching Android font families"

if [ -f "$FONT_DIR/sans.xml" ]; then
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    replace_family "$xml" sans-serif "$FONT_DIR/sans.xml"
    replace_family "$xml" sans-serif-condensed "$FONT_DIR/condensed.xml"
    replace_family "$xml" roboto-flex "$FONT_DIR/sans.xml"
  done
  status_ok "Native Sans-serif font (bundled in DroidSans.ttf)"
else
  ext_sans=$(find_first '*.ttf' "$MFFM_DIR/Sans")
  [ -z "$ext_sans" ] && ext_sans=$(find_first '*.otf' "$MFFM_DIR/Sans")
  [ -z "$ext_sans" ] && ext_sans=$(find_first 'Sans*.ttf' "$MFFM_DIR")
  [ -z "$ext_sans" ] && ext_sans=$(find_first 'Roboto-Regular.ttf' "$MFFM_DIR")
  if [ -n "$ext_sans" ]; then
    cp -f "$ext_sans" "$SYS_FONT/Roboto-Regular.ttf"
    cp -f "$ext_sans" "$SYS_FONT/Roboto-Bold.ttf"
    if is_variable_font "$ext_sans"; then
      axes_info=$(extract_fvar_axes "$ext_sans")
      frag_file="$FONT_DIR/ext_sans.xml"
      generate_vf_xml_fragment "$ext_sans" "Roboto-Regular.ttf" "$axes_info" > "$frag_file"
      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        replace_family "$xml" sans-serif "$frag_file"
        replace_family "$xml" roboto-flex "$frag_file"
      done
      status_ok "External Variable Sans-serif font (${ext_sans##*/}) auto-configured natively"
    else
      status_ok "External Sans-serif font (copied from MFFM folder)"
    fi
  else
    status_skip "Sans-serif font not supplied"
  fi
fi

if [ -f "$ORIGINAL_PRODUCT_XML" ] && [ -f "$FONT_DIR/sans.xml" ]; then
  install_product_font_payload "$PRODUCT_FONT"
  patch_product_fonts_customization "$PRODUCT_XML"
  if [ "$MOUNTIFY" != "true" ] && [ ! -d "/data/adb/modules/mountify" ]; then
    install_product_font_payload "$MODPATH/product/fonts"
    patch_product_fonts_customization "$MODPATH/product/etc/fonts_customization.xml"
  fi
  if [ "${PRODUCT_GS_PATCHED:-0}" -gt 0 ]; then
    status_ok "Product Google Sans families pattern-patched ($PRODUCT_GS_PATCHED)"
  else
    status_skip "Product fonts_customization.xml has no Google Sans families to patch"
  fi
else
  status_skip "Product fonts_customization.xml (not present on this ROM)"
fi

section "3/5" "Applying optional font resources"

for prefix in Beng Serif; do
  bundled=$(find_first "$prefix*.zip" "$FONT_DIR" "$MFFM_DIR/Bengali" "$MFFM_DIR/Serif" "$MFFM_DIR")
  [ -n "$bundled" ] && unzip -oq "$bundled" -d "$FONT_DIR"
done
if [ -f "$FONT_DIR/mono.xml" ]; then
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    [ -f "$xml" ] || continue
    replace_family "$xml" monospace "$FONT_DIR/mono.xml"
    replace_family "$xml" cutive-mono "$FONT_DIR/mono.xml"
    replace_family "$xml" droidsans-mono "$FONT_DIR/mono.xml"
    if [ ! -f "$FONT_DIR/serif.xml" ]; then
      replace_family "$xml" serif-monospace "$FONT_DIR/mono.xml" "prepend"
    fi
  done
  status_ok "Native Monospace font (bundled in DroidSans.ttf)"
elif [ -f "$FONT_DIR/CutiveMono.ttf" ] && [ -f "$FONT_DIR/DroidSansMono.ttf" ]; then
  cp -f "$FONT_DIR/CutiveMono.ttf" "$SYS_FONT/CutiveMono.ttf"
  cp -f "$FONT_DIR/DroidSansMono.ttf" "$SYS_FONT/DroidSansMono.ttf"
  status_ok "Native Monospace font (module standalone files)"
else
  ext_mono=$(find_first '*.ttf' "$MFFM_DIR/Monospace" "$MFFM_DIR/Mono")
  [ -z "$ext_mono" ] && ext_mono=$(find_first '*.otf' "$MFFM_DIR/Monospace" "$MFFM_DIR/Mono")
  [ -z "$ext_mono" ] && ext_mono=$(find_first 'Mono*.ttf' "$MFFM_DIR")
  [ -z "$ext_mono" ] && ext_mono=$(find_first 'Mono*.otf' "$MFFM_DIR")
  if [ -n "$ext_mono" ]; then
    cp -f "$ext_mono" "$SYS_FONT/CutiveMono.ttf"
    cp -f "$ext_mono" "$SYS_FONT/DroidSansMono.ttf"
    if is_variable_font "$ext_mono"; then
      axes_info=$(extract_fvar_axes "$ext_mono")
      frag_file="$FONT_DIR/ext_mono.xml"
      generate_vf_xml_fragment "$ext_mono" "CutiveMono.ttf" "$axes_info" > "$frag_file"
      configure_variable_family_profile MONOSPACE_UPRIGHT "$ext_mono" normal "400" "$frag_file"
      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        replace_family "$xml" monospace "$frag_file"
        replace_family "$xml" cutive-mono "$frag_file"
        replace_family "$xml" droidsans-mono "$frag_file"
      done
      status_ok "External Variable Monospace font (${ext_mono##*/}) auto-configured natively"
    else
      status_ok "External Monospace font (copied from MFFM folder)"
    fi
  else
    prune_obsolete_profile_keys MONOSPACE_UPRIGHT
    status_skip "Monospace font not supplied"
  fi
fi

if [ -f "$FONT_DIR/bengali.xml" ]; then
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    [ -f "$xml" ] || continue
    replace_lang_family "$xml" "und-Beng" "$FONT_DIR/bengali.xml"
    replace_lang_family "$xml" "bn" "$FONT_DIR/bengali.xml"
  done
  status_ok "Native Bengali font (bundled in DroidSans.ttf with full 100-900 weight class)"
elif [ -f "$FONT_DIR/Beng-Regular.ttf" ] && [ -f "$FONT_DIR/Beng-Medium.ttf" ] && [ -f "$FONT_DIR/Beng-Bold.ttf" ]; then
  cp -f "$FONT_DIR/Beng-Regular.ttf" "$SYS_FONT/NotoSansBengali-VF.ttf"
  cp -f "$FONT_DIR/Beng-Medium.ttf" "$SYS_FONT/NotoSerifBengali-VF.ttf"
  cp -f "$FONT_DIR/Beng-Bold.ttf" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    [ -f "$xml" ] || continue
    sed -i '/<family lang="und-Beng" variant="elegant">/,/<\/family>/c\<family lang="und-Beng" variant="elegant">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
    sed -i '/<family lang="und-Beng" variant="compact">/,/<\/family>/c\<family lang="und-Beng" variant="compact">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
  done
  status_ok "Bengali fonts (standalone module files)"
else
  ext_beng=$(find_first '*.ttf' "$MFFM_DIR/Bengali" "$MFFM_DIR/Beng")
  [ -z "$ext_beng" ] && ext_beng=$(find_first '*.otf' "$MFFM_DIR/Bengali" "$MFFM_DIR/Beng")
  [ -z "$ext_beng" ] && ext_beng=$(find_first 'Beng*.ttf' "$MFFM_DIR")
  [ -z "$ext_beng" ] && ext_beng=$(find_first 'Beng*.otf' "$MFFM_DIR")
  if [ -n "$ext_beng" ]; then
    if is_variable_font "$ext_beng"; then
      cp -f "$ext_beng" "$SYS_FONT/NotoSansBengali-VF.ttf"
      cp -f "$ext_beng" "$SYS_FONT/NotoSerifBengali-VF.ttf"
      cp -f "$ext_beng" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
      axes_info=$(extract_fvar_axes "$ext_beng")
      frag_file="$FONT_DIR/ext_beng.xml"
      generate_vf_xml_fragment "$ext_beng" "NotoSansBengali-VF.ttf" "$axes_info" > "$frag_file"
      configure_variable_family_profile BENGALI_UPRIGHT "$ext_beng" normal "100 200 300 400 500 600 700 800 900" "$frag_file"
      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        replace_lang_family "$xml" "und-Beng" "$frag_file"
        replace_lang_family "$xml" "bn" "$frag_file"
      done
      status_ok "External Variable Bengali font (${ext_beng##*/}) auto-configured natively"
    else
      beng_reg=$(find_best_face 400 normal "$MFFM_DIR/Bengali" "$MFFM_DIR/Beng" "$MFFM_DIR")
      beng_med=$(find_best_face 500 normal "$MFFM_DIR/Bengali" "$MFFM_DIR/Beng" "$MFFM_DIR")
      beng_bold=$(find_best_face 700 normal "$MFFM_DIR/Bengali" "$MFFM_DIR/Beng" "$MFFM_DIR")
      [ -z "$beng_reg" ] && beng_reg="$ext_beng"
      cp -f "$beng_reg" "$SYS_FONT/NotoSansBengali-VF.ttf"
      [ -n "$beng_med" ] && cp -f "$beng_med" "$SYS_FONT/NotoSerifBengali-VF.ttf" || cp -f "$beng_reg" "$SYS_FONT/NotoSerifBengali-VF.ttf"
      [ -n "$beng_bold" ] && cp -f "$beng_bold" "$SYS_FONT/NotoSansBengaliUI-VF.ttf" || cp -f "$beng_reg" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        sed -i '/<family lang="und-Beng" variant="elegant">/,/<\/family>/c\<family lang="und-Beng" variant="elegant">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
        sed -i '/<family lang="und-Beng" variant="compact">/,/<\/family>/c\<family lang="und-Beng" variant="compact">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
      done
      status_ok "External Static Bengali fonts auto-matched (${beng_reg##*/})"
    fi
  else
    prune_obsolete_profile_keys BENGALI_UPRIGHT
    status_skip "Bengali fonts not supplied"
  fi
fi

if [ -f "$FONT_DIR/serif.xml" ]; then
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    [ -f "$xml" ] || continue
    replace_family "$xml" serif "$FONT_DIR/serif.xml" "split"
    replace_family "$xml" noto-serif "$FONT_DIR/serif.xml" "split"
    replace_family "$xml" serif-monospace "$FONT_DIR/serif.xml" "split"
  done
  status_ok "Native Serif font (bundled in DroidSans.ttf)"
elif [ -f "$FONT_DIR/NotoSerif-Regular.ttf" ] && [ -f "$FONT_DIR/NotoSerif-Bold.ttf" ]; then
  cp -f "$FONT_DIR/NotoSerif-Regular.ttf" "$SYS_FONT/NotoSerif-Regular.ttf"
  [ -f "$FONT_DIR/NotoSerif-Italic.ttf" ] && cp -f "$FONT_DIR/NotoSerif-Italic.ttf" "$SYS_FONT/NotoSerif-Italic.ttf"
  cp -f "$FONT_DIR/NotoSerif-Bold.ttf" "$SYS_FONT/NotoSerif-Bold.ttf"
  [ -f "$FONT_DIR/NotoSerif-BoldItalic.ttf" ] && cp -f "$FONT_DIR/NotoSerif-BoldItalic.ttf" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
  status_ok "Native Serif font (module standalone files)"
else
  ext_s_reg=$(find_best_face 400 normal "$MFFM_DIR/Serif" "$MFFM_DIR")
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_first '*.ttf' "$MFFM_DIR/Serif")
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_first '*.otf' "$MFFM_DIR/Serif")
  ext_s_ital=$(find_best_face 400 italic "$MFFM_DIR/Serif" "$MFFM_DIR")
  ext_s_bold=$(find_best_face 700 normal "$MFFM_DIR/Serif" "$MFFM_DIR")
  ext_s_bital=$(find_best_face 700 italic "$MFFM_DIR/Serif" "$MFFM_DIR")

  if [ -n "$ext_s_reg" ]; then
    cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-Regular.ttf"
    [ -n "$ext_s_ital" ] && cp -f "$ext_s_ital" "$SYS_FONT/NotoSerif-Italic.ttf"
    [ -n "$ext_s_bold" ] && cp -f "$ext_s_bold" "$SYS_FONT/NotoSerif-Bold.ttf" || cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-Bold.ttf"
    [ -n "$ext_s_bital" ] && cp -f "$ext_s_bital" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
    if is_variable_font "$ext_s_reg"; then
      axes_info=$(extract_fvar_axes "$ext_s_reg")
      frag_file="$FONT_DIR/ext_serif.xml"
      generate_vf_xml_fragment "$ext_s_reg" "NotoSerif-Regular.ttf" "$axes_info" > "$frag_file"
      configure_variable_family_profile SERIF_UPRIGHT "$ext_s_reg" normal "400 700" "$frag_file"
      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        replace_family "$xml" serif "$frag_file" "split"
        replace_family "$xml" noto-serif "$frag_file" "split"
      done
      status_ok "External Variable Serif font (${ext_s_reg##*/}) auto-configured natively"
    else
      status_ok "External Serif fonts auto-matched (${ext_s_reg##*/})"
    fi
  else
    prune_obsolete_profile_keys SERIF_UPRIGHT
    prune_obsolete_profile_keys SERIF_ITALIC
    status_skip "Dedicated serif fonts not supplied"
  fi
fi

section "4/5" "Finalizing root integration"

if [ "$KSU" = "true" ] || [ "$APATCH" = "true" ]; then
  if command -v setfattr >/dev/null 2>&1; then
    for directory in "$SYS_FONT" "$PRODUCT_FONT" "$SYS_ETC" "$PRODUCT_ETC"; do
      setfattr -n trusted.overlay.opaque -v y "$directory" 2>/dev/null
    done
    if [ "$MOUNTIFY" != "true" ] && [ ! -d "/data/adb/modules/mountify" ]; then
      for directory in "$MODPATH/product/fonts" "$MODPATH/product/etc"; do
        setfattr -n trusted.overlay.opaque -v y "$directory" 2>/dev/null
      done
    fi
    status_ok "OverlayFS opaque attributes"
  else
    status_warn "setfattr unavailable; mounting metamodule may be required"
  fi
else
  status_ok "Magisk module overlay"
fi

section "5/5" "Running custom local scripts"

run_custom_scripts

set_perm_recursive "$MODPATH" 0 0 0755 0644
for script in service.sh uninstall.sh post-mount.sh; do
  [ -f "$MODPATH/$script" ] && set_perm "$MODPATH/$script" 0 0 0755
done
rm -rf "$FONT_DIR"
rm -f "$MODPATH/font-config.sh"
status_ok "Permissions and cleanup"

ui_print ""
ui_print "  +----------------------------------------+"
ui_print "  |       INSTALLATION SUCCESSFUL          |"
ui_print "  +----------------------------------------+"
ui_print ""
ui_print "     __  __  _____  _____  __  __"
ui_print "    |  \/  ||  ___||  ___||  \/  |"
ui_print "    | |\/| || |_   | |_   | |\/| |"
ui_print "    | |  | ||  _|  |  _|  | |  | |"
ui_print "    |_|  |_||_|    |_|    |_|  |_|"
ui_print ""
ui_print "             © 2026 MFFM / Mistu"
ui_print ""
ui_print "    Reboot to apply the font."
ui_print "    Debug log: $LOG_FILE"
ui_print ""
