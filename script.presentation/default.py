"""Einstiegspunkt: Deck wählen, rendern, Server starten, Fenster öffnen."""
import os
import sys

import xbmc
import xbmcgui

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import deck_browser                     # noqa: E402
import deck_cache                       # noqa: E402
import handy_server                     # noqa: E402
import konfig                           # noqa: E402
import praesentations_fenster as pf     # noqa: E402
import renderer                         # noqa: E402
import sitzung as sitzung_modul         # noqa: E402
import texte                            # noqa: E402
from texte import T                     # noqa: E402

SKIN_DATEI = "script-presentation-main.xml"


def _protokoll(text, stufe=None):
    xbmc.log(f"[script.presentation] {text}", stufe or xbmc.LOGINFO)


def _fehler(text):
    _protokoll(text, xbmc.LOGERROR)
    xbmcgui.Dialog().ok(T(30100), text)


def _zeige_url(url):
    """Die URL als Dialog, nicht im Präsentationsfenster.

    Kodi zeichnet im Präsentationsfenster keine Textelemente (am Gerät
    nachgewiesen); die Dialogvorlage des Skins kann es sehr wohl. Danach zeigt
    der Fernseher nur noch Folie und QR-Code.
    """
    if url:
        xbmcgui.Dialog().ok(T(30101),
                            f"{T(30102)}\n\n{url}\n\n{T(30103)}")
    else:
        xbmcgui.Dialog().ok(T(30100), f"{T(30104)}\n{T(30105)}")


def _melde_luecken(manifest):
    """Weist einmalig auf Folien hin, die fehlen oder nicht gezeichnet wurden."""
    teile = []
    if manifest.get("verloreneFolien"):
        teile.append(T(30111, manifest["verloreneFolien"]))
    if manifest.get("fehlendeBilder"):
        teile.append(T(30112, manifest["fehlendeBilder"]))
    if teile:
        xbmcgui.Dialog().notification(T(30100), ", ".join(teile))


def _waehle_deck(k):
    decks = deck_browser.finde_decks(k.deck_ordner)
    if not decks:
        _fehler(T(30106, k.deck_ordner))
        return None
    wahl = xbmcgui.Dialog().select(T(30107), [d["name"] for d in decks])
    return decks[wahl] if wahl >= 0 else None


def _bereite_vor(k, r, pfad):
    cache = deck_cache.DeckCache(os.path.join(k.daten_pfad, "cache"), k.cache_grenze_bytes)
    dialog = xbmcgui.DialogProgress()
    dialog.create(T(30100), T(30108))
    try:
        return cache.hole(pfad, r, k.skalierung,
                          fortschritt=lambda p, t: dialog.update(p, t))
    finally:
        dialog.close()


def _qr_bild(k, url):
    """QR ist Beiwerk: ein Fehler hier darf den Vortrag nie verhindern."""
    if not url:
        return ""
    try:
        import qr
        ziel = os.path.join(k.daten_pfad, "qr.png")
        qr.als_png(url, ziel, modulgroesse=10, rahmen=40, leinwand=(1920, 1080))
        return ziel
    except Exception as e:
        _protokoll(f"QR übersprungen: {e}")
        return ""


def main():
    k = konfig.Konfig()
    # Zuerst die Sprache: alles Folgende meldet sich schon übersetzt.
    texte.einrichten(k.sprache, k.sprach_ordner)
    deck = _waehle_deck(k)
    if deck is None:
        return

    # Der Renderer richtet sich nach der Dateiendung: DeckCraft für .pptx und
    # .deckcraft, pdfrender für .pdf. Beide haben dieselbe Schnittstelle.
    try:
        r = renderer.fuer_deck(deck["pfad"], k.binary_pfad, k.pdf_binary_pfad)
        _protokoll(f"Renderer: {r.version()}")
    except renderer.RendererFehler as e:
        return _fehler(str(e))

    try:
        manifest = _bereite_vor(k, r, deck["pfad"])
    except Exception as e:
        return _fehler(f"{T(30109)}\n{e}")

    _melde_luecken(manifest)

    folien = manifest.get("folien") or []
    if not folien:
        return _fehler(T(30110))

    s = sitzung_modul.Sitzung(len(folien))
    with open(os.path.join(k.addon_pfad, "resources", "web", "presenter.html"),
              encoding="utf-8") as f:
        seite = texte.fuelle_seite(f.read())

    def anstupsen():
        """Weckt den GUI-Thread, damit er den Handy-Befehl nachzeichnet.
        executebuiltin ist thread-sicher; die Taste selbst bewirkt nichts."""
        xbmc.executebuiltin("Action(noop)")

    server = handy_server.HandyServer(s, manifest, seite, port=k.port,
                                      anstupsen=anstupsen)
    url = ""
    try:
        url = server.starten()
        _protokoll(f"Referentenansicht: {url.rsplit('/p/', 1)[0]}/p/<token>/")
    except OSError as e:
        _protokoll(f"Handy-Ansicht aus: {e}", xbmc.LOGERROR)

    # Ab hier muss der Server in jedem Fall wieder gestoppt werden: das Add-on
    # läuft im Kodi-Prozess, ein übrig gebliebener Thread hält den Port belegt.
    fenster = None
    try:
        qr_pfad = _qr_bild(k, url)
        _zeige_url(url)
        fenster = pf.PraesentationsFenster(
            SKIN_DATEI, k.addon_pfad, "Default", "1080i")
        fenster.setze_daten(s, manifest, qr_pfad)
        pf.fuehre_praesentation(s, server, fenster)   # show() + Hauptschleife
    finally:
        server.stoppen()        # idempotent; fängt Fehler vor dem Fenster ab
        if fenster is not None:
            del fenster


if __name__ == "__main__":
    main()
