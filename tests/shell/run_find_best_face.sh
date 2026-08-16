#!/bin/sh
# Exercises find_best_face extracted live from template/customize.sh so the
# flash-time filename weight heuristic cannot drift from the expectations in
# tests/weight_vectors.json.
#
# Usage: run_find_best_face.sh <customize.sh> <workdir>
# stdin : one case per line: <target_weight> <target_style> <file,file,...>
# stdout: one line per case: <case-number> <basename|NONE>

set -eu

CUSTOMIZE_SH=$1
WORKDIR=$2
FACES=$WORKDIR/faces
mkdir -p "$FACES"

awk '/^find_best_face\(\) \{/,/^\}/' "$CUSTOMIZE_SH" > "$WORKDIR/funcs.sh"
# shellcheck source=/dev/null
. "$WORKDIR/funcs.sh"

n=0
while read -r weight style files; do
  n=$((n + 1))
  # Tolerate CRLF input (e.g. contributors on Windows)
  files=$(printf '%s' "$files" | tr -d '\r')
  dir=$FACES/$n
  mkdir "$dir"
  saved_ifs=$IFS
  IFS=,
  for name in $files; do
    : > "$dir/$name"
  done
  IFS=$saved_ifs
  result=$(find_best_face "$weight" "$style" "$dir" || true)
  if [ -n "$result" ]; then
    printf '%s %s\n' "$n" "${result##*/}"
  else
    printf '%s NONE\n' "$n"
  fi
  rm -rf "$dir"
done
