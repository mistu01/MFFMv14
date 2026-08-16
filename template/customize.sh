#!/system/bin/sh
# MFFMv14 Font Module Installer

# Add Termux environment paths if available to access Python and fontTools during recovery/root installation
if [ -d "/data/data/com.termux/files/usr/bin" ]; then
  export PATH="/data/data/com.termux/files/usr/bin:$PATH"
  export LD_LIBRARY_PATH="/data/data/com.termux/files/usr/lib:$LD_LIBRARY_PATH"
  export HOME="/data/data/com.termux/files/home"
  export TMPDIR="/data/data/com.termux/files/usr/tmp"
  mkdir -p "$TMPDIR" 2>/dev/null
fi

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

# Prune old debug logs, keeping the newest few for post-mortem comparison with
# this run's log. Only mffmv14_debug_*.log files are touched; unrelated user
# files in LOG_DIR are left alone.
MFFM_LOG_KEEP=${MFFM_LOG_KEEP:-3}
if [ -d "$LOG_DIR" ]; then
  old_logs=$(ls -t "$LOG_DIR"/mffmv14_debug_*.log 2>/dev/null | tail -n +"$((MFFM_LOG_KEEP + 1))")
  for old_log in $old_logs; do
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
    match=$(find "$dir" -maxdepth 1 -type f -iname "$pattern" 2>/dev/null | head -n 1)
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
    for file in "$dir"/*.ttf "$dir"/*.otf "$dir"/*.TTF "$dir"/*.OTF "$dir"/*.Ttf "$dir"/*.Otf; do
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
  local font_file=$1 font_sys_name=$2 axes_str=$3 style=${4:-normal}
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

  # Android fonts.xml requires <axis tag="wght" stylevalue="N" /> as a child
  # element inside <font> — the axis="wght=N" single-attribute form is invalid.
  local w w_clamp
  for w in 100 200 300 400 500 600 700 800 900; do
    w_clamp=$w
    [ $w_clamp -lt $wght_min ] && w_clamp=$wght_min
    [ $w_clamp -gt $wght_max ] && w_clamp=$wght_max
    if [ "$has_wght" = "1" ]; then
      printf '    <font weight="%d" style="%s">\n' "$w" "$style"
      printf '        <axis tag="wght" stylevalue="%d" />\n' "$w_clamp"
      printf '        %s\n' "$font_sys_name"
      printf '    </font>\n'
    else
      printf '    <font weight="%d" style="%s">%s</font>\n' "$w" "$style" "$font_sys_name"
    fi
  done
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


ROOT_IMPL=Unknown
if [ "$KSU" = "true" ] || [ -n "$KSU_VER_CODE" ]; then
  ROOT_IMPL=KernelSU
elif [ "$APATCH" = "true" ] || [ -n "$APATCH_VER_CODE" ]; then
  ROOT_IMPL=APatch
elif command -v magisk >/dev/null 2>&1; then
  ROOT_IMPL=Magisk
fi

get_overlay_lowerdir() {
  local target_mount=$1
  local line lowerdirs
  line=$(awk -v m="$target_mount" '$2 == m && $3 == "overlay" { print $4 }' /proc/mounts 2>/dev/null | tail -n 1)
  [ -n "$line" ] || line=$(grep -E "[[:space:]]${target_mount}[[:space:]]+overlay[[:space:]]" /proc/mounts 2>/dev/null | tail -n 1)
  if [ -n "$line" ]; then
    lowerdirs=$(printf '%s\n' "$line" | sed -n 's/.*lowerdir=\([^, )]*\).*/\1/p')
    if [ -n "$lowerdirs" ]; then
      printf '%s\n' "${lowerdirs##*:}"
      return 0
    fi
  fi
  return 1
}

first_dev() {
  for item in "$@"; do
    [ -n "$item" ] && [ -b "$item" ] && { printf '%s\n' "$item"; return 0; }
  done
  return 1
}

find_block_dev() {
  local target_mount=$1
  local dev=""
  dev=$(awk -v m="$target_mount" '$2 == m && $1 ~ /^\/dev\/block\// { print $1; exit }' /proc/mounts 2>/dev/null)
  if [ -z "$dev" ] || [ ! -b "$dev" ]; then
    case "$target_mount" in
      /system|/system_root|/)
        dev=$(first_dev /dev/block/mapper/system /dev/block/mapper/system_a /dev/block/mapper/system_b /dev/block/bootdevice/by-name/system /dev/block/by-name/system 2>/dev/null)
        ;;
      /product|/system/product)
        dev=$(first_dev /dev/block/mapper/product /dev/block/mapper/product_a /dev/block/mapper/product_b /dev/block/bootdevice/by-name/product /dev/block/by-name/product 2>/dev/null)
        ;;
    esac
  fi
  [ -n "$dev" ] && [ -b "$dev" ] && printf '%s' "$dev"
}

extract_from_block_dev() {
  local dev=$1 target_file=$2 dest=$3
  [ -n "$dev" ] && [ -b "$dev" ] || return 1
  local tmp_mnt="/dev/.mffm_stock_probe_$$"
  mkdir -p "$tmp_mnt" 2>/dev/null || return 1
  if mount -o ro,nodev,noexec "$dev" "$tmp_mnt" 2>/dev/null || \
     mount -t erofs -o ro,nodev,noexec "$dev" "$tmp_mnt" 2>/dev/null || \
     mount -t ext4 -o ro,nodev,noexec "$dev" "$tmp_mnt" 2>/dev/null || \
     mount -t f2fs -o ro,nodev,noexec "$dev" "$tmp_mnt" 2>/dev/null; then
    local src_file=""
    if [ -f "$tmp_mnt/system$target_file" ] && [ ! -L "$tmp_mnt/system$target_file" ]; then
      src_file="$tmp_mnt/system$target_file"
    elif [ -f "$tmp_mnt/system_root/system$target_file" ] && [ ! -L "$tmp_mnt/system_root/system$target_file" ]; then
      src_file="$tmp_mnt/system_root/system$target_file"
    elif [ -f "$tmp_mnt/product$target_file" ] && [ ! -L "$tmp_mnt/product$target_file" ]; then
      src_file="$tmp_mnt/product$target_file"
    elif [ -f "$tmp_mnt$target_file" ] && [ ! -L "$tmp_mnt$target_file" ]; then
      src_file="$tmp_mnt$target_file"
    fi
    if [ -n "$src_file" ] && [ -f "$src_file" ]; then
      cp -f "$src_file" "$dest" 2>/dev/null
    fi
    umount "$tmp_mnt" 2>/dev/null
    rmdir "$tmp_mnt" 2>/dev/null
    [ -f "$dest" ] && return 0
  fi
  rmdir "$tmp_mnt" 2>/dev/null
  return 1
}

MIRROR=
if command -v magisk >/dev/null 2>&1; then
  MAGISK_PATH=$(magisk --path 2>/dev/null)
  [ -n "$MAGISK_PATH" ] && [ -d "$MAGISK_PATH/.magisk/mirror" ] && MIRROR="$MAGISK_PATH/.magisk/mirror"
fi
[ -n "$MIRROR" ] || MIRROR=$(first_dir /debug_ramdisk/.magisk/mirror /data/adb/magisk/mirror /dev/.magisk/mirror /sbin/.magisk/mirror 2>/dev/null)

LOWER_SYSTEM=$(get_overlay_lowerdir /system 2>/dev/null)
[ -n "$LOWER_SYSTEM" ] || LOWER_SYSTEM=$(get_overlay_lowerdir /system_root 2>/dev/null)
[ -n "$LOWER_SYSTEM" ] || LOWER_SYSTEM=$(get_overlay_lowerdir / 2>/dev/null)
LOWER_PRODUCT=$(get_overlay_lowerdir /product 2>/dev/null)
[ -n "$LOWER_PRODUCT" ] || LOWER_PRODUCT=$(get_overlay_lowerdir /system/product 2>/dev/null)

STOCK_XML_BACKUP="/data/adb/mffm_stock_xml"

find_pristine_xml() {
  local target_rel_path=$1
  local part_type=$2
  local cached_file="$STOCK_XML_BACKUP/${target_rel_path##*/}"
  local result=""

  # 1. Tier 1: Hardware Block Device Direct Read-Only Probe (Direct Physical Storage - 100% Genuine Factory ROM)
  local block_dev=""
  if [ "$part_type" = "system" ]; then
    block_dev=$(first_dev \
      "$(find_block_dev /system_root)" \
      "$(find_block_dev /system)" \
      "$(find_block_dev /)" \
      2>/dev/null)
  else
    block_dev=$(first_dev \
      "$(find_block_dev /product)" \
      "$(find_block_dev /system/product)" \
      "$(find_block_dev /system_root)" \
      "$(find_block_dev /system)" \
      "$(find_block_dev /)" \
      2>/dev/null)
  fi
  if [ -n "$block_dev" ]; then
    local temp_dest="/dev/.mffm_extracted_${target_rel_path##*/}"
    rm -f "$temp_dest" 2>/dev/null
    if extract_from_block_dev "$block_dev" "$target_rel_path" "$temp_dest"; then
      mkdir -p "$STOCK_XML_BACKUP" 2>/dev/null
      cp -f "$temp_dest" "$cached_file" 2>/dev/null
      rm -f "$temp_dest" 2>/dev/null
      printf '%s\n' "$cached_file"
      return 0
    fi
    rm -f "$temp_dest" 2>/dev/null
  fi

  # 2. Tier 2: Magisk Root Mirrors across all possible search roots and SAR paths
  local m_root=""
  for m_root in "$MIRROR" /debug_ramdisk/.magisk/mirror /data/adb/magisk/mirror /dev/.magisk/mirror /sbin/.magisk/mirror /dev/magisk/mirror; do
    [ -n "$m_root" ] && [ -d "$m_root" ] || continue
    if [ "$part_type" = "system" ]; then
      result=$(first_file \
        "$m_root/system_root/system$target_rel_path" \
        "$m_root/system$target_rel_path" \
        "$m_root/system/system$target_rel_path" \
        "$m_root$target_rel_path" \
        2>/dev/null)
    else
      result=$(first_file \
        "$m_root/product$target_rel_path" \
        "$m_root/system/product$target_rel_path" \
        "$m_root/system_root/product$target_rel_path" \
        "$m_root/system_root/system/product$target_rel_path" \
        "$m_root$target_rel_path" \
        2>/dev/null)
    fi
    if [ -n "$result" ] && [ -f "$result" ]; then
      mkdir -p "$STOCK_XML_BACKUP" 2>/dev/null
      cp -f "$result" "$cached_file" 2>/dev/null
      printf '%s\n' "$cached_file"
      return 0
    fi
  done

  # 3. Tier 3: OverlayFS lowerdir (Mountify, KernelSU, APatch)
  if [ "$part_type" = "system" ] && [ -n "$LOWER_SYSTEM" ]; then
    result=$(first_file \
      "$LOWER_SYSTEM/system$target_rel_path" \
      "$LOWER_SYSTEM$target_rel_path" \
      2>/dev/null)
  elif [ "$part_type" = "product" ]; then
    result=$(first_file \
      "$LOWER_PRODUCT/product$target_rel_path" \
      "$LOWER_PRODUCT$target_rel_path" \
      "$LOWER_SYSTEM/product$target_rel_path" \
      "$LOWER_SYSTEM/system/product$target_rel_path" \
      2>/dev/null)
  fi
  if [ -n "$result" ] && [ -f "$result" ]; then
    mkdir -p "$STOCK_XML_BACKUP" 2>/dev/null
    cp -f "$result" "$cached_file" 2>/dev/null
    printf '%s\n' "$cached_file"
    return 0
  fi

  # 4. Tier 4: Saved Persistent Stock Cache
  if [ -f "$cached_file" ]; then
    printf '%s\n' "$cached_file"
    return 0
  fi

  # 5. Tier 5: Direct System Path
  local direct_path=""
  if [ "$part_type" = "system" ]; then
    direct_path=$(first_file /system_root/system$target_rel_path /system$target_rel_path 2>/dev/null)
  else
    direct_path=$(first_file /product$target_rel_path /system/product$target_rel_path /system_root/system/product$target_rel_path 2>/dev/null)
  fi
  if [ -n "$direct_path" ] && [ -f "$direct_path" ]; then
    printf '%s\n' "$direct_path"
    return 0
  fi

  return 1
}

find_original_xmls() {
  ORIGINAL_FONTS_XML=$(find_pristine_xml "/etc/fonts.xml" "system")
  ORIGINAL_FALLBACK_XML=$(find_pristine_xml "/etc/font_fallback.xml" "system")
  ORIGINAL_PRODUCT_XML=$(find_pristine_xml "/etc/fonts_customization.xml" "product")
}

find_original_xmls

FONT_DIR="$MODPATH/Files"
SYS_FONT="$MODPATH/system/fonts"
SYS_ETC="$MODPATH/system/etc"
SYS_XML="$SYS_ETC/fonts.xml"
SYS_FALLBACK="$SYS_ETC/font_fallback.xml"
PRODUCT_FONT="$MODPATH/system/product/fonts"
PRODUCT_ETC="$MODPATH/system/product/etc"
PRODUCT_XML="$PRODUCT_ETC/fonts_customization.xml"
MFFM_STORAGE=""
for _sbase in /sdcard /storage/emulated/0 /data/media/0 /mnt/pass_through/0/emulated/0; do
  if [ -d "$_sbase/MFFM" ]; then
    MFFM_STORAGE="$_sbase"
    break
  fi
done
[ -z "$MFFM_STORAGE" ] && MFFM_STORAGE=/sdcard
MFFM_DIR="$MFFM_STORAGE/MFFM"

get_category_dirs() {
  local cat=$1 dirs="" dir sbase sub
  for sbase in "$MFFM_STORAGE" /sdcard /storage/emulated/0 /data/media/0 /mnt/pass_through/0/emulated/0; do
    [ -d "$sbase/MFFM" ] || continue
    case "$cat" in
      Bengali|bengali|beng)
        for sub in Bengali bengali Beng beng; do
          dir="$sbase/MFFM/$sub"
          [ -d "$dir" ] && case " $dirs " in *" $dir "*) ;; *) dirs="${dirs:+$dirs }$dir" ;; esac
        done
        dir="$sbase/MFFM"
        [ -d "$dir" ] && case " $dirs " in *" $dir "*) ;; *) dirs="${dirs:+$dirs }$dir" ;; esac
        ;;
      Monospace|monospace|mono)
        for sub in Monospace monospace Mono mono Code code; do
          dir="$sbase/MFFM/$sub"
          [ -d "$dir" ] && case " $dirs " in *" $dir "*) ;; *) dirs="${dirs:+$dirs }$dir" ;; esac
        done
        dir="$sbase/MFFM"
        [ -d "$dir" ] && case " $dirs " in *" $dir "*) ;; *) dirs="${dirs:+$dirs }$dir" ;; esac
        ;;
      Serif|serif)
        for sub in Serif serif; do
          dir="$sbase/MFFM/$sub"
          [ -d "$dir" ] && case " $dirs " in *" $dir "*) ;; *) dirs="${dirs:+$dirs }$dir" ;; esac
        done
        dir="$sbase/MFFM"
        [ -d "$dir" ] && case " $dirs " in *" $dir "*) ;; *) dirs="${dirs:+$dirs }$dir" ;; esac
        ;;
    esac
  done
  printf '%s' "$dirs"
}

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

[ -n "$ORIGINAL_FONTS_XML" ] && [ -f "$ORIGINAL_FONTS_XML" ] || fail "Could not locate live system fonts.xml"
cp -f "$ORIGINAL_FONTS_XML" "$SYS_XML" || fail "Could not copy system fonts.xml"
[ -n "$ORIGINAL_FALLBACK_XML" ] && [ -f "$ORIGINAL_FALLBACK_XML" ] && cp -f "$ORIGINAL_FALLBACK_XML" "$SYS_FALLBACK"

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
      val=$weight
      [ -n "$wght_min" ] && [ "$val" -lt "$wght_min" ] && val=$wght_min
      [ -n "$wght_max" ] && [ "$val" -gt "$wght_max" ] && val=$wght_max
      {
        printf '# Android %s (%s): variable wght range %s..%s\n' "$weight" "$label" "$wght_min" "$wght_max"
        printf '%s=%s\n' "$config_key" "$val"
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

ensure_variable_config_file() {
  [ -n "$VF_CONFIG_FILE" ] && [ -f "$VF_CONFIG_FILE" ] && return 0

  safe_family=$(printf '%s' "$FONT_FAMILY" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_*//;s/_*$//')
  [ -n "$safe_family" ] || safe_family=Variable_Font

  if [ -z "$VF_CONFIG_ID" ]; then
    VF_CONFIG_ID="vf-$(printf '%s' "${safe_family}_MFFMv14" | md5sum 2>/dev/null | cut -c1-20)"
    [ -z "$VF_CONFIG_ID" ] && VF_CONFIG_ID="vf-12345678901234567890"
  fi
  [ -z "$VF_CONFIG_SCHEMA" ] && VF_CONFIG_SCHEMA="2"

  VF_CONFIG_FILE="$MFFM_DIR/MFFMv14_${safe_family}_${VF_CONFIG_ID}.conf"
  VF_LEGACY_CONFIG="$MFFM_DIR/MFFMv14_${safe_family}_VF.conf"
  VF_CONFIG_RESET=0

  # Preserve existing configuration when updating the same module family or identity
  if [ -d "$MFFM_DIR" ]; then
    local candidate saved_identity
    if [ ! -f "$VF_CONFIG_FILE" ]; then
      for candidate in "$MFFM_DIR"/MFFMv14_${safe_family}_*.conf "$VF_LEGACY_CONFIG"; do
        [ -f "$candidate" ] || continue
        saved_identity=$(sed -n 's/^[[:space:]]*MODULE_IDENTITY[[:space:]]*=[[:space:]]*//p' "$candidate" 2>/dev/null |
          tail -n 1 | sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//')
        if [ "$saved_identity" = "$VF_CONFIG_ID" ] || [ -z "$saved_identity" ]; then
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
    ui_print "  [OK] Created variable-axis configuration: ${VF_CONFIG_FILE##*/}"
  else
    VF_CONFIG_CREATED=0
    if ! grep -q "^[[:space:]]*MODULE_IDENTITY[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
      printf 'MODULE_IDENTITY=%s\n' "$VF_CONFIG_ID" >> "$VF_CONFIG_FILE"
    fi
  fi
  [ -f "$VF_CONFIG_FILE" ] || fail "Could not create variable-axis configuration: $VF_CONFIG_FILE"

  # Clean any other stale/leftover configuration files from previous modules
  if [ -d "$MFFM_DIR" ]; then
    for old_conf in "$MFFM_DIR"/*.conf "$MFFM_DIR"/MFFMv14_*.conf; do
      [ -f "$old_conf" ] || continue
      [ "$old_conf" != "$VF_CONFIG_FILE" ] && rm -f "$old_conf" 2>/dev/null
    done
  fi
}

configure_variable_family_profile() {
  local profile=$1 font_file=$2 xml_style=$3 weights=$4
  shift 4
  local fragment_list="$*"
  [ -f "$font_file" ] || return 0

  ensure_variable_config_file
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
  ensure_variable_config_file

  if [ -n "$VF_UPRIGHT_AXIS_META" ]; then
    ensure_profile_keys SANS_UPRIGHT "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS"
    apply_profile SANS_UPRIGHT normal "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS" "$FONT_DIR/sans.xml"
    if [ -f "$FONT_DIR/condensed.xml" ]; then
      ensure_profile_keys CONDENSED_UPRIGHT "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS"
      apply_profile CONDENSED_UPRIGHT normal "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS" "$FONT_DIR/condensed.xml"
    fi
  fi

  if [ -n "$VF_ITALIC_AXIS_META" ]; then
    ensure_profile_keys SANS_ITALIC "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS"
    apply_profile SANS_ITALIC italic "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS" "$FONT_DIR/sans.xml"
    if [ -f "$FONT_DIR/condensed.xml" ]; then
      ensure_profile_keys CONDENSED_ITALIC "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS"
      apply_profile CONDENSED_ITALIC italic "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS" "$FONT_DIR/condensed.xml"
    fi
  fi

  if [ -n "$VF_MONO_AXIS_META" ] && [ -f "$FONT_DIR/mono.xml" ]; then
    ensure_profile_keys MONOSPACE_UPRIGHT "$VF_MONO_AXIS_META" "$VF_MONO_WEIGHTS"
    apply_profile MONOSPACE_UPRIGHT normal "$VF_MONO_AXIS_META" "$VF_MONO_WEIGHTS" "$FONT_DIR/mono.xml"
  fi

  if [ -n "$VF_SERIF_UPRIGHT_AXIS_META" ] && [ -f "$FONT_DIR/serif.xml" ]; then
    ensure_profile_keys SERIF_UPRIGHT "$VF_SERIF_UPRIGHT_AXIS_META" "$VF_SERIF_UPRIGHT_WEIGHTS"
    apply_profile SERIF_UPRIGHT normal "$VF_SERIF_UPRIGHT_AXIS_META" "$VF_SERIF_UPRIGHT_WEIGHTS" "$FONT_DIR/serif.xml"
  fi

  if [ -n "$VF_SERIF_ITALIC_AXIS_META" ] && [ -f "$FONT_DIR/serif.xml" ]; then
    ensure_profile_keys SERIF_ITALIC "$VF_SERIF_ITALIC_AXIS_META" "$VF_SERIF_ITALIC_WEIGHTS"
    apply_profile SERIF_ITALIC italic "$VF_SERIF_ITALIC_AXIS_META" "$VF_SERIF_ITALIC_WEIGHTS" "$FONT_DIR/serif.xml"
  fi

  if [ -n "$VF_BENGALI_AXIS_META" ] && [ -f "$FONT_DIR/bengali.xml" ]; then
    ensure_profile_keys BENGALI_UPRIGHT "$VF_BENGALI_AXIS_META" "$VF_BENGALI_WEIGHTS"
    apply_profile BENGALI_UPRIGHT normal "$VF_BENGALI_AXIS_META" "$VF_BENGALI_WEIGHTS" "$FONT_DIR/bengali.xml"
  fi
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

if [ "$FONT_MODE" = "variable" ] || [ -n "$VF_MONO_AXIS_META" ] || [ -n "$VF_SERIF_UPRIGHT_AXIS_META" ] || [ -n "$VF_BENGALI_AXIS_META" ]; then
  prepare_variable_config
  ui_print "    Axis config  : $VF_CONFIG_FILE"
fi

if [ "$FONT_MODE" != "variable" ]; then
  prune_obsolete_profile_keys SANS_UPRIGHT
  prune_obsolete_profile_keys SANS_ITALIC
  prune_obsolete_profile_keys CONDENSED_UPRIGHT
  prune_obsolete_profile_keys CONDENSED_ITALIC
fi

section "1/5" "Installing primary font payload"

for font_file in $FONT_FILES; do
  [ -f "$FONT_DIR/$font_file" ] || fail "Payload font is missing: $font_file"
  cp -f "$FONT_DIR/$font_file" "$SYS_FONT/$font_file" || fail "Could not install $font_file"
  status_ok "$font_file"
done

section "2/5" "Patching Android font families"

# Sans-serif is mandatory and must be bundled inside the module (DroidSans.ttf).
# External supply via MFFM/Sans is not supported.
if [ -f "$FONT_DIR/sans.xml" ]; then
  for xml in "$SYS_XML" "$SYS_FALLBACK"; do
    replace_family "$xml" sans-serif "$FONT_DIR/sans.xml"
    replace_family "$xml" sans-serif-condensed "$FONT_DIR/condensed.xml"
    replace_family "$xml" roboto-flex "$FONT_DIR/sans.xml"
  done
  status_ok "Native Sans-serif font (bundled in DroidSans.ttf)"
else
  status_skip "Sans-serif font not bundled in module — skipping"
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
# ── Shared Python weight scanner (used by Monospace, Bengali, Serif) ──────────
# Outputs "weight:style:path" lines for each .ttf/.otf in the given directories.
# Combines OS/2 usWeightClass with name-table / filename label resolution for
# correct weight assignment even when fonts have misconfigured OS/2 headers.
_py_scan_font_weights() {
  [ -n "$py_bin" ] || return 1
  $py_bin -c '
import sys, os
try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit(1)
for d in sys.argv[1:]:
    if not d or not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not (f.endswith(".ttf") or f.endswith(".otf")):
            continue
        path = os.path.join(d, f)
        try:
            font = TTFont(path, lazy=True)
            os2 = font.get("OS/2")
            wt = os2.usWeightClass if os2 else 400
            name = font.get("name")
            sub = (name.getDebugName(2) or "") if name else ""
            full = (name.getDebugName(4) or "") if name else ""
            label = (f + " " + sub + " " + full).lower()
            name_wt = None
            if "thin" in label or "hairline" in label: name_wt = 100
            elif "extralight" in label or "ultralight" in label: name_wt = 200
            elif "light" in label: name_wt = 300
            elif "medium" in label: name_wt = 500
            elif "semibold" in label or "demibold" in label: name_wt = 600
            elif "extrabold" in label or "ultrabold" in label: name_wt = 800
            elif "black" in label or "heavy" in label: name_wt = 900
            elif "bold" in label: name_wt = 700
            elif "regular" in label or "book" in label: name_wt = 400
            if wt == 400 and name_wt:
                wt = name_wt
            elif name_wt and abs(name_wt - 400) > abs(wt - 400):
                wt = name_wt
            fs = os2.fsSelection if os2 else 0
            is_italic = bool(fs & 0x01) or "italic" in sub.lower() or "oblique" in sub.lower() or "italic" in f.lower()
            style = "italic" if is_italic else "normal"
            font.close()
            print(f"{wt}:{style}:{path}")
        except Exception:
            pass
' "$@" 2>/dev/null
}

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
  [ -z "$VF_MONO_AXIS_META" ] && prune_obsolete_profile_keys MONOSPACE_UPRIGHT
  status_ok "Native Monospace font (bundled in DroidSans.ttf)"
else
  # ── Find first font file in Monospace dirs to check variable vs static ──
  _mono_dirs=$(get_category_dirs Monospace)
  ext_mono=$(find_first 'Mono*.ttf' "$FONT_DIR" $_mono_dirs)
  [ -z "$ext_mono" ] && ext_mono=$(find_first 'Mono*.otf' "$FONT_DIR" $_mono_dirs)
  [ -z "$ext_mono" ] && ext_mono=$(find_first 'CutiveMono.ttf' "$FONT_DIR" $_mono_dirs)
  [ -z "$ext_mono" ] && ext_mono=$(find_first 'DroidSansMono.ttf' "$FONT_DIR" $_mono_dirs)
  [ -z "$ext_mono" ] && ext_mono=$(find_first '*.ttf' $_mono_dirs)
  [ -z "$ext_mono" ] && ext_mono=$(find_first '*.otf' $_mono_dirs)
  if [ -n "$ext_mono" ]; then
    if is_variable_font "$ext_mono"; then
      cp -f "$ext_mono" "$SYS_FONT/CutiveMono.ttf"
      cp -f "$ext_mono" "$SYS_FONT/DroidSansMono.ttf"
      axes_info=$(extract_fvar_axes "$ext_mono")
      frag_file="$FONT_DIR/ext_mono.xml"
      generate_vf_xml_fragment "$ext_mono" "DroidSansMono.ttf" "$axes_info" > "$frag_file"
      configure_variable_family_profile MONOSPACE_UPRIGHT "$ext_mono" normal "100 200 300 400 500 600 700 800 900" "$frag_file"
      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        replace_family "$xml" monospace "$frag_file"
        replace_family "$xml" cutive-mono "$frag_file"
        replace_family "$xml" droidsans-mono "$frag_file"
      done
      status_ok "Variable Monospace font (${ext_mono##*/}) auto-configured natively"
    else
      prune_obsolete_profile_keys MONOSPACE_UPRIGHT
      # ── Static family: discover distinct weights, bundle into DroidSansMono.ttf TTC ──
      # POSIX-sh ordered list — no declare -A (not supported in mksh/ash)
      _mono_ttc_files=""
      _mono_idx_counter=0

      _mono_get_idx() {
        local needle="$1" i=0 line
        [ -n "$needle" ] || { echo "0"; return; }
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          [ "$line" = "$needle" ] && echo "$i" && return
          i=$((i+1))
        done << EOF
$_mono_ttc_files
EOF
        i=0
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          [ "$line" = "$_mr400" ] && echo "$i" && return
          i=$((i+1))
        done << EOF
$_mono_ttc_files
EOF
        echo "0"
      }

      _mono_add_face() {
        local file="$1" line already=0
        [ -n "$file" ] || return
        while IFS= read -r line; do
          [ "$line" = "$file" ] && already=1 && break
        done << EOF
$_mono_ttc_files
EOF
        [ "$already" = "0" ] && {
          _mono_ttc_files="${_mono_ttc_files:+$_mono_ttc_files
}$file"
          _mono_idx_counter=$((_mono_idx_counter + 1))
        }
      }

      # ── Weight discovery: OS/2 usWeightClass (Python) or filename heuristic ─
      _mr100="" _mr200="" _mr300="" _mr400="" _mr500="" _mr600="" _mr700="" _mr800="" _mr900=""

      local py_bin=""
      command -v python3 >/dev/null 2>&1 && py_bin="python3"
      [ -z "$py_bin" ] && command -v python >/dev/null 2>&1 && py_bin="python"
      if [ -n "$py_bin" ] && ! $py_bin -c "import fontTools" 2>/dev/null; then
        if [ -d "/data/data/com.termux/files/usr/bin" ]; then
          status_skip "fontTools not found. Auto-installing via Termux pip..."
          su -c "env PATH=/data/data/com.termux/files/usr/bin:\$PATH pip install fonttools brotli 2>&1" || true
          $py_bin -c "import fontTools" 2>/dev/null || py_bin=""
          [ -z "$py_bin" ] && status_skip "fontTools install failed — falling back to single-file mode"
        else
          py_bin=""
        fi
      fi

      if [ -n "$py_bin" ] && $py_bin -c "import fontTools" 2>/dev/null; then
        _py_wmap=$(_py_scan_font_weights $_mono_dirs)
        if [ -n "$_py_wmap" ]; then
          while IFS= read -r _wl; do
            [ -z "$_wl" ] && continue
            _wt=${_wl%%:*}; _rest=${_wl#*:}; _sty=${_rest%%:*}; _fp=${_rest#*:}
            [ "$_sty" != "normal" ] && continue
            case "$_wt" in
              100) [ -z "$_mr100" ] && _mr100="$_fp" ;;
              200) [ -z "$_mr200" ] && _mr200="$_fp" ;;
              300) [ -z "$_mr300" ] && _mr300="$_fp" ;;
              400) [ -z "$_mr400" ] && _mr400="$_fp" ;;
              500) [ -z "$_mr500" ] && _mr500="$_fp" ;;
              600) [ -z "$_mr600" ] && _mr600="$_fp" ;;
              700) [ -z "$_mr700" ] && _mr700="$_fp" ;;
              800) [ -z "$_mr800" ] && _mr800="$_fp" ;;
              900) [ -z "$_mr900" ] && _mr900="$_fp" ;;
            esac
          done << EOF
$_py_wmap
EOF
        fi
      fi

      [ -z "$_mr100" ] && _mr100=$(find_best_face 100 normal $_mono_dirs)
      [ -z "$_mr200" ] && _mr200=$(find_best_face 200 normal $_mono_dirs)
      [ -z "$_mr300" ] && _mr300=$(find_best_face 300 normal $_mono_dirs)
      [ -z "$_mr400" ] && _mr400=$(find_best_face 400 normal $_mono_dirs)
      [ -z "$_mr500" ] && _mr500=$(find_best_face 500 normal $_mono_dirs)
      [ -z "$_mr600" ] && _mr600=$(find_best_face 600 normal $_mono_dirs)
      [ -z "$_mr700" ] && _mr700=$(find_best_face 700 normal $_mono_dirs)
      [ -z "$_mr800" ] && _mr800=$(find_best_face 800 normal $_mono_dirs)
      [ -z "$_mr900" ] && _mr900=$(find_best_face 900 normal $_mono_dirs)
      [ -z "$_mr400" ] && _mr400="$ext_mono"

      _mono_add_face "$_mr100"; _mono_add_face "$_mr200"; _mono_add_face "$_mr300"
      _mono_add_face "$_mr400"; _mono_add_face "$_mr500"; _mono_add_face "$_mr600"
      _mono_add_face "$_mr700"; _mono_add_face "$_mr800"; _mono_add_face "$_mr900"

      _midx400=$(_mono_get_idx "$_mr400")
      _midx100=$(_mono_get_idx "${_mr100:-$_mr400}")
      _midx200=$(_mono_get_idx "${_mr200:-${_mr300:-$_mr400}}")
      _midx300=$(_mono_get_idx "${_mr300:-$_mr400}")
      _midx500=$(_mono_get_idx "${_mr500:-$_mr400}")
      _midx600=$(_mono_get_idx "${_mr600:-${_mr500:-$_mr400}}")
      _midx700=$(_mono_get_idx "${_mr700:-${_mr600:-$_mr400}}")
      _midx800=$(_mono_get_idx "${_mr800:-$_mr700}")
      _midx900=$(_mono_get_idx "${_mr900:-$_mr800}")

      frag_file="$FONT_DIR/ext_mono.xml"

      if [ -z "$py_bin" ] && [ "$_mono_idx_counter" -gt 2 ]; then
        status_skip "WARNING: Multiple Monospace faces detected but Termux+Python not found."
        status_skip "Install Termux and run: pip install fonttools — then reflash."
        status_skip "Falling back to single-file install (Regular only)."
      fi

      if [ -n "$py_bin" ] && $py_bin -c "import fontTools" 2>/dev/null; then
        _mono_ttc_out="$SYS_FONT/DroidSansMono.ttf"
        _mono_ttc_err=$(printf '%s\n' "$_mono_ttc_files" | $py_bin -c '
import sys
from fontTools.ttLib import TTFont, TTCollection
out = sys.argv[1]
files = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
if not files:
    sys.exit(1)
col = TTCollection()
for f in files:
    try:
        col.fonts.append(TTFont(f))
    except Exception as e:
        sys.stderr.write(f"Error loading {f}: {e}\n")
if not col.fonts:
    sys.exit(1)
col.save(out)
' "$_mono_ttc_out" 2>&1)
        if [ ! -f "$_mono_ttc_out" ] || [ ! -s "$_mono_ttc_out" ]; then
          status_warn "Monospace TTC bundling failed — falling back to single-file mode"
          [ -n "$_mono_ttc_err" ] && mffm_log_line "  TTC error: $_mono_ttc_err"
          cp -f "$_mr400" "$SYS_FONT/DroidSansMono.ttf"
          cp -f "$_mr400" "$SYS_FONT/CutiveMono.ttf"
          status_ok "Static Monospace installed (single-file fallback, Regular only)"
        else
          cp -f "$_mono_ttc_out" "$SYS_FONT/CutiveMono.ttf"
          {
            [ -n "$_mr100" ] && printf '    <font weight="100" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx100"
            [ -n "$_mr200" ] && printf '    <font weight="200" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx200"
            [ -n "$_mr300" ] && printf '    <font weight="300" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx300"
            printf '    <font weight="400" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx400"
            [ -n "$_mr500" ] && printf '    <font weight="500" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx500"
            [ -n "$_mr600" ] && printf '    <font weight="600" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx600"
            [ -n "$_mr700" ] && printf '    <font weight="700" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx700"
            [ -n "$_mr800" ] && printf '    <font weight="800" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx800"
            [ -n "$_mr900" ] && printf '    <font weight="900" style="normal" index="%s">DroidSansMono.ttf</font>\n' "$_midx900"
          } > "$frag_file"
          for xml in "$SYS_XML" "$SYS_FALLBACK"; do
            [ -f "$xml" ] || continue
            replace_family "$xml" monospace "$frag_file"
            replace_family "$xml" cutive-mono "$frag_file"
            replace_family "$xml" droidsans-mono "$frag_file"
          done
          status_ok "Static Monospace TTC bundled ($_mono_idx_counter distinct faces → DroidSansMono.ttf, indexed)"
        fi
      else
        cp -f "$_mr400" "$SYS_FONT/DroidSansMono.ttf"
        cp -f "$_mr400" "$SYS_FONT/CutiveMono.ttf"
        status_ok "Static Monospace installed (single-file fallback, Regular only)"
      fi
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
  [ -z "$VF_BENGALI_AXIS_META" ] && prune_obsolete_profile_keys BENGALI_UPRIGHT
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
  _beng_dirs=$(get_category_dirs Bengali)
  # Flatten this category into a private staging directory. This accepts a
  # complete static family placed in a nested Bengali subfolder while keeping
  # discovery isolated from Sans, Serif, and Monospace files elsewhere in MFFM.
  _beng_stage="$FONT_DIR/.mffm-bengali-static"
  for _beng_dir in $_beng_dirs; do
    [ -d "$_beng_dir" ] || continue
    mkdir -p "$_beng_stage"
    find "$_beng_dir" -type f \( -iname '*.ttf' -o -iname '*.otf' \) ! -iname 'DroidSans.ttf' ! -iname 'GoogleSansClock*.ttf' -exec cp -f {} "$_beng_stage"/ \; 2>/dev/null
  done
  if [ -d "$_beng_stage" ] && find "$_beng_stage" -maxdepth 1 -type f \( -iname '*.ttf' -o -iname '*.otf' \) -print -quit | grep -q .; then
    _beng_dirs="$_beng_stage $_beng_dirs"
  fi
  ext_beng=$(find_first 'Beng*.ttf' "$FONT_DIR" $_beng_dirs)
  [ -z "$ext_beng" ] && ext_beng=$(find_first 'Beng*.otf' "$FONT_DIR" $_beng_dirs)
  [ -z "$ext_beng" ] && ext_beng=$(find_first 'NotoSansBengali*.ttf' "$FONT_DIR" $_beng_dirs)
  [ -z "$ext_beng" ] && ext_beng=$(find_first 'NotoSerifBengali*.ttf' "$FONT_DIR" $_beng_dirs)
  [ -z "$ext_beng" ] && ext_beng=$(find_first '*.ttf' $_beng_dirs)
  [ -z "$ext_beng" ] && ext_beng=$(find_first '*.otf' $_beng_dirs)
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
      status_ok "Variable Bengali font (${ext_beng##*/}) auto-configured natively"
    else
      prune_obsolete_profile_keys BENGALI_UPRIGHT
      # ── POSIX-sh ordered list (no declare -A — not supported in mksh/ash) ─
      _beng_ttc_files=""
      _beng_idx_counter=0

      _beng_get_idx() {
        local needle="$1" i=0 line
        [ -n "$needle" ] || { echo "0"; return; }
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          [ "$line" = "$needle" ] && echo "$i" && return
          i=$((i+1))
        done << EOF
$_beng_ttc_files
EOF
        i=0
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          [ "$line" = "$_r400" ] && echo "$i" && return
          i=$((i+1))
        done << EOF
$_beng_ttc_files
EOF
        echo "0"
      }

      _beng_add_face() {
        local file="$1" line already=0
        [ -n "$file" ] || return
        while IFS= read -r line; do
          [ "$line" = "$file" ] && already=1 && break
        done << EOF
$_beng_ttc_files
EOF
        [ "$already" = "0" ] && {
          _beng_ttc_files="${_beng_ttc_files:+$_beng_ttc_files
}$file"
          _beng_idx_counter=$((_beng_idx_counter + 1))
        }
      }

      frag_file="$FONT_DIR/ext_beng.xml"

      # ── Detect Python + fontTools (used for both weight-scan AND TTC build) ─
      local py_bin=""
      command -v python3 >/dev/null 2>&1 && py_bin="python3"
      [ -z "$py_bin" ] && command -v python >/dev/null 2>&1 && py_bin="python"

      if [ -n "$py_bin" ] && ! $py_bin -c "import fontTools" 2>/dev/null; then
        if [ -d "/data/data/com.termux/files/usr/bin" ]; then
          status_skip "fontTools not found. Auto-installing via Termux pip..."
          su -c "env PATH=/data/data/com.termux/files/usr/bin:\$PATH pip install fonttools brotli 2>&1" || true
          $py_bin -c "import fontTools" 2>/dev/null || py_bin=""
          [ -z "$py_bin" ] && status_skip "fontTools install failed — falling back to filename-based mode"
        else
          py_bin=""
        fi
      fi

      # ── Weight discovery: OS/2 usWeightClass (Python) or filename heuristic ─
      _r100="" _r200="" _r300="" _r400="" _r500="" _r600="" _r700="" _r800="" _r900=""

      if [ -n "$py_bin" ] && $py_bin -c "import fontTools" 2>/dev/null; then
        # Read usWeightClass from OS/2 table — works even for hex-named cache files
        _py_weight_map=$(_py_scan_font_weights $_beng_dirs)
        # Parse output: "weight:style:path" lines — pick best file per slot
        if [ -n "$_py_weight_map" ]; then
          while IFS= read -r _wline; do
            [ -z "$_wline" ] && continue
            _wt=${_wline%%:*}
            _rest=${_wline#*:}
            _sty=${_rest%%:*}
            _fp=${_rest#*:}
            [ "$_sty" != "normal" ] && continue
            case "$_wt" in
              100) [ -z "$_r100" ] && _r100="$_fp" ;;
              200) [ -z "$_r200" ] && _r200="$_fp" ;;
              300) [ -z "$_r300" ] && _r300="$_fp" ;;
              400) [ -z "$_r400" ] && _r400="$_fp" ;;
              500) [ -z "$_r500" ] && _r500="$_fp" ;;
              600) [ -z "$_r600" ] && _r600="$_fp" ;;
              700) [ -z "$_r700" ] && _r700="$_fp" ;;
              800) [ -z "$_r800" ] && _r800="$_fp" ;;
              900) [ -z "$_r900" ] && _r900="$_fp" ;;
            esac
          done << EOF
$_py_weight_map
EOF
        fi
      fi

      # Fallback: filename heuristic (for weights not yet assigned by Python scan)
      [ -z "$_r100" ] && _r100=$(find_best_face 100 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r200" ] && _r200=$(find_best_face 200 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r300" ] && _r300=$(find_best_face 300 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r400" ] && _r400=$(find_best_face 400 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r500" ] && _r500=$(find_best_face 500 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r600" ] && _r600=$(find_best_face 600 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r700" ] && _r700=$(find_best_face 700 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r800" ] && _r800=$(find_best_face 800 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r900" ] && _r900=$(find_best_face 900 normal $_beng_dirs "$MFFM_DIR")
      [ -z "$_r400" ] && _r400="$ext_beng"

      _beng_add_face "$_r100"; _beng_add_face "$_r200"; _beng_add_face "$_r300"
      _beng_add_face "$_r400"; _beng_add_face "$_r500"; _beng_add_face "$_r600"
      _beng_add_face "$_r700"; _beng_add_face "$_r800"; _beng_add_face "$_r900"

      # ── Resolve TTC index for each weight (cascading fallback for missing) ─
      _idx100=$(_beng_get_idx "${_r100:-$_r400}")
      _idx200=$(_beng_get_idx "${_r200:-${_r300:-$_r400}}")
      _idx300=$(_beng_get_idx "${_r300:-$_r400}")
      _idx400=$(_beng_get_idx "$_r400")
      _idx500=$(_beng_get_idx "${_r500:-$_r400}")
      _idx600=$(_beng_get_idx "${_r600:-${_r500:-$_r400}}")
      _idx700=$(_beng_get_idx "${_r700:-${_r600:-$_r400}}")
      _idx800=$(_beng_get_idx "${_r800:-$_r700}")
      _idx900=$(_beng_get_idx "${_r900:-$_r800}")

      if [ -z "$py_bin" ] && [ "$_beng_idx_counter" -gt 3 ]; then
        status_skip "WARNING: Multiple Bengali faces detected but Termux+Python not found."
        status_skip "Install Termux and run: pip install fonttools  — then reflash."
        status_skip "Falling back to 3-file install (Regular/Medium/Bold only)."
      fi

      if [ -n "$py_bin" ] && $py_bin -c "import fontTools" 2>/dev/null; then
        # ── TTC bundle: all distinct faces packed into NotoSansBengali-VF.ttf ─
        _beng_ttc_out="$SYS_FONT/NotoSansBengali-VF.ttf"
        _beng_ttc_err=$(printf '%s\n' "$_beng_ttc_files" | $py_bin -c '
import sys
from fontTools.ttLib import TTFont, TTCollection
out = sys.argv[1]
files = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
if not files:
    sys.exit(1)
col = TTCollection()
for f in files:
    try:
        col.fonts.append(TTFont(f))
    except Exception as e:
        sys.stderr.write(f"Error loading {f}: {e}\n")
if not col.fonts:
    sys.exit(1)
col.save(out)
' "$_beng_ttc_out" 2>&1)
        if [ ! -f "$_beng_ttc_out" ] || [ ! -s "$_beng_ttc_out" ]; then
          status_warn "Bengali TTC bundling failed — falling back to 3-file mode"
          [ -n "$_beng_ttc_err" ] && mffm_log_line "  TTC error: $_beng_ttc_err"
          # ── 3-file fallback inside TTC-path (bundler failed) ──────────────────
          cp -f "${_r400}" "$SYS_FONT/NotoSansBengali-VF.ttf"
          cp -f "${_r500:-$_r400}" "$SYS_FONT/NotoSerifBengali-VF.ttf"
          cp -f "${_r700:-${_r600:-$_r400}}" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
          status_ok "Static Bengali installed (3-file fallback: Regular/Medium/Bold)"
        else
          cp -f "$_beng_ttc_out" "$SYS_FONT/NotoSerifBengali-VF.ttf"
          cp -f "$_beng_ttc_out" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
          # Generate XML fragment — only weights with a real face file
          {
            [ -n "$_r100" ] && printf '    <font weight="100" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx100"
            [ -n "$_r200" ] && printf '    <font weight="200" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx200"
            [ -n "$_r300" ] && printf '    <font weight="300" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx300"
            printf '    <font weight="400" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx400"
            [ -n "$_r500" ] && printf '    <font weight="500" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx500"
            [ -n "$_r600" ] && printf '    <font weight="600" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx600"
            [ -n "$_r700" ] && printf '    <font weight="700" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx700"
            [ -n "$_r800" ] && printf '    <font weight="800" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx800"
            [ -n "$_r900" ] && printf '    <font weight="900" style="normal" index="%s">NotoSansBengali-VF.ttf</font>\n' "$_idx900"
          } > "$frag_file"
          for xml in "$SYS_XML" "$SYS_FALLBACK"; do
            [ -f "$xml" ] || continue
            replace_lang_family "$xml" "und-Beng" "$frag_file"
            replace_lang_family "$xml" "bn" "$frag_file"
          done
          status_ok "Static Bengali TTC bundled ($_beng_idx_counter distinct faces → NotoSansBengali-VF.ttf, indexed)"
        fi
      else
        # ── 3-file fallback: no Python/fontTools available ───────────────────
        local _fb_reg="${_r400}"
        local _fb_med="${_r500:-$_r400}"
        local _fb_bld="${_r700:-${_r600:-$_r400}}"
        cp -f "$_fb_reg" "$SYS_FONT/NotoSansBengali-VF.ttf"
        cp -f "$_fb_med" "$SYS_FONT/NotoSerifBengali-VF.ttf"
        cp -f "$_fb_bld" "$SYS_FONT/NotoSansBengaliUI-VF.ttf"
        for xml in "$SYS_XML" "$SYS_FALLBACK"; do
          [ -f "$xml" ] || continue
          sed -i '/<family lang="und-Beng" variant="elegant">/,/<\/family>/c\<family lang="und-Beng" variant="elegant">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
          sed -i '/<family lang="und-Beng" variant="compact">/,/<\/family>/c\<family lang="und-Beng" variant="compact">\n    <font weight="400" style="normal">NotoSansBengali-VF.ttf<\/font>\n    <font weight="500" style="normal">NotoSerifBengali-VF.ttf<\/font>\n    <font weight="700" style="normal">NotoSansBengaliUI-VF.ttf<\/font>\n<\/family>' "$xml"
        done
        status_ok "Static Bengali installed (3-file mode, Regular/Medium/Bold only)"
      fi
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
  [ -z "$VF_SERIF_UPRIGHT_AXIS_META" ] && prune_obsolete_profile_keys SERIF_UPRIGHT
  [ -z "$VF_SERIF_ITALIC_AXIS_META" ] && prune_obsolete_profile_keys SERIF_ITALIC
  status_ok "Native Serif font (bundled in DroidSans.ttf)"
else
  _serif_dirs=$(get_category_dirs Serif)
  ext_s_reg=$(find_first 'Serif*.ttf' "$FONT_DIR" $_serif_dirs)
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_first 'Serif*.otf' "$FONT_DIR" $_serif_dirs)
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_first 'NotoSerif*.ttf' "$FONT_DIR" $_serif_dirs)
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_best_face 400 normal $_serif_dirs)
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_first '*.ttf' $_serif_dirs)
  [ -z "$ext_s_reg" ] && ext_s_reg=$(find_first '*.otf' $_serif_dirs)

  if [ -n "$ext_s_reg" ]; then
    if is_variable_font "$ext_s_reg"; then
      # Variable serif: copy to stock serif slots, generate axis XML
      cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-Regular.ttf"
      cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-Bold.ttf"
      axes_info=$(extract_fvar_axes "$ext_s_reg")
      frag_file="$FONT_DIR/ext_serif.xml"
      generate_vf_xml_fragment "$ext_s_reg" "NotoSerif-Regular.ttf" "$axes_info" normal > "$frag_file"
      configure_variable_family_profile SERIF_UPRIGHT "$ext_s_reg" normal "100 200 300 400 500 600 700 800 900" "$frag_file"

      ext_s_ital=$(find_first '*Italic*.ttf' $_serif_dirs)
      [ -z "$ext_s_ital" ] && ext_s_ital=$(find_first '*Italic*.otf' $_serif_dirs)
      [ -z "$ext_s_ital" ] && ext_s_ital=$(find_best_face 400 italic $_serif_dirs)
      if [ -n "$ext_s_ital" ] && is_variable_font "$ext_s_ital"; then
        cp -f "$ext_s_ital" "$SYS_FONT/NotoSerif-Italic.ttf"
        cp -f "$ext_s_ital" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
        axes_ital_info=$(extract_fvar_axes "$ext_s_ital")
        frag_ital_file="$FONT_DIR/ext_serif_ital.xml"
        generate_vf_xml_fragment "$ext_s_ital" "NotoSerif-Italic.ttf" "$axes_ital_info" italic > "$frag_ital_file"
        configure_variable_family_profile SERIF_ITALIC "$ext_s_ital" italic "100 200 300 400 500 600 700 800 900" "$frag_ital_file"
        cat "$frag_ital_file" >> "$frag_file"
      else
        cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-Italic.ttf"
        cp -f "$ext_s_reg" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
        prune_obsolete_profile_keys SERIF_ITALIC
      fi

      for xml in "$SYS_XML" "$SYS_FALLBACK"; do
        [ -f "$xml" ] || continue
        replace_family "$xml" serif "$frag_file" "split"
        replace_family "$xml" noto-serif "$frag_file" "split"
      done
      status_ok "Variable Serif font (${ext_s_reg##*/}) auto-configured natively"
    else
      prune_obsolete_profile_keys SERIF_UPRIGHT
      prune_obsolete_profile_keys SERIF_ITALIC
      # ── Static family: discover all distinct weights + styles, bundle into NotoSerif-Regular.ttf TTC ──
      # POSIX-sh ordered list — no declare -A (not supported in mksh/ash)
      _serif_ttc_files=""
      _serif_idx_counter=0

      _serif_get_idx() {
        local needle="$1" i=0 line
        [ -n "$needle" ] || { echo "0"; return; }
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          [ "$line" = "$needle" ] && echo "$i" && return
          i=$((i+1))
        done << EOF
$_serif_ttc_files
EOF
        i=0
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          [ "$line" = "$_sr400" ] && echo "$i" && return
          i=$((i+1))
        done << EOF
$_serif_ttc_files
EOF
        echo "0"
      }

      _serif_add_face() {
        local file="$1" line already=0
        [ -n "$file" ] || return
        while IFS= read -r line; do
          [ "$line" = "$file" ] && already=1 && break
        done << EOF
$_serif_ttc_files
EOF
        [ "$already" = "0" ] && {
          _serif_ttc_files="${_serif_ttc_files:+$_serif_ttc_files
}$file"
          _serif_idx_counter=$((_serif_idx_counter + 1))
        }
      }

      frag_file="$FONT_DIR/ext_serif.xml"

      # ── Detect Python + fontTools (weight-scan + TTC build) ───────────────
      local py_bin=""
      command -v python3 >/dev/null 2>&1 && py_bin="python3"
      [ -z "$py_bin" ] && command -v python >/dev/null 2>&1 && py_bin="python"
      if [ -n "$py_bin" ] && ! $py_bin -c "import fontTools" 2>/dev/null; then
        if [ -d "/data/data/com.termux/files/usr/bin" ]; then
          status_skip "fontTools not found. Auto-installing via Termux pip..."
          su -c "env PATH=/data/data/com.termux/files/usr/bin:\$PATH pip install fonttools brotli 2>&1" || true
          $py_bin -c "import fontTools" 2>/dev/null || py_bin=""
          [ -z "$py_bin" ] && status_skip "fontTools install failed — falling back to filename-based mode"
        else
          py_bin=""
        fi
      fi

      # ── Weight discovery: OS/2 usWeightClass (Python) or filename heuristic ─
      _sr100="" _sr200="" _sr300="" _sr400="" _sr500="" _sr600="" _sr700="" _sr800="" _sr900=""
      _si100="" _si300="" _si400="" _si700=""

      if [ -n "$py_bin" ] && $py_bin -c "import fontTools" 2>/dev/null; then
        _py_serif_map=$(_py_scan_font_weights $_serif_dirs)
        if [ -n "$_py_serif_map" ]; then
          while IFS= read -r _wl; do
            [ -z "$_wl" ] && continue
            _wt=${_wl%%:*}; _rest=${_wl#*:}; _sty=${_rest%%:*}; _fp=${_rest#*:}
            if [ "$_sty" = "normal" ]; then
              case "$_wt" in
                100) [ -z "$_sr100" ] && _sr100="$_fp" ;;
                200) [ -z "$_sr200" ] && _sr200="$_fp" ;;
                300) [ -z "$_sr300" ] && _sr300="$_fp" ;;
                400) [ -z "$_sr400" ] && _sr400="$_fp" ;;
                500) [ -z "$_sr500" ] && _sr500="$_fp" ;;
                600) [ -z "$_sr600" ] && _sr600="$_fp" ;;
                700) [ -z "$_sr700" ] && _sr700="$_fp" ;;
                800) [ -z "$_sr800" ] && _sr800="$_fp" ;;
                900) [ -z "$_sr900" ] && _sr900="$_fp" ;;
              esac
            elif [ "$_sty" = "italic" ]; then
              case "$_wt" in
                100) [ -z "$_si100" ] && _si100="$_fp" ;;
                300) [ -z "$_si300" ] && _si300="$_fp" ;;
                400) [ -z "$_si400" ] && _si400="$_fp" ;;
                700) [ -z "$_si700" ] && _si700="$_fp" ;;
              esac
            fi
          done << EOF
$_py_serif_map
EOF
        fi
      fi

      # Fallback: filename heuristic for any slots not filled by Python scan
      [ -z "$_sr100" ] && _sr100=$(find_best_face 100 normal $_serif_dirs)
      [ -z "$_sr200" ] && _sr200=$(find_best_face 200 normal $_serif_dirs)
      [ -z "$_sr300" ] && _sr300=$(find_best_face 300 normal $_serif_dirs)
      [ -z "$_sr400" ] && _sr400=$(find_best_face 400 normal $_serif_dirs)
      [ -z "$_sr500" ] && _sr500=$(find_best_face 500 normal $_serif_dirs)
      [ -z "$_sr600" ] && _sr600=$(find_best_face 600 normal $_serif_dirs)
      [ -z "$_sr700" ] && _sr700=$(find_best_face 700 normal $_serif_dirs)
      [ -z "$_sr800" ] && _sr800=$(find_best_face 800 normal $_serif_dirs)
      [ -z "$_sr900" ] && _sr900=$(find_best_face 900 normal $_serif_dirs)
      [ -z "$_sr400" ] && _sr400="$ext_s_reg"
      [ -z "$_si400" ] && _si400=$(find_best_face 400 italic $_serif_dirs)
      [ -z "$_si700" ] && _si700=$(find_best_face 700 italic $_serif_dirs)
      [ -z "$_si100" ] && _si100=$(find_best_face 100 italic $_serif_dirs)
      [ -z "$_si300" ] && _si300=$(find_best_face 300 italic $_serif_dirs)

      # Register all distinct real files (upright first, then italic)
      _serif_add_face "$_sr100"; _serif_add_face "$_sr200"; _serif_add_face "$_sr300"
      _serif_add_face "$_sr400"; _serif_add_face "$_sr500"; _serif_add_face "$_sr600"
      _serif_add_face "$_sr700"; _serif_add_face "$_sr800"; _serif_add_face "$_sr900"
      _serif_add_face "$_si100"; _serif_add_face "$_si300"
      _serif_add_face "$_si400"; _serif_add_face "$_si700"

      if [ -z "$py_bin" ] && [ "$_serif_idx_counter" -gt 4 ]; then
        status_skip "WARNING: Multiple Serif faces detected but Termux+Python not found."
        status_skip "Install Termux and run: pip install fonttools — then reflash."
        status_skip "Falling back to 4-file install (Regular/Italic/Bold/BoldItalic only)."
      fi

      if [ -n "$py_bin" ] && $py_bin -c "import fontTools" 2>/dev/null; then
        _serif_ttc_out="$SYS_FONT/NotoSerif-Regular.ttf"
        _serif_ttc_err=$(printf '%s\n' "$_serif_ttc_files" | $py_bin -c '
import sys
from fontTools.ttLib import TTFont, TTCollection
out = sys.argv[1]
files = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
if not files:
    sys.exit(1)
col = TTCollection()
for f in files:
    try:
        col.fonts.append(TTFont(f))
    except Exception as e:
        sys.stderr.write(f"Error loading {f}: {e}\n")
if not col.fonts:
    sys.exit(1)
col.save(out)
' "$_serif_ttc_out" 2>&1)
        if [ ! -f "$_serif_ttc_out" ] || [ ! -s "$_serif_ttc_out" ]; then
          status_warn "Serif TTC bundling failed — falling back to 4-file mode"
          [ -n "$_serif_ttc_err" ] && mffm_log_line "  TTC error: $_serif_ttc_err"
          local _sfb_reg="$_sr400"
          local _sfb_ital="${_si400:-$_sr400}"
          local _sfb_bold="${_sr700:-${_sr600:-$_sr400}}"
          local _sfb_bital="${_si700:-$_sfb_ital}"
          cp -f "$_sfb_reg"  "$SYS_FONT/NotoSerif-Regular.ttf"
          cp -f "$_sfb_ital" "$SYS_FONT/NotoSerif-Italic.ttf"
          cp -f "$_sfb_bold" "$SYS_FONT/NotoSerif-Bold.ttf"
          cp -f "$_sfb_bital" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
          status_ok "Static Serif installed (4-file fallback: Regular/Italic/Bold/BoldItalic)"
        else
          # Replicate TTC to remaining stock serif slots
          cp -f "$_serif_ttc_out" "$SYS_FONT/NotoSerif-Italic.ttf"
          cp -f "$_serif_ttc_out" "$SYS_FONT/NotoSerif-Bold.ttf"
          cp -f "$_serif_ttc_out" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
          # Build XML: upright + italic entries
          {
            [ -n "$_sr100" ] && printf '    <font weight="100" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr100")"
            [ -n "$_sr200" ] && printf '    <font weight="200" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr200")"
            [ -n "$_sr300" ] && printf '    <font weight="300" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr300")"
            printf '    <font weight="400" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr400")"
            [ -n "$_sr500" ] && printf '    <font weight="500" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr500")"
            [ -n "$_sr600" ] && printf '    <font weight="600" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr600")"
            [ -n "$_sr700" ] && printf '    <font weight="700" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr700")"
            [ -n "$_sr800" ] && printf '    <font weight="800" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr800")"
            [ -n "$_sr900" ] && printf '    <font weight="900" style="normal" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_sr900")"
            # Italic entries
            [ -n "$_si100" ] && printf '    <font weight="100" style="italic" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_si100")"
            [ -n "$_si300" ] && printf '    <font weight="300" style="italic" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_si300")"
            [ -n "$_si400" ] && printf '    <font weight="400" style="italic" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_si400")"
            [ -n "$_si700" ] && printf '    <font weight="700" style="italic" index="%s">NotoSerif-Regular.ttf</font>\n' "$(_serif_get_idx "$_si700")"
          } > "$frag_file"
          for xml in "$SYS_XML" "$SYS_FALLBACK"; do
            [ -f "$xml" ] || continue
            replace_family "$xml" serif "$frag_file" "split"
            replace_family "$xml" noto-serif "$frag_file" "split"
          done
          status_ok "Static Serif TTC bundled ($_serif_idx_counter distinct faces → NotoSerif-Regular.ttf, indexed)"
        fi  # TTC success/failure
      else
        # ── 4-file fallback: no Python/fontTools available ───────────────────
        local _sfb_reg="$_sr400"
        local _sfb_ital="${_si400:-$_sr400}"
        local _sfb_bold="${_sr700:-${_sr600:-$_sr400}}"
        local _sfb_bital="${_si700:-$_sfb_ital}"
        cp -f "$_sfb_reg"  "$SYS_FONT/NotoSerif-Regular.ttf"
        cp -f "$_sfb_ital" "$SYS_FONT/NotoSerif-Italic.ttf"
        cp -f "$_sfb_bold" "$SYS_FONT/NotoSerif-Bold.ttf"
        cp -f "$_sfb_bital" "$SYS_FONT/NotoSerif-BoldItalic.ttf"
        status_ok "Static Serif installed (4-file fallback: Regular/Italic/Bold/BoldItalic)"
      fi  # py_bin
    fi  # is_variable_font else static
  else
    prune_obsolete_profile_keys SERIF_UPRIGHT
    prune_obsolete_profile_keys SERIF_ITALIC
    status_skip "Dedicated serif fonts not supplied"
  fi  # ext_s_reg
fi  # Serif section

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
if [ -n "$VF_CONFIG_FILE" ] && [ -f "$VF_CONFIG_FILE" ]; then
  if ! grep -Eq '^[[:space:]]*[A-Z_]+_(WGHT|WDTH)=' "$VF_CONFIG_FILE" 2>/dev/null; then
    rm -f "$VF_CONFIG_FILE" 2>/dev/null
    VF_CONFIG_FILE=""
  fi
fi

# Clean leftover configuration files belonging to previous/other modules in /sdcard/MFFM
if [ -d "$MFFM_DIR" ]; then
  for old_conf in "$MFFM_DIR"/*.conf "$MFFM_DIR"/MFFMv14_*.conf; do
    [ -f "$old_conf" ] || continue
    [ -n "$VF_CONFIG_FILE" ] && [ "$old_conf" = "$VF_CONFIG_FILE" ] && continue
    rm -f "$old_conf" 2>/dev/null
  done
fi

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
