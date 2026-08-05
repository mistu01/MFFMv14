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
  for old_log in "$LOG_DIR"/mffmv14_debug_*.log; do
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
  directory=$1
  pattern=$2
  [ -d "$directory" ] || return 1
  find "$directory" -maxdepth 1 -type f -name "$pattern" 2>/dev/null | head -n 1
}

run_custom_scripts() {
  local custom_script custom_list custom_output custom_status custom_trace line
  custom_list="$MFFM_DIR/.mffmv14-custom-scripts.$$"
  custom_output="$MFFM_DIR/.mffmv14-custom-output.$$"

  find "$MFFM_DIR" -maxdepth 1 -type f -name '*.sh' 2>/dev/null | sort > "$custom_list"
  if [ ! -s "$custom_list" ]; then
    rm -f "$custom_list"
    status_skip "No custom local scripts"
    return 0
  fi

  # These scripts run as root, and any app holding storage permission can write to $MFFM_DIR,
  # so require an explicit opt-in marker instead of trusting whatever is on external storage.
  if [ ! -f "$CUSTOM_SCRIPTS_MARKER" ]; then
    rm -f "$custom_list"
    status_skip "Custom local scripts found but not enabled"
    ui_print "         Scripts in $MFFM_DIR run as root."
    ui_print "         To allow them, create ${CUSTOM_SCRIPTS_MARKER##*/} in $MFFM_DIR and reflash."
    return 0
  fi

  export MODPATH FONT_DIR SYS_FONT SYS_ETC SYS_XML SYS_FALLBACK
  export PRODUCT_FONT PRODUCT_ETC PRODUCT_XML MFFM_DIR
  export FONT_MODE FONT_FAMILY FONT_FILES FONT_PRIMARY
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

# The Bengali families are keyed by lang/variant rather than name, so replace_family cannot be
# reused. awk keeps this consistent with the other XML edits: toybox sed mishandles `c\` with
# embedded newlines.
replace_beng_family() {
  local xml=$1 variant=$2
  [ -f "$xml" ] || return 0
  grep -q "<family lang=\"und-Beng\" variant=\"$variant\">" "$xml" 2>/dev/null || return 0
  awk -v variant="$variant" '
    !inside && index($0, "<family lang=\"und-Beng\" variant=\"" variant "\">") > 0 {
      print "  <family lang=\"und-Beng\" variant=\"" variant "\">"
      print "    <font weight=\"400\" style=\"normal\">NotoSansBengali-VF.ttf</font>"
      print "    <font weight=\"500\" style=\"normal\">NotoSerifBengali-VF.ttf</font>"
      print "    <font weight=\"700\" style=\"normal\">NotoSansBengaliUI-VF.ttf</font>"
      print "  </family>"
      if (index($0, "</family>") == 0) { inside=1 }
      next
    }
    inside {
      if (index($0, "</family>") > 0) { inside=0 }
      next
    }
    { print }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"
}

# Fonts are installed several times under $MODPATH (system overlay plus one or two product
# overlays). Hard-linking keeps a single copy of the collection on disk instead of one per path.
link_or_copy() {
  ln -f "$1" "$2" 2>/dev/null || cp -f "$1" "$2"
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
  local dev mnt fs opt _rest file
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

  while read -r dev mnt fs opt _rest; do
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
CUSTOM_SCRIPTS_MARKER="$MFFM_DIR/allow-custom-scripts"

[ -f "$MODPATH/font-config.sh" ] || fail "font-config.sh is missing"
. "$MODPATH/font-config.sh"
[ "$FONT_MODE" = "static" ] || [ "$FONT_MODE" = "variable" ] || fail "Unknown FONT_MODE: $FONT_MODE"
[ -n "$FONT_FILES" ] || fail "FONT_FILES is empty"
[ -f "$FONT_DIR/sans.xml" ] || fail "Generated sans.xml is missing"

mkdir -p "$SYS_FONT" "$SYS_ETC" "$PRODUCT_FONT" "$PRODUCT_ETC" || fail "Could not create module overlay directories"
if [ "$MOUNTIFY" != "true" ] && [ ! -d "/data/adb/modules/mountify" ]; then
  mkdir -p "$MODPATH/product/fonts" "$MODPATH/product/etc" || fail "Could not create root product overlay directories"
fi
# /sdcard is not mounted during a recovery flash: only variable modules truly need it.
mkdir -p "$MFFM_DIR" 2>/dev/null
if [ ! -d "$MFFM_DIR" ]; then
  [ "$FONT_MODE" = "variable" ] && fail "Could not create $MFFM_DIR for variable-font settings"
  status_warn "$MFFM_DIR is unavailable; skipping local settings and custom scripts"
fi
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
  # The awk program below assumes the opening tag, the fonts, and </family> are on separate lines.
  # A single-line or self-closing family would make it swallow everything up to the next </family>.
  if grep -qE "<family[^>]*name=\"$family\"[^>]*(/>|>.*</family>)" "$xml" 2>/dev/null; then
    status_warn "Skipping $family in ${xml##*/}: this ROM writes the family on one line"
    return 0
  fi
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

PRODUCT_RUBIK_REGULAR="Rubik-Regular.ttf"
PRODUCT_RUBIK_ITALIC="Rubik-Italic.ttf"

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
  resolve_product_rubik_sources

  if [ -f "$FONT_DIR/DroidSans.ttf" ]; then
    link_or_copy "$FONT_DIR/DroidSans.ttf" "$dest/$PRODUCT_RUBIK_REGULAR" || fail "Could not install $PRODUCT_RUBIK_REGULAR into $dest"
    # Without a dedicated italic source the italic entries reference Rubik-Regular by index,
    # so a second copy of the collection would never be read.
    rm -f "$dest/$PRODUCT_RUBIK_ITALIC"
    if [ "$PRODUCT_HAS_DEDICATED_ITALIC" = "1" ]; then
      link_or_copy "$FONT_DIR/$PRODUCT_RUBIK_ITALIC_SRC" "$dest/$PRODUCT_RUBIK_ITALIC" || fail "Could not install $PRODUCT_RUBIK_ITALIC into $dest"
    fi
  else
    for font_file in $FONT_FILES; do
      [ -f "$FONT_DIR/$font_file" ] || fail "Product font payload missing: $font_file"
      link_or_copy "$FONT_DIR/$font_file" "$dest/$font_file" || fail "Could not install $font_file into $dest"
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

  resolve_product_rubik_sources
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

  # grep -c already prints 0 on no match, so a `|| echo 0` fallback would emit a second line here.
  PRODUCT_GS_PATCHED=$(grep -cE '<(family-list|familyset|family)[^A-Za-z0-9_-][^>]*name="(sans-serif|google-sans|google-sans-[^"]*|variable-[^"]*)"' "$xml" 2>/dev/null)
  case $PRODUCT_GS_PATCHED in
    ''|*[!0-9]*) PRODUCT_GS_PATCHED=0 ;;
  esac
  if ! grep -q "$PRODUCT_RUBIK_REGULAR" "$xml" 2>/dev/null; then
    PRODUCT_GS_PATCHED=0
  fi
  return 0
}

config_value() {
  local key=$1
  sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$VF_CONFIG_FILE" 2>/dev/null |
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
    *) printf '%s' "$1" ;;
  esac
}

ensure_profile_keys() {
  local profile=$1 axis_meta=$2 weights=$3
  local title
  title=$(profile_title "$profile")
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
    if ! grep -q "^[[:space:]]*${config_key}[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
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
    if ! grep -q "^[[:space:]]*${config_key}[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
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

prepare_variable_config() {
  safe_family=$(printf '%s' "$FONT_FAMILY" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_*//;s/_*$//')
  [ -n "$safe_family" ] || safe_family=Variable_Font
  [ -n "$VF_CONFIG_ID" ] || fail "Variable module identity is missing"
  [ "$VF_CONFIG_SCHEMA" = "2" ] || fail "Unsupported variable config schema: $VF_CONFIG_SCHEMA"
  if ! printf '%s\n' "$VF_CONFIG_ID" | grep -Eq '^vf-[a-f0-9]{20}$'; then
    fail "Variable module identity is invalid: $VF_CONFIG_ID"
  fi
  VF_CONFIG_FILE="$MFFM_DIR/MFFMv14_${safe_family}_${VF_CONFIG_ID}.conf"
  VF_CONFIG_RESET=0

  # Clean old or stale config files from previous installations/font modules in MFFM_DIR
  if [ -d "$MFFM_DIR" ]; then
    local old_cfg old_count=0
    for old_cfg in "$MFFM_DIR"/MFFMv14_*.conf; do
      [ -f "$old_cfg" ] || continue
      if [ "$old_cfg" = "$VF_CONFIG_FILE" ]; then
        saved_identity=$(sed -n 's/^[[:space:]]*MODULE_IDENTITY[[:space:]]*=[[:space:]]*//p' "$old_cfg" 2>/dev/null |
          tail -n 1 | sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//')
        saved_schema=$(sed -n 's/^[[:space:]]*CONFIG_SCHEMA[[:space:]]*=[[:space:]]*//p' "$old_cfg" 2>/dev/null |
          tail -n 1 | sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//')
        if [ "$saved_identity" = "$VF_CONFIG_ID" ] && [ "$saved_schema" = "$VF_CONFIG_SCHEMA" ]; then
          # Valid matching config for this specific module -> KEEP & USE IT!
          continue
        fi
      fi
      # Old, stale, or mismatched font config -> clean it up!
      rm -f "$old_cfg" 2>/dev/null
      old_count=$((old_count + 1))
      VF_CONFIG_RESET=1
    done
    if [ $old_count -gt 0 ]; then
      ui_print "  [OK] Cleaned $old_count old/stale config file(s) from $MFFM_DIR"
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
  link_or_copy "$FONT_DIR/$font_file" "$SYS_FONT/$font_file" || fail "Could not install $font_file"
  status_ok "$font_file"
done

section "2/5" "Patching Android font families"

for xml in "$SYS_XML" "$SYS_FALLBACK"; do
  replace_family "$xml" sans-serif "$FONT_DIR/sans.xml"
  replace_family "$xml" sans-serif-condensed "$FONT_DIR/condensed.xml"
  replace_family "$xml" roboto-flex "$FONT_DIR/sans.xml"
done
status_ok "Sans-serif and Roboto Flex XML"

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
  bundled=$(find_first "$FONT_DIR" "$prefix*.zip")
  [ -n "$bundled" ] || bundled=$(find_first "$MFFM_DIR" "$prefix*.zip")
  [ -n "$bundled" ] || continue
  if command -v unzip >/dev/null 2>&1; then
    unzip -oq "$bundled" -d "$FONT_DIR" || status_warn "Could not extract ${bundled##*/}"
  else
    status_warn "unzip is unavailable; ignoring ${bundled##*/} (extract the fonts next to it instead)"
  fi
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
  ext_mono=$(find_first "$MFFM_DIR" 'Mono*.ttf')
  if [ -n "$ext_mono" ]; then
    cp -f "$ext_mono" "$SYS_FONT/CutiveMono.ttf"
    cp -f "$ext_mono" "$SYS_FONT/DroidSansMono.ttf"
    status_ok "External Monospace font (copied from MFFM folder)"
  else
    status_skip "Monospace font not supplied"
  fi
fi

if [ -f "$FONT_DIR/Beng-Regular.ttf" ] && [ -f "$FONT_DIR/Beng-Medium.ttf" ] && [ -f "$FONT_DIR/Beng-Bold.ttf" ]; then
  cp -f "$FONT_DIR/Beng-Regular.ttf" "$SYS_FONT/NotoSansBengali-VF.ttf"
  cp -f "$FONT_DIR/Beng-Medium.ttf" "$SYS_FONT/NotoSerifBengali-VF.ttf"
  cp -f "$FONT_DIR/Beng-Bold.ttf" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    [ -f "$xml" ] || continue
    replace_beng_family "$xml" elegant
    replace_beng_family "$xml" compact
  done
  status_ok "Bengali fonts"
else
  status_skip "Bengali fonts not supplied"
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
  ext_s_reg=$(find_first "$MFFM_DIR" 'Serif-Regular.ttf')
  ext_s_ital=$(find_first "$MFFM_DIR" 'Serif-Italic.ttf')
  ext_s_bold=$(find_first "$MFFM_DIR" 'Serif-Bold.ttf')
  ext_s_bital=$(find_first "$MFFM_DIR" 'Serif-BoldItalic.ttf')

  if [ -n "$ext_s_reg" ] && [ -n "$ext_s_bold" ]; then
    cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-Regular.ttf"
    [ -n "$ext_s_ital" ] && cp -f "$ext_s_ital" "$SYS_FONT/NotoSerif-Italic.ttf"
    cp -f "$ext_s_bold" "$SYS_FONT/NotoSerif-Bold.ttf"
    [ -n "$ext_s_bital" ] && cp -f "$ext_s_bital" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
    status_ok "External Serif fonts (copied from MFFM folder)"
  else
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
