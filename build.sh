#!/usr/bin/env bash
# Baut ein installierbares Zip (Kodi: Add-ons > Aus ZIP-Datei installieren).
set -euo pipefail
cd "$(dirname "$0")"
ID=script.presentation
VERSION=$(grep -oP '<addon[^>]*version="\K[^"]+' "$ID/addon.xml")

for werkzeug in deckcraft-cli:build-deckcraft.sh pdfrender:build-pdfrender.sh; do
  datei="${werkzeug%%:*}"
  skript="${werkzeug##*:}"
  if [ ! -x "$ID/bin/$datei" ]; then
    echo "Das Binary fehlt unter $ID/bin/$datei." >&2
    echo "Erst tools/$skript ausführen." >&2
    exit 1
  fi
done

mkdir -p dist
OUT="dist/$ID-$VERSION.zip"
rm -f "$OUT"
zip -qr "$OUT" "$ID" -x '*/__pycache__/*' '*.pyc'
echo "$OUT ($(du -h "$OUT" | cut -f1))"
