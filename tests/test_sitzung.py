import threading
import time

import sitzung


def test_startet_bei_null():
    s = sitzung.Sitzung(5)
    assert s.index == 0 and s.version == 1


def test_vor_und_zurueck():
    s = sitzung.Sitzung(3)
    s.vor()
    s.vor()
    assert s.index == 2
    s.zurueck()
    assert s.index == 1


def test_enden_sind_wirkungslos_nicht_fehlerhaft():
    """Review Focus 3."""
    s = sitzung.Sitzung(2)
    s.zurueck()
    assert s.index == 0
    v = s.version
    s.zurueck()
    assert s.index == 0 and s.version == v, "wirkungslose Aktion erhöht die Version nicht"
    s.vor()
    s.vor()
    s.vor()
    assert s.index == 1


def test_deck_ohne_folien_stuerzt_nicht_ab():
    """Review Focus 3: leeres Deck."""
    s = sitzung.Sitzung(0)
    s.vor()
    s.zurueck()
    s.springe(3)
    assert s.index == 0
    assert s.zustand()["anzahl"] == 0


def test_deck_mit_einer_folie():
    s = sitzung.Sitzung(1)
    s.vor()
    assert s.index == 0


def test_springe_begrenzt():
    s = sitzung.Sitzung(4)
    s.springe(99)
    assert s.index == 3
    s.springe(-5)
    assert s.index == 0


def test_version_steigt_monoton():
    s = sitzung.Sitzung(5)
    versionen = []
    for _ in range(4):
        s.vor()
        versionen.append(s.version)
    assert versionen == sorted(versionen)
    assert len(set(versionen)) == 4


def test_blende_und_timer():
    s = sitzung.Sitzung(2)
    assert s.blende is False
    s.blende_umschalten()
    assert s.blende is True
    zeit1 = s.zustand()["sekunden"]
    time.sleep(0.05)
    s.timer_zuruecksetzen()
    assert s.zustand()["sekunden"] <= zeit1 + 0.05


def test_zustand_enthaelt_was_das_handy_braucht():
    s = sitzung.Sitzung(3)
    z = s.zustand()
    assert set(z) >= {"index", "anzahl", "version", "blende", "sekunden"}


def test_warten_kehrt_sofort_zurueck_wenn_version_neuer():
    s = sitzung.Sitzung(3)
    s.vor()
    start = time.monotonic()
    z = s.warte_auf_aenderung(seit=1, zeitgrenze=5)
    assert time.monotonic() - start < 0.5
    assert z["version"] == s.version


def test_warten_wird_durch_aenderung_geweckt():
    s = sitzung.Sitzung(3)
    ergebnis = {}

    def warter():
        ergebnis["z"] = s.warte_auf_aenderung(seit=s.version, zeitgrenze=5)

    t = threading.Thread(target=warter)
    t.start()
    time.sleep(0.1)
    s.vor()
    t.join(timeout=2)
    assert not t.is_alive(), "Warter muss geweckt werden"
    assert ergebnis["z"]["index"] == 1


def test_warten_laeuft_in_die_zeitgrenze():
    s = sitzung.Sitzung(3)
    start = time.monotonic()
    z = s.warte_auf_aenderung(seit=s.version, zeitgrenze=0.2)
    assert 0.15 < time.monotonic() - start < 1.0
    assert z["version"] == s.version


def test_zwei_warter_werden_beide_geweckt():
    """Review Focus 4: zwei Handys gleichzeitig."""
    s = sitzung.Sitzung(5)
    treffer = []

    def warter():
        treffer.append(s.warte_auf_aenderung(seit=s.version, zeitgrenze=5))

    threads = [threading.Thread(target=warter) for _ in range(2)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    s.vor()
    for t in threads:
        t.join(timeout=2)
    assert len(treffer) == 2


def test_beenden_weckt_warter():
    s = sitzung.Sitzung(3)
    ergebnis = {}

    def warter():
        ergebnis["z"] = s.warte_auf_aenderung(seit=s.version, zeitgrenze=5)

    t = threading.Thread(target=warter)
    t.start()
    time.sleep(0.1)
    s.beenden()
    t.join(timeout=2)
    assert not t.is_alive()
    assert ergebnis["z"]["beendet"] is True


def test_gleichzeitige_kommandos_bleiben_konsistent():
    """Review Focus 4."""
    s = sitzung.Sitzung(1000)

    def blaettern():
        for _ in range(100):
            s.vor()

    threads = [threading.Thread(target=blaettern) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert s.index == 400
    assert s.version == 401
