"""Läuft gegen das echte Binary: python -m pytest -m binary

Auf einem x86-Rechner ist das mitgelieferte aarch64-Binary nicht ausführbar;
die betroffenen Tests überspringen dann mit Begründung. Der eigentliche
Nachweis auf dem Zielgerät läuft über SSH, siehe docs/.
"""
import os
import subprocess

import pytest

import deck_cache
import renderer

WURZEL = os.path.join(os.path.dirname(__file__), "..")
BINARY = os.path.join(WURZEL, "script.presentation", "bin", "deckcraft-cli")
DECK = os.path.join(WURZEL, "tests", "data", "testdeck.pptx")

pytestmark = pytest.mark.binary


def _laeuft_hier():
    if not os.path.isfile(BINARY):
        return False
    try:
        return subprocess.run([BINARY, "--version"], capture_output=True,
                              timeout=20).returncode == 0
    except OSError:
        return False


lauffaehig = pytest.mark.skipif(
    not _laeuft_hier(),
    reason="deckcraft-cli ist hier nicht ausführbar (aarch64-Binary auf fremder Architektur)")


def test_binary_ist_vorhanden():
    assert os.path.isfile(BINARY), "erst tools/build-deckcraft.sh ausführen"


def test_binary_ist_fuer_aarch64_und_statisch():
    ausgabe = subprocess.run(["file", BINARY], capture_output=True, text=True).stdout
    assert "ARM aarch64" in ausgabe
    assert "statically linked" in ausgabe


def test_testdeck_liegt_bei():
    assert os.path.getsize(DECK) > 1000


@lauffaehig
def test_info_liest_notizen():
    info = renderer.DeckcraftRenderer(BINARY).info(DECK)
    assert len(info.folien) == 5
    assert "NIEMALS" in info.folien[0].notizen
    assert info.folien[4].notizen == "", "letzte Folie hat bewusst keine Notiz"


@lauffaehig
def test_render_erzeugt_bilder_in_voller_groesse(tmp_path):
    bilder = renderer.DeckcraftRenderer(BINARY).render(DECK, str(tmp_path / "o"), 2)
    assert len(bilder) == 5
    for p in bilder:
        assert os.path.getsize(p) > 1000


@lauffaehig
def test_voller_cache_durchlauf(tmp_path):
    r = renderer.DeckcraftRenderer(BINARY)
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    m = c.hole(DECK, r, 2)
    assert len(m["folien"]) == 5
    assert os.path.isfile(m["folien"][0]["bild"])
    assert os.path.isfile(m["folien"][0]["vorschau"])
    assert "NIEMALS" in m["folien"][0]["notizen"]


@lauffaehig
def test_dateiname_mit_umlauten_und_leerzeichen(tmp_path):
    """Review Focus 2 gegen das echte Binary."""
    heikel = tmp_path / "Mein Vörtrag (2026).pptx"
    with open(DECK, "rb") as q, open(heikel, "wb") as z:
        z.write(q.read())
    bilder = renderer.DeckcraftRenderer(BINARY).render(str(heikel), str(tmp_path / "o2"), 1)
    assert len(bilder) == 5
