#!/system/bin/sh
# Re-apply OverlayFS opacity for KernelSU/APatch after their mount stage.

MODDIR=${0%/*}
if [ "$KSU" = "true" ] || [ "$APATCH" = "true" ]; then
  if command -v setfattr >/dev/null 2>&1; then
    for directory in \
      "$MODDIR/system/fonts" \
      "$MODDIR/system/product/fonts" \
      "$MODDIR/system/etc" \
      "$MODDIR/system/product/etc"
    do
      [ -d "$directory" ] && setfattr -n trusted.overlay.opaque -v y "$directory" 2>/dev/null
    done
  fi
fi

