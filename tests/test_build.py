import os
import subprocess

WURZEL = os.path.join(os.path.dirname(__file__), "..")


def lies(*teile):
    with open(os.path.join(WURZEL, *teile), encoding="utf-8") as f:
        return f.read()


def test_version_ist_festgenagelt():
    assert lies("tools", "deckcraft.version").strip() == "0.15.0"


def test_build_skript_nutzt_das_gepruefte_rezept():
    s = lies("tools", "build-deckcraft.sh")
    assert "aarch64-unknown-linux-musl" in s
    assert "-C linker=rust-lld" in s
    assert "-C link-self-contained=yes" in s
    assert "-p deckcraft-cli" in s


def test_build_skript_klont_das_feste_tag():
    s = lies("tools", "build-deckcraft.sh")
    assert '--branch "v$VERSION"' in s, "ohne Tag ist der Build nicht reproduzierbar"


def test_build_skript_prueft_die_architektur():
    s = lies("tools", "build-deckcraft.sh")
    assert "ARM aarch64" in s, "ein x86-Binary darf nicht unbemerkt ins Add-on wandern"


def test_build_skript_bricht_bei_fehlern_ab():
    for datei in ("tools/build-deckcraft.sh", "build.sh"):
        assert "set -euo pipefail" in lies(*datei.split("/")), \
            f"{datei} braucht set -euo pipefail"


def test_skripte_sind_syntaktisch_gueltig():
    for datei in ("tools/build-deckcraft.sh", "build.sh"):
        subprocess.run(["bash", "-n", os.path.join(WURZEL, datei)], check=True)


def test_skripte_sind_ausfuehrbar():
    for datei in ("tools/build-deckcraft.sh", "build.sh"):
        assert os.access(os.path.join(WURZEL, datei), os.X_OK), f"{datei} ist nicht ausführbar"


def test_binary_ist_nicht_in_git():
    assert "script.presentation/bin/" in lies(".gitignore")


def test_build_sh_liest_die_version_aus_addon_xml():
    assert "addon.xml" in lies("build.sh")


def test_addon_version_hat_drei_stellen():
    import re
    xml = lies("script.presentation", "addon.xml")
    assert re.search(r'<addon[^>]*version="\d+\.\d+\.\d+"', xml)


def test_pdf_build_skript_nutzt_dasselbe_rezept():
    s = lies("tools", "build-pdfrender.sh")
    assert "aarch64-unknown-linux-musl" in s
    assert "-C linker=rust-lld" in s
    assert "-C link-self-contained=yes" in s
    assert "ARM aarch64" in s
    assert "set -euo pipefail" in s


def test_pdf_werkzeug_haengt_nur_an_hayro():
    """Kein C, keine Systembibliothek -- sonst bricht der Cross-Build."""
    s = lies("tools", "pdfrender", "Cargo.toml")
    import re
    block = s.split("[dependencies]", 1)[1].split("[profile", 1)[0]
    kisten = re.findall(r"^([a-z0-9_-]+)\s*=", block, re.M)
    assert kisten == ["hayro"], f"unerwartete Abhaengigkeiten: {kisten}"


def test_pdf_werkzeug_ist_syntaktisch_gueltiges_rust():
    import subprocess
    pfad = os.path.join(WURZEL, "tools", "pdfrender", "src", "main.rs")
    with open(pfad, encoding="utf-8") as f:
        quelle = f.read()
    assert quelle.count("{") == quelle.count("}")
    assert "fn main()" in quelle


def test_build_sh_verweigert_ohne_binaries(tmp_path):
    """Verhaltenstest statt Zeichenkettensuche: ohne Binary kein ZIP."""
    import shutil
    import subprocess
    kopie = tmp_path / "projekt"
    shutil.copytree(WURZEL, kopie, symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "dist", "__pycache__",
                                                  ".pytest_cache", "target", ".superpowers"))
    binordner = kopie / "script.presentation" / "bin"
    shutil.rmtree(binordner, ignore_errors=True)
    ergebnis = subprocess.run(["bash", "build.sh"], cwd=kopie,
                              capture_output=True, text=True)
    assert ergebnis.returncode != 0, "build.sh haette abbrechen muessen"
    assert "deckcraft-cli" in ergebnis.stderr

    # Nur das eine Binary da: es muss weiterhin am PDF-Werkzeug scheitern.
    binordner.mkdir(parents=True, exist_ok=True)
    gefaelscht = binordner / "deckcraft-cli"
    gefaelscht.write_text("#!/bin/sh\nexit 0\n")
    gefaelscht.chmod(0o755)
    ergebnis = subprocess.run(["bash", "build.sh"], cwd=kopie,
                              capture_output=True, text=True)
    assert ergebnis.returncode != 0
    assert "pdfrender" in ergebnis.stderr
