#!/system/bin/sh
# MFFM Runtime uninstall
# By default we keep /data/adb/mffm_runtime to avoid breaking existing font modules that depend on it.
# Remove manually if desired: rm -rf /data/adb/mffm_runtime

# Do NOT auto-remove /data/adb/mffm_runtime — font modules depend on it
# Uncomment to fully clean:
# rm -rf /data/adb/mffm_runtime 2>/dev/null

