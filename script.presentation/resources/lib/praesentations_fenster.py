"""Vollbildfenster für die Folien auf dem Fernseher.

Dieses Modul liest absichtlich nirgends das Notizfeld aus dem Manifest.
Referentennotizen gehören auf das Handy, nie auf den Fernseher; der Test
test_fenstermodul_liest_das_notizfeld_nirgends hält das fest.
"""
import os
import threading

import xbmcgui

from texte import T

def _medium(name):
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "skins", "Default", "media", name))


# Einfarbig schwarzes Vollbild für die Schwarzblende.
SCHWARZ = _medium("schwarz.png")

# Kodi-Aktionscodes auf Aktionsnamen. Bewusst als Tabelle, damit die
# Zuordnung ohne laufendes Kodi prüfbar ist.
AKTIONEN = {
    1: "zurueck",    # links
    3: "zurueck",    # hoch
    13: "zurueck",   # vorheriger Titel
    2: "vor",        # rechts
    4: "vor",        # runter
    7: "vor",        # OK
    14: "vor",       # nächster Titel
    11: "raster",    # Info
    117: "blende",   # Kontextmenü
    10: "ende",      # Menü zurück
    92: "ende",      # Navigation zurück
}

STEUERUNG_FOLIE = 100


def bild_fuer(manifest, index):
    folien = manifest.get("folien") or []
    if 0 <= index < len(folien):
        return folien[index].get("bild") or ""
    return ""


def raster_eintraege(manifest):
    """Beschriftungen für das Sprungraster: ausschließlich Nummer und Titel."""
    folien = manifest.get("folien") or []
    ohne = T(30118)
    return [f"{i + 1}. {f.get('titel') or ohne}" for i, f in enumerate(folien)]


def fuehre_praesentation(sitzung_, server, fenster):
    """Zeigt das Fenster und hält es aus dem Hauptthread aktuell.

    Kodi nimmt GUI-Änderungen nur aus seinem eigenen Thread an: ein Nebenthread
    meldet zwar Erfolg, auf dem Fernseher passiert aber nichts -- am Gerät
    nachgewiesen (Befehl vom Handy quittiert, Folie blieb stehen). Befehle vom
    Handy erreichen den Fernseher deshalb über Kodis eigenen, thread-sicheren
    Dispatch: der HTTP-Thread stupst eine wirkungslose Taste an, die onAction
    im GUI-Thread auslöst, und dort wird neu gezeichnet.

    Das Add-on läuft im Kodi-Prozess; ein nicht gestoppter Server-Thread würde
    das Script überleben, den Port belegen und fernsteuerbar bleiben.
    """
    try:
        fenster.doModal()
    finally:
        server.stoppen()


def fuehre_aus(sitzung_, aktion):
    """Führt eine Aktion aus. Gibt 'ende' oder 'raster' zurück, sonst None."""
    if aktion == "vor":
        sitzung_.vor()
    elif aktion == "zurueck":
        sitzung_.zurueck()
    elif aktion == "blende":
        sitzung_.blende_umschalten()
    elif aktion in ("ende", "raster"):
        return aktion
    return None


class PraesentationsFenster(xbmcgui.WindowXML):
    """Erwartet sitzung, manifest und optional den QR-Pfad über setze_daten().

    Das Fenster zeigt ausschließlich Bilder: die Folie, die Startkarte mit dem
    QR-Code und die Schwarzblende. Kodi zeichnet hier keine Textelemente (am
    Gerät nachgewiesen), und Geschriebenes gehört ohnehin auf das Handy.
    """

    def setze_daten(self, sitzung_, manifest, qr_pfad=""):
        self.sitzung = sitzung_
        self.manifest = manifest
        self.qr_pfad = qr_pfad
        self._startkarte_sichtbar = True
        # Auf den aktuellen Stand setzen, nicht auf 0: sonst meldet
        # warte_auf_aenderung sofort eine Änderung, die Hauptschleife dreht
        # ohne Pause durch und nimmt Kodis GUI-Thread die Rechenzeit.
        self._letzte_version = sitzung_.version
        self._bereit = False   # vor onInit gibt es keine Steuerelemente
        self.beendet = False

    def onInit(self):
        self._bereit = True
        if not self.qr_pfad:
            self._startkarte_sichtbar = False   # ohne QR gibt es nichts zu zeigen
        self._zeichne()

    def _zeichne(self):
        """Zeichnet den aktuellen Stand.

        Jede Änderung läuft über setImage(). Der Beobachter-Thread ist nicht
        Kodis GUI-Thread; setVisible und setProperty bleiben von dort wirkungslos
        (am Gerät nachgewiesen: die Folie wechselte, der QR-Kasten blieb stehen
        und die Blende vom Handy tat nichts), setImage dagegen wirkt. Ausgeblendet
        wird mit einem transparenten Bild, nicht mit setImage("") -- das
        behandelt Kodi als "nichts ändern".
        """
        z = self.sitzung.zustand()
        self._letzte_version = z["version"]
        # Alles läuft über ein einziges Bildelement: Startkarte, Schwarzblende
        # und Folie ersetzen einander. Ein zweites, überlagerndes Element blieb
        # am Gerät unsichtbar, und setImage mit einem transparenten Bild wirkte
        # unzuverlässig -- dieses hier aktualisiert immer.
        if z["blende"]:
            bild = SCHWARZ
        elif self._startkarte_sichtbar:
            bild = self.qr_pfad
        else:
            bild = bild_fuer(self.manifest, z["index"])
        self.getControl(STEUERUNG_FOLIE).setImage(bild)

    def aktualisiere_wenn_noetig(self):
        """Zeichnet neu, wenn sich die Sitzung geändert hat."""
        if not self._bereit:
            return
        if self.sitzung.version != self._letzte_version:
            # Auch ohne Tastendruck: wer nur über das Handy blättert, soll den
            # QR-Kasten nicht den ganzen Vortrag über jeder Folie sehen.
            if self.sitzung.index != 0 or self.sitzung.blende:
                self._startkarte_sichtbar = False
            self._zeichne()

    def onAction(self, action):
        aktion = AKTIONEN.get(action.getId())
        if aktion is None:
            # Angestupst vom HTTP-Thread: nichts verändern, nur nachziehen.
            self.aktualisiere_wenn_noetig()
            return
        if self._startkarte_sichtbar:
            # Der erste Tastendruck blendet nur die Startkarte aus.
            self._startkarte_sichtbar = False
            self._zeichne()
            if aktion != "ende":
                return
        ergebnis = fuehre_aus(self.sitzung, aktion)
        if ergebnis == "ende":
            self.close()
        elif ergebnis == "raster":
            self._zeige_raster()
        else:
            self._zeichne()

    def _zeige_raster(self):
        """Folienliste zum Springen; OK springt, Zurück kehrt ohne Sprung zurück."""
        eintraege = raster_eintraege(self.manifest)
        if not eintraege:
            return
        wahl = xbmcgui.Dialog().select(T(30117), eintraege)
        if wahl >= 0:
            self.sitzung.springe(wahl)
        self._zeichne()
