"""Prüft die Skin-Datei des Fensters.

Am Gerät aufgefallen: `white.png` wird aus dem Skin des Nutzers erwartet.
Hat dessen Skin die Textur nicht, bleiben Kasten und Schwarzblende unsichtbar --
ohne jede Fehlermeldung im Log. Mitgelieferte Texturen schließen das aus.
"""
import os
import re
import xml.etree.ElementTree as ET

import pytest

SKIN_DIR = os.path.join(os.path.dirname(__file__), "..", "script.presentation",
                        "resources", "skins", "Default")
XML = os.path.join(SKIN_DIR, "1080i", "script-presentation-main.xml")
MEDIA = os.path.join(SKIN_DIR, "media")


@pytest.fixture
def baum():
    return ET.parse(XML)


def texturen(baum):
    namen = set()
    for t in baum.iter("texture"):
        if t.text and t.text.strip():
            namen.add(t.text.strip())
    return namen


def test_alle_texturen_werden_mitgeliefert(baum):
    fehlend = [n for n in texturen(baum) if not os.path.isfile(os.path.join(MEDIA, n))]
    assert not fehlend, f"nicht mitgelieferte Texturen: {fehlend}"


def test_texturen_sind_echte_pngs(baum):
    for n in texturen(baum):
        with open(os.path.join(MEDIA, n), "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n", f"{n} ist kein PNG"


def test_steuerelement_ids_stimmen_mit_dem_modul_ueberein(baum):
    import praesentations_fenster as pf
    ids = {int(c.get("id")) for c in baum.iter("control") if c.get("id")}
    for name in ("STEUERUNG_FOLIE",):
        assert getattr(pf, name) in ids, f"{name} fehlt in der Skin-Datei"


def test_kein_defaultcontrol_auf_einem_bild(baum):
    """Ein Bild kann keinen Fokus annehmen; Kodi meldet das als Fehler."""
    wurzel = baum.getroot()
    dc = wurzel.find("defaultcontrol")
    if dc is not None and dc.text:
        ziel = int(dc.text.strip())
        typen = {int(c.get("id")): c.get("type")
                 for c in baum.iter("control") if c.get("id")}
        assert typen.get(ziel) not in ("image", "label"), \
            f"defaultcontrol zeigt auf ein {typen.get(ziel)}"


def test_fenster_enthaelt_keine_textelemente(baum):
    """Am Gerät nachgewiesen: Kodi zeichnet in diesem Fenster weder Label noch
    Textbox, Bilder dagegen zuverlässig. Ein unsichtbares Steuerelement ist
    schlimmer als keines -- und Geschriebenes gehört ohnehin auf das Handy."""
    textarten = [c.get("type") for c in baum.iter("control")
                 if c.get("type") in ("label", "textbox", "fadelabel")]
    assert not textarten, f"Textelemente im Fenster: {textarten}"


def test_nur_bildelemente_im_fenster(baum):
    """Jede Änderung muss über setImage laufen; andere Elementarten hätten
    keinen Weg, aus dem Beobachter-Thread aktualisiert zu werden."""
    arten = {c.get("type") for c in baum.iter("control")}
    assert arten == {"image"}, f"fremde Elementarten: {arten - {'image'}}"
