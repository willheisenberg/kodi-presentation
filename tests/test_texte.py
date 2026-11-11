import json
import os
import re

import pytest

import texte

WURZEL = os.path.join(os.path.dirname(__file__), "..")
PO = os.path.join(WURZEL, "script.presentation", "resources", "language")
QUELLE = os.path.join(WURZEL, "tools", "texte.json")


def po_eintraege(ordner):
    pfad = os.path.join(PO, ordner, "strings.po")
    with open(pfad, encoding="utf-8") as f:
        inhalt = f.read()
    paare = re.findall(r'msgctxt "#(\d+)"\nmsgid "(.*)"\nmsgstr "(.*)"', inhalt)
    return {nr: msgstr for nr, _, msgstr in paare}


def test_beide_sprachen_kennen_dieselben_nummern():
    """Ein Text, den es nur in einer Sprache gibt, wäre im Betrieb leer."""
    de = po_eintraege("resource.language.de_de")
    en = po_eintraege("resource.language.en_gb")
    assert set(de) == set(en), f"nur in einer Sprache: {set(de) ^ set(en)}"
    assert len(de) > 40


def test_keine_leeren_uebersetzungen():
    for ordner in ("resource.language.de_de", "resource.language.en_gb"):
        leer = [nr for nr, wert in po_eintraege(ordner).items() if not wert.strip()]
        assert not leer, f"{ordner}: leere Texte {leer}"


def test_platzhalter_stimmen_zwischen_den_sprachen_ueberein():
    """%s in der einen, keines in der anderen Sprache -> Absturz beim Formatieren."""
    de, en = po_eintraege("resource.language.de_de"), po_eintraege("resource.language.en_gb")
    for nr in de:
        assert de[nr].count("%s") == en[nr].count("%s"), f"#{nr}: {de[nr]!r} / {en[nr]!r}"


def test_quelle_und_po_sind_deckungsgleich():
    """Die .po werden aus tools/texte.json erzeugt; nichts darf abweichen."""
    quelle = json.load(open(QUELLE, encoding="utf-8"))
    de = po_eintraege("resource.language.de_de")
    assert set(quelle) == set(de)
    for nr, (deutsch, _) in quelle.items():
        assert de[nr] == deutsch, f"#{nr}: {de[nr]!r} != {deutsch!r}"


def test_deutsch_liefert_deutsche_texte(addon_stub):
    t = texte.Texte(texte.DEUTSCH, PO)
    assert t(30107) == "Präsentation wählen"
    assert t(30201) == "Weiter"


def test_englisch_liefert_englische_texte(addon_stub):
    t = texte.Texte(texte.ENGLISCH, PO)
    assert t(30107) == "Choose a presentation"
    assert t(30201) == "Next"


def test_automatisch_fragt_kodi(addon_stub):
    """Bei 'Automatisch' entscheidet Kodis Oberflächensprache, nicht die .po-Datei."""
    gefragt = []

    def getLocalizedString(nummer):
        gefragt.append(nummer)
        return "von Kodi"

    addon_stub.getLocalizedString = getLocalizedString
    t = texte.Texte(texte.AUTOMATISCH, PO)
    assert t(30107) == "von Kodi"
    assert gefragt == [30107]


def test_automatisch_faellt_auf_die_datei_zurueck(addon_stub):
    """Liefert Kodi nichts, darf kein leerer Text auf dem Fernseher landen."""
    addon_stub.getLocalizedString = lambda nummer: ""
    t = texte.Texte(texte.AUTOMATISCH, PO)
    assert t(30107) == "Präsentation wählen"


def test_platzhalter_werden_gefuellt(addon_stub):
    t = texte.Texte(texte.ENGLISCH, PO)
    assert t(30106, "/storage/decks") == "No presentations found in /storage/decks."


def test_unbekannte_nummer_bricht_nicht_ab(addon_stub):
    t = texte.Texte(texte.DEUTSCH, PO)
    assert t(99999) == ""


def test_alle_benutzten_nummern_sind_uebersetzt():
    """Jede im Code aufgerufene Nummer muss in beiden Sprachen stehen."""
    lib = os.path.join(WURZEL, "script.presentation", "resources", "lib")
    benutzt = set()
    dateien = [os.path.join(lib, n) for n in os.listdir(lib) if n.endswith(".py")]
    dateien.append(os.path.join(WURZEL, "script.presentation", "default.py"))
    for pfad in dateien:
        with open(pfad, encoding="utf-8") as f:
            benutzt |= {m for m in re.findall(r"\bT\((\d{5})", f.read())}
    bekannt = set(po_eintraege("resource.language.de_de"))
    fehlend = benutzt - bekannt
    assert not fehlend, f"im Code benutzt, aber nicht übersetzt: {sorted(fehlend)}"


def test_seite_wird_vollstaendig_gefuellt(addon_stub):
    t = texte.Texte(texte.ENGLISCH, PO)
    html = '<html lang="{{LANG}}"><b>{{T30201}}</b><i>{{T30206}}</i></html>'
    gefuellt = texte.fuelle_seite(html, t)
    assert "{{" not in gefuellt, f"Platzhalter übrig: {gefuellt}"
    assert 'lang="en"' in gefuellt
    assert "Next" in gefuellt and "No notes for this slide." in gefuellt


def test_seite_auf_deutsch(addon_stub):
    t = texte.Texte(texte.DEUTSCH, PO)
    gefuellt = texte.fuelle_seite('<html lang="{{LANG}}">{{T30201}}</html>', t)
    assert 'lang="de"' in gefuellt and "Weiter" in gefuellt


def test_echte_seite_hat_keine_platzhalter_mehr(addon_stub):
    """Die ausgelieferte Seite darf keine unersetzten Marken enthalten."""
    pfad = os.path.join(WURZEL, "script.presentation", "resources", "web", "presenter.html")
    with open(pfad, encoding="utf-8") as f:
        roh = f.read()
    t = texte.Texte(texte.ENGLISCH, PO)
    gefuellt = texte.fuelle_seite(roh, t)
    uebrig = re.findall(r"\{\{[^}]*\}\}", gefuellt)
    assert not uebrig, f"nicht ersetzt: {uebrig}"
