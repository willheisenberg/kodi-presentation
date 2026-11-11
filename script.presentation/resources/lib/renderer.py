"""Wrapper um deckcraft-cli. Einzige Stelle, die einen Fremdprozess startet.

Die Schnittstelle ist bewusst schmal gehalten: info() und render(). Sollte
DeckCraft einmal ersetzt werden, ist das die einzige Datei, die das merkt.
"""
import json
import os
import re
import subprocess
from dataclasses import dataclass, field

from texte import T

ZEITGRENZE = 300  # Sekunden; ein 500-Folien-Deck bleibt weit darunter


class RendererFehler(Exception):
    pass


def _folien_nummer(name):
    """Sortierschlüssel nach der Zahl im Dateinamen.

    DeckCraft benennt zweistellig: slide-01 … slide-99, slide-100 … Rein
    lexikografisch landete slide-100 zwischen slide-10 und slide-11, womit
    ab 100 Folien Bild und Notiz auseinanderliefen.
    """
    ziffern = "".join(z for z in name.split("-", 1)[-1] if z.isdigit())
    return (int(ziffern) if ziffern else 0, name)


@dataclass(frozen=True)
class Folie:
    index: int
    titel: str
    notizen: str


@dataclass(frozen=True)
class DeckInfo:
    titel: str
    folien: list = field(default_factory=list)
    folien_groesse: tuple = (960.0, 540.0)
    verlorene_folien: int = 0
    beschaedigte_medien: int = 0


class DeckcraftRenderer:
    def __init__(self, binary_pfad):
        self._binary = binary_pfad

    def _ruf(self, *argumente, stdout_in_fehler=True):
        if not os.path.isfile(self._binary):
            raise RendererFehler(T(30120, self._binary))
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
            # Trifft u.a. bei falscher Architektur zu (Exec format error).
            raise RendererFehler(T(30123, e))
        if ergebnis.returncode != 0:
            # stdout von `info` ist das JSON mit allen Referentennotizen. Es darf
            # nie in eine Meldung wandern, die auf dem Fernseher landen kann.
            ersatz = ergebnis.stdout.strip() if stdout_in_fehler else ""
            fehler = ergebnis.stderr.strip() or ersatz or "ohne Meldung"
            raise RendererFehler(T(30124, fehler))
        return ergebnis

    def version(self):
        return self._ruf("--version").stdout.strip()

    def info(self, pfad):
        ergebnis = self._ruf("info", os.path.abspath(pfad), stdout_in_fehler=False)
        try:
            roh = json.loads(ergebnis.stdout)
        except json.JSONDecodeError as e:
            raise RendererFehler(T(30125, e))
        return self._lies_info(roh, ergebnis.stderr)

    @staticmethod
    def _lies_info(roh, stderr):
        """Wertet defensiv aus: fehlende Felder sind kein Fehler, nur leer."""
        folien = [
            Folie(
                index=int(f.get("index", i)),
                titel=str(f.get("title") or ""),
                notizen=str(f.get("notes") or ""),
            )
            for i, f in enumerate(roh.get("slides") or [])
        ]
        groesse = roh.get("slideSize") or [960.0, 540.0]

        def zaehle(muster):
            treffer = re.search(muster, stderr or "")
            return int(treffer.group(1)) if treffer else 0

        return DeckInfo(
            titel=str(roh.get("title") or ""),
            folien=folien,
            folien_groesse=(float(groesse[0]), float(groesse[1])),
            verlorene_folien=zaehle(r"(\d+) slides? could"),
            beschaedigte_medien=zaehle(r"(\d+) pictures? or media"),
        )

    def render(self, pfad, ziel_ordner, skalierung):
        """Rendert alle Folien nach ziel_ordner und gibt die Bildpfade sortiert zurück.

        Der Pfad wird absolut übergeben. deckcraft-cli kennt kein `--` als
        Options-Ende -- es liest `--` als Dateinamen -- und ein absoluter Pfad
        beginnt immer mit /, kann also nie als Option missverstanden werden.
        """
        os.makedirs(ziel_ordner, exist_ok=True)
        self._ruf("render", "--all", "--scale", str(skalierung),
                  os.path.abspath(pfad), ziel_ordner)
        bilder = [
            os.path.join(ziel_ordner, name)
            for name in sorted(os.listdir(ziel_ordner), key=_folien_nummer)
            if name.startswith("slide-") and name.endswith(".png")
        ]
        if not bilder:
            raise RendererFehler(T(30126))
        return bilder


# Welcher Renderer für welche Endung. PDF kommt ohne Referentennotizen;
# alles Weitere steht in pdf_renderer.
ENDUNGEN_DECKCRAFT = (".pptx", ".deckcraft")
ENDUNGEN_PDF = (".pdf",)


def fuer_deck(pfad, deckcraft_binary, pdf_binary):
    """Wählt den Renderer nach der Dateiendung.

    Die beiden Renderer haben dieselben drei Methoden; Cache, Fenster und
    Handy-Ansicht merken vom Unterschied nichts.
    """
    endung = os.path.splitext(pfad)[1].lower()
    if endung in ENDUNGEN_DECKCRAFT:
        return DeckcraftRenderer(deckcraft_binary)
    if endung in ENDUNGEN_PDF:
        import pdf_renderer
        return pdf_renderer.PdfRenderer(pdf_binary)
    raise RendererFehler(f"{pfad}: {endung or 'ohne Endung'}")
