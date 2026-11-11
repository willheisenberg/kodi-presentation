"""Findet Präsentationen im eingestellten Ordner.

Nutzt xbmcvfs statt os.listdir, damit Kodi-Quellen wie smb:// funktionieren.
"""
import xbmcvfs

# PDF kommt ohne Referentennotizen; siehe pdf_renderer.
ENDUNGEN = (".pptx", ".deckcraft", ".pdf")


def _als_ordner(pfad):
    """Kodi-Eigenheit: xbmcvfs.exists() liefert für Verzeichnisse ohne
    abschließenden Schrägstrich False."""
    return pfad.rstrip("/") + "/"


def _verbinde(ordner, name):
    """Setzt Pfade zusammen, ohne doppelten Schrägstrich und ohne os.path,
    das bei smb://-Pfaden falsch läge."""
    return ordner.rstrip("/") + "/" + name


def _ist_beiwerk(name):
    """Punktdateien und macOS-Doppel (._name) sind keine Präsentationen."""
    return name.startswith(".")


def finde_decks(ordner):
    if not ordner or not xbmcvfs.exists(_als_ordner(ordner)):
        return []
    try:
        _, dateien = xbmcvfs.listdir(ordner)
    except OSError:
        return []
    decks = [
        {"pfad": _verbinde(ordner, name), "name": name}
        for name in dateien
        if name.lower().endswith(ENDUNGEN) and not _ist_beiwerk(name)
    ]
    decks.sort(key=lambda d: d["name"].lower())
    return decks
