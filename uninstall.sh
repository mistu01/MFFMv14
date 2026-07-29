#!/system/bin/sh
# Restore Google font-provider components when module is uninstalled.

GMS=com.google.android.gms
for component in \
  com.google.android.gms.fonts.provider.FontsProvider \
  com.google.android.gms.fonts.update.UpdateSchedulerService
do
  pm enable "$GMS/$component" >/dev/null 2>&1 || cmd package enable "$GMS/$component" >/dev/null 2>&1
done
