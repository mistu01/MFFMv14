#!/system/bin/sh
# MFFMv14 shared library: XML family rewriting and variable-axis substitution.
#
# Sourced by customize.sh during installation and by system/bin/font-config at runtime, so both
# paths produce byte-identical XML from the same inputs. Callers must define ui_print, status_ok,
# status_warn, status_skip and fail before sourcing this file.

PRODUCT_RUBIK_REGULAR="Rubik-Regular.ttf"
PRODUCT_RUBIK_ITALIC="Rubik-Italic.ttf"

replace_family() {
  xml=$1
  family=$2
  fragment_file=$3
  mode=${4:-"replace"}
  [ -f "$xml" ] || return 0
  [ -f "$fragment_file" ] || return 0
  grep -q "<family[^>]*name=\"$family\"" "$xml" 2>/dev/null || return 0
  # The awk program below assumes the opening tag, the fonts, and </family> are on separate lines.
  # A single-line or self-closing family would make it swallow everything up to the next </family>.
  if grep -qE "<family[^>]*name=\"$family\"[^>]*(/>|>.*</family>)" "$xml" 2>/dev/null; then
    status_warn "Skipping $family in ${xml##*/}: this ROM writes the family on one line"
    return 0
  fi
  fragment=$(cat "$fragment_file")
  awk -v target="$family" -v replacement="$fragment" -v mode="$mode" '
    !inside && index($0, "<family") > 0 && index($0, "name=\"" target "\"") > 0 {
      if (target == "sans-serif" || mode == "split") {
        print
        print replacement
        print "  </family>"
        print "  <family>"
      } else {
        print
        print replacement
      }
      inside=1
      next
    }
    inside {
      if (target == "sans-serif" || mode == "split" || mode == "prepend") {
        print
        if (index($0, "</family>") > 0) { inside=0 }
      } else {
        if (index($0, "</family>") > 0) { print; inside=0 }
      }
      next
    }
    { print }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"
}

# The Bengali families are keyed by lang/variant rather than name, so replace_family cannot be
# reused. awk keeps this consistent with the other XML edits: toybox sed mishandles `c\` with
# embedded newlines.
replace_beng_family() {
  local xml=$1 variant=$2 open_tag
  [ -f "$xml" ] || return 0
  open_tag="<family lang=\"und-Beng\" variant=\"$variant\">"
  grep -qF "$open_tag" "$xml" 2>/dev/null || return 0
  # Like replace_family, the awk program needs one element per line: it replaces whole lines, so
  # anything sharing a line with the open tag would be dropped. Skip rather than corrupt the XML.
  if ! grep -qE "^[[:space:]]*<family lang=\"und-Beng\" variant=\"$variant\">[[:space:]]*$" "$xml" 2>/dev/null; then
    status_warn "Skipping und-Beng ($variant) in ${xml##*/}: this ROM writes the family on one line"
    return 0
  fi
  awk -v open_tag="$open_tag" '
    !inside && $0 ~ "^[[:space:]]*" open_tag "[[:space:]]*$" {
      print "  " open_tag
      print "    <font weight=\"400\" style=\"normal\">NotoSansBengali-VF.ttf</font>"
      print "    <font weight=\"500\" style=\"normal\">NotoSerifBengali-VF.ttf</font>"
      print "    <font weight=\"700\" style=\"normal\">NotoSansBengaliUI-VF.ttf</font>"
      print "  </family>"
      inside=1
      next
    }
    inside {
      # The closing line may also carry the start of the next family; keep that remainder.
      if (index($0, "</family>") > 0) {
        inside=0
        rest = substr($0, index($0, "</family>") + length("</family>"))
        if (rest ~ /[^[:space:]]/) { print rest }
      }
      next
    }
    { print }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"
}

# PRODUCT_RUBIK_*_SRC and PRODUCT_HAS_DEDICATED_ITALIC are read by the caller.
# shellcheck disable=SC2034
resolve_product_rubik_sources() {
  PRODUCT_HAS_DEDICATED_ITALIC=0
  PRODUCT_RUBIK_REGULAR_SRC=$FONT_PRIMARY
  PRODUCT_RUBIK_ITALIC_SRC=

  set -- $FONT_FILES
  if [ -n "$1" ]; then
    PRODUCT_RUBIK_REGULAR_SRC=$1
  fi
  [ -n "$PRODUCT_RUBIK_REGULAR_SRC" ] || fail "No primary font available for product Rubik spoof"

  if [ "$FONT_MODE" = "variable" ] && [ -n "$2" ] && [ "$2" != "$1" ]; then
    PRODUCT_RUBIK_ITALIC_SRC=$2
    PRODUCT_HAS_DEDICATED_ITALIC=1
  fi
}

patch_product_fonts_customization() {
  local xml=${1:-"$PRODUCT_XML"}
  local sans_fragment="$FONT_DIR/sans.xml"

  [ -f "$ORIGINAL_PRODUCT_XML" ] || return 0
  [ -f "$sans_fragment" ] || fail "Generated sans.xml is missing"

  if ! grep -qE '<(family-list|familyset|family)[^A-Za-z0-9_-][^>]*name="(sans-serif|google-sans|google-sans-[^"]*|variable-[^"]*)"' \
    "$ORIGINAL_PRODUCT_XML" 2>/dev/null; then
    PRODUCT_GS_PATCHED=0
    return 0
  fi

  resolve_product_rubik_sources
  cp -f "$ORIGINAL_PRODUCT_XML" "$xml" || fail "Could not copy product fonts_customization.xml"

  awk -v sans_file="$sans_fragment" \
      -v rubik_regular="$PRODUCT_RUBIK_REGULAR" \
      -v rubik_italic="$PRODUCT_RUBIK_ITALIC" \
      -v has_dedicated_italic="$PRODUCT_HAS_DEDICATED_ITALIC" '
    function abs(v) { return v < 0 ? -v : v }
    function is_open_tag(line, open_tag) {
      return match(line, "<" open_tag "[^A-Za-z0-9_-]")
    }
    function open_count(line, open_tag,   n, rest) {
      n = 0; rest = line
      while (match(rest, "<" open_tag "[^A-Za-z0-9_-]")) {
        n++
        rest = substr(rest, RSTART + RLENGTH)
      }
      return n
    }
    function close_count(line, open_tag,   n, rest) {
      n = 0; rest = line
      while (match(rest, "</" open_tag ">")) {
        n++
        rest = substr(rest, RSTART + RLENGTH)
      }
      return n
    }
    function extract_name(line) {
      if (match(line, /name="[^"]+"/)) {
        return substr(line, RSTART + 6, RLENGTH - 7)
      }
      return ""
    }
    function is_gs_name(name) {
      return name == "sans-serif" || name ~ /^google-sans($|-)/ || name ~ /^variable-/
    }
    function attr_value(text, key,   pat) {
      pat = key "=\"[^\"]+\""
      if (match(text, pat)) {
        return substr(text, RSTART + length(key) + 2, RLENGTH - length(key) - 3)
      }
      return ""
    }
    function store_face(weight, style, index_attr, axes,   key) {
      if (weight == "") weight = "400"
      if (style == "") style = "normal"
      key = weight SUBSEP style
      face_weight[key] = weight + 0
      face_index[key] = index_attr
      face_axes[key] = axes
      if (style == "italic") {
        italic_weights[++italic_count] = weight + 0
        italic_key[weight + 0] = key
      } else {
        normal_weights[++normal_count] = weight + 0
        normal_key[weight + 0] = key
      }
    }
    function load_sans(path,   line, in_font, style, weight, index_attr, axes, file) {
      in_font = 0
      while ((getline line < path) > 0) {
        if (!in_font && line ~ /<font[[:space:]]/) {
          in_font = 1
          style = attr_value(line, "style")
          weight = attr_value(line, "weight")
          index_attr = attr_value(line, "index")
          axes = ""
          file = ""
          if (match(line, /[A-Za-z0-9._-]+\.(ttf|otf|ttc|otc)/)) {
            file = substr(line, RSTART, RLENGTH)
          }
          if (line ~ /<\/font>/) {
            store_face(weight, style, index_attr, axes)
            in_font = 0
          }
          continue
        }
        if (in_font) {
          if (match(line, /<axis[^>]*\/?>/)) {
            if (axes != "") axes = axes "\n"
            axes = axes line
          }
          if (file == "" && match(line, /[A-Za-z0-9._-]+\.(ttf|otf|ttc|otc)/)) {
            file = substr(line, RSTART, RLENGTH)
          }
          if (line ~ /<\/font>/) {
            store_face(weight, style, index_attr, axes)
            in_font = 0
          }
        }
      }
      close(path)
    }
    function closest_key(want_weight, want_style,   i, best, best_diff, w, use_italic) {
      use_italic = (want_style == "italic" && italic_count > 0)
      if (use_italic) {
        best = italic_key[italic_weights[1]]
        best_diff = abs(italic_weights[1] - want_weight)
        for (i = 2; i <= italic_count; i++) {
          w = italic_weights[i]
          if (abs(w - want_weight) < best_diff) {
            best = italic_key[w]
            best_diff = abs(w - want_weight)
          }
        }
        return best
      }
      if (normal_count == 0) return ""
      best = normal_key[normal_weights[1]]
      best_diff = abs(normal_weights[1] - want_weight)
      for (i = 2; i <= normal_count; i++) {
        w = normal_weights[i]
        if (abs(w - want_weight) < best_diff) {
          best = normal_key[w]
          best_diff = abs(w - want_weight)
        }
      }
      return best
    }
    function choose_file(want_style) {
      if (want_style == "italic" && has_dedicated_italic == "1" && italic_count > 0) {
        return rubik_italic
      }
      return rubik_regular
    }
    function emit_font(indent, stock_weight, stock_style,   key, out, idx, n, i, axes_line) {
      if (stock_weight == "") stock_weight = "400"
      if (stock_style == "") stock_style = "normal"
      key = closest_key(stock_weight + 0, stock_style)
      if (key == "") {
        print indent "<font weight=\"" stock_weight "\" style=\"" stock_style "\">" rubik_regular "</font>"
        return
      }
      out = indent "<font weight=\"" stock_weight "\" style=\"" stock_style "\""
      idx = face_index[key]
      if (idx != "") out = out " index=\"" idx "\""
      out = out ">" choose_file(stock_style)
      if (face_axes[key] != "") {
        print out
        n = split(face_axes[key], axis_lines, "\n")
        for (i = 1; i <= n; i++) {
          axes_line = axis_lines[i]
          sub(/^[[:space:]]+/, "", axes_line)
          if (axes_line != "") print indent "  " axes_line
        }
        print indent "</font>"
      } else {
        print out "</font>"
      }
    }
    function flush_font(   weight, style) {
      if (!in_font_block) return
      weight = attr_value(font_open, "weight")
      style = attr_value(font_open, "style")
      if (weight == "") weight = "400"
      if (style == "") style = "normal"
      if (font_indent == "") font_indent = "    "
      emit_font(font_indent, weight, style)
      in_font_block = 0
      font_open = ""
    }
    function maybe_enter_gs(line,   nm) {
      if (gs_active) return
      if (is_open_tag(line, "family-list")) {
        nm = extract_name(line)
        if (nm != "" && is_gs_name(nm)) {
          gs_active = 1; gs_tag = "family-list"
          gs_depth = open_count(line, gs_tag) - close_count(line, gs_tag)
          if (gs_depth <= 0) gs_active = 0
          return
        }
      }
      if (is_open_tag(line, "familyset")) {
        nm = extract_name(line)
        if (nm != "" && is_gs_name(nm)) {
          gs_active = 1; gs_tag = "familyset"
          gs_depth = open_count(line, gs_tag) - close_count(line, gs_tag)
          if (gs_depth <= 0) gs_active = 0
          return
        }
      }
      if (is_open_tag(line, "family")) {
        nm = extract_name(line)
        if (nm != "" && is_gs_name(nm)) {
          gs_active = 1; gs_tag = "family"
          gs_depth = open_count(line, gs_tag) - close_count(line, gs_tag)
          if (gs_depth <= 0) gs_active = 0
        }
      }
    }
    BEGIN {
      normal_count = 0
      italic_count = 0
      gs_active = 0
      gs_depth = 0
      in_font_block = 0
      entered_this_line = 0
      load_sans(sans_file)
    }
    {
      line = $0
      entered_this_line = 0

      if (!gs_active && !in_font_block) {
        maybe_enter_gs(line)
        if (gs_active) entered_this_line = 1
      }

      if (gs_active && !in_font_block && line ~ /<font([[:space:]>])/) {
        in_font_block = 1
        font_open = line
        if (match(line, /^[[:space:]]*/)) font_indent = substr(line, RSTART, RLENGTH)
        else font_indent = "    "
        if (line ~ /<\/font>/) flush_font()
      } else if (in_font_block) {
        if (line ~ /<\/font>/) flush_font()
      } else {
        print line
      }

      if (gs_active && !in_font_block && !entered_this_line) {
        gs_depth += open_count(line, gs_tag) - close_count(line, gs_tag)
        if (gs_depth <= 0) {
          gs_active = 0
          gs_tag = ""
          gs_depth = 0
        }
      }
    }
  ' "$xml" > "$xml.tmp" && mv -f "$xml.tmp" "$xml"

  # grep -c already prints 0 on no match, so a `|| echo 0` fallback would emit a second line here.
  PRODUCT_GS_PATCHED=$(grep -cE '<(family-list|familyset|family)[^A-Za-z0-9_-][^>]*name="(sans-serif|google-sans|google-sans-[^"]*|variable-[^"]*)"' "$xml" 2>/dev/null)
  case $PRODUCT_GS_PATCHED in
    ''|*[!0-9]*) PRODUCT_GS_PATCHED=0 ;;
  esac
  if ! grep -q "$PRODUCT_RUBIK_REGULAR" "$xml" 2>/dev/null; then
    PRODUCT_GS_PATCHED=0
  fi
  return 0
}

config_value() {
  local key=$1
  sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$VF_CONFIG_FILE" 2>/dev/null |
    tail -n 1 |
    sed 's/[[:space:]]*[#;].*$//;s/[[:space:]]//g;s/\r$//'
}

weight_label() {
  case "$1" in
    100) printf 'THIN' ;;
    200) printf 'EXTRALIGHT' ;;
    300) printf 'LIGHT' ;;
    400) printf 'REGULAR' ;;
    500) printf 'MEDIUM' ;;
    600) printf 'SEMIBOLD' ;;
    700) printf 'BOLD' ;;
    800) printf 'EXTRABOLD' ;;
    900) printf 'BLACK' ;;
    *) printf 'WEIGHT_%s' "$1" ;;
  esac
}

profile_title() {
  case "$1" in
    SANS_UPRIGHT) printf 'SANS-SERIF / UPRIGHT' ;;
    SANS_ITALIC) printf 'SANS-SERIF / ITALIC' ;;
    CONDENSED_UPRIGHT) printf 'CONDENSED / UPRIGHT' ;;
    CONDENSED_ITALIC) printf 'CONDENSED / ITALIC' ;;
    *) printf '%s' "$1" ;;
  esac
}

ensure_profile_keys() {
  local profile=$1 axis_meta=$2 weights=$3
  local title
  title=$(profile_title "$profile")
  local axis_record axis_tag remainder axis_min axis_default axis_max
  local config_key axis_key weight label wght_min wght_max

  if [ "$VF_CONFIG_CREATED" = "1" ]; then
    {
      printf '\n# ------------------------------------------------------------------------------\n'
      printf '# %s\n' "$title"
      printf '# ------------------------------------------------------------------------------\n'
    } >> "$VF_CONFIG_FILE"
  fi

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    [ "$axis_tag" = "wght" ] && { wght_min=$axis_min; wght_max=$axis_max; }
  done

  for weight in $weights; do
    label=$(weight_label "$weight")
    config_key="${profile}_${label}_WGHT"
    if ! grep -q "^[[:space:]]*${config_key}[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
      {
        printf '# Android %s (%s): variable wght range %s..%s\n' "$weight" "$label" "$wght_min" "$wght_max"
        printf '%s=%s\n' "$config_key" "$weight"
      } >> "$VF_CONFIG_FILE"
    fi
  done

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    [ "$axis_tag" = "wght" ] && continue
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    axis_key=$(printf '%s' "$axis_tag" | tr '[:lower:]' '[:upper:]')
    config_key="${profile}_${axis_key}"
    if ! grep -q "^[[:space:]]*${config_key}[[:space:]]*=" "$VF_CONFIG_FILE" 2>/dev/null; then
      {
        printf '# %s axis range %s..%s; compiled value %s\n' "$axis_tag" "$axis_min" "$axis_max" "$axis_default"
        printf '%s=%s\n' "$config_key" "$axis_default"
      } >> "$VF_CONFIG_FILE"
    fi
  done
}

reset_config_value() {
  local config_key=$1 reset_value=$2
  awk -v wanted_key="$config_key" -v wanted_value="$reset_value" '
    $0 ~ "^[[:space:]]*" wanted_key "[[:space:]]*=" {
      print wanted_key "=" wanted_value
      replaced=1
      next
    }
    { print }
    END {
      if (!replaced) print wanted_key "=" wanted_value
    }
  ' "$VF_CONFIG_FILE" > "$VF_CONFIG_FILE.tmp" && mv -f "$VF_CONFIG_FILE.tmp" "$VF_CONFIG_FILE"
}

validate_axis_value() {
  local config_key=$1 axis_value=$2 axis_min=$3 axis_max=$4 reset_value=$5
  case "$axis_value" in
    AUTO|Auto|auto) return 1 ;;
    "")
      status_warn "$config_key was empty; reset to $reset_value"
      reset_config_value "$config_key" "$reset_value"
      return 1
      ;;
  esac
  if ! printf '%s\n' "$axis_value" | grep -Eq '^-?([0-9]+([.][0-9]*)?|[.][0-9]+)$'; then
    status_warn "$config_key='$axis_value' is invalid; reset to $reset_value"
    reset_config_value "$config_key" "$reset_value"
    return 1
  fi
  if ! awk -v value="$axis_value" -v minimum="$axis_min" -v maximum="$axis_max" \
    'BEGIN { exit !(value >= minimum && value <= maximum) }'; then
    status_warn "$config_key=$axis_value is outside $axis_min..$axis_max; reset to $reset_value"
    reset_config_value "$config_key" "$reset_value"
    return 1
  fi
  return 0
}

apply_axis_value() {
  local style_name=$1 declared_weight=$2 axis_tag=$3 axis_value=$4 fragment_file
  shift 4
  for fragment_file in "$@"; do
    [ -f "$fragment_file" ] || continue
    awk -v wanted_style="$style_name" -v wanted_weight="$declared_weight" \
      -v wanted_tag="$axis_tag" -v wanted_value="$axis_value" '
      /<font[[:space:]]/ {
        active = index($0, "style=\"" wanted_style "\"") > 0
        if (wanted_weight != "") {
          active = active && index($0, "weight=\"" wanted_weight "\"") > 0
        }
      }
      active && index($0, "<axis tag=\"" wanted_tag "\"") > 0 {
        sub(/stylevalue="[^"]*"/, "stylevalue=\"" wanted_value "\"")
      }
      { print }
      /<\/font>/ { active=0 }
    ' "$fragment_file" > "$fragment_file.tmp" && mv -f "$fragment_file.tmp" "$fragment_file"
  done
}

apply_profile() {
  local profile=$1 xml_style=$2 axis_meta=$3 weights=$4
  shift 4
  local fragment_list="$*"
  local axis_record axis_tag remainder axis_min axis_default axis_max axis_key config_key axis_value weight label wght_min wght_max

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    [ "$axis_tag" = "wght" ] && { wght_min=$axis_min; wght_max=$axis_max; }
  done

  for weight in $weights; do
    label=$(weight_label "$weight")
    config_key="${profile}_${label}_WGHT"
    axis_value=$(config_value "$config_key")
    validate_axis_value "$config_key" "$axis_value" "$wght_min" "$wght_max" "$weight" || continue
    apply_axis_value "$xml_style" "$weight" wght "$axis_value" $fragment_list
  done

  for axis_record in $axis_meta; do
    axis_tag=${axis_record%%|*}
    [ "$axis_tag" = "wght" ] && continue
    remainder=${axis_record#*|}
    axis_min=${remainder%%|*}
    remainder=${remainder#*|}
    axis_default=${remainder%%|*}
    axis_max=${remainder##*|}
    axis_key=$(printf '%s' "$axis_tag" | tr '[:lower:]' '[:upper:]')
    config_key="${profile}_${axis_key}"
    axis_value=$(config_value "$config_key")
    validate_axis_value "$config_key" "$axis_value" "$axis_min" "$axis_max" "$axis_default" || continue
    apply_axis_value "$xml_style" "" "$axis_tag" "$axis_value" $fragment_list
  done
}

# The four axis profiles a variable module can expose. fragment_dir holds the pristine sans.xml /
# condensed.xml / serif.xml emitted by build.py; the values come from $VF_CONFIG_FILE.
apply_axis_profiles() {
  local fragment_dir=$1
  apply_profile SANS_UPRIGHT normal "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS" \
    "$fragment_dir/sans.xml" "$fragment_dir/serif.xml"
  apply_profile SANS_ITALIC italic "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS" \
    "$fragment_dir/sans.xml" "$fragment_dir/serif.xml"
  apply_profile CONDENSED_UPRIGHT normal "$VF_UPRIGHT_AXIS_META" "$VF_UPRIGHT_WEIGHTS" \
    "$fragment_dir/condensed.xml"
  apply_profile CONDENSED_ITALIC italic "$VF_ITALIC_AXIS_META" "$VF_ITALIC_WEIGHTS" \
    "$fragment_dir/condensed.xml"
}

variable_config_path() {
  local safe_family
  safe_family=$(printf '%s' "$FONT_FAMILY" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_*//;s/_*$//')
  [ -n "$safe_family" ] || safe_family=Variable_Font
  printf '%s/MFFMv14_%s_%s.conf' "$MFFM_DIR" "$safe_family" "$VF_CONFIG_ID"
}

patch_sans_families() {
  local xml=$1 fragment_dir=$2
  [ -f "$xml" ] || return 0
  replace_family "$xml" sans-serif "$fragment_dir/sans.xml"
  replace_family "$xml" sans-serif-condensed "$fragment_dir/condensed.xml"
  replace_family "$xml" roboto-flex "$fragment_dir/sans.xml"
}

patch_mono_families() {
  local xml=$1 fragment_dir=$2
  [ -f "$xml" ] || return 0
  [ -f "$fragment_dir/mono.xml" ] || return 0
  replace_family "$xml" monospace "$fragment_dir/mono.xml"
  replace_family "$xml" cutive-mono "$fragment_dir/mono.xml"
  replace_family "$xml" droidsans-mono "$fragment_dir/mono.xml"
  if [ ! -f "$fragment_dir/serif.xml" ]; then
    replace_family "$xml" serif-monospace "$fragment_dir/mono.xml" "prepend"
  fi
}

patch_serif_families() {
  local xml=$1 fragment_dir=$2
  [ -f "$xml" ] || return 0
  [ -f "$fragment_dir/serif.xml" ] || return 0
  replace_family "$xml" serif "$fragment_dir/serif.xml" "split"
  replace_family "$xml" noto-serif "$fragment_dir/serif.xml" "split"
  replace_family "$xml" serif-monospace "$fragment_dir/serif.xml" "split"
}
