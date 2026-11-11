"""Übersetzte Texte für Fernseher, Dialoge und Handy-Seite.

Kodi übersetzt Add-on-Texte nur in der Sprache seiner eigenen Oberfläche. Wer
im Add-on eine feste Sprache wählt, bekommt sie deshalb nicht von Kodi, sondern
direkt aus der passenden `strings.po`.

Alle Texte stammen aus `tools/texte.json` und werden daraus in beide `.po`
erzeugt -- ein Text, den es nur in einer Sprache gibt, ist damit unmöglich.
"""
import os
import re

import xbmcaddon

AUTOMATISCH = 0
DEUTSCH = 1
ENGLISCH = 2

ORDNER = {
    DEUTSCH: "resource.language.de_de",
    ENGLISCH: "resource.language.en_gb",
}
# Fällt Kodi bei "Automatisch" aus, wird hierauf zurückgegriffen.
RUECKFALL = DEUTSCH

_EINTRAG = re.compile(r'msgctxt "#(\d+)"\nmsgid "(?:.*)"\nmsgstr "(.*)"')


def _lies_po(pfad):
    try:
        with open(pfad, encoding="utf-8") as f:
            return {int(nr): wert for nr, wert in _EINTRAG.findall(f.read())}
    except OSError:
        return {}


class Texte:
    """Löst Textnummern auf. Aufrufbar: `t(30107)` oder `t(30106, pfad)`."""

    def __init__(self, sprache, sprachordner):
        self._sprache = sprache
        self._wurzel = sprachordner
        self._cache = {}
        self._addon = xbmcaddon.Addon() if sprache == AUTOMATISCH else None

    def _tabelle(self, sprache):
        if sprache not in self._cache:
            ordner = ORDNER.get(sprache, ORDNER[RUECKFALL])
            self._cache[sprache] = _lies_po(
                os.path.join(self._wurzel, ordner, "strings.po"))
        return self._cache[sprache]

    def sprache_fuer_seite(self):
        """Welche Sprache die Handy-Seite auszeichnen soll.

        Bei "Automatisch" richtet sich das nach Kodis Oberfläche; welche das
        ist, verrät Kodi nicht unmittelbar -- deshalb wird eine bekannte
        Zeichenkette verglichen.
        """
        if self._sprache != AUTOMATISCH:
            return self._sprache
        probe = self(30201)
        return ENGLISCH if probe == self._tabelle(ENGLISCH).get(30201) else DEUTSCH

    def __call__(self, nummer, *werte):
        if self._sprache == AUTOMATISCH:
            text = ""
            try:
                text = self._addon.getLocalizedString(nummer) or ""
            except Exception:
                text = ""
            if not text:
                # Kodi kennt die Sprache nicht oder liefert nichts: lieber ein
                # deutscher Text als ein leerer auf dem Fernseher.
                text = self._tabelle(RUECKFALL).get(nummer, "")
        else:
            text = self._tabelle(self._sprache).get(nummer, "")
        if werte:
            try:
                return text % werte
            except (TypeError, ValueError):
                return text
        return text


# Sprachkürzel für das lang-Attribut der Handy-Seite.
KUERZEL = {DEUTSCH: "de", ENGLISCH: "en"}

_MARKE = re.compile(r"\{\{T(\d+)\}\}")


def fuelle_seite(html, t=None):
    """Ersetzt {{T<nummer>}} und {{LANG}} in der Handy-Seite.

    Die Seite folgt damit derselben Sprache wie der Fernseher, nicht der
    Spracheinstellung des Handy-Browsers.
    """
    t = t or _aktuell
    if t is None:
        return html
    sprache = t.sprache_fuer_seite()
    html = html.replace("{{LANG}}", KUERZEL.get(sprache, "de"))
    return _MARKE.sub(lambda m: t(int(m.group(1))), html)


_aktuell = None


def einrichten(sprache, sprachordner):
    """Legt die Sprache für den ganzen Lauf fest und gibt die Texte zurück."""
    global _aktuell
    _aktuell = Texte(sprache, sprachordner)
    return _aktuell


def T(nummer, *werte):
    """Kurzform für den laufenden Vortrag; vor dem Einrichten liefert sie ''."""
    if _aktuell is None:
        return ""
    return _aktuell(nummer, *werte)
