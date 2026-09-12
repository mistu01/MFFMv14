#!/system/bin/sh
# ==============================================================================
# MFFMv14 Google Font Update Neutralizer (Service Daemon)
#
# Automatically executes at late-start service boot stage to check,
# clear, and prevent Google/AOSP font updates from overriding system fonts.
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

log_msg() {
  local timestamp sd_dir
  timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "N/A")
  printf '[%s] [SERVICE] %s\n' "$timestamp" "$1" >> "$LOG_FILE" 2>/dev/null
  sd_dir=$(get_mffm_dir)
  if [ -d "$sd_dir" ]; then
    printf '[%s] [SERVICE] %s\n' "$timestamp" "$1" >> "$sd_dir/font_service.log" 2>/dev/null
  fi
}

neutralize_google_fonts() {
  local reason="${1:-boot}"
  log_msg "Executing neutralization routine (trigger: $reason)..."

  # 1. Reset AOSP FontManagerService updatable configuration
  if command -v cmd >/dev/null 2>&1; then
    cmd_res=$(cmd font clear 2>&1)
    log_msg "cmd font clear result: $cmd_res"
  fi

  # 2. Purge staged /data/fonts updates
  if [ -d "/data/fonts" ] || [ -f "/data/system/font_fallback.xml" ]; then
    rm -rf /data/fonts/files/* 2>/dev/null
    rm -rf /data/fonts/config/* 2>/dev/null
    rm -rf /data/fonts/* 2>/dev/null
    rm -rf /data/fonts 2>/dev/null
    rm -rf /data/system/font_fallback.xml 2>/dev/null
    log_msg "Purged /data/fonts directory and fallback XML"
  fi

  # 3. Disable Google Play Services font update components
  if pm path "$GMS" >/dev/null 2>&1 || cmd package path "$GMS" >/dev/null 2>&1; then
    for component in \
      com.google.android.gms.fonts.provider.FontsProvider \
      com.google.android.gms.fonts.update.UpdateSchedulerService
    do
      pm disable "$GMS/$component" >/dev/null 2>&1 || \
        pm disable-user --user 0 "$GMS/$component" >/dev/null 2>&1 || \
        cmd package disable-user --user 0 "$GMS/$component" >/dev/null 2>&1
    done

    # 4. Clear GMS downloaded font caches
    rm -rf /data/data/com.google.android.gms/files/fonts/opentype/* 2>/dev/null
    rm -rf /data/data/com.google.android.gms/files/fonts/* 2>/dev/null
    rm -rf /data/user/0/com.google.android.gms/files/fonts/* 2>/dev/null
    rm -rf /data/user_de/0/com.google.android.gms/files/fonts/* 2>/dev/null
    rm -rf /data/data/com.google.android.gms/app_fonts/* 2>/dev/null
    log_msg "Disabled GMS font components and purged font caches"
  fi

  log_msg "Neutralization routine complete"
}

# Handle standalone daemon invocation
if [ "$1" = "--daemon" ]; then
  echo "$$" > "$MODDIR/service.pid"
  log_msg "Watcher daemon started (PID: $$)"
  while true; do
    sleep 3600
    if [ -d "/data/fonts" ] && [ "$(ls -A /data/fonts 2>/dev/null)" ]; then
      neutralize_google_fonts "watcher detected /data/fonts"
    fi
  done
  exit 0
fi

# ── Main Service Boot Sequence ────────────────────────────────────────────────
until [ "$(getprop sys.boot_completed 2>/dev/null)" = "1" ]; do
  sleep 2
done
sleep 2

# Wait for decrypted internal storage to become accessible so logs can mirror to /sdcard/MFFM
for _i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  _target_mffm=$(get_mffm_dir)
  [ -d "$_target_mffm" ] && break
  sleep 2
done

neutralize_google_fonts "boot_completed"

# Launch background watcher loop
(
  log_msg "Background watcher daemon starting..."
  while true; do
    sleep 3600
    if [ -d "/data/fonts" ] && [ "$(ls -A /data/fonts 2>/dev/null)" ]; then
      neutralize_google_fonts "watcher detected /data/fonts"
    fi
  done
) &
# Record the background subshell's PID ($! gives the last backgrounded process)
echo "$!" > "$MODDIR/service.pid"
log_msg "Background watcher daemon spawned (PID: $!)"


