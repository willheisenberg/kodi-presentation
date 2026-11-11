import os
import sys

import pytest

import deck_cache
import renderer


class FakeRenderer:
    """Zählt Aufrufe und legt die erwarteten Dateien an."""

    def __init__(self, folien=2, fehler=None):
        self.folien = folien
        self.fehler = fehler
        self.render_aufrufe = 0
        self.zuletzt_gerendert = None

    def info(self, pfad):
        return renderer.DeckInfo(
            titel="Deck",
            folien=[renderer.Folie(i, f"Folie {i}", f"Notiz {i}") for i in range(self.folien)],
            folien_groesse=(960.0, 540.0),
        )

    def render(self, pfad, ziel, skalierung):
        self.render_aufrufe += 1
        self.zuletzt_gerendert = pfad
        if self.fehler:
            raise renderer.RendererFehler(self.fehler)
        os.makedirs(ziel, exist_ok=True)
        pfade = []
        for i in range(self.folien):
            p = os.path.join(ziel, f"slide-{i + 1:02d}.png")
            with open(p, "wb") as f:
                f.write(b"x" * 100)
            pfade.append(p)
        return pfade


def deck(tmp_path, name="vortrag.pptx"):
    p = tmp_path / name
    p.write_bytes(b"PK\x03\x04" + b"0" * 500)
    return str(p)


def test_schluessel_aendert_sich_mit_dem_inhalt(tmp_path):
    p = deck(tmp_path)
    a = deck_cache.schluessel(p)
    os.utime(p, (0, 0))
    assert deck_cache.schluessel(p) != a


def test_schluessel_ist_stabil(tmp_path):
    p = deck(tmp_path)
    assert deck_cache.schluessel(p) == deck_cache.schluessel(p)


def test_erster_zugriff_rendert_zweiter_nicht(tmp_path):
    r = FakeRenderer()
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    p = deck(tmp_path)
    m1 = c.hole(p, r, 2)
    m2 = c.hole(p, r, 2)
    assert r.render_aufrufe == 2, "einmal TV-Auflösung, einmal Vorschau"
    assert m1["folien"][0]["notizen"] == "Notiz 0"
    assert m2 == m1


def test_manifest_enthaelt_alle_felder(tmp_path):
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    m = c.hole(deck(tmp_path), FakeRenderer(), 2)
    assert set(m) >= {"quelle", "hash", "gerendert", "folienGroesse", "folien"}
    assert set(m["folien"][0]) >= {"index", "titel", "notizen", "bild", "vorschau"}
    assert os.path.isabs(m["folien"][0]["bild"])


def test_geaendertes_deck_wird_neu_gerendert(tmp_path):
    r = FakeRenderer()
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    p = deck(tmp_path)
    c.hole(p, r, 2)
    vorher = r.render_aufrufe
    with open(p, "ab") as f:
        f.write(b"mehr")
    c.hole(p, r, 2)
    assert r.render_aufrufe > vorher


def test_abbruch_hinterlaesst_keinen_gueltigen_eintrag(tmp_path):
    """Review Focus 5: halbfertiger Cache darf beim nächsten Start nicht zählen."""
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    p = deck(tmp_path)
    with pytest.raises(renderer.RendererFehler):
        c.hole(p, FakeRenderer(fehler="Platte voll"), 2)
    assert not c.ist_gueltig(p)
    m = c.hole(p, FakeRenderer(), 2)
    assert len(m["folien"]) == 2


def test_vfs_pfad_wird_lokal_kopiert(tmp_path, monkeypatch):
    """Review Focus 1: smb:// kann das Binary nicht öffnen."""
    quelle = deck(tmp_path, "netz.pptx")
    kopien = []

    def fake_copy(von, nach):
        kopien.append((von, nach))
        with open(nach, "wb") as z, open(quelle, "rb") as q:
            z.write(q.read())
        return True

    monkeypatch.setattr(sys.modules["xbmcvfs"], "copy", fake_copy)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    r = FakeRenderer()
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    c.hole("smb://nas/decks/netz.pptx", r, 2)
    assert kopien, "VFS-Pfad muss kopiert werden"
    assert not r.zuletzt_gerendert.startswith("smb://")


def test_vfs_temporaerdatei_wird_aufgeraeumt(tmp_path, monkeypatch):
    quelle = deck(tmp_path, "netz2.pptx")
    kopien = []

    def fake_copy(von, nach):
        kopien.append(nach)
        with open(nach, "wb") as z, open(quelle, "rb") as q:
            z.write(q.read())
        return True

    monkeypatch.setattr(sys.modules["xbmcvfs"], "copy", fake_copy)
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    c.hole("smb://nas/decks/netz2.pptx", FakeRenderer(), 2)
    assert kopien and not os.path.exists(kopien[0]), "Temporärdatei muss weg sein"


def test_ist_vfs_erkennt_schemata():
    assert deck_cache.ist_vfs("smb://nas/a.pptx")
    assert deck_cache.ist_vfs("nfs://host/a.pptx")
    assert not deck_cache.ist_vfs("/storage/a.pptx")
    assert not deck_cache.ist_vfs("C:\\decks\\a.pptx")


def test_aufraeumen_entfernt_aelteste_eintraege(tmp_path):
    wurzel = str(tmp_path / "cache")
    gross = deck_cache.DeckCache(wurzel, 10**9)
    r = FakeRenderer(folien=2)
    for n in range(4):
        gross.hole(deck(tmp_path, f"d{n}.pptx"), r, 2)
    assert gross.groesse_bytes() > 500

    klein = deck_cache.DeckCache(wurzel, 500)
    entfernt = klein.aufraeumen()
    assert entfernt > 0
    assert klein.groesse_bytes() <= 500


def test_geaendertes_vfs_deck_wird_neu_gerendert(tmp_path, monkeypatch):
    """K1: Der Cache-Schlüssel bestand bei smb:// nur aus dem Pfad und war damit
    konstant. Ein am NAS überarbeitetes Deck wurde nie neu gerendert -- der
    Vortrag lief mit der alten Fassung und den alten Notizen."""
    quelle = deck(tmp_path, "netz.pptx")
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "copy",
                        lambda von, nach: open(nach, "wb").write(open(quelle, "rb").read()) or True)
    stat = sys.modules["xbmcvfs"].Stat
    stat.mtime, stat.size = 1000, 500

    r = FakeRenderer(folien=2)
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    vfs = "smb://nas/decks/netz.pptx"
    c.hole(vfs, r, 2)
    nach_erstem = r.render_aufrufe
    c.hole(vfs, r, 2)
    assert r.render_aufrufe == nach_erstem, "unveränderte Datei darf nicht neu rendern"

    stat.mtime, stat.size = 2000, 900          # Deck wurde am NAS überarbeitet
    r.folien = 5
    m = c.hole(vfs, r, 2)
    assert r.render_aufrufe > nach_erstem, "geändertes VFS-Deck muss neu gerendert werden"
    assert len(m["folien"]) == 5


def test_vfs_ohne_stat_rendert_lieber_neu(tmp_path, monkeypatch):
    """Kann die Größe nicht ermittelt werden, ist ein Fehltreffer das kleinere
    Übel: Rendern kostet Zehntelsekunden, eine veraltete Folie den Vortrag."""
    quelle = deck(tmp_path, "nostat.pptx")
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "copy",
                        lambda von, nach: open(nach, "wb").write(open(quelle, "rb").read()) or True)

    def kaputt(_p):
        raise OSError("Freigabe antwortet nicht")

    monkeypatch.setattr(sys.modules["xbmcvfs"], "Stat", kaputt)
    a = deck_cache.schluessel("smb://nas/x.pptx")
    b = deck_cache.schluessel("smb://nas/x.pptx")
    assert a != b, "ohne Stat muss jeder Aufruf einen Fehltreffer erzeugen"


def test_frischer_eintrag_wird_nicht_sofort_aufgeraeumt(tmp_path):
    """W1: aufraeumen() löschte den gerade gerenderten Eintrag mit, wenn er
    allein die Obergrenze riss. Das Manifest kam zurück, die Bilder waren weg --
    schwarzer Fernseher über den ganzen Vortrag, ohne jede Meldung."""
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 1000)   # winzige Grenze
    m = c.hole(deck(tmp_path), FakeRenderer(folien=4), 2)
    assert os.path.isfile(m["folien"][0]["bild"]), "Bild des frischen Decks fehlt"
    assert os.path.isfile(m["folien"][3]["bild"])
    assert c.ist_gueltig(m["quelle"]), "frischer Eintrag wurde weggeräumt"


def test_abgeschnittenes_manifest_wird_verworfen(tmp_path):
    """W2: Ein Absturz während des Schreibens hinterließ ein halbes deck.json.
    ist_gueltig() sagte True, json.load() warf -- und zwar bei jedem Start
    erneut, bis jemand den Ordner per SSH löschte. Spec §8 verlangt das Gegenteil."""
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    p = deck(tmp_path)
    m = c.hole(p, FakeRenderer(folien=3), 2)
    manifest = os.path.join(c._ordner(p), deck_cache.MANIFEST)
    roh = open(manifest, encoding="utf-8").read()
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(roh[:len(roh) // 2])          # Stromausfall mitten im Schreiben

    m2 = c.hole(p, FakeRenderer(folien=3), 2)
    assert len(m2["folien"]) == 3, "kaputter Eintrag muss verworfen und neu gerendert werden"


def test_fehlende_bilder_werden_im_manifest_vermerkt(tmp_path):
    """W7b: Liefert der Renderer weniger Bilder als Folien, startete der Vortrag
    stillschweigend mit schwarzen Folien am Ende."""
    class ZuWenigBilder(FakeRenderer):
        def render(self, pfad, ziel, skalierung):
            self.folien, merk = 2, self.folien
            pfade = FakeRenderer.render(self, pfad, ziel, skalierung)
            self.folien = merk
            return pfade

    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    m = c.hole(deck(tmp_path), ZuWenigBilder(folien=5), 2)
    assert m["fehlendeBilder"] == 3, f"nicht vermerkt: {m.get('fehlendeBilder')}"


def test_abbruch_laesst_keine_bytes_auf_der_platte(tmp_path):
    """Ein abgebrochener Lauf muss auch seine schon geschriebenen Bilder entfernen.

    Darauf ruht das Argument, dass pdfrender keine Seitenobergrenze braucht:
    Die Zeitgrenze von 300 s deckelt, wie viel ein Riesen-PDF überhaupt
    schreiben kann, und dieses Aufräumen gibt es danach wieder frei. Bliebe
    der Rumpf liegen, liefe /storage mit jedem Fehlversuch weiter voll.
    """

    class SchreibtDannFehler:
        def info(self, pfad):
            return renderer.DeckInfo(
                titel="Deck",
                folien=[renderer.Folie(0, "Folie 0", "")],
                folien_groesse=(960.0, 540.0),
            )

        def render(self, pfad, ziel, skalierung):
            os.makedirs(ziel, exist_ok=True)
            for i in range(20):
                with open(os.path.join(ziel, f"slide-{i + 1:02d}.png"), "wb") as f:
                    f.write(b"x" * 10_000)
            raise renderer.RendererFehler("Zeitgrenze von 300 s überschritten")

    wurzel = tmp_path / "cache"
    c = deck_cache.DeckCache(str(wurzel), 10**9)
    p = deck(tmp_path)
    with pytest.raises(renderer.RendererFehler):
        c.hole(p, SchreibtDannFehler(), 2)
    assert c.groesse_bytes() == 0, "Rumpf des abgebrochenen Laufs blieb liegen"
    assert list(wurzel.iterdir()) == []
