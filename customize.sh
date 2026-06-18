#!/system/bin/sh
# ==============================================================================
# MFFMv14 Font Module Installer
# Script credits: MFFM / Mistu
# Last modified: 2026-06-18
# ==============================================================================
# Generated font-config.sh selects static or variable XML behavior.

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

# update-binary normally enables this before root-manager setup. The fallback
# also supports managers that launch customize.sh in a separate shell.
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
  local message
  message=$1
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

# Keep readable installer messages alongside the shell execution trace.
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

ORIGINAL_SYSTEM=$(first_dir "$MIRROR/system" /system /system_root/system 2>/dev/null)
ORIGINAL_PRODUCT=$(first_dir "$MIRROR/product" "$MIRROR/system/product" /product /system/product /system_root/system/product 2>/dev/null)
ORIGINAL_FONTS_XML=$(first_file "$ORIGINAL_SYSTEM/etc/fonts.xml" /system/etc/fonts.xml /system_root/system/etc/fonts.xml 2>/dev/null)
ORIGINAL_FALLBACK_XML=$(first_file "$ORIGINAL_SYSTEM/etc/font_fallback.xml" /system/etc/font_fallback.xml /system_root/system/etc/font_fallback.xml 2>/dev/null)
ORIGINAL_PRODUCT_XML=$(first_file "$ORIGINAL_PRODUCT/etc/fonts_customization.xml" /product/etc/fonts_customization.xml /system/product/etc/fonts_customization.xml 2>/dev/null)

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
[ -f "$FONT_DIR/sans.xml" ] || fail "Generated sans.xml is missing"

mkdir -p "$SYS_FONT" "$SYS_ETC" "$PRODUCT_FONT" "$PRODUCT_ETC" || fail "Could not create module overlay directories"
mkdir -p "$MFFM_DIR" || fail "Could not create $MFFM_DIR for variable-font settings"
[ -f "$ORIGINAL_FONTS_XML" ] || fail "Could not locate the live system fonts.xml"
cp -f "$ORIGINAL_FONTS_XML" "$SYS_XML" || fail "Could not copy system fonts.xml"
[ -f "$ORIGINAL_FALLBACK_XML" ] && cp -f "$ORIGINAL_FALLBACK_XML" "$SYS_FALLBACK"
[ -f "$ORIGINAL_PRODUCT_XML" ] && cp -f "$ORIGINAL_PRODUCT_XML" "$PRODUCT_XML"

replace_family() {
  xml=$1
  family=$2
  fragment_file=$3
  [ -f "$xml" ] || return 0
  [ -f "$fragment_file" ] || return 0
  grep -q "<family[^>]*name=\"$family\"" "$xml" 2>/dev/null || return 0
  fragment=$(cat "$fragment_file")
  awk -v target="$family" -v replacement="$fragment" '
    $0 ~ "<family[^>]*name=\\\"" target "\\\"" {
      print
      print replacement
      inside=1
      next
    }
    inside {
      if ($0 ~ /<\/family>/) { print; inside=0 }
      next
    }
    { print }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"
}

add_clock_family() {
  fragment=$(cat "$FONT_DIR/clock.xml")
  if [ ! -f "$PRODUCT_XML" ]; then
    cat > "$PRODUCT_XML" <<EOF
<fonts-modification version="1">
  <family customizationType="new-named-family" name="google-sans-clock">
$fragment
  </family>
</fonts-modification>
EOF
    return
  fi
  if grep -q 'name="google-sans-clock"' "$PRODUCT_XML"; then
    replace_family "$PRODUCT_XML" google-sans-clock "$FONT_DIR/clock.xml"
    return
  fi
  awk -v replacement="$fragment" '
    /<\/fonts-modification>/ {
      print "  <family customizationType=\"new-named-family\" name=\"google-sans-clock\">"
      print replacement
      print "  </family>"
    }
    { print }
  ' "$PRODUCT_XML" > "$PRODUCT_XML.tmp" && mv -f "$PRODUCT_XML.tmp" "$PRODUCT_XML"
}

config_value() {
  local key
  key=$1
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
    *) printf '%s' "$1" ;;
  esac
}

ensure_profile_keys() {
  local profile axis_meta weights title axis_record axis_tag remainder axis_min axis_default axis_max
  local config_key axis_key weight label wght_min wght_max
  profile=$1
  axis_meta=$2
  weights=$3
  title=$(profile_title "$profile")

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
  local config_key reset_value
  config_key=$1
  reset_value=$2
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
  local config_key axis_value axis_min axis_max reset_value
  config_key=$1
  axis_value=$2
  axis_min=$3
  axis_max=$4
  reset_value=$5
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
  local style_name declared_weight axis_tag axis_value fragment_file
  style_name=$1
  declared_weight=$2
  axis_tag=$3
  axis_value=$4
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
  local profile xml_style axis_meta weights fragment_list axis_record axis_tag remainder axis_min
  local axis_default axis_max axis_key config_key axis_value weight label wght_min wght_max
  profile=$1
  xml_style=$2
  axis_meta=$3
  weights=$4
  shift 4
  fragment_list="$*"

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
  VF_LEGACY_CONFIG="$MFFM_DIR/MFFMv14_${safe_family}_VF.conf"
  VF_CONFIG_RESET=0

  # Remove the pre-identity format so it cannot leak settings into this module.
  if [ -f "$VF_LEGACY_CONFIG" ]; then
    rm -f "$VF_LEGACY_CONFIG" || fail "Could not remove legacy variable configuration"
    VF_CONFIG_RESET=1
  fi

  if [ -f "$VF_CONFIG_FILE" ]; then
    saved_identity=$(sed -n 's/^[[:space:]]*MODULE_IDENTITY[[:space:]]*=[[:space:]]*//p' "$VF_CONFIG_FILE" |
      tail -n 1 | sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//')
    saved_schema=$(sed -n 's/^[[:space:]]*CONFIG_SCHEMA[[:space:]]*=[[:space:]]*//p' "$VF_CONFIG_FILE" |
      tail -n 1 | sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//')
    if [ "$saved_identity" != "$VF_CONFIG_ID" ] || [ "$saved_schema" != "$VF_CONFIG_SCHEMA" ]; then
      rm -f "$VF_CONFIG_FILE" || fail "Could not remove mismatched variable configuration"
      VF_CONFIG_RESET=1
    fi
  fi

  if [ ! -f "$VF_CONFIG_FILE" ]; then
    cat > "$VF_CONFIG_FILE" <<EOF
# ==============================================================================
# MFFMv14 VARIABLE FONT CONFIGURATION
# ==============================================================================
# Font: $FONT_FAMILY
# Module identity: $VF_CONFIG_ID
#
# CONFIG USAGE
# ------------
# 1. Edit only the numeric values below, save, then reflash this module.
# 2. Named WGHT keys control one Android face. Example:
#      SANS_UPRIGHT_REGULAR_WGHT=450
#    changes only Regular (Android weight 400) to variable wght 450.
# 3. SANS_* values affect sans-serif, serif fallback, and clock families.
# 4. CONDENSED_* values affect only sans-serif-condensed.
# 5. UPRIGHT and ITALIC are independent. Italic profiles expose ital/slnt
#    with the exact values compiled from a single-font or separate-font setup.
# 6. Every axis comment shows its valid range. Invalid or out-of-range values
#    are reset to their compiled defaults automatically during reflash.
# 7. AUTO may be used to restore the compiler-generated value for one key.
# 8. Do not edit CONFIG_SCHEMA or MODULE_IDENTITY. A mismatch resets this file.
# ==============================================================================
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
    "$FONT_DIR/sans.xml" "$FONT_DIR/serif.xml" "$FONT_DIR/clock.xml"
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

section "1/4" "Installing primary font payload"

for font_file in $FONT_FILES; do
  [ -f "$FONT_DIR/$font_file" ] || fail "Payload font is missing: $font_file"
  cp -f "$FONT_DIR/$font_file" "$SYS_FONT/$font_file" || fail "Could not install $font_file"
  status_ok "$font_file"
done

section "2/4" "Patching Android font families"

for xml in "$SYS_XML" "$SYS_FALLBACK"; do
  replace_family "$xml" sans-serif "$FONT_DIR/sans.xml"
  replace_family "$xml" sans-serif-condensed "$FONT_DIR/condensed.xml"
  replace_family "$xml" roboto-flex "$FONT_DIR/sans.xml"
done
status_ok "Sans-serif and Roboto Flex XML"

if [ -n "$CLOCK_FONT" ] && [ -f "$FONT_DIR/$FONT_PRIMARY" ]; then
  cp -f "$FONT_DIR/$FONT_PRIMARY" "$PRODUCT_FONT/$CLOCK_FONT"
  add_clock_family
  status_ok "Google Sans Clock family"
else
  status_skip "Google Sans Clock family"
fi

section "3/4" "Applying optional font resources"

# Optional resources may be bundled or placed in /sdcard/MFFM.
for prefix in Beng Serif; do
  bundled=$(find_first "$FONT_DIR" "$prefix*.zip")
  [ -n "$bundled" ] || bundled=$(find_first "$MFFM_DIR" "$prefix*.zip")
  [ -n "$bundled" ] && unzip -oq "$bundled" -d "$FONT_DIR"
done
mono=$(find_first "$FONT_DIR" 'Mono*.ttf')
[ -n "$mono" ] || mono=$(find_first "$MFFM_DIR" 'Mono*.ttf')
if [ -n "$mono" ]; then
  cp -f "$mono" "$SYS_FONT/CutiveMono.ttf"
  cp -f "$mono" "$SYS_FONT/DroidSansMono.ttf"
  status_ok "Monospace font"
else
  status_skip "Monospace font not supplied"
fi

if [ -f "$FONT_DIR/Beng-Regular.ttf" ] && [ -f "$FONT_DIR/Beng-Medium.ttf" ] && [ -f "$FONT_DIR/Beng-Bold.ttf" ]; then
  cp -f "$FONT_DIR/Beng-Regular.ttf" "$SYS_FONT/NotoSansBengali-VF.ttf"
  cp -f "$FONT_DIR/Beng-Medium.ttf" "$SYS_FONT/NotoSerifBengali-VF.ttf"
  cp -f "$FONT_DIR/Beng-Bold.ttf" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    [ -f "$xml" ] || continue
    sed -i '/<family lang="und-Beng" variant="elegant">/,/<\/family>/c\<family lang="und-Beng" variant="elegant">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
    sed -i '/<family lang="und-Beng" variant="compact">/,/<\/family>/c\<family lang="und-Beng" variant="compact">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
  done
  status_ok "Bengali fonts"
else
  status_skip "Bengali fonts not supplied"
fi

if [ -f "$FONT_DIR/Serif-Regular.ttf" ] && [ -f "$FONT_DIR/Serif-Italic.ttf" ] && [ -f "$FONT_DIR/Serif-Bold.ttf" ] && [ -f "$FONT_DIR/Serif-BoldItalic.ttf" ]; then
  cp -f "$FONT_DIR/Serif-Regular.ttf" "$SYS_FONT/NotoSerif-Regular.ttf"
  cp -f "$FONT_DIR/Serif-Italic.ttf" "$SYS_FONT/NotoSerif-Italic.ttf"
  cp -f "$FONT_DIR/Serif-Bold.ttf" "$SYS_FONT/NotoSerif-Bold.ttf"
  cp -f "$FONT_DIR/Serif-BoldItalic.ttf" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
  status_ok "Dedicated serif fonts"
else
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    replace_family "$xml" serif "$FONT_DIR/serif.xml"
  done
  status_ok "Selected family mapped as serif"
fi

section "4/4" "Finalizing root integration"

if [ "$KSU" = "true" ] || [ "$APATCH" = "true" ]; then
  if command -v setfattr >/dev/null 2>&1; then
    for directory in "$SYS_FONT" "$PRODUCT_FONT" "$SYS_ETC" "$PRODUCT_ETC"; do
      setfattr -n trusted.overlay.opaque -v y "$directory" 2>/dev/null
    done
    status_ok "OverlayFS opaque attributes"
  else
    status_warn "setfattr unavailable; mounting metamodule may be required"
  fi
else
  status_ok "Magisk module overlay"
fi

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
