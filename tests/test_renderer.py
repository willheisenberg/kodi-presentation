import json
import os
import stat

import pytest

import renderer


def attrappe(tmp_path, skript):
    """Legt ein ausführbares Skript an, das sich wie deckcraft-cli verhält."""
    pfad = tmp_path / "deckcraft-cli"
    pfad.write_text("#!/bin/sh\n" + skript)
    pfad.chmod(pfad.stat().st_mode | stat.S_IEXEC)
    return str(pfad)


INFO_JSON = json.dumps({
    "title": "Testdeck",
    "slideSize": [959.97, 540.0],
    "slides": [
        {"index": 0, "title": "Erste Folie", "notes": "Begrüßung, nicht vorlesen"},
        {"index": 1, "title": "Zweite", "notes": ""},
    ],
})


def test_version_liest_das_binary(tmp_path):
    b = attrappe(tmp_path, 'echo "deckcraft-cli 0.15.0"')
    assert renderer.DeckcraftRenderer(b).version() == "deckcraft-cli 0.15.0"


def test_fehlendes_binary_meldet_den_pfad(tmp_path):
    r = renderer.DeckcraftRenderer(str(tmp_path / "gibtsnicht"))
    with pytest.raises(renderer.RendererFehler) as e:
        r.version()
    assert "gibtsnicht" in str(e.value)


def test_info_liefert_folien_und_notizen(tmp_path):
    b = attrappe(tmp_path, f"cat <<'EOF'\n{INFO_JSON}\nEOF")
    info = renderer.DeckcraftRenderer(b).info("/tmp/deck.pptx")
    assert info.titel == "Testdeck"
    assert len(info.folien) == 2
    assert info.folien[0].notizen == "Begrüßung, nicht vorlesen"
    assert info.folien[1].notizen == ""
    assert info.folien_groesse == (959.97, 540.0)


def test_info_bei_kaputtem_json(tmp_path):
    b = attrappe(tmp_path, 'echo "kein json"')
    with pytest.raises(renderer.RendererFehler):
        renderer.DeckcraftRenderer(b).info("/tmp/deck.pptx")


def test_info_meldet_verlorene_folien(tmp_path):
    b = attrappe(tmp_path, f"cat <<'EOF'\n{INFO_JSON}\nEOF\n"
                           'echo "warning: 2 slides could not be read" >&2')
    info = renderer.DeckcraftRenderer(b).info("/tmp/deck.pptx")
    assert info.verlorene_folien == 2


def test_render_uebergibt_argumente_als_liste(tmp_path):
    """Review Focus 2: Leerzeichen, Umlaute und führender Bindestrich im Namen.

    deckcraft-cli kennt kein `--` als Options-Ende (auf dem Geraet geprueft:
    "deckcraft-cli: --: No such file or directory"). Der Schutz gegen einen
    fuehrenden Bindestrich ist deshalb der absolute Pfad, der immer mit / beginnt.
    """
    protokoll = tmp_path / "args.txt"
    # Argumentfolge: render --all --scale 2 PFAD ZIEL  ->  Ziel ist $6
    b = attrappe(tmp_path, f'for a in "$@"; do echo "$a" >> {protokoll}; done\n'
                           'mkdir -p "$6"; touch "$6/slide-01.png"')
    heikel = str(tmp_path / "-mein Vörtrag 'quote'.pptx")
    open(heikel, "w").close()
    ziel = tmp_path / "out"
    renderer.DeckcraftRenderer(b).render(heikel, str(ziel), 2)
    zeilen = protokoll.read_text().splitlines()
    assert "--" not in zeilen, "deckcraft-cli liest `--` als Dateinamen"
    pfad_arg = [z for z in zeilen if z.endswith(".pptx")]
    assert pfad_arg, f"kein Pfadargument gefunden: {zeilen}"
    assert pfad_arg[0] == os.path.abspath(heikel)
    assert not pfad_arg[0].startswith("-"), "absoluter Pfad schuetzt vor Options-Verwechslung"


def test_info_uebergibt_absoluten_pfad(tmp_path, monkeypatch):
    protokoll = tmp_path / "info_args.txt"
    b = attrappe(tmp_path, f'for a in "$@"; do echo "$a" >> {protokoll}; done\n'
                           f"cat <<'EOF'\n{INFO_JSON}\nEOF")
    rel = "-deck.pptx"
    monkeypatch.chdir(tmp_path)
    open(rel, "w").close()
    renderer.DeckcraftRenderer(b).info(rel)
    zeilen = protokoll.read_text().splitlines()
    assert "--" not in zeilen
    assert os.path.abspath(rel) in zeilen


def test_render_gibt_sortierte_bildpfade_zurueck(tmp_path):
    b = attrappe(tmp_path, 'mkdir -p "$6"\n'
                           'for n in 03 01 02; do touch "$6/slide-$n.png"; done')
    ziel = tmp_path / "out"
    bilder = renderer.DeckcraftRenderer(b).render(str(tmp_path / "d.pptx"), str(ziel), 2)
    assert [os.path.basename(p) for p in bilder] == ["slide-01.png", "slide-02.png", "slide-03.png"]


def test_render_fehler_enthaelt_stderr(tmp_path):
    b = attrappe(tmp_path, 'echo "font table broken" >&2; exit 1')
    with pytest.raises(renderer.RendererFehler) as e:
        renderer.DeckcraftRenderer(b).render("/tmp/d.pptx", str(tmp_path / "o"), 2)
    assert "font table broken" in str(e.value)


def test_info_fehler_zeigt_keine_notizen(tmp_path):
    """W5: stdout von `info` ist das JSON mit allen Notizen. Schlägt der Aufruf
    nach der Ausgabe fehl und ist stderr leer, landete es in der Fehlermeldung --
    und damit im Dialog auf dem Fernseher."""
    b = attrappe(tmp_path, f"cat <<'EOF'\n{INFO_JSON}\nEOF\nexit 1")
    with pytest.raises(renderer.RendererFehler) as e:
        renderer.DeckcraftRenderer(b).info("/tmp/deck.pptx")
    meldung = str(e.value)
    assert "nicht vorlesen" not in meldung.lower(), "Notiz in der Fehlermeldung!"
    assert "Begrüßung" not in meldung


def test_render_sortiert_natuerlich(tmp_path):
    """W7: ab 100 Folien ordnet lexikografische Sortierung falsch.
    Am Gerät belegt: DeckCraft benennt zweistellig, also slide-99, slide-100."""
    b = attrappe(tmp_path, 'mkdir -p "$6"\n'
                           'for n in 01 02 09 10 11 99 100 101 120; do '
                           'touch "$6/slide-$n.png"; done')
    bilder = renderer.DeckcraftRenderer(b).render(str(tmp_path / "d.pptx"),
                                                  str(tmp_path / "out"), 1)
    nummern = [int(os.path.basename(p).split("-")[1].split(".")[0]) for p in bilder]
    assert nummern == sorted(nummern), f"falsche Reihenfolge: {nummern}"
    assert nummern == [1, 2, 9, 10, 11, 99, 100, 101, 120]
