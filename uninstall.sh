#!/system/bin/sh
# ==============================================================================
# MFFMv14 Uninstall Script
# Copyright © 2026 MFFM / Mistu
# Last modified: 2026-06-18
# ==============================================================================
# Restore Google font-provider components when the module is removed.

GMS=com.google.android.gms
for component in \
  com.google.android.gms.fonts.provider.FontsProvider \
  com.google.android.gms.fonts.update.UpdateSchedulerService
do
  pm enable "$GMS/$component" >/dev/null 2>&1 || cmd package enable "$GMS/$component" >/dev/null 2>&1
done
