import inspect

import pytest

import praesentations_fenster as pf
import sitzung

class NurBilderFenster:
    """Fängt jeden GUI-Zugriff ab. setVisible und setProperty wirken aus einem
    Nebenthread nicht (am Gerät nachgewiesen); erlaubt ist nur setImage."""

    def __init__(self):
        self.bilder = {}

    def setProperty(self, name, wert):
        raise AssertionError("setProperty wirkt aus dem Nebenthread nicht")

    def getControl(self, cid):
        fenster = self

        class Steuerung:
            def setImage(self, pfad):
                fenster.bilder[cid] = pfad

            def setVisible(self, sichtbar):
                raise AssertionError("setVisible wirkt aus dem Nebenthread nicht")
        return Steuerung()


def _fenster_mit(sitzung_, manifest, qr="/qr.png"):
    f = pf.PraesentationsFenster.__new__(pf.PraesentationsFenster)
    f.setze_daten(sitzung_, manifest, qr)
    f._bereit = True
    f.bilder = {}
    f.setProperty = NurBilderFenster.setProperty.__get__(f)
    f.getControl = NurBilderFenster.getControl.__get__(f)
    return f


class ServerAttrappe:
    def __init__(self):
        self.gestoppt = False

    def stoppen(self):
        self.gestoppt = True


# Kodi-Aktionscodes, siehe xbmcgui
LINKS, RECHTS, HOCH, RUNTER = 1, 2, 3, 4
OK, ZURUECK_MENUE, INFO = 7, 10, 11
VORHERIGER, NAECHSTER = 13, 14
KONTEXTMENUE, NAV_ZURUECK = 117, 92


@pytest.mark.parametrize("code", [RECHTS, RUNTER, OK, NAECHSTER])
def test_vorwaerts_tasten(code):
    assert pf.AKTIONEN.get(code) == "vor"


@pytest.mark.parametrize("code", [LINKS, HOCH, VORHERIGER])
def test_rueckwaerts_tasten(code):
    assert pf.AKTIONEN.get(code) == "zurueck"


def test_info_oeffnet_das_raster():
    assert pf.AKTIONEN.get(INFO) == "raster"


def test_kontextmenue_schaltet_die_blende():
    assert pf.AKTIONEN.get(KONTEXTMENUE) == "blende"


@pytest.mark.parametrize("code", [ZURUECK_MENUE, NAV_ZURUECK])
def test_zurueck_beendet(code):
    assert pf.AKTIONEN.get(code) == "ende"


def test_unbekannte_taste_tut_nichts():
    assert pf.AKTIONEN.get(999) is None


def test_fuehre_aus_blaettert():
    s = sitzung.Sitzung(3)
    assert pf.fuehre_aus(s, "vor") is None
    assert s.index == 1
    pf.fuehre_aus(s, "zurueck")
    assert s.index == 0


def test_fuehre_aus_meldet_ende():
    s = sitzung.Sitzung(3)
    assert pf.fuehre_aus(s, "ende") == "ende"


def test_fuehre_aus_meldet_raster():
    s = sitzung.Sitzung(3)
    assert pf.fuehre_aus(s, "raster") == "raster"


def test_fuehre_aus_schaltet_blende():
    s = sitzung.Sitzung(3)
    pf.fuehre_aus(s, "blende")
    assert s.blende is True


def test_bildpfad_der_aktuellen_folie():
    manifest = {"folien": [{"index": 0, "bild": "/c/a.png"},
                           {"index": 1, "bild": "/c/b.png"}]}
    assert pf.bild_fuer(manifest, 0) == "/c/a.png"
    assert pf.bild_fuer(manifest, 1) == "/c/b.png"
    assert pf.bild_fuer(manifest, 9) == ""


def test_bildpfad_bei_leerem_deck():
    assert pf.bild_fuer({"folien": []}, 0) == ""
    assert pf.bild_fuer({}, 0) == ""


def test_rastereintraege_zeigen_titel_ohne_notizen():
    manifest = {"folien": [{"index": 0, "titel": "Erste", "notizen": "geheim"},
                           {"index": 1, "titel": "", "notizen": "auch geheim"}]}
    eintraege = pf.raster_eintraege(manifest)
    assert eintraege == ["1. Erste", "2. ohne Titel"]
    assert not any("geheim" in e for e in eintraege)


def test_fenstermodul_liest_das_notizfeld_nirgends():
    """Harte Zusage der Spec: Notizen erscheinen nie auf dem Fernseher."""
    quelle = inspect.getsource(pf)
    assert '"notizen"' not in quelle and "'notizen'" not in quelle, \
        "Das Fenstermodul darf das Manifest-Feld notizen nicht lesen"


def test_fenster_zeichnet_nicht_vor_oninit():
    """Vor onInit gibt es keine Steuerelemente; ein Zeichnen muss unterbleiben."""
    f = pf.PraesentationsFenster.__new__(pf.PraesentationsFenster)
    f.setze_daten(sitzung.Sitzung(3), {"folien": [{"index": 0, "bild": "/a.png"}]})
    f.aktualisiere_wenn_noetig()   # darf getControl nicht anfassen


def test_startkarte_verschwindet_auch_ohne_tastendruck():
    """W3: Wer nur über das Handy blättert, drückte nie eine Taste -- der
    QR-Kasten blieb den ganzen Vortrag über jeder Folie, vor Publikum."""
    f = pf.PraesentationsFenster.__new__(pf.PraesentationsFenster)
    s = sitzung.Sitzung(5)
    f.setze_daten(s, {"folien": [{"index": i, "bild": f"/{i}.png"} for i in range(5)]}, "/qr.png")
    f._bereit = True
    gezeichnet = []
    f._zeichne = lambda: gezeichnet.append(f._startkarte_sichtbar)
    assert f._startkarte_sichtbar is True
    s.vor()                      # Befehl vom Handy
    f.aktualisiere_wenn_noetig()
    assert f._startkarte_sichtbar is False, "Karte muss bei der ersten Änderung weg sein"


def test_startkarte_bleibt_vor_der_ersten_aenderung():
    f = pf.PraesentationsFenster.__new__(pf.PraesentationsFenster)
    s = sitzung.Sitzung(5)
    f.setze_daten(s, {"folien": [{"index": 0, "bild": "/0.png"}]}, "/qr.png")
    f._bereit = True
    f._zeichne = lambda: None
    f.aktualisiere_wenn_noetig()
    assert f._startkarte_sichtbar is True


class ModalFenster:
    """Fenster-Attrappe für doModal."""

    def __init__(self, wirft=False):
        self.wirft = wirft
        self.aufgerufen = False

    def doModal(self):
        self.aufgerufen = True
        if self.wirft:
            raise RuntimeError("Fenster kaputt")


def test_praesentation_zeigt_das_fenster_und_stoppt_den_server():
    s = sitzung.Sitzung(3)
    server = ServerAttrappe()
    fenster = ModalFenster()
    pf.fuehre_praesentation(s, server, fenster)
    assert fenster.aufgerufen and server.gestoppt


def test_praesentation_stoppt_den_server_auch_bei_fehler():
    """W6: Weil das Add-on im Kodi-Prozess läuft, überlebt ein nicht gestoppter
    Server-Thread das Script -- Port belegt, Sitzung weiter fernsteuerbar."""
    s = sitzung.Sitzung(3)
    server = ServerAttrappe()
    fenster = ModalFenster(wirft=True)
    with pytest.raises(RuntimeError):
        pf.fuehre_praesentation(s, server, fenster)
    assert server.gestoppt, "Server muss auch bei einer Ausnahme gestoppt werden"


def test_unbekannte_taste_zeichnet_nach():
    """Der HTTP-Thread stupst über Kodis Dispatch eine wirkungslose Taste an;
    sie darf nichts verändern, muss aber neu zeichnen -- das ist der einzige
    Weg, auf dem ein Handy-Befehl den Fernseher erreicht."""
    s = sitzung.Sitzung(3)
    f = _fenster_mit(s, {"folien": [{"index": i, "bild": f"/{i}.png"} for i in range(3)]})
    f._zeichne()
    s.vor()                                  # Befehl kam über HTTP herein

    class Unbekannt:
        def getId(self):
            return 999

    f.onAction(Unbekannt())
    assert f.bilder[pf.STEUERUNG_FOLIE] == "/1.png", "Fernseher muss nachziehen"
    assert s.index == 1, "die Taste selbst darf nichts verändern"


def test_zurueck_schliesst_das_fenster():
    s = sitzung.Sitzung(3)
    f = _fenster_mit(s, {"folien": [{"index": 0, "bild": "/0.png"}]})
    f._zeichne()
    geschlossen = []
    f.close = lambda: geschlossen.append(1)

    class Aktion:
        def getId(self):
            return 92

    f.onAction(Aktion())
    assert geschlossen, "Zurück muss das Fenster schließen"
