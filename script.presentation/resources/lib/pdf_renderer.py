"""Renderer für PDF-Decks, hinter derselben Schnittstelle wie DeckCraft.

Benutzt `pdfrender`, ein kleines Programm aus `tools/pdfrender` dieses Repos.
Es rastert über `hayro` (Apache-2.0 ODER MIT), einen reinen Rust-PDF-Renderer
auf `vello_cpu` -- derselben CPU-Engine, die auch DeckCraft verwendet. Gebaut
wird es mit `tools/build-pdfrender.sh`, nach demselben Rezept wie das
DeckCraft-Binary: statisch gegen musl, ohne C-Toolchain.

**PDFs tragen keine Referentennotizen.** Das Notizfeld bleibt deshalb leer, und
die Handy-Ansicht zeigt dort ihren Hinweistext. Genau deswegen bleibt .pptx das
bessere Format für einen Vortrag.
"""
import json
import os
import subprocess

from renderer import (ZEITGRENZE, DeckInfo, Folie, RendererFehler,
                      _folien_nummer)
from texte import T


class PdfRenderer:
    """Dieselben drei Methoden wie DeckcraftRenderer: version, info, render."""

    def __init__(self, binary_pfad):
        self._binary = binary_pfad

    def _ruf(self, *argumente, stdout_in_fehler=True):
        if not os.path.isfile(self._binary):
            raise RendererFehler(T(30127, self._binary))
        if not os.access(self._binary, os.X_OK):
            raise RendererFehler(T(30121, self._binary))
        try:
            ergebnis = subprocess.run(
                [self._binary, *argumente],
                capture_output=True, text=True, timeout=ZEITGRENZE,
            )
        except subprocess.TimeoutExpired:
            raise RendererFehler(T(30122, ZEITGRENZE))
        except OSError as e:
            raise RendererFehler(T(30123, e))
        if ergebnis.returncode != 0:
            ersatz = ergebnis.stdout.strip() if stdout_in_fehler else ""
            raise RendererFehler(ergebnis.stderr.strip() or ersatz or T(30128, self._binary))
        return ergebnis

    def version(self):
        return self._ruf("--version").stdout.strip()

    def info(self, pfad):
        """Eine „Folie" je Seite. Titel ist die Seitenzahl, Notizen bleiben leer."""
        ergebnis = self._ruf("info", os.path.abspath(pfad), stdout_in_fehler=False)
        try:
            roh = json.loads(ergebnis.stdout)
        except json.JSONDecodeError as e:
            raise RendererFehler(T(30125, e))
        anzahl = max(0, int(roh.get("seiten") or 0))
        folien = [Folie(index=i, titel=T(30119, i + 1), notizen="")
                  for i in range(anzahl)]
        return DeckInfo(
            titel="",
            folien=folien,
            folien_groesse=(float(roh.get("breitePt") or 960.0),
                            float(roh.get("hoehePt") or 540.0)),
        )

    # Breite einer DeckCraft-Folie in Punkten; daran richtet sich die
    # Zielauflösung aus, damit PDFs beliebiger Seitengröße gleich groß werden.
    FOLIENBREITE_PT = 960

    def render(self, pfad, ziel_ordner, skalierung):
        """`skalierung` meint wie bei DeckCraft Pixel je Punkt einer 960er Folie.

        Ein PDF kann beliebig gesetzt sein -- 1440 Punkte Breite ergäben sonst
        2880 Pixel, das Vierfache eines 1080p-Fernsehers. Deshalb wird eine
        feste Zielbreite vorgegeben statt eines Maßstabs.
        """
        os.makedirs(ziel_ordner, exist_ok=True)
        breite = int(round(self.FOLIENBREITE_PT * float(skalierung)))
        self._ruf("render", os.path.abspath(pfad),
                  "--width", str(breite), ziel_ordner)
        bilder = [
            os.path.join(ziel_ordner, name)
            for name in sorted(os.listdir(ziel_ordner), key=_folien_nummer)
            if name.startswith("slide-") and name.endswith(".png")
        ]
        if not bilder:
            raise RendererFehler(T(30126))
        return bilder
