import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import handy_server
import sitzung


@pytest.fixture
def aufbau(tmp_path):
    bild = tmp_path / "thumb-01.jpg"
    bild.write_bytes(b"\xff\xd8\xff" + b"0" * 50)
    manifest = {"titel": "Testdeck", "folien": [
        {"index": 0, "titel": "Erste", "notizen": "Nicht vorlesen",
         "vorschau": str(bild), "bild": ""},
        {"index": 1, "titel": "Zweite", "notizen": "", "vorschau": str(bild), "bild": ""},
    ]}
    s = sitzung.Sitzung(2)
    server = handy_server.HandyServer(s, manifest, "<html>Hallo</html>", port=0)
    url = server.starten()
    yield s, server, url
    server.stoppen()


def hole(url, daten=None):
    anfrage = urllib.request.Request(
        url, data=daten,
        headers={"Content-Type": "application/json"} if daten else {})
    with urllib.request.urlopen(anfrage, timeout=5) as a:
        return a.status, a.read(), a.headers


def test_seite_wird_ausgeliefert(aufbau):
    _, _, url = aufbau
    status, koerper, _ = hole(url)
    assert status == 200 and b"Hallo" in koerper


def test_falsches_token_gibt_404(aufbau):
    _, server, _ = aufbau
    with pytest.raises(urllib.error.HTTPError) as e:
        hole(f"http://127.0.0.1:{server.port}/p/falschestoken/")
    assert e.value.code == 404, "404 statt 403, um den Dienst nicht zu bestätigen"


def test_zustand_liefert_notizen_der_aktuellen_folie(aufbau):
    _, _, url = aufbau
    _, koerper, _ = hole(url + "state?seit=0")
    z = json.loads(koerper)
    assert z["notizen"] == "Nicht vorlesen"
    assert z["titel"] == "Erste"
    assert z["naechsterTitel"] == "Zweite"
    assert z["anzahl"] == 2


def test_kommando_blaettert_weiter(aufbau):
    s, _, url = aufbau
    hole(url + "cmd", json.dumps({"aktion": "vor"}).encode())
    assert s.index == 1


def test_kommando_springe(aufbau):
    s, _, url = aufbau
    hole(url + "cmd", json.dumps({"aktion": "springe", "ziel": 1}).encode())
    assert s.index == 1


def test_unbekanntes_kommando_gibt_400(aufbau):
    _, _, url = aufbau
    with pytest.raises(urllib.error.HTTPError) as e:
        hole(url + "cmd", json.dumps({"aktion": "fliegen"}).encode())
    assert e.value.code == 400


def test_long_poll_wird_durch_blaettern_geweckt(aufbau):
    s, _, url = aufbau
    ergebnis = {}

    def warter():
        _, koerper, _ = hole(url + f"state?seit={s.version}")
        ergebnis["z"] = json.loads(koerper)

    t = threading.Thread(target=warter)
    t.start()
    time.sleep(0.2)
    s.vor()
    t.join(timeout=5)
    assert not t.is_alive()
    assert ergebnis["z"]["index"] == 1


def test_vorschaubild_wird_ausgeliefert(aufbau):
    _, _, url = aufbau
    status, koerper, kopf = hole(url + "thumb/0.jpg")
    assert status == 200 and koerper.startswith(b"\xff\xd8\xff")
    assert kopf["Content-Type"] == "image/jpeg"


def test_png_vorschau_bekommt_png_typ(tmp_path):
    """DeckCraft liefert PNG, nicht JPEG: der Typ muss aus der Datei kommen."""
    bild = tmp_path / "slide-01.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    manifest = {"folien": [{"index": 0, "titel": "A", "notizen": "",
                            "vorschau": str(bild), "bild": ""}]}
    server = handy_server.HandyServer(sitzung.Sitzung(1), manifest, "<html></html>", port=0)
    url = server.starten()
    try:
        _, koerper, kopf = hole(url + "thumb/0.jpg")
        assert koerper.startswith(b"\x89PNG")
        assert kopf["Content-Type"] == "image/png"
    finally:
        server.stoppen()


def test_vorschaubild_ausserhalb_des_bereichs_gibt_404(aufbau):
    _, _, url = aufbau
    with pytest.raises(urllib.error.HTTPError) as e:
        hole(url + "thumb/99.jpg")
    assert e.value.code == 404


def test_token_ist_lang_genug(aufbau):
    _, server, _ = aufbau
    assert len(server.token) >= 10


def test_stoppen_gibt_den_port_frei(tmp_path):
    s = sitzung.Sitzung(1)
    server = handy_server.HandyServer(s, {"folien": []}, "<html></html>", port=0)
    server.starten()
    port = server.port
    server.stoppen()
    zweiter = handy_server.HandyServer(sitzung.Sitzung(1), {"folien": []},
                                       "<html></html>", port=port)
    zweiter.starten()
    zweiter.stoppen()


def test_springe_mit_unsinnigem_ziel_gibt_400(aufbau):
    """W4: int("abc") flog bis in socketserver -- der Request starb ohne
    Antwort und Kodis Log bekam einen Traceback."""
    _, _, url = aufbau
    with pytest.raises(urllib.error.HTTPError) as e:
        hole(url + "cmd", json.dumps({"aktion": "springe", "ziel": "abc"}).encode())
    assert e.value.code == 400


def test_koerper_der_kein_objekt_ist_gibt_400(aufbau):
    """W4: ein nackter Zahlenkörper löste AttributeError aus."""
    _, _, url = aufbau
    with pytest.raises(urllib.error.HTTPError) as e:
        hole(url + "cmd", b"5")
    assert e.value.code == 400


def test_rohes_nicht_ascii_im_token_gibt_404(aufbau):
    """W4: secrets.compare_digest wirft bei Nicht-ASCII. Der Verbindungsabbruch
    unterschied den Dienst von einem schweigenden Port -- ganz ohne Token.

    urllib kodiert prozentual und trifft den Fall nicht; ein Scanner schickt die
    Bytes roh, deshalb hier ein nackter Socket.
    """
    import socket
    _, server, _ = aufbau
    s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    try:
        s.sendall("GET /p/ä/ HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
                  .encode("utf-8"))
        antwort = s.recv(200)
    finally:
        s.close()
    assert antwort, "Server hat die Verbindung ohne Antwort geschlossen"
    assert b"404" in antwort.split(b"\r\n")[0], antwort[:80]


def test_gueltige_aktion_bleibt_unberuehrt(aufbau):
    """Gegenprobe: die Absicherung darf die normalen Wege nicht verengen."""
    s, _, url = aufbau
    status, koerper, _ = hole(url + "cmd", json.dumps({"aktion": "springe", "ziel": 1}).encode())
    assert status == 200 and json.loads(koerper)["ok"] is True
    assert s.index == 1


def test_erfolgreicher_befehl_stupst_die_oberflaeche_an(tmp_path):
    """Kodi zeichnet nur aus seinem eigenen Thread. Der HTTP-Thread darf die
    Oberfläche deshalb nicht selbst anfassen, sondern stupst sie über Kodis
    thread-sicheren Dispatch an."""
    stupser = []
    manifest = {"folien": [{"index": i, "titel": f"F{i}", "notizen": "",
                            "vorschau": "", "bild": ""} for i in range(3)]}
    s = sitzung.Sitzung(3)
    server = handy_server.HandyServer(s, manifest, "<html></html>", port=0,
                                      anstupsen=lambda: stupser.append(1))
    url = server.starten()
    try:
        hole(url + "cmd", json.dumps({"aktion": "vor"}).encode())
        assert stupser, "nach einem Befehl muss angestupst werden"
        vorher = len(stupser)
        with pytest.raises(urllib.error.HTTPError):
            hole(url + "cmd", json.dumps({"aktion": "fliegen"}).encode())
        assert len(stupser) == vorher, "abgelehnte Befehle stupsen nicht an"
    finally:
        server.stoppen()
