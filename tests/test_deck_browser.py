import sys

import deck_browser


def _vfs(monkeypatch, dateien, existiert=True):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: existiert)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir", lambda p: ([], dateien))


def test_findet_nur_praesentationen(tmp_path, monkeypatch):
    _vfs(monkeypatch, ["a.pptx", "b.deckcraft", "c.txt", "d.PPTX", "e.mp4"])
    gefunden = {d["name"] for d in deck_browser.finde_decks(str(tmp_path))}
    assert gefunden == {"a.pptx", "b.deckcraft", "d.PPTX"}


def test_leerer_ordner_gibt_leere_liste(tmp_path, monkeypatch):
    _vfs(monkeypatch, [])
    assert deck_browser.finde_decks(str(tmp_path)) == []


def test_fehlender_ordner_gibt_leere_liste(monkeypatch):
    _vfs(monkeypatch, ["a.pptx"], existiert=False)
    assert deck_browser.finde_decks("/gibt/es/nicht") == []


def test_leerer_ordnername_gibt_leere_liste():
    assert deck_browser.finde_decks("") == []
    assert deck_browser.finde_decks(None) == []


def test_sortiert_nach_namen(tmp_path, monkeypatch):
    _vfs(monkeypatch, ["zebra.pptx", "apfel.pptx", "Ärger.pptx"])
    namen = [d["name"] for d in deck_browser.finde_decks(str(tmp_path))]
    assert namen == sorted(namen, key=str.lower)
    assert namen[0] == "apfel.pptx"


def test_vfs_pfade_werden_zusammengesetzt(monkeypatch):
    _vfs(monkeypatch, ["x.pptx"])
    d = deck_browser.finde_decks("smb://nas/decks")[0]
    assert d["pfad"] == "smb://nas/decks/x.pptx"


def test_vfs_pfad_mit_schraegstrich_am_ende(monkeypatch):
    _vfs(monkeypatch, ["x.pptx"])
    d = deck_browser.finde_decks("smb://nas/decks/")[0]
    assert d["pfad"] == "smb://nas/decks/x.pptx", "kein doppelter Schrägstrich"


def test_fehler_beim_lesen_gibt_leere_liste(monkeypatch):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)

    def kaputt(p):
        raise OSError("Freigabe weg")

    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir", kaputt)
    assert deck_browser.finde_decks("smb://nas/weg") == []


def test_ordner_wird_mit_schraegstrich_geprueft(monkeypatch):
    """Kodi-Eigenheit: xbmcvfs.exists() sagt für Verzeichnisse ohne / am Ende False.

    Am Gerät aufgefallen: das Add-on meldete "Keine Präsentationen gefunden",
    obwohl die Datei im Ordner lag.
    """
    gefragt = []

    def exists(p):
        gefragt.append(p)
        return p.endswith("/")      # genau wie Kodi es tut

    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", exists)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir", lambda p: ([], ["a.pptx"]))
    decks = deck_browser.finde_decks("/storage/presentations")
    assert decks, f"Ordner nicht gefunden; geprüft wurde: {gefragt}"
    assert all(p.endswith("/") for p in gefragt), f"ohne Schrägstrich geprüft: {gefragt}"


def test_findet_auch_pdfs(tmp_path, monkeypatch):
    """PDF ist seit der Erweiterung ein gültiges Deck-Format -- ohne Notizen."""
    _vfs(monkeypatch, ["a.pptx", "b.pdf", "c.PDF", "d.txt", "e.odp"])
    gefunden = {d["name"] for d in deck_browser.finde_decks(str(tmp_path))}
    assert gefunden == {"a.pptx", "b.pdf", "c.PDF"}


def test_odp_und_ppt_bleiben_aussen_vor(tmp_path, monkeypatch):
    """Am Gerät geprüft: DeckCraft lehnt beide ab, ein Konverter fehlt."""
    _vfs(monkeypatch, ["a.odp", "b.ppt", "c.key"])
    assert deck_browser.finde_decks(str(tmp_path)) == []


def test_versteckte_dateien_und_apple_reste_werden_uebergangen(tmp_path, monkeypatch):
    """macOS legt neben jeder Datei ein ._name an, Linux-Werkzeuge Punktdateien.
    Beides sind keine Decks und wuerden beim Rendern nur scheitern."""
    _vfs(monkeypatch, ["slides.pdf", "._slides.pdf", ".versteckt.pptx",
                       ".DS_Store", "echt.pptx"])
    gefunden = {d["name"] for d in deck_browser.finde_decks(str(tmp_path))}
    assert gefunden == {"slides.pdf", "echt.pptx"}


def test_findet_auch_die_pptx_geschwister(tmp_path, monkeypatch):
    """Eine .ppsx kam per Mail und lag im Ordner -- und war unsichtbar.

    Dabei haette der Renderer sie anstandslos angezeigt; nur diese Liste
    stand davor.
    """
    _vfs(monkeypatch, ["vortrag.ppsx", "makros.pptm", "vorlage.potx", "fremd.odp"])
    gefunden = {d["name"] for d in deck_browser.finde_decks(str(tmp_path))}
    assert gefunden == {"vortrag.ppsx", "makros.pptm", "vorlage.potx"}
