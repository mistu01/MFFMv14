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
SYS_BIN="$MODPATH/system/bin"
MFFM_DIR=/sdcard/MFFM
CUSTOM_SCRIPTS_MARKER="$MFFM_DIR/allow-custom-scripts"
# Kept after installation so system/bin/font-config can rebuild the XML from an edited .conf.
RUNTIME_DIR="$MODPATH/mffm"

[ -f "$MODPATH/fontlib.sh" ] || fail "fontlib.sh is missing"
# shellcheck source=fontlib.sh
. "$MODPATH/fontlib.sh"
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

prepare_variable_config() {
  [ -n "$VF_CONFIG_ID" ] || fail "Variable module identity is missing"
  [ "$VF_CONFIG_SCHEMA" = "2" ] || fail "Unsupported variable config schema: $VF_CONFIG_SCHEMA"
  if ! printf '%s\n' "$VF_CONFIG_ID" | grep -Eq '^vf-[a-f0-9]{20}$'; then
    fail "Variable module identity is invalid: $VF_CONFIG_ID"
  fi
  VF_CONFIG_FILE=$(variable_config_path)
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

  # font-config re-applies the axis values later from the pristine fragments, so snapshot them
  # before the values are substituted in place.
  save_runtime_payload
  apply_axis_profiles "$FONT_DIR"
}

# Everything font-config needs on device to rebuild the XML from an edited .conf: the axis
# metadata, the library, the pristine fragments and the ROM's untouched XML.
save_runtime_payload() {
  local name
  mkdir -p "$RUNTIME_DIR/fragments" "$RUNTIME_DIR/original" || fail "Could not create $RUNTIME_DIR"
  cp -f "$MODPATH/font-config.sh" "$RUNTIME_DIR/font-config.sh" || fail "Could not save the axis metadata"
  cp -f "$MODPATH/fontlib.sh" "$RUNTIME_DIR/fontlib.sh" || fail "Could not save fontlib.sh"
  for name in sans.xml condensed.xml serif.xml mono.xml; do
    copy_if_exists "$FONT_DIR/$name" "$RUNTIME_DIR/fragments/$name"
  done
  copy_if_exists "$ORIGINAL_FONTS_XML" "$RUNTIME_DIR/original/fonts.xml"
  copy_if_exists "$ORIGINAL_FALLBACK_XML" "$RUNTIME_DIR/original/font_fallback.xml"
  copy_if_exists "$ORIGINAL_PRODUCT_XML" "$RUNTIME_DIR/original/fonts_customization.xml"
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
  patch_sans_families "$xml" "$FONT_DIR"
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
    patch_mono_families "$xml" "$FONT_DIR"
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
    patch_serif_families "$xml" "$FONT_DIR"
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

# Only a variable module has axis values worth re-applying on device.
if [ "$FONT_MODE" = "variable" ] && [ -f "$MODPATH/font-config" ]; then
  mkdir -p "$SYS_BIN" || fail "Could not create $SYS_BIN"
  cp -f "$MODPATH/font-config" "$SYS_BIN/font-config" || fail "Could not install font-config"
  status_ok "font-config (re-apply axis values without re-flashing)"
else
  rm -rf "$RUNTIME_DIR"
fi

set_perm_recursive "$MODPATH" 0 0 0755 0644
for script in service.sh uninstall.sh post-mount.sh; do
  [ -f "$MODPATH/$script" ] && set_perm "$MODPATH/$script" 0 0 0755
done
[ -f "$SYS_BIN/font-config" ] && set_perm "$SYS_BIN/font-config" 0 0 0755
rm -rf "$FONT_DIR"
rm -f "$MODPATH/font-config.sh" "$MODPATH/font-config" "$MODPATH/fontlib.sh"
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
if [ -f "$SYS_BIN/font-config" ]; then
  ui_print "    Axis values: edit ${VF_CONFIG_FILE##*/} in $MFFM_DIR, then run"
  ui_print "    'su -c font-config' and reboot."
fi
ui_print "    Debug log: $LOG_FILE"
ui_print ""
