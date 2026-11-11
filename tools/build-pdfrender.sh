#!/usr/bin/env bash
# Baut das PDF-Renderprogramm als statisches aarch64-Binary und legt es ins Add-on.
#
# Der Quellcode liegt in tools/pdfrender und benutzt ausschliesslich hayro
# (Apache-2.0 ODER MIT), einen reinen Rust-PDF-Rasterizer auf vello_cpu --
# derselben CPU-Engine, die auch DeckCraft verwendet. Kein C, keine
# Systembibliothek, dasselbe Rezept wie tools/build-deckcraft.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

ZIEL_TRIPLE=aarch64-unknown-linux-musl
AUSGABE="script.presentation/bin/pdfrender"

command -v cargo >/dev/null || { echo "cargo fehlt: https://rustup.rs" >&2; exit 1; }
rustup target add "$ZIEL_TRIPLE"

RUSTFLAGS="-C linker=rust-lld -C link-self-contained=yes" \
  cargo build --release --manifest-path tools/pdfrender/Cargo.toml --target "$ZIEL_TRIPLE"

mkdir -p "$(dirname "$AUSGABE")"
cp "tools/pdfrender/target/$ZIEL_TRIPLE/release/pdfrender" "$AUSGABE"
llvm-strip "$AUSGABE" 2>/dev/null || strip "$AUSGABE" 2>/dev/null || true
chmod +x "$AUSGABE"

if ! file "$AUSGABE" | grep -q "ARM aarch64"; then
  echo "Falsche Architektur! $(file "$AUSGABE")" >&2
  exit 1
fi
echo "fertig: $AUSGABE ($(du -h "$AUSGABE" | cut -f1))"
