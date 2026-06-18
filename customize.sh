#!/system/bin/sh
# ==============================================================================
# MFFMv14 Font Module Installer
# Script credits: MFFM / Mistu
# Last modified: 2026-06-18
# ==============================================================================
# Generated font-config.sh selects static or variable XML behavior.

[ "$DEBUG" = "1" ] && set -x

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

LOG_DIR=/sdcard/Download
LOG_FILE="$LOG_DIR/mffmv14_install_$(date '+%Y%m%d_%H%M%S' 2>/dev/null || echo current).log"
mkdir -p "$LOG_DIR" 2>/dev/null

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

mkdir -p "$SYS_FONT" "$SYS_ETC" "$PRODUCT_FONT" "$PRODUCT_ETC" "$MFFM_DIR"
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

{
  echo "MFFMv14 installation completed"
  echo "root_manager=$ROOT_IMPL"
  echo "font_mode=$FONT_MODE"
  echo "font_family=$FONT_FAMILY"
  echo "system_xml=$ORIGINAL_FONTS_XML"
} >> "$LOG_FILE" 2>/dev/null

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
ui_print "    Log: $LOG_FILE"
ui_print ""
