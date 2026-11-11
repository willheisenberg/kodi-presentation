import os
import re

import pytest

SEITE = os.path.join(os.path.dirname(__file__), "..", "script.presentation",
                     "resources", "web", "presenter.html")


@pytest.fixture
def html():
    with open(SEITE, encoding="utf-8") as f:
        return f.read()


def test_keine_externen_ressourcen(html):
    """Im LAN gibt es womöglich kein Internet."""
    treffer = re.findall(r'(?:src|href)\s*=\s*["\'](https?:)?//', html)
    assert not treffer, f"externe Ressource gefunden: {treffer}"


def test_relative_pfade_statt_absoluter(html):
    """Die Seite läuft unter /p/<token>/ und muss relativ verlinken."""
    assert not re.search(r'fetch\(\s*["\']/', html), "fetch darf nicht mit / beginnen"


def test_spricht_die_richtigen_routen_an(html):
    assert "state?seit=" in html
    assert "cmd" in html
    assert "thumb/" in html


def test_enthaelt_die_bedienelemente(html):
    for kennung in ('id="notizen"', 'id="vor"', 'id="zurueck"',
                    'id="timer"', 'id="zaehler"', 'id="blende"'):
        assert kennung in html, f"fehlt: {kennung}"


def test_viewport_fuer_handys(html):
    assert 'name="viewport"' in html


def test_sprache_ist_ein_platzhalter(html):
    """Die Seite soll der im Add-on eingestellten Sprache folgen."""
    assert 'lang="{{LANG}}"' in html


def test_keine_fest_verdrahteten_texte(html):
    """Alle sichtbaren Texte kommen aus den Sprachdateien."""
    import re
    verdaechtig = []
    for wort in ("Weiter", "Zurück", "Bildschirm schwarz", "Timer zurücksetzen",
                 "Keine Notizen", "Keine Verbindung", "Nächste", "keine Folien",
                 "Referentenansicht", "Präsentation beendet"):
        if wort in html:
            verdaechtig.append(wort)
    assert not verdaechtig, f"fest verdrahtet statt übersetzt: {verdaechtig}"


def test_enthaelt_textplatzhalter(html):
    import re
    nummern = set(re.findall(r"\{\{T(\d{5})\}\}", html))
    assert len(nummern) >= 10, f"zu wenige Platzhalter: {sorted(nummern)}"
