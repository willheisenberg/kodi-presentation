#!/usr/bin/env bash
# Baut deckcraft-cli als statisches aarch64-Binary und legt es ins Add-on.
#
# Das Rezept ist auf LibreELEC 12.2.1 / Raspberry Pi 5 geprüft: statisch gegen
# musl, gelinkt mit rust-lld. Dadurch braucht der Build keine C-Toolchain und
# das Ergebnis keine Bibliothek auf dem Zielgerät.
set -euo pipefail
cd "$(dirname "$0")/.."

ZIEL_TRIPLE=aarch64-unknown-linux-musl
VERSION="$(tr -d '[:space:]' < tools/deckcraft.version)"
AUSGABE="script.presentation/bin/deckcraft-cli"

command -v cargo >/dev/null || { echo "cargo fehlt: https://rustup.rs" >&2; exit 1; }
command -v git >/dev/null   || { echo "git fehlt" >&2; exit 1; }
rustup target add "$ZIEL_TRIPLE"

ARBEIT="$(mktemp -d)"
trap 'rm -rf "$ARBEIT"' EXIT

echo "DeckCraft $VERSION wird geholt …"
git clone --depth 1 --branch "v$VERSION" \
  https://github.com/storytold/deckcraft.git "$ARBEIT/src"

GEBAUT="$(grep -m1 '^version' "$ARBEIT/src/Cargo.toml" | cut -d'"' -f2)"
if [ "$GEBAUT" != "$VERSION" ]; then
  echo "Achtung: Upstream meldet $GEBAUT, erwartet war $VERSION." >&2
fi

( cd "$ARBEIT/src" && RUSTFLAGS="-C linker=rust-lld -C link-self-contained=yes" \
    cargo build --release -p deckcraft-cli --target "$ZIEL_TRIPLE" )

mkdir -p "$(dirname "$AUSGABE")"
cp "$ARBEIT/src/target/$ZIEL_TRIPLE/release/deckcraft-cli" "$AUSGABE"
llvm-strip "$AUSGABE" 2>/dev/null || strip "$AUSGABE" 2>/dev/null || true
chmod +x "$AUSGABE"

if ! file "$AUSGABE" | grep -q "ARM aarch64"; then
  echo "Falsche Architektur! $(file "$AUSGABE")" >&2
  exit 1
fi
echo "fertig: $AUSGABE ($(du -h "$AUSGABE" | cut -f1))"
