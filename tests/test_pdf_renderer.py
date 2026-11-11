import json
import os
import stat

import pytest

import pdf_renderer
import renderer

INFO = '{"seiten":5,"breitePt":959.98,"hoehePt":540.00}'


def attrappe(tmp_path, skript, name="pdfrender"):
    p = tmp_path / name
    p.write_text("#!/bin/sh\n" + skript)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_version(tmp_path):
    b = attrappe(tmp_path, 'echo "pdfrender 0.1.0"')
    assert pdf_renderer.PdfRenderer(b).version() == "pdfrender 0.1.0"


def test_info_liefert_eine_folie_je_seite(tmp_path):
    b = attrappe(tmp_path, f"echo '{INFO}'")
    info = pdf_renderer.PdfRenderer(b).info("/tmp/x.pdf")
    assert len(info.folien) == 5
    assert info.folien_groesse == (959.98, 540.0)


def test_folien_heissen_nach_der_seitenzahl(tmp_path):
    b = attrappe(tmp_path, f"echo '{INFO}'")
    info = pdf_renderer.PdfRenderer(b).info("/tmp/x.pdf")
    assert info.folien[0].titel == "Seite 1"
    assert info.folien[4].titel == "Seite 5"


def test_pdf_hat_keine_notizen(tmp_path):
    """PDFs transportieren keine Referentennotizen -- das Feld bleibt leer,
    und die Handy-Ansicht zeigt dort ihren Hinweistext."""
    b = attrappe(tmp_path, f"echo '{INFO}'")
    info = pdf_renderer.PdfRenderer(b).info("/tmp/x.pdf")
    assert all(f.notizen == "" for f in info.folien)


def test_kaputtes_pdf_meldet_verstaendlich(tmp_path):
    b = attrappe(tmp_path, 'echo "pdfrender: x.pdf: kein lesbares PDF" >&2; exit 1')
    with pytest.raises(renderer.RendererFehler) as e:
        pdf_renderer.PdfRenderer(b).info("/tmp/x.pdf")
    assert "pdf" in str(e.value).lower()


def test_render_uebergibt_absoluten_pfad(tmp_path, monkeypatch):
    protokoll = tmp_path / "args.txt"
    # Argumentfolge: render PFAD --scale S ZIEL  ->  Ziel ist $5
    b = attrappe(tmp_path, f'for a in "$@"; do echo "$a" >> {protokoll}; done\n'
                           'mkdir -p "$5"; touch "$5/slide-01.png" "$5/slide-02.png"')
    monkeypatch.chdir(tmp_path)
    open("-heikel.pdf", "w").close()
    bilder = pdf_renderer.PdfRenderer(b).render("-heikel.pdf", str(tmp_path / "o"), 2)
    zeilen = protokoll.read_text().splitlines()
    assert "render" in zeilen
    assert os.path.abspath("-heikel.pdf") in zeilen, "absoluter Pfad schuetzt vor Bindestrich"
    assert len(bilder) == 2


def test_render_sortiert_natuerlich(tmp_path):
    b = attrappe(tmp_path, 'mkdir -p "$5"\n'
                           'for n in 02 10 1 100; do touch "$5/slide-$n.png"; done')
    bilder = pdf_renderer.PdfRenderer(b).render(str(tmp_path / "x.pdf"), str(tmp_path / "o"), 1)
    nummern = [int(os.path.basename(p).split("-")[1].split(".")[0]) for p in bilder]
    assert nummern == sorted(nummern)


# --- Auswahl des passenden Renderers ---

def test_pptx_bekommt_deckcraft(tmp_path):
    r = renderer.fuer_deck("/decks/a.pptx", "/bin/deckcraft-cli", "/bin/pdfrender")
    assert isinstance(r, renderer.DeckcraftRenderer)


def test_deckcraft_datei_bekommt_deckcraft(tmp_path):
    r = renderer.fuer_deck("/decks/a.deckcraft", "/bin/deckcraft-cli", "/bin/pdfrender")
    assert isinstance(r, renderer.DeckcraftRenderer)


def test_pdf_bekommt_pdfrender(tmp_path):
    r = renderer.fuer_deck("/decks/a.pdf", "/bin/deckcraft-cli", "/bin/pdfrender")
    assert isinstance(r, pdf_renderer.PdfRenderer)


def test_grossschreibung_egal():
    r = renderer.fuer_deck("/decks/A.PDF", "/bin/deckcraft-cli", "/bin/pdfrender")
    assert isinstance(r, pdf_renderer.PdfRenderer)


def test_unbekannte_endung_meldet_fehler():
    with pytest.raises(renderer.RendererFehler):
        renderer.fuer_deck("/decks/a.odp", "/bin/deckcraft-cli", "/bin/pdfrender")


def test_vfs_pfad_waehlt_nach_endung():
    r = renderer.fuer_deck("smb://nas/a.pdf", "/bin/deckcraft-cli", "/bin/pdfrender")
    assert isinstance(r, pdf_renderer.PdfRenderer)


def test_render_zielt_auf_die_bildschirmbreite(tmp_path):
    """Ein PDF mit 1440 Punkten Breite ergab bei "Pixel je Punkt" 2880 Pixel --
    das Vierfache dessen, was ein 1080p-Fernseher zeigt. Gerendert wird deshalb
    auf eine Zielbreite, unabhaengig von der Seitengroesse des PDFs."""
    protokoll = tmp_path / "args.txt"
    b = attrappe(tmp_path, f'for a in "$@"; do echo "$a" >> {protokoll}; done\n'
                           'mkdir -p "$5"; touch "$5/slide-01.png"')
    pdf_renderer.PdfRenderer(b).render(str(tmp_path / "x.pdf"), str(tmp_path / "o"), 2)
    zeilen = protokoll.read_text().splitlines()
    assert "--width" in zeilen, f"keine Zielbreite uebergeben: {zeilen}"
    assert "1920" in zeilen, "Skalierung 2 muss 1920 Pixel Breite ergeben"


def test_skalierung_eins_ergibt_960(tmp_path):
    protokoll = tmp_path / "args.txt"
    b = attrappe(tmp_path, f'for a in "$@"; do echo "$a" >> {protokoll}; done\n'
                           'mkdir -p "$5"; touch "$5/slide-01.png"')
    pdf_renderer.PdfRenderer(b).render(str(tmp_path / "x.pdf"), str(tmp_path / "o"), 1)
    assert "960" in protokoll.read_text().splitlines()
