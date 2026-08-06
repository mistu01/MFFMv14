#!/data/data/com.termux/files/usr/bin/env sh
# MFFMv14 one-shot builder for Termux: installs the toolchain, builds the module and flashes it.
#
#   sh termux-build.sh [options] [-- build.py options...]
#
# Run it as the normal Termux user. Only the flashing step needs root and it acquires that itself
# through `su`, because `pkg` breaks when it is run as root.

set -eu

PROJECT_DIR=$(unset CDPATH && cd -- "$(dirname -- "$0")" && pwd)
SKIP_DEPS=0
SKIP_FLASH=0
ASSUME_YES=0
CUSTOM_FONTS_DIR=0

RED=''
GREEN=''
YELLOW=''
BOLD=''
RESET=''
if [ -t 1 ]; then
  RED=$(printf '\033[31m')
  GREEN=$(printf '\033[32m')
  YELLOW=$(printf '\033[33m')
  BOLD=$(printf '\033[1m')
  RESET=$(printf '\033[0m')
fi

say() { printf '%s==>%s %s\n' "$BOLD" "$RESET" "$1"; }
ok() { printf '  %s[OK]%s %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '  %s[!!]%s %s\n' "$YELLOW" "$RESET" "$1" >&2; }
die() {
  printf '%serror:%s %s\n' "$RED" "$RESET" "$1" >&2
  exit 1
}

# su -c takes a single command string, so a path interpolated into it must be quoted for that shell.
shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

usage() {
  cat <<'EOF'
usage: sh termux-build.sh [options] [-- build.py options...]

  --no-deps     skip package installation (use an already prepared environment)
  --no-flash    build only; do not install the module with su
  --yes         do not ask for confirmation before flashing
  -h, --help    show this help

Anything after -- is passed to build.py, for example:
  sh termux-build.sh -- --mode variable --fonts-dir ~/storage/shared/Download/MyFont
EOF
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case $1 in
    --no-deps) SKIP_DEPS=1; shift ;;
    --no-flash) SKIP_FLASH=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    -h|--help) usage 0 ;;
    --) shift; break ;;
    *) die "unknown option: $1 (build.py options go after --)" ;;
  esac
done
# Forwarded options stay in "$@" so paths containing spaces survive; only inspect them here.
for arg in "$@"; do
  case $arg in
    --fonts-dir|--fonts-dir=*) CUSTOM_FONTS_DIR=1 ;;
  esac
done

# --- environment -----------------------------------------------------------------------------

say "Checking the environment"
[ -n "${PREFIX:-}" ] && [ -d "$PREFIX" ] || die "\$PREFIX is not set; this script is for Termux"
command -v pkg >/dev/null 2>&1 || die "pkg is missing; this script is for Termux"
[ "$(id -u)" != "0" ] || die "run this as the normal Termux user, not root: pkg refuses to work as root
(the script uses su on its own for the flashing step)"
[ -f "$PROJECT_DIR/build.py" ] || die "$PROJECT_DIR does not look like an MFFMv14 checkout"
ok "Termux, $PROJECT_DIR"

# Shared storage is mounted noexec, so a checkout there cannot execute the downloaded signer.
probe="$PROJECT_DIR/.mffm-exec-probe"
printf '#!%s/bin/sh\nexit 0\n' "$PREFIX" >"$probe" 2>/dev/null ||
  die "cannot write to $PROJECT_DIR"
chmod +x "$probe" 2>/dev/null || true
if "$probe" 2>/dev/null; then
  ok "the project directory allows execution (the signer can run)"
else
  warn "$PROJECT_DIR is mounted noexec, so the ZIP signer cannot run here."
  warn "Building unsigned instead; move the project to \$HOME to get signed ZIPs."
  set -- "$@" --no-sign
fi
rm -f "$probe"

# --- dependencies ----------------------------------------------------------------------------

if [ "$SKIP_DEPS" = "1" ]; then
  say "Skipping package installation (--no-deps)"
else
  say "Installing the toolchain"
  # brotli and cryptography are C/Rust extensions: the Termux packages are prebuilt, while pip would
  # compile them from source and cryptography needs a full Rust toolchain to do that.
  pkg install -y python python-pip openssl python-brotli python-cryptography ||
    die "pkg install failed; run 'pkg update' and try again"
  ok "python, openssl, brotli, cryptography"
  python -m pip install --quiet --upgrade pip || warn "could not upgrade pip; continuing"
  python -m pip install --quiet -r "$PROJECT_DIR/requirements.txt" ||
    die "pip install -r requirements.txt failed"
  ok "fonttools, opentype-feature-freezer"
fi

python -c 'import fontTools' 2>/dev/null || die "fontTools is not importable; re-run without --no-deps"

if [ ! -d "$HOME/storage" ]; then
  warn "shared storage is not set up; run 'termux-setup-storage' to build from fonts in /sdcard"
fi

# --- build -----------------------------------------------------------------------------------

say "Building the module"
cd "$PROJECT_DIR"
FONTS_DIR="$PROJECT_DIR/Fonts"
[ "$CUSTOM_FONTS_DIR" = "0" ] || FONTS_DIR=""
if [ -n "$FONTS_DIR" ] && [ -z "$(find "$FONTS_DIR" -type f \
  \( -iname '*.ttf' -o -iname '*.otf' -o -iname '*.ttc' -o -iname '*.otc' -o -iname '*.woff' \
  -o -iname '*.woff2' \) 2>/dev/null | head -n 1)" ]; then
  die "no fonts in $FONTS_DIR
Put them there, or pass a directory: sh termux-build.sh -- --fonts-dir ~/storage/shared/Download/MyFont"
fi

BUILD_LOG="$PROJECT_DIR/.mffm-build-log"
BUILD_STATUS="$PROJECT_DIR/.mffm-build-status"
{ python build.py --no-interactive "$@"; printf '%s\n' "$?" >"$BUILD_STATUS"; } | tee "$BUILD_LOG"
build_status=$(cat "$BUILD_STATUS" 2>/dev/null || echo 1)
rm -f "$BUILD_STATUS"
[ "$build_status" = "0" ] || { rm -f "$BUILD_LOG"; die "build.py failed (exit $build_status)"; }

# build.py prints the ZIP it wrote as its "Output" line. Taking the path from there instead of
# guessing the newest file in dist/ keeps --output-dir working and can never pick an earlier run's
# ZIP, however the filesystem happens to order timestamps.
ZIP=$(sed -n 's/^Output *: *//p' "$BUILD_LOG" | tail -n 1)
rm -f "$BUILD_LOG"
if [ -z "$ZIP" ]; then
  say "The build wrote no ZIP (--no-zip), so there is nothing to install"
  exit 0
fi
[ -f "$ZIP" ] || die "build.py reported $ZIP but that file does not exist"
ok "$ZIP"

# --- flash -----------------------------------------------------------------------------------

if [ "$SKIP_FLASH" = "1" ]; then
  say "Not flashing (--no-flash)"
  quoted=$(shell_quote "$ZIP")
  printf '\nFlash it from your manager app, or with the CLI of your root manager:\n'
  printf '  su -c "magisk --install-module %s"   # Magisk\n' "$quoted"
  printf '  su -c "ksud module install %s"       # KernelSU\n' "$quoted"
  printf '  su -c "apd module install %s"        # APatch\n' "$quoted"
  exit 0
fi

say "Installing the module"
if ! command -v su >/dev/null 2>&1 || [ "$(su -c 'id -u' 2>/dev/null)" != "0" ]; then
  warn "no root shell available; the ZIP was built but not installed"
  printf '\nCopy it out and flash it from your manager app:\n  cp %s ~/storage/shared/Download/\n' "$(shell_quote "$ZIP")"
  exit 0
fi

INSTALL_CMD=""
for candidate in magisk ksud apd; do
  if su -c "command -v $candidate" >/dev/null 2>&1; then
    case $candidate in
      magisk) INSTALL_CMD="magisk --install-module" ;;
      ksud) INSTALL_CMD="ksud module install" ;;
      apd) INSTALL_CMD="apd module install" ;;
    esac
    break
  fi
done
if [ -z "$INSTALL_CMD" ]; then
  warn "found root but no magisk/ksud/apd; flash from your manager app instead"
  printf '\n  cp %s ~/storage/shared/Download/\n' "$(shell_quote "$ZIP")"
  exit 0
fi

if [ "$ASSUME_YES" != "1" ]; then
  printf 'Install with "%s"? [y/N] ' "$INSTALL_CMD"
  # Without a terminal read hits EOF; treat that as a decline instead of exiting silently.
  read -r answer || answer=""
  case $answer in
    y|Y|yes|YES) ;;
    *) die "aborted; the ZIP is at $ZIP" ;;
  esac
fi

su -c "$INSTALL_CMD $(shell_quote "$ZIP")" ||
  die "$INSTALL_CMD failed; try flashing $ZIP from your manager app"
ok "installed with $INSTALL_CMD"

printf '\n%sReboot to apply the font.%s\n' "$BOLD" "$RESET"
CONF=$(ls -1t "$HOME"/storage/shared/MFFM/MFFMv14_*.conf 2>/dev/null | head -n 1)
if [ -n "$CONF" ]; then
  printf 'Variable axes: edit %s, then run "su -c font-config" and reboot.\n' "$CONF"
fi
