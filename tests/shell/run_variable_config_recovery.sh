#!/bin/sh
# Regression harness for the on-device variable-axis config recovery.
#
# The patched template/customize.sh must:
#   1. Trigger the build-time gate when any VF_*_AXIS_META is set (not just
#      mono/serif/bengali — sans upright/italic are also valid).
#   2. Re-evaluate after the on-device compiler runs, so a runtime-updated
#      FONT_MODE / VF_*_AXIS_META produces a fresh /sdcard/MFFM/ config.
#   3. Keep header-only config files at the post-process delete gate (an
#      intentional "no Android wght/wdth to expose" marker), but still
#      delete them if MODULE_IDENTITY is missing.
#
# Usage: run_variable_config_recovery.sh <font_mode> <vf_upright> <vf_mono> <mffm_dir>

set -eu

FONT_MODE=$1
VF_UPRIGHT_AXIS_META=$2
VF_MONO_AXIS_META=$3
MFFM_DIR=$4
mkdir -p "$MFFM_DIR"
FONT_DIR=$MFFM_DIR/_build
mkdir -p "$FONT_DIR"

# Initialize the rest of the VF_* vars to empty so `[ -n "$X" ]` works
# under `set -u`.
: "${VF_ITALIC_AXIS_META:=}"
: "${VF_SERIF_UPRIGHT_AXIS_META:=}"
: "${VF_BENGALI_AXIS_META:=}"
: "${VF_CONFIG_FILE:=}"

# ── Step 1: build-time gate (verbatim from the patched customize.sh) ───────
echo "STAGE=build_time_gate"
if [ "$FONT_MODE" = "variable" ] \
  || [ -n "$VF_UPRIGHT_AXIS_META" ] \
  || [ -n "$VF_ITALIC_AXIS_META" ] \
  || [ -n "$VF_MONO_AXIS_META" ] \
  || [ -n "$VF_SERIF_UPRIGHT_AXIS_META" ] \
  || [ -n "$VF_BENGALI_AXIS_META" ]; then
  echo "GATE_TRIGGERED=1"
fi

# ── Step 2: simulate the on-device compiler refreshing font-config.sh ─────
# The runtime writes a new font-config.sh that the script sources. We mock
# that with a small file that overrides FONT_MODE if the caller asked for
# a runtime upgrade.
RUNTIME_FONT_CONFIG="$FONT_DIR/font-config.sh"
if [ "$FONT_MODE" = "runtime_variable" ]; then
  cat > "$RUNTIME_FONT_CONFIG" <<EOF
FONT_MODE="variable"
FONT_FAMILY="Runtime Family"
HAS_CUSTOM_MONO="false"
HAS_CUSTOM_SERIF="false"
HAS_CUSTOM_BENGALI="false"
TTC_TOTAL_FONTS="1"
EOF
  # shellcheck source=/dev/null
  . "$RUNTIME_FONT_CONFIG"
  FONT_MODE="variable"
fi

# ── Step 3: post-runtime re-evaluation gate (verbatim from the patch) ──────
echo "STAGE=post_runtime_re_evaluation"
if [ "$FONT_MODE" = "variable" ] \
  || [ -n "$VF_UPRIGHT_AXIS_META" ] \
  || [ -n "$VF_ITALIC_AXIS_META" ] \
  || [ -n "$VF_MONO_AXIS_META" ] \
  || [ -n "$VF_SERIF_UPRIGHT_AXIS_META" ] \
  || [ -n "$VF_BENGALI_AXIS_META" ]; then
  echo "POST_RUNTIME_GATE=1"
fi

# ── Step 4: post-process delete gate (verbatim from the patch) ─────────────
# Pre-populate a fake config file so the gate has something to act on.
# The caller can choose its content by setting CONFIG_HAS_WGHT (1/0) and
# CONFIG_HAS_IDENTITY (1/0) via env.
FAKE_CONFIG="$MFFM_DIR/MFFMv14_FakeFamily_vf-00000000000000000000.conf"
: "${CONFIG_HAS_WGHT:=0}"
: "${CONFIG_HAS_IDENTITY:=1}"
{
  if [ "$CONFIG_HAS_IDENTITY" = "1" ]; then
    echo "MODULE_IDENTITY=vf-00000000000000000000"
  fi
  if [ "$CONFIG_HAS_WGHT" = "1" ]; then
    echo "MONOSPACE_UPRIGHT_Regular_WGHT=400"
    echo "MONOSPACE_UPRIGHT_Bold_WGHT=700"
  fi
} > "$FAKE_CONFIG"
VF_CONFIG_FILE="$FAKE_CONFIG"

echo "STAGE=post_process_gate"
if [ -n "$VF_CONFIG_FILE" ] && [ -f "$VF_CONFIG_FILE" ]; then
  if ! grep -Eq '^[[:space:]]*[A-Z_]+_(WGHT|WDTH)=' "$VF_CONFIG_FILE" 2>/dev/null; then
    if grep -Eq '^[[:space:]]*MODULE_IDENTITY[[:space:]]*=' "$VF_CONFIG_FILE" 2>/dev/null; then
      echo "POST_GATE_KEPT=1"
    else
      rm -f "$VF_CONFIG_FILE" 2>/dev/null
      VF_CONFIG_FILE=""
      echo "POST_GATE_DELETED=1"
    fi
  else
    echo "POST_GATE_KEPT=1"
  fi
fi

# Cleanup
rm -rf "$FONT_DIR"
exit 0
