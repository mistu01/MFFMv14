#!/system/bin/sh
# ==============================================================================
# MFFMv14 Boot Service
# Copyright © 2026 MFFM / Mistu
# Last modified: 2026-06-18
# ==============================================================================
# Disable Google Play Services font downloads after boot so they cannot override the module.

until [ "$(getprop sys.boot_completed 2>/dev/null)" = "1" ]; do sleep 2; done
sleep 2

GMS=com.google.android.gms
if pm path "$GMS" >/dev/null 2>&1 || cmd package path "$GMS" >/dev/null 2>&1; then
  for component in \
    com.google.android.gms.fonts.provider.FontsProvider \
    com.google.android.gms.fonts.update.UpdateSchedulerService
  do
    pm disable "$GMS/$component" >/dev/null 2>&1 || \
      pm disable-user --user 0 "$GMS/$component" >/dev/null 2>&1 || \
      cmd package disable-user --user 0 "$GMS/$component" >/dev/null 2>&1
  done
  rm -rf /data/fonts 2>/dev/null
  rm -rf /data/data/com.google.android.gms/files/fonts/opentype/* 2>/dev/null
  rm -rf /data/user/0/com.google.android.gms/files/fonts/opentype/* 2>/dev/null
fi
