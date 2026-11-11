import os
import shutil
import struct
import subprocess

import pytest

import qr

URL = "http://192.168.178.10:8099/p/Ab3xK9zQ/"


def test_matrix_ist_quadratisch():
    m = qr.matrix(URL)
    assert len(m) == len(m[0])


def test_groesse_folgt_der_version():
    """Seitenlaenge ist 17 + 4 * Version."""
    n = len(qr.matrix("kurz"))
    assert (n - 17) % 4 == 0
    assert 1 <= (n - 17) // 4 <= 5


def test_version_waechst_mit_der_laenge():
    klein = len(qr.matrix("kurz"))
    gross = len(qr.matrix("x" * 90))
    assert gross > klein


def test_zu_langer_text_wird_abgelehnt():
    with pytest.raises(ValueError):
        qr.matrix("x" * 200)


def test_sucherquadrate_an_drei_ecken():
    """Ein QR-Code hat in drei Ecken ein 7x7-Suchmuster."""
    m = qr.matrix("test")
    n = len(m)
    for oy, ox in ((0, 0), (0, n - 7), (n - 7, 0)):
        assert all(m[oy][ox + i] for i in range(7)), "Oberkante des Suchmusters"
        assert all(m[oy + i][ox] for i in range(7)), "linke Kante"
        assert not m[oy + 1][ox + 1], "innerer Ring muss hell sein"
        assert m[oy + 3][ox + 3], "Kern muss dunkel sein"


def test_vierte_ecke_hat_kein_suchmuster():
    m = qr.matrix("test")
    n = len(m)
    ecke = [m[n - 7 + i][n - 7 + j] for i in range(7) for j in range(7)]
    assert not all(ecke[:7])


def test_dunkles_modul_sitzt_richtig():
    m = qr.matrix("test")
    version = (len(m) - 17) // 4
    assert m[4 * version + 9][8] is True


def test_taktspur_wechselt_sich_ab():
    m = qr.matrix("test")
    n = len(m)
    for i in range(8, n - 8):
        assert m[6][i] == (i % 2 == 0), f"waagerechte Taktspur bei {i}"
        assert m[i][6] == (i % 2 == 0), f"senkrechte Taktspur bei {i}"


def test_gleicher_text_gleiche_matrix():
    assert qr.matrix("abc") == qr.matrix("abc")


def test_png_wird_geschrieben(tmp_path):
    ziel = str(tmp_path / "qr.png")
    qr.als_png(URL, ziel, modulgroesse=4)
    assert os.path.getsize(ziel) > 0
    with open(ziel, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_png_hat_ruhezone(tmp_path):
    """Ohne helle Randzone ist ein QR-Code nicht scannbar."""
    ziel = str(tmp_path / "qr.png")
    qr.als_png("test", ziel, modulgroesse=2)
    breite_module = len(qr.matrix("test")) + 8  # 4 Module Rand je Seite
    with open(ziel, "rb") as f:
        f.read(8)
        struct.unpack(">I", f.read(4))[0]
        f.read(4)
        breite, hoehe = struct.unpack(">II", f.read(8))
    assert breite == breite_module * 2 == hoehe


@pytest.mark.skipif(not shutil.which("zbarimg"), reason="zbarimg nicht installiert")
@pytest.mark.parametrize("text", [
    URL,
    "http://10.0.0.2:8099/p/aB_9-xYz/",
    "kurz",
    "x" * 90,
])
def test_zbarimg_liest_den_code_zurueck(tmp_path, text):
    """Der eigentliche Beweis: ein echter Decoder liest heraus, was hineinging."""
    ziel = str(tmp_path / "qr.png")
    qr.als_png(text, ziel, modulgroesse=8)
    ergebnis = subprocess.run(["zbarimg", "--quiet", "--raw", ziel],
                              capture_output=True, text=True)
    assert ergebnis.returncode == 0, f"zbarimg fand keinen Code: {ergebnis.stderr}"
    assert ergebnis.stdout.strip() == text


def test_rahmen_macht_die_karte_lesbar(tmp_path):
    """Die Startkarte ist ein einziges Bild: QR auf hellem Grund mit dunklem
    Rahmen. Ohne Rahmen verschwindet weißer QR-Grund auf weißen Folien."""
    ohne = str(tmp_path / "ohne.png")
    mit = str(tmp_path / "mit.png")
    qr.als_png(URL, ohne, modulgroesse=6)
    qr.als_png(URL, mit, modulgroesse=6, rahmen=40)
    assert os.path.getsize(mit) > 0
    with open(mit, "rb") as f:
        f.read(16)
        breite_mit = struct.unpack(">II", f.read(8))[0]
    with open(ohne, "rb") as f:
        f.read(16)
        breite_ohne = struct.unpack(">II", f.read(8))[0]
    assert breite_mit == breite_ohne + 80, "Rahmen muss die Karte vergrößern"


@pytest.mark.skipif(not shutil.which("zbarimg"), reason="zbarimg nicht installiert")
def test_karte_mit_rahmen_bleibt_scannbar(tmp_path):
    ziel = str(tmp_path / "karte.png")
    qr.als_png(URL, ziel, modulgroesse=8, rahmen=48)
    ergebnis = subprocess.run(["zbarimg", "--quiet", "--raw", ziel],
                              capture_output=True, text=True)
    assert ergebnis.returncode == 0 and ergebnis.stdout.strip() == URL


def test_leinwand_zentriert_den_code(tmp_path):
    """Die Startkarte ist ein ganzseitiges Bild: schwarzer Grund, QR in der
    Mitte. So braucht sie kein eigenes Steuerelement im Fenster."""
    ziel = str(tmp_path / "karte.png")
    qr.als_png(URL, ziel, modulgroesse=6, rahmen=24, leinwand=(1920, 1080))
    with open(ziel, "rb") as f:
        f.read(16)
        breite, hoehe = struct.unpack(">II", f.read(8))
    assert (breite, hoehe) == (1920, 1080)


@pytest.mark.skipif(not shutil.which("zbarimg"), reason="zbarimg nicht installiert")
def test_leinwandkarte_bleibt_scannbar(tmp_path):
    ziel = str(tmp_path / "karte.png")
    qr.als_png(URL, ziel, modulgroesse=10, rahmen=40, leinwand=(1920, 1080))
    e = subprocess.run(["zbarimg", "--quiet", "--raw", ziel], capture_output=True, text=True)
    assert e.returncode == 0 and e.stdout.strip() == URL
