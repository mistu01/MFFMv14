#!/system/bin/sh
MODDIR=${0%/*}
RUNTIME_DEST="/data/adb/mffm_runtime"
[ -d "$RUNTIME_DEST" ] && chmod -R 755 "$RUNTIME_DEST" 2>/dev/null
