#!/system/bin/sh
# MFFM Runtime - ensure runtime remains executable after boot
RUNTIME_DEST="/data/adb/mffm_runtime"
[ -d "$RUNTIME_DEST" ] && chmod -R 755 "$RUNTIME_DEST" 2>/dev/null
[ -x "$RUNTIME_DEST/bin/python3" ] && chmod 755 "$RUNTIME_DEST/bin/python3" 2>/dev/null
[ -x "$RUNTIME_DEST/bin/mffm-helper" ] && chmod 755 "$RUNTIME_DEST/bin/mffm-helper" 2>/dev/null
