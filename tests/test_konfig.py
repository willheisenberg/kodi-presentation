import konfig


def test_vorgaben_wenn_nichts_gesetzt(addon_stub, tmp_path):
    addon_stub.pfad = str(tmp_path)
    k = konfig.Konfig()
    assert k.deck_ordner == "/storage/presentations"
    assert k.skalierung == 2
    assert k.port == 8099
    assert k.cache_grenze_bytes == 2 * 1024**3


def test_liest_gesetzte_werte(addon_stub, tmp_path):
    addon_stub.pfad = str(tmp_path)
    addon_stub.werte = {"deck_ordner": "/storage/vortraege", "skalierung": "4",
                        "port": "9000", "cache_grenze_gb": "5"}
    k = konfig.Konfig()
    assert k.deck_ordner == "/storage/vortraege"
    assert k.skalierung == 4
    assert k.port == 9000
    assert k.cache_grenze_bytes == 5 * 1024**3


def test_unsinnige_werte_fallen_auf_vorgabe_zurueck(addon_stub, tmp_path):
    addon_stub.pfad = str(tmp_path)
    addon_stub.werte = {"skalierung": "quatsch", "port": "-1"}
    k = konfig.Konfig()
    assert k.skalierung == 2
    assert k.port == 8099


def test_binary_pfad_liegt_im_addon(addon_stub, tmp_path):
    addon_stub.pfad = str(tmp_path)
    k = konfig.Konfig()
    assert k.binary_pfad == str(tmp_path / "bin" / "deckcraft-cli")


def test_special_pfade_werden_uebersetzt(addon_stub, tmp_path):
    """Kodi liefert profile als special://-Pfad; os.makedirs scheitert daran.

    Am Gerät aufgefallen: "[Errno 30] Read-only file system: 'special:'".
    """
    addon_stub.pfad = "special://home/addons/script.presentation"
    k = konfig.Konfig()
    assert not k.addon_pfad.startswith("special:"), k.addon_pfad
    assert not k.daten_pfad.startswith("special:"), k.daten_pfad
    assert not k.binary_pfad.startswith("special:"), k.binary_pfad
    assert k.daten_pfad.startswith("/tmp/kodi/userdata")
