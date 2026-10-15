#!/bin/sh
# Browser preview of the picker UI (Firefox headless, mock data).
# usage: tools/preview/shot.sh <detail|crewpop|devpop|empty> <out.png> [de|en]
# Needs the game images extracted to $RES (see README in this folder).
H=$(cd "$(dirname "$0")" && pwd)
RES=${RES:-$HOME/.cache/wot-picker-preview}
python3 -I "$H/preview.py" "$H/../../src/res/gui/gameface/mods/advances_picker" "$RES" "$H/p_$1.html" "$1" "${3:-de}"
P=$H/.ffprofile; mkdir -p "$P"
echo 'user_pref("layout.css.devPixelsPerPx", "1.0"); user_pref("font.minimum-size.x-western", 0);' > "$P/user.js"
timeout 60 firefox --headless --no-remote --profile "$P" --window-size=1920,1080 --screenshot "$(realpath "$2")" "file://$H/p_$1.html" >/dev/null 2>&1
