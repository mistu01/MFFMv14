#!/system/bin/sh
# ==============================================================================
# MFFMv14 Google Font Update Neutralizer (Action Script)
#
# Executed via KernelSU / APatch / MMRL "Action" button or CLI:
#   su -c sh /data/adb/modules/<module_id>/action.sh
# ==============================================================================

MODDIR=${0%/*}
GMS="com.google.android.gms"
LOG_FILE="$MODDIR/font_service.log"

get_mffm_dir() {
  for _sbase in /sdcard /storage/emulated/0 /data/media/0 /mnt/pass_through/0/emulated/0; do
    if [ -d "$_sbase/MFFM" ]; then
      echo "$_sbase/MFFM"
      return 0
    fi
  done
  for _sbase in /sdcard /storage/emulated/0 /data/media/0 /mnt/pass_through/0/emulated/0; do
    if [ -d "$_sbase" ]; then
      mkdir -p "$_sbase/MFFM" 2>/dev/null
      if [ -d "$_sbase/MFFM" ]; then
        echo "$_sbase/MFFM"
        return 0
      fi
    fi
  done
  echo "/sdcard/MFFM"
}

ui_print() {
  echo "$1"
}

log_msg() {
  local timestamp sd_dir
  timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "N/A")
  printf '[%s] [ACTION] %s\n' "$timestamp" "$1" >> "$LOG_FILE" 2>/dev/null
  sd_dir=$(get_mffm_dir)
  if [ -d "$sd_dir" ]; then
    printf '[%s] [ACTION] %s\n' "$timestamp" "$1" >> "$sd_dir/font_service.log" 2>/dev/null
  fi
}

ui_print "===================================================="
ui_print "       MFFMv14 Google Font Update Neutralizer       "
ui_print "===================================================="
ui_print ""

log_msg "Manual action script triggered"

# ── 1. Check & Clear AOSP Updatable Fonts (FontManagerService) ────────────────
ui_print "[*] Checking AOSP FontManagerService (/data/fonts)..."
if [ -d "/data/fonts" ] && [ "$(ls -A /data/fonts 2>/dev/null)" ]; then
  ui_print "  [!] Staged Google font updates detected in /data/fonts"
else
  ui_print "  [*] No active staged fonts in /data/fonts"
fi

if command -v cmd >/dev/null 2>&1; then
  ui_print "[*] Resetting FontManagerService via 'cmd font clear'..."
  cmd_res=$(cmd font clear 2>&1)
  if [ $? -eq 0 ]; then
    ui_print "  [OK] FontManagerService configuration cleared"
    log_msg "cmd font clear succeeded: $cmd_res"
  else
    ui_print "  [WARN] 'cmd font clear' returned: $cmd_res (normal on older Android versions)"
    log_msg "cmd font clear warning: $cmd_res"
  fi
fi

# ── 2. Force Purge /data/fonts ────────────────────────────────────────────────
ui_print "[*] Purging /data/fonts hierarchy..."
rm -rf /data/fonts/files/* 2>/dev/null
rm -rf /data/fonts/config/* 2>/dev/null
rm -rf /data/fonts/* 2>/dev/null
rm -rf /data/fonts 2>/dev/null
rm -rf /data/system/font_fallback.xml 2>/dev/null
ui_print "  [OK] /data/fonts directory purged"
log_msg "/data/fonts purged"

# ── 3. Disable Google Play Services (GMS) Font Providers ─────────────────────
ui_print "[*] Neutralizing Google Play Services font updaters..."
gms_disabled_count=0
for component in \
  com.google.android.gms.fonts.provider.FontsProvider \
  com.google.android.gms.fonts.update.UpdateSchedulerService
do
  if pm disable "$GMS/$component" >/dev/null 2>&1 || \
     pm disable-user --user 0 "$GMS/$component" >/dev/null 2>&1 || \
     cmd package disable-user --user 0 "$GMS/$component" >/dev/null 2>&1; then
    gms_disabled_count=$((gms_disabled_count + 1))
  fi
done

if [ "$gms_disabled_count" -gt 0 ]; then
  ui_print "  [OK] Disabled $gms_disabled_count GMS font update components"
  log_msg "Disabled $gms_disabled_count GMS font components"
else
  ui_print "  [*] GMS font components already disabled or not present"
fi

# ── 4. Purge GMS Downloaded Font Caches ───────────────────────────────────────
ui_print "[*] Clearing GMS downloaded font caches..."
rm -rf /data/data/com.google.android.gms/files/fonts/opentype/* 2>/dev/null
rm -rf /data/data/com.google.android.gms/files/fonts/* 2>/dev/null
rm -rf /data/user/0/com.google.android.gms/files/fonts/* 2>/dev/null
rm -rf /data/user_de/0/com.google.android.gms/files/fonts/* 2>/dev/null
rm -rf /data/data/com.google.android.gms/app_fonts/* 2>/dev/null
ui_print "  [OK] GMS font caches cleared"
log_msg "GMS font caches cleared"

# ── 5. Check & Restart Background Protection Daemon ──────────────────────────
ui_print "[*] Verifying background protection service..."
daemon_pid=""
if [ -f "$MODDIR/service.pid" ]; then
  daemon_pid=$(cat "$MODDIR/service.pid" 2>/dev/null)
fi

if [ -n "$daemon_pid" ] && [ -d "/proc/$daemon_pid" ]; then
  ui_print "  [OK] Protection daemon is active (PID: $daemon_pid)"
else
  ui_print "  [!] Daemon not running — spawning fresh background protector..."
  if [ -f "$MODDIR/service.sh" ]; then
    sh "$MODDIR/service.sh" --daemon >/dev/null 2>&1 &
    ui_print "  [OK] Background protector started"
    log_msg "Protection daemon restarted via action.sh"
  fi
fi

ui_print ""
ui_print "===================================================="
ui_print "  [OK] Google Font Update Neutralization Complete!  "
ui_print "===================================================="
ui_print "Tip: If system fonts were overridden before this fix,"
ui_print "     reboot your device or restart SystemUI to apply."
ui_print ""

exit 0
