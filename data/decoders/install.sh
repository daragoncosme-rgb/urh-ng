#!/bin/sh
# Install the URH-NG external decoders on Linux and macOS.
# Copies the decoder programs to ~/.config/urh/decoders and adds the
# decodings to ~/.config/urh/decodings.txt (a backup is made first).
# URH and URH-NG share this file. Close URH before running this script.
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
CONF="$HOME/.config/urh"
DEST="$CONF/decoders"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)               PLAT=linux-x64 ;;
  Linux-aarch64|Linux-arm64)  PLAT=linux-arm64 ;;
  Darwin-x86_64)              PLAT=macos-x64 ;;
  Darwin-arm64)               PLAT=macos-arm64 ;;
  *) echo "Unsupported platform: $(uname -s) $(uname -m)"; exit 1 ;;
esac

case "$DEST" in *,*|*\;*|*\'*|*\"*)
  echo "Your home path contains , ; ' or \" and URH cannot use it in decodings.txt: $DEST"; exit 1 ;;
esac

mkdir -p "$DEST"
for n in homematic homematic_complete enocean_switchtelegram; do
  cp "$HERE/$PLAT/$n" "$DEST/$n"
  chmod +x "$DEST/$n"
  if [ "$(uname -s)" = Darwin ]; then
    xattr -d com.apple.quarantine "$DEST/$n" 2>/dev/null || true
    command -v codesign >/dev/null && codesign -s - -f "$DEST/$n" >/dev/null 2>&1 || true
  fi
done

FILE="$CONF/decodings.txt"
if [ -f "$FILE" ]; then
  cp "$FILE" "$FILE.bak.$(date +%Y%m%d%H%M%S)"
else
  # URH only creates the file when decodings are saved; start with the bundled list
  : > "$FILE"
fi

TMP=$(mktemp)
cat "$HERE/decodings.txt" > "$TMP"
# Paths in double quotes: URH splits the command at spaces otherwise
cat >> "$TMP" <<LINES
'HomeMatic (complete: whitening + CRC)', 'External Program', '"$DEST/homematic_complete" d;"$DEST/homematic_complete" e',
'HomeMatic (cipher only)', 'External Program', '"$DEST/homematic" d;"$DEST/homematic" e',
'EnOcean Switch Telegram', 'External Program', '"$DEST/enocean_switchtelegram" d;"$DEST/enocean_switchtelegram" e',
LINES

# Only add lines whose name is not in the file yet
added=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  name=$(printf '%s' "$line" | cut -d, -f1)
  if ! grep -qF -- "$name," "$FILE"; then
    printf '%s\n' "$line" >> "$FILE"; added=$((added+1))
  fi
done < "$TMP"
rm -f "$TMP"

# Quick test
"$DEST/enocean_switchtelegram" d 1010 >/dev/null && echo "Decoders OK ($PLAT) in $DEST"
echo "$added decodings added to $FILE"
echo "Open URH: they are in the Analysis tab and in Edit -> Decoding."
