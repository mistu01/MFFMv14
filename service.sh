#!/system/bin/sh
# Disable Google Play Services font downloads post-boot to prevent overrides.

boot_wait=0
until [ "$(getprop sys.boot_completed 2>/dev/null)" = "1" ]; do
  boot_wait=$((boot_wait + 1))
  [ "$boot_wait" -gt 150 ] && exit 0
  sleep 2
done
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
