"""Stubs für die Kodi-Module, damit die Tests ohne Kodi laufen."""
import sys
import types

import pytest


class _StubAddon:
    def __init__(self, *a, **k):
        self.werte = {}
        self.pfad = "/tmp/addon"

    def getSetting(self, key):
        return self.werte.get(key, "")

    def getSettingInt(self, key):
        return int(self.werte.get(key, 0))

    def setSetting(self, key, wert):
        self.werte[key] = wert

    def getAddonInfo(self, key):
        # Kodi liefert profile als special://-Pfad. Python kann damit nichts
        # anfangen -- genau daran ist das Add-on am Geraet gescheitert.
        return {
            "path": self.pfad,
            "profile": "special://profile/addon_data/script.presentation/",
            "id": "script.presentation",
        }.get(key, "")

    def getLocalizedString(self, _id):
        return ""


def _stub_module(name, **inhalt):
    modul = types.ModuleType(name)
    for k, v in inhalt.items():
        setattr(modul, k, v)
    sys.modules[name] = modul
    return modul


_stub_module("xbmc", log=lambda *a, **k: None, LOGINFO=1, LOGERROR=3,
             translatePath=lambda p: p, executebuiltin=lambda *a: None)
_stub_module("xbmcaddon", Addon=_StubAddon)
class _StubStat:
    """Bildet xbmcvfs.Stat nach; Tests verstellen die Klassenattribute."""
    mtime = 1000
    size = 500

    def __init__(self, pfad):
        self._pfad = pfad

    def st_mtime(self):
        return _StubStat.mtime

    def st_size(self):
        return _StubStat.size


def _translate(pfad):
    """Bildet Kodis translatePath nach, inklusive der special://-Schemata."""
    return (pfad.replace("special://profile", "/tmp/kodi/userdata")
                .replace("special://home", "/tmp/kodi")
                .replace("special://temp", "/tmp/kodi/temp"))


_stub_module("xbmcvfs", exists=lambda p: False, listdir=lambda p: ([], []),
             copy=lambda a, b: True, delete=lambda p: True,
             translatePath=_translate, mkdirs=lambda p: True, Stat=_StubStat)
_stub_module("xbmcgui", WindowXML=object, Dialog=object,
             DialogProgress=object, ListItem=object)
_stub_module("xbmcplugin")


@pytest.fixture
def addon_stub():
    """Frischer Add-on-Stub je Test."""
    stub = _StubAddon()
    sys.modules["xbmcaddon"].Addon = lambda *a, **k: stub
    return stub


@pytest.fixture(autouse=True)
def _texte_eingerichtet():
    """Die Module übersetzen über texte.T(); ohne Einrichtung käme überall ein
    leerer String heraus. In Tests gilt Deutsch, sofern nichts anderes gesetzt wird."""
    import os
    import texte
    texte.einrichten(texte.DEUTSCH, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "script.presentation", "resources", "language"))
