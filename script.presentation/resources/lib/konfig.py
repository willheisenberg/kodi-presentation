"""Liest die Add-on-Einstellungen und hält die Vorgaben an einer Stelle."""
import os

import xbmcaddon
import xbmcvfs

VORGABEN = {
    "deck_ordner": "/storage/presentations",
    "skalierung": 2,
    "port": 8099,
    "cache_grenze_gb": 2,
    "sprache": 0,
}


class Konfig:
    def __init__(self):
        self._addon = xbmcaddon.Addon()

    def _text(self, schluessel):
        wert = self._addon.getSetting(schluessel)
        return wert if wert else VORGABEN[schluessel]

    def _zahl(self, schluessel, kleinster, groesster):
        """Unsinnige Werte fallen stillschweigend auf die Vorgabe zurück."""
        try:
            wert = int(self._addon.getSetting(schluessel))
        except (TypeError, ValueError):
            return VORGABEN[schluessel]
        return wert if kleinster <= wert <= groesster else VORGABEN[schluessel]

    @property
    def deck_ordner(self):
        return self._text("deck_ordner")

    @property
    def skalierung(self):
        return self._zahl("skalierung", 1, 4)

    @property
    def port(self):
        return self._zahl("port", 1024, 65535)

    @property
    def cache_grenze_bytes(self):
        return self._zahl("cache_grenze_gb", 1, 100) * 1024**3

    @property
    def addon_pfad(self):
        return self._pfad("path")

    @property
    def daten_pfad(self):
        return self._pfad("profile")

    def _pfad(self, schluessel):
        """Kodi liefert diese Angaben als special://-Pfade, mit denen Python
        nichts anfangen kann -- erst übersetzen."""
        return xbmcvfs.translatePath(self._addon.getAddonInfo(schluessel))

    @property
    def sprache(self):
        """0 = wie Kodi, 1 = Deutsch, 2 = Englisch."""
        return self._zahl("sprache", 0, 2)

    @property
    def sprach_ordner(self):
        return os.path.join(self.addon_pfad, "resources", "language")

    @property
    def binary_pfad(self):
        return os.path.join(self.addon_pfad, "bin", "deckcraft-cli")

    @property
    def pdf_binary_pfad(self):
        return os.path.join(self.addon_pfad, "bin", "pdfrender")
