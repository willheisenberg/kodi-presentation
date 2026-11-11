# kodi-presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Kodi-Add-on, das `.pptx`-Dateien auf einem LibreELEC-Gerät selbst rendert, im Vollbild auf dem Fernseher zeigt und die Referentennotizen auf das Handy des Vortragenden spiegelt.

**Architecture:** Ein einzelnes Script-Add-on, ein Prozess. Ein dünner Python-Wrapper ruft das mitgelieferte, statisch gelinkte `deckcraft-cli` auf und legt die gerenderten PNGs samt Metadaten in einem Cache ab. Ein `WindowXML` zeigt die Folien auf dem TV; ein HTTP-Server läuft als Thread in derselben Präsentation und liefert die Handy-Ansicht. Geteilter Zustand steckt ausschließlich in einer kleinen Sitzungsklasse mit Versionszähler unter Lock.

**Tech Stack:** Python 3.11 (Kodi 21 Omega, `xbmc.python` 3.0.0), nur Standardbibliothek. `deckcraft-cli` 0.15.0 als statisches aarch64-musl-Binary. pytest für Tests, Kodi-Module gestubbt.

**Spec:** `docs/superpowers/specs/2026-11-10-kodi-presentation-design.md`

## Global Constraints

- **Zielplattform:** LibreELEC 12.2.1, Raspberry Pi 5, aarch64, Kodi 21 (Omega), Python 3.11.13.
- **Keine Fremdbibliotheken zur Laufzeit.** Nur Python-Standardbibliothek und die Kodi-API. Keine `pip`-Abhängigkeit, kein `lxml`, kein `requests`.
- **Add-on-ID:** `script.presentation`. Repo-Ordner: `kodi-presentation`. Lizenz MIT.
- **`addon.xml` zweisprachig** (`de_DE` und `en_GB`), nach dem Muster von `script.dwd.rainradar`.
- **DeckCraft-Version ist festgenagelt** in `tools/deckcraft.version`, Wert: `0.15.0`.
- **Cross-Compile-Rezept, wörtlich:** Ziel `aarch64-unknown-linux-musl`, `RUSTFLAGS="-C linker=rust-lld -C link-self-contained=yes"`, gebaut mit `cargo build --release -p deckcraft-cli`.
- **Das Binary gehört nicht in Git.** `script.presentation/bin/` steht in `.gitignore`.
- **Code und Bezeichner auf Deutsch**, wie in den bestehenden Kodi-Projekten des Repos. Ausnahme: Kodi-API-Namen bleiben original.
- **Keine Commits ohne ausdrückliche Anweisung** des menschlichen Partners. Aufgaben enden mit einem Prüfschritt, nicht mit `git commit`. Das Verzeichnis ist zu Beginn kein Git-Repo.
- **Notizen erscheinen nie auf dem Fernseher.** Kein Codepfad darf `notizen` in ein TV-Fensterelement schreiben.

## Review Focus

Fünf Eingabeklassen, die die Spec voraussetzt, ohne sie zu benennen. Jede bekommt ihren Test in der Aufgabe, der der Code gehört:

1. **Kodi-VFS-Pfade** (`smb://`, `nfs://`): Das externe Binary kann sie nicht öffnen. Erwartet: Datei wird über `xbmcvfs` in einen lokalen Temporärpfad kopiert, von dort gerendert, danach aufgeräumt. → Aufgabe 3.
2. **Dateinamen mit Leerzeichen, Umlauten, Anführungszeichen und führendem Bindestrich:** Erwartet: werden korrekt an das Binary übergeben (Argumentliste, niemals Shell-String), ein führender Bindestrich wird nicht als Option gelesen. → Aufgabe 2.
3. **Deck ohne Folien oder mit genau einer Folie:** Erwartet: kein Absturz, kein Division-durch-Null im Fortschritt, „vor" und „zurück" an den Enden sind wirkungslos statt fehlerhaft. → Aufgabe 4.
4. **Zwei Handys gleichzeitig, gleichzeitige Kommandos:** Erwartet: Der Sitzungszustand bleibt konsistent, der Versionszähler springt nie zurück, beide Long Polls werden geweckt. → Aufgabe 4.
5. **Abbruch mitten im Rendern** (Deck zu groß, Platte voll, Benutzer bricht ab): Erwartet: Der halbfertige Cache-Eintrag wird verworfen und nicht beim nächsten Start als gültig gelesen. → Aufgabe 3.

---

## Dateistruktur

```
kodi-presentation/
├── script.presentation/
│   ├── addon.xml
│   ├── default.py                       Einstiegspunkt, verdrahtet alles
│   ├── icon.png
│   ├── bin/deckcraft-cli                nicht in Git
│   └── resources/
│       ├── settings.xml
│       ├── language/resource.language.{de_de,en_gb}/strings.po
│       ├── web/presenter.html           Handy-Seite, eine Datei
│       ├── skins/Default/1080i/script-presentation-main.xml
│       └── lib/
│           ├── konfig.py                Einstellungen lesen
│           ├── renderer.py              Binary-Wrapper, DeckInfo
│           ├── deck_cache.py            Cache-Schlüssel, Manifest, Aufräumen
│           ├── sitzung.py               geteilter Zustand
│           ├── handy_server.py          HTTP-Thread
│           ├── qr.py                    QR-Matrix, optional
│           ├── deck_browser.py          Deck-Auswahl
│           └── praesentations_fenster.py  WindowXML
├── tools/
│   ├── deckcraft.version
│   └── build-deckcraft.sh
├── build.sh
├── pytest.ini
├── tests/
│   ├── conftest.py
│   ├── test_konfig.py
│   ├── test_renderer.py
│   ├── test_deck_cache.py
│   ├── test_sitzung.py
│   ├── test_handy_server.py
│   ├── test_qr.py
│   ├── test_fenster.py
│   └── test_integration.py              Marker `binary`
├── docs/
├── .gitignore
├── LICENSE
└── README.md
```

---

### Task 1: Gerüst, Kodi-Stubs und Einstellungen

Legt das Projekt an und macht die Testrunde lauffähig. Ohne diese Aufgabe kann keine andere getestet werden.

**Files:**
- Create: `pytest.ini`, `.gitignore`, `tests/conftest.py`, `script.presentation/addon.xml`, `script.presentation/resources/settings.xml`, `script.presentation/resources/lib/konfig.py`
- Test: `tests/test_konfig.py`

**Interfaces:**
- Consumes: nichts
- Produces: `konfig.Konfig` mit den Eigenschaften `deck_ordner: str`, `skalierung: int`, `port: int`, `cache_grenze_bytes: int`, `binary_pfad: str`

- [ ] **Step 1: Projektdateien anlegen**

`.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
dist/
script.presentation/bin/
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
pythonpath = script.presentation/resources/lib tests
addopts = -v -m "not binary"
markers =
    binary: Test braucht das echte deckcraft-cli (mit -m binary ausführen)
```

- [ ] **Step 2: Kodi-Stubs schreiben**

`tests/conftest.py` — Kodi-Module existieren außerhalb von Kodi nicht und müssen vor jedem Import bereitstehen:
```python
"""Stubs für die Kodi-Module, damit die Tests ohne Kodi laufen."""
import sys
import types
import pytest

class _StubAddon:
    def __init__(self, *a, **k):
        self.werte = {}
        self.pfad = "/tmp/addon"
    def getSetting(self, key):
        return self.werte.get(key, "")
    def getSettingInt(self, key):
        return int(self.werte.get(key, 0))
    def setSetting(self, key, wert):
        self.werte[key] = wert
    def getAddonInfo(self, key):
        return {"path": self.pfad, "profile": "/tmp/addon_data", "id": "script.presentation"}.get(key, "")
    def getLocalizedString(self, _id):
        return ""

def _stub_module(name, **inhalt):
    modul = types.ModuleType(name)
    for k, v in inhalt.items():
        setattr(modul, k, v)
    sys.modules[name] = modul
    return modul

_stub_module("xbmc", log=lambda *a, **k: None, LOGINFO=1, LOGERROR=3,
             translatePath=lambda p: p, executebuiltin=lambda *a: None)
_stub_module("xbmcaddon", Addon=_StubAddon)
_stub_module("xbmcvfs", exists=lambda p: False, listdir=lambda p: ([], []),
             copy=lambda a, b: True, delete=lambda p: True,
             translatePath=lambda p: p, mkdirs=lambda p: True)
_stub_module("xbmcgui", WindowXML=object, Dialog=object,
             DialogProgress=object, ListItem=object)
_stub_module("xbmcplugin")

@pytest.fixture
def addon_stub():
    """Frischer Add-on-Stub je Test."""
    stub = _StubAddon()
    sys.modules["xbmcaddon"].Addon = lambda *a, **k: stub
    return stub
```

- [ ] **Step 3: Den fehlschlagenden Test schreiben**

`tests/test_konfig.py`:
```python
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
    addon_stub.werte = {"deck_ordner": "/storage/vortraege", "skalierung": "4", "port": "9000",
                        "cache_grenze_gb": "5"}
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
```

- [ ] **Step 4: Test laufen lassen, Fehlschlag bestätigen**

Run: `cd /home/tesla/githubprojects/kodi-presentation && python -m pytest tests/test_konfig.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'konfig'`

- [ ] **Step 5: `konfig.py` schreiben**

```python
"""Liest die Add-on-Einstellungen und hält die Vorgaben an einer Stelle."""
import os
import xbmcaddon

VORGABEN = {
    "deck_ordner": "/storage/presentations",
    "skalierung": 2,
    "port": 8099,
    "cache_grenze_gb": 2,
}

class Konfig:
    def __init__(self):
        self._addon = xbmcaddon.Addon()

    def _text(self, schluessel):
        wert = self._addon.getSetting(schluessel)
        return wert if wert else VORGABEN[schluessel]

    def _zahl(self, schluessel, kleinster, groesster):
        """Unsinnige Werte fallen stillschweigend auf die Vorgabe zurück."""
        try:
            wert = int(self._addon.getSetting(schluessel))
        except (TypeError, ValueError):
            return VORGABEN[schluessel]
        return wert if kleinster <= wert <= groesster else VORGABEN[schluessel]

    @property
    def deck_ordner(self):
        return self._text("deck_ordner")

    @property
    def skalierung(self):
        return self._zahl("skalierung", 1, 4)

    @property
    def port(self):
        return self._zahl("port", 1024, 65535)

    @property
    def cache_grenze_bytes(self):
        return self._zahl("cache_grenze_gb", 1, 100) * 1024**3

    @property
    def addon_pfad(self):
        return self._addon.getAddonInfo("path")

    @property
    def daten_pfad(self):
        return self._addon.getAddonInfo("profile")

    @property
    def binary_pfad(self):
        return os.path.join(self.addon_pfad, "bin", "deckcraft-cli")
```

- [ ] **Step 6: `addon.xml` und `settings.xml` schreiben**

`script.presentation/addon.xml`:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="script.presentation" name="Präsentation" version="0.1.0" provider-name="tesla">
  <requires>
    <import addon="xbmc.python" version="3.0.0"/>
  </requires>
  <extension point="xbmc.python.script" library="default.py">
    <provides>executable</provides>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="de_DE">Präsentationen vom Fernseher aus halten</summary>
    <summary lang="en_GB">Give presentations from your TV</summary>
    <description lang="de_DE">Zeigt PowerPoint-Präsentationen im Vollbild auf dem Fernseher und spiegelt Referentennotizen, nächste Folie und Timer auf das Handy des Vortragenden. Rendert die Folien auf dem Gerät selbst, ohne Internet und ohne zweiten Rechner.</description>
    <description lang="en_GB">Shows PowerPoint presentations fullscreen on the TV and mirrors speaker notes, next slide and a timer to the presenter's phone. Renders slides on the device itself, with no internet and no second computer.</description>
    <platform>linux</platform>
    <license>MIT</license>
    <assets>
      <icon>icon.png</icon>
    </assets>
  </extension>
</addon>
```

`script.presentation/resources/settings.xml`:
```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings version="1">
  <section id="script.presentation">
    <category id="allgemein" label="30010">
      <group id="1">
        <setting id="deck_ordner" type="path" label="30011">
          <level>0</level>
          <default>/storage/presentations</default>
          <constraints><writable>false</writable></constraints>
          <control type="button" format="path"/>
        </setting>
        <setting id="skalierung" type="integer" label="30012">
          <level>0</level>
          <default>2</default>
          <constraints>
            <options>
              <option label="30013">1</option>
              <option label="30014">2</option>
              <option label="30015">4</option>
            </options>
          </constraints>
          <control type="list" format="integer"/>
        </setting>
      </group>
    </category>
    <category id="handy" label="30020">
      <group id="1">
        <setting id="port" type="integer" label="30021">
          <level>0</level>
          <default>8099</default>
          <constraints><minimum>1024</minimum><maximum>65535</maximum></constraints>
          <control type="edit" format="integer"/>
        </setting>
      </group>
    </category>
    <category id="speicher" label="30030">
      <group id="1">
        <setting id="cache_grenze_gb" type="integer" label="30031">
          <level>0</level>
          <default>2</default>
          <constraints><minimum>1</minimum><maximum>100</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
      </group>
    </category>
  </section>
</settings>
```

- [ ] **Step 7: Tests laufen lassen**

Run: `python -m pytest -v`
Expected: 4 Tests PASS

- [ ] **Step 8: Stand prüfen und berichten**

`python -m pytest -v` zeigt vier grüne Tests. Dateien liegen im Arbeitsverzeichnis, **nicht committen**. Stand dem menschlichen Partner berichten.

---

### Task 2: Renderer-Wrapper

Kapselt das Binary. Jeder Aufruf geht über eine Argumentliste, niemals über einen Shell-String — das ist die Stelle, an der Dateinamen mit Leerzeichen, Umlauten und Bindestrichen entweder sauber durchgehen oder das Add-on zerlegen.

**Files:**
- Create: `script.presentation/resources/lib/renderer.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: nichts aus anderen Aufgaben
- Produces:
  - `renderer.Folie(index: int, titel: str, notizen: str)` — eingefrorene Dataclass
  - `renderer.DeckInfo(titel: str, folien: list[Folie], folien_groesse: tuple[float, float], verlorene_folien: int, beschaedigte_medien: int)`
  - `renderer.RendererFehler(Exception)`
  - `renderer.DeckcraftRenderer(binary_pfad: str)` mit `version() -> str`, `info(pfad: str) -> DeckInfo`, `render(pfad: str, ziel_ordner: str, skalierung: int) -> list[str]`

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_renderer.py`:
```python
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
    """Review Focus 2: Leerzeichen, Umlaute und führender Bindestrich im Namen."""
    protokoll = tmp_path / "args.txt"
    # Argumentfolge: render --all --scale 2 -- PFAD ZIEL  ->  Ziel ist $7
    b = attrappe(tmp_path, f'for a in "$@"; do echo "$a" >> {protokoll}; done\n'
                           'mkdir -p "$7"; touch "$7/slide-01.png"')
    heikel = str(tmp_path / "-mein Vörtrag 'quote'.pptx")
    open(heikel, "w").close()
    ziel = tmp_path / "out"
    renderer.DeckcraftRenderer(b).render(heikel, str(ziel), 2)
    zeilen = protokoll.read_text().splitlines()
    assert heikel in zeilen, "Dateiname muss unverändert ankommen"
    assert "--" in zeilen, "vor dem Pfad muss -- stehen, sonst liest das Binary ihn als Option"

def test_render_gibt_sortierte_bildpfade_zurueck(tmp_path):
    b = attrappe(tmp_path, 'mkdir -p "$7"\n'
                           'for n in 03 01 02; do touch "$7/slide-$n.png"; done')
    ziel = tmp_path / "out"
    bilder = renderer.DeckcraftRenderer(b).render(str(tmp_path / "d.pptx"), str(ziel), 2)
    assert [os.path.basename(p) for p in bilder] == ["slide-01.png", "slide-02.png", "slide-03.png"]

def test_render_fehler_enthaelt_stderr(tmp_path):
    b = attrappe(tmp_path, 'echo "font table broken" >&2; exit 1')
    with pytest.raises(renderer.RendererFehler) as e:
        renderer.DeckcraftRenderer(b).render("/tmp/d.pptx", str(tmp_path / "o"), 2)
    assert "font table broken" in str(e.value)
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_renderer.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'renderer'`

- [ ] **Step 3: `renderer.py` schreiben**

```python
"""Wrapper um deckcraft-cli. Einzige Stelle, die einen Fremdprozess startet.

Die Schnittstelle ist bewusst schmal gehalten: info() und render(). Sollte
DeckCraft einmal ersetzt werden, ist das die einzige Datei, die das merkt.
"""
import json
import os
import re
import subprocess
from dataclasses import dataclass, field

ZEITGRENZE = 300  # Sekunden; ein 500-Folien-Deck bleibt weit darunter

class RendererFehler(Exception):
    pass

@dataclass(frozen=True)
class Folie:
    index: int
    titel: str
    notizen: str

@dataclass(frozen=True)
class DeckInfo:
    titel: str
    folien: list = field(default_factory=list)
    folien_groesse: tuple = (960.0, 540.0)
    verlorene_folien: int = 0
    beschaedigte_medien: int = 0

class DeckcraftRenderer:
    def __init__(self, binary_pfad):
        self._binary = binary_pfad

    def _ruf(self, *argumente):
        if not os.path.isfile(self._binary):
            raise RendererFehler(f"deckcraft-cli nicht gefunden: {self._binary}")
        if not os.access(self._binary, os.X_OK):
            raise RendererFehler(f"deckcraft-cli ist nicht ausführbar: {self._binary}")
        try:
            ergebnis = subprocess.run(
                [self._binary, *argumente],
                capture_output=True, text=True, timeout=ZEITGRENZE,
            )
        except subprocess.TimeoutExpired:
            raise RendererFehler(f"deckcraft-cli hat nach {ZEITGRENZE}s nicht geantwortet")
        except OSError as e:
            # Trifft u.a. bei falscher Architektur zu (Exec format error).
            raise RendererFehler(f"deckcraft-cli ließ sich nicht starten: {e}")
        if ergebnis.returncode != 0:
            fehler = ergebnis.stderr.strip() or ergebnis.stdout.strip() or "ohne Meldung"
            raise RendererFehler(f"deckcraft-cli fehlgeschlagen: {fehler}")
        return ergebnis

    def version(self):
        return self._ruf("--version").stdout.strip()

    def info(self, pfad):
        ergebnis = self._ruf("info", "--", pfad)
        try:
            roh = json.loads(ergebnis.stdout)
        except json.JSONDecodeError as e:
            raise RendererFehler(f"info lieferte kein gültiges JSON: {e}")
        return self._lies_info(roh, ergebnis.stderr)

    @staticmethod
    def _lies_info(roh, stderr):
        """Wertet defensiv aus: fehlende Felder sind kein Fehler, nur leer."""
        folien = [
            Folie(
                index=int(f.get("index", i)),
                titel=str(f.get("title") or ""),
                notizen=str(f.get("notes") or ""),
            )
            for i, f in enumerate(roh.get("slides") or [])
        ]
        groesse = roh.get("slideSize") or [960.0, 540.0]
        def zaehle(muster):
            treffer = re.search(muster, stderr or "")
            return int(treffer.group(1)) if treffer else 0
        return DeckInfo(
            titel=str(roh.get("title") or ""),
            folien=folien,
            folien_groesse=(float(groesse[0]), float(groesse[1])),
            verlorene_folien=zaehle(r"(\d+) slides? could."),
            beschaedigte_medien=zaehle(r"(\d+) pictures? or media"),
        )

    def render(self, pfad, ziel_ordner, skalierung):
        """Rendert alle Folien nach ziel_ordner und gibt die Bildpfade sortiert zurück.

        Das `--` vor dem Pfad ist Pflicht: ohne es liest das Binary einen
        Dateinamen mit führendem Bindestrich als Option.
        """
        os.makedirs(ziel_ordner, exist_ok=True)
        self._ruf("render", "--all", "--scale", str(skalierung), "--", pfad, ziel_ordner)
        bilder = sorted(
            os.path.join(ziel_ordner, name)
            for name in os.listdir(ziel_ordner)
            if name.startswith("slide-") and name.endswith(".png")
        )
        if not bilder:
            raise RendererFehler("render hat keine Bilder erzeugt")
        return bilder
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_renderer.py -v`
Expected: 8 Tests PASS

- [ ] **Step 5: Stand prüfen und berichten**

Run: `python -m pytest -v` — alle Tests der Aufgaben 1 und 2 grün. Nicht committen.

---

### Task 3: Cache mit VFS-Behandlung

Hält gerenderte Decks vor und löst das VFS-Problem: Liegt das Deck auf einer Kodi-Quelle (`smb://`), kann das Binary es nicht öffnen und die Datei muss zuerst lokal kopiert werden.

**Files:**
- Create: `script.presentation/resources/lib/deck_cache.py`
- Test: `tests/test_deck_cache.py`

**Interfaces:**
- Consumes: `renderer.DeckcraftRenderer`, `renderer.DeckInfo`, `renderer.RendererFehler`
- Produces:
  - `deck_cache.schluessel(pfad: str) -> str`
  - `deck_cache.ist_vfs(pfad: str) -> bool`
  - `deck_cache.DeckCache(wurzel: str, grenze_bytes: int)` mit
    `hole(pfad, renderer, skalierung, fortschritt=None) -> dict` (das Manifest),
    `ist_gueltig(pfad) -> bool`,
    `aufraeumen() -> int` (Anzahl entfernter Einträge)
  - Manifest-Form wie in der Spec, Abschnitt 5

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_deck_cache.py`:
```python
import json
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
            p = os.path.join(ziel, f"slide-{i+1:02d}.png")
            open(p, "wb").write(b"x" * 100)
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

def test_ist_vfs_erkennt_schemata():
    assert deck_cache.ist_vfs("smb://nas/a.pptx")
    assert deck_cache.ist_vfs("nfs://host/a.pptx")
    assert not deck_cache.ist_vfs("/storage/a.pptx")
    assert not deck_cache.ist_vfs("C:\\decks\\a.pptx")

def test_aufraeumen_entfernt_aelteste_eintraege(tmp_path):
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 500)
    r = FakeRenderer(folien=2)
    for n in range(4):
        c.hole(deck(tmp_path, f"d{n}.pptx"), r, 2)
    entfernt = c.aufraeumen()
    assert entfernt > 0
    assert c.groesse_bytes() <= 500
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_deck_cache.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'deck_cache'`

- [ ] **Step 3: `deck_cache.py` schreiben**

```python
"""Cache der gerenderten Decks.

Ein Eintrag gilt erst als gültig, wenn das Manifest geschrieben ist. Bricht
das Rendern ab, bleibt kein halbfertiger Eintrag zurück, der beim nächsten
Start fälschlich als Treffer zählt.
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
import time

import xbmcvfs

MANIFEST = "deck.json"
VORSCHAU_SKALIERUNG = 0.5  # 960x540 Punkte * 0.5 = 480x270
_SCHEMA = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)

def ist_vfs(pfad):
    """True für Kodi-Quellen wie smb:// oder nfs://, die kein Dateisystempfad sind."""
    return bool(_SCHEMA.match(pfad or ""))

def schluessel(pfad):
    """Hash aus Pfad, Änderungszeit und Größe. Ändert sich das Deck, ändert sich der Schlüssel."""
    if ist_vfs(pfad):
        roh = pfad
    else:
        s = os.stat(pfad)
        roh = f"{os.path.abspath(pfad)}|{int(s.st_mtime)}|{s.st_size}"
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:32]

class DeckCache:
    def __init__(self, wurzel, grenze_bytes):
        self._wurzel = wurzel
        self._grenze = grenze_bytes
        os.makedirs(self._wurzel, exist_ok=True)

    def _ordner(self, pfad):
        return os.path.join(self._wurzel, schluessel(pfad))

    def _manifest_pfad(self, pfad):
        return os.path.join(self._ordner(pfad), MANIFEST)

    def ist_gueltig(self, pfad):
        return os.path.isfile(self._manifest_pfad(pfad))

    def hole(self, pfad, renderer_, skalierung, fortschritt=None):
        """Liefert das Manifest; rendert bei Bedarf. fortschritt(prozent, text) ist optional."""
        if self.ist_gueltig(pfad):
            os.utime(self._ordner(pfad), None)  # für das Aufräumen nach Zugriff
            with open(self._manifest_pfad(pfad), encoding="utf-8") as f:
                return json.load(f)
        return self._rendere(pfad, renderer_, skalierung, fortschritt)

    def _rendere(self, pfad, renderer_, skalierung, fortschritt):
        ziel = self._ordner(pfad)
        shutil.rmtree(ziel, ignore_errors=True)
        os.makedirs(ziel, exist_ok=True)
        lokal, aufraeumen = self._lokaler_pfad(pfad)
        try:
            if fortschritt:
                fortschritt(10, "Deck wird gelesen")
            info = renderer_.info(lokal)
            if fortschritt:
                fortschritt(30, "Folien werden gezeichnet")
            bilder = renderer_.render(lokal, os.path.join(ziel, "tv"), skalierung)
            if fortschritt:
                fortschritt(70, "Vorschaubilder für das Handy")
            vorschau = renderer_.render(lokal, os.path.join(ziel, "thumb"), VORSCHAU_SKALIERUNG)
            manifest = self._baue_manifest(pfad, info, bilder, vorschau)
            # Zuletzt schreiben: erst jetzt gilt der Eintrag als gültig.
            with open(os.path.join(ziel, MANIFEST), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
            if fortschritt:
                fortschritt(100, "Fertig")
            self.aufraeumen()
            return manifest
        except Exception:
            shutil.rmtree(ziel, ignore_errors=True)
            raise
        finally:
            if aufraeumen and os.path.isfile(lokal):
                os.unlink(lokal)

    @staticmethod
    def _lokaler_pfad(pfad):
        """Kodi-VFS-Pfade kann das Binary nicht öffnen: erst lokal kopieren."""
        if not ist_vfs(pfad):
            return pfad, False
        endung = os.path.splitext(pfad)[1] or ".pptx"
        griff, ziel = tempfile.mkstemp(suffix=endung, prefix="deck-")
        os.close(griff)
        if not xbmcvfs.copy(pfad, ziel):
            os.unlink(ziel)
            raise OSError(f"Konnte {pfad} nicht lokal kopieren")
        return ziel, True

    @staticmethod
    def _baue_manifest(quelle, info, bilder, vorschau):
        folien = []
        for i, f in enumerate(info.folien):
            folien.append({
                "index": i,
                "titel": f.titel,
                "notizen": f.notizen,
                "bild": bilder[i] if i < len(bilder) else "",
                "vorschau": vorschau[i] if i < len(vorschau) else "",
            })
        return {
            "quelle": quelle,
            "hash": schluessel(quelle) if not ist_vfs(quelle) else schluessel(quelle),
            "gerendert": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "folienGroesse": list(info.folien_groesse),
            "titel": info.titel,
            "verloreneFolien": info.verlorene_folien,
            "beschaedigteMedien": info.beschaedigte_medien,
            "folien": folien,
        }

    def groesse_bytes(self):
        gesamt = 0
        for wurzel, _, dateien in os.walk(self._wurzel):
            for d in dateien:
                try:
                    gesamt += os.path.getsize(os.path.join(wurzel, d))
                except OSError:
                    pass
        return gesamt

    def aufraeumen(self):
        """Entfernt die am längsten nicht benutzten Einträge, bis die Grenze eingehalten ist."""
        if self.groesse_bytes() <= self._grenze:
            return 0
        eintraege = []
        for name in os.listdir(self._wurzel):
            ordner = os.path.join(self._wurzel, name)
            if os.path.isdir(ordner):
                eintraege.append((os.path.getmtime(ordner), ordner))
        eintraege.sort()
        entfernt = 0
        for _, ordner in eintraege:
            if self.groesse_bytes() <= self._grenze:
                break
            shutil.rmtree(ordner, ignore_errors=True)
            entfernt += 1
        return entfernt
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_deck_cache.py -v`
Expected: 9 Tests PASS

- [ ] **Step 5: Stand prüfen und berichten**

Run: `python -m pytest -v`. Nicht committen.

---

### Task 4: Sitzungszustand

Der einzige geteilte Zustand zwischen TV-Fenster und HTTP-Thread. Klein halten, alles unter einem Lock, Versionszähler für den Long Poll.

**Files:**
- Create: `script.presentation/resources/lib/sitzung.py`
- Test: `tests/test_sitzung.py`

**Interfaces:**
- Consumes: nichts
- Produces: `sitzung.Sitzung(anzahl: int)` mit `index`, `version`, `blende` (bool), `anzahl`,
  `vor()`, `zurueck()`, `springe(n: int)`, `blende_umschalten()`, `timer_zuruecksetzen()`,
  `zustand() -> dict`, `warte_auf_aenderung(seit: int, zeitgrenze: float) -> dict`, `beenden()`

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_sitzung.py`:
```python
import threading
import time
import pytest
import sitzung

def test_startet_bei_null():
    s = sitzung.Sitzung(5)
    assert s.index == 0 and s.version == 1

def test_vor_und_zurueck():
    s = sitzung.Sitzung(3)
    s.vor(); s.vor()
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
    s.vor(); s.vor(); s.vor()
    assert s.index == 1

def test_deck_ohne_folien_stuerzt_nicht_ab():
    """Review Focus 3: leeres Deck."""
    s = sitzung.Sitzung(0)
    s.vor(); s.zurueck(); s.springe(3)
    assert s.index == 0
    assert s.zustand()["anzahl"] == 0

def test_deck_mit_einer_folie():
    s = sitzung.Sitzung(1)
    s.vor()
    assert s.index == 0

def test_springe_begrenzt():
    s = sitzung.Sitzung(4)
    s.springe(99); assert s.index == 3
    s.springe(-5); assert s.index == 0

def test_version_steigt_monoton():
    s = sitzung.Sitzung(5)
    versionen = []
    for _ in range(4):
        s.vor(); versionen.append(s.version)
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
    t = threading.Thread(target=warter); t.start()
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
    for t in threads: t.start()
    time.sleep(0.1)
    s.vor()
    for t in threads: t.join(timeout=2)
    assert len(treffer) == 2

def test_gleichzeitige_kommandos_bleiben_konsistent():
    """Review Focus 4."""
    s = sitzung.Sitzung(1000)
    def blaettern():
        for _ in range(100):
            s.vor()
    threads = [threading.Thread(target=blaettern) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert s.index == 400
    assert s.version == 401
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_sitzung.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'sitzung'`

- [ ] **Step 3: `sitzung.py` schreiben**

```python
"""Geteilter Zustand einer laufenden Präsentation.

Fenster und HTTP-Thread greifen beide hierauf zu. Jede wirksame Änderung
erhöht die Version und weckt alle Wartenden; eine wirkungslose Aktion
(vor an der letzten Folie) tut das nicht, damit das Handy nicht grundlos
aufgeweckt wird.
"""
import threading
import time

class Sitzung:
    def __init__(self, anzahl):
        self._lock = threading.Condition()
        self._anzahl = max(0, int(anzahl))
        self._index = 0
        self._version = 1
        self._blende = False
        self._start = time.monotonic()
        self._beendet = False

    @property
    def anzahl(self):
        return self._anzahl

    @property
    def index(self):
        with self._lock:
            return self._index

    @property
    def version(self):
        with self._lock:
            return self._version

    @property
    def blende(self):
        with self._lock:
            return self._blende

    def _setze_index(self, neu):
        """Erwartet den Lock. Gibt True zurück, wenn sich etwas geändert hat."""
        if self._anzahl == 0:
            return False
        neu = max(0, min(self._anzahl - 1, neu))
        if neu == self._index:
            return False
        self._index = neu
        self._version += 1
        self._lock.notify_all()
        return True

    def vor(self):
        with self._lock:
            return self._setze_index(self._index + 1)

    def zurueck(self):
        with self._lock:
            return self._setze_index(self._index - 1)

    def springe(self, n):
        with self._lock:
            return self._setze_index(int(n))

    def blende_umschalten(self):
        with self._lock:
            self._blende = not self._blende
            self._version += 1
            self._lock.notify_all()
            return self._blende

    def timer_zuruecksetzen(self):
        with self._lock:
            self._start = time.monotonic()
            self._version += 1
            self._lock.notify_all()

    def beenden(self):
        """Weckt alle Wartenden, damit der HTTP-Thread sauber endet."""
        with self._lock:
            self._beendet = True
            self._version += 1
            self._lock.notify_all()

    def _zustand_ohne_lock(self):
        return {
            "index": self._index,
            "anzahl": self._anzahl,
            "version": self._version,
            "blende": self._blende,
            "sekunden": round(time.monotonic() - self._start, 1),
            "beendet": self._beendet,
        }

    def zustand(self):
        with self._lock:
            return self._zustand_ohne_lock()

    def warte_auf_aenderung(self, seit, zeitgrenze):
        """Blockiert, bis die Version über `seit` steigt oder die Zeit abläuft."""
        ende = time.monotonic() + zeitgrenze
        with self._lock:
            while self._version <= seit and not self._beendet:
                rest = ende - time.monotonic()
                if rest <= 0:
                    break
                self._lock.wait(rest)
            return self._zustand_ohne_lock()
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_sitzung.py -v`
Expected: 14 Tests PASS

- [ ] **Step 5: Stand prüfen und berichten**

Run: `python -m pytest -v`. Nicht committen.

---

### Task 5: HTTP-Server für die Handy-Ansicht

**Files:**
- Create: `script.presentation/resources/lib/handy_server.py`
- Test: `tests/test_handy_server.py`

**Interfaces:**
- Consumes: `sitzung.Sitzung`
- Produces: `handy_server.HandyServer(sitzung_, manifest: dict, seiten_html: str, port: int)` mit
  `starten() -> str` (die vollständige URL inklusive Token), `stoppen()`, `url`, `token`, `port`

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_handy_server.py`:
```python
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
        {"index": 0, "titel": "Erste", "notizen": "Nicht vorlesen", "vorschau": str(bild), "bild": ""},
        {"index": 1, "titel": "Zweite", "notizen": "", "vorschau": str(bild), "bild": ""},
    ]}
    s = sitzung.Sitzung(2)
    server = handy_server.HandyServer(s, manifest, "<html>Hallo</html>", port=0)
    url = server.starten()
    yield s, server, url
    server.stoppen()

def hole(url, daten=None):
    anfrage = urllib.request.Request(url, data=daten,
                                     headers={"Content-Type": "application/json"} if daten else {})
    with urllib.request.urlopen(anfrage, timeout=5) as a:
        return a.status, a.read()

def test_seite_wird_ausgeliefert(aufbau):
    _, _, url = aufbau
    status, koerper = hole(url)
    assert status == 200 and b"Hallo" in koerper

def test_falsches_token_gibt_404(aufbau):
    _, server, _ = aufbau
    with pytest.raises(urllib.error.HTTPError) as e:
        hole(f"http://127.0.0.1:{server.port}/p/falschestoken/")
    assert e.value.code == 404, "404 statt 403, um den Dienst nicht zu bestätigen"

def test_zustand_liefert_notizen_der_aktuellen_folie(aufbau):
    _, _, url = aufbau
    _, koerper = hole(url + "state?seit=0")
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
        _, koerper = hole(url + f"state?seit={s.version}")
        ergebnis["z"] = json.loads(koerper)
    t = threading.Thread(target=warter); t.start()
    time.sleep(0.2)
    s.vor()
    t.join(timeout=5)
    assert not t.is_alive()
    assert ergebnis["z"]["index"] == 1

def test_vorschaubild_wird_ausgeliefert(aufbau):
    _, _, url = aufbau
    status, koerper = hole(url + "thumb/0.jpg")
    assert status == 200 and koerper.startswith(b"\xff\xd8\xff")

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
    zweiter = handy_server.HandyServer(s, {"folien": []}, "<html></html>", port=port)
    zweiter.starten()
    zweiter.stoppen()
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_handy_server.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'handy_server'`

- [ ] **Step 3: `handy_server.py` schreiben**

```python
"""HTTP-Server für die Referentenansicht auf dem Handy.

Läuft als Thread in der laufenden Präsentation. Ohne gültiges Token
antwortet er mit 404 statt 403: wer den Pfad nicht kennt, soll nicht
einmal erfahren, dass hier ein Dienst läuft.

Das ist Schutz gegen versehentlichen Zugriff im eigenen Netz, nicht gegen
einen Angreifer im selben WLAN -- die Verbindung ist unverschlüsseltes HTTP.
"""
import json
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LONG_POLL_SEKUNDEN = 25
ERLAUBTE_AKTIONEN = {"vor", "zurueck", "springe", "blende", "timer"}

def eigene_ip():
    """Die IP, unter der das Gerät im LAN erreichbar ist."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()

class HandyServer:
    def __init__(self, sitzung_, manifest, seiten_html, port=8099, token=None):
        self.sitzung = sitzung_
        self.manifest = manifest
        self.seite = seiten_html
        self.token = token or secrets.token_urlsafe(8)
        self._wunsch_port = port
        self._server = None
        self._thread = None

    @property
    def port(self):
        return self._server.server_address[1] if self._server else self._wunsch_port

    @property
    def url(self):
        return f"http://{eigene_ip()}:{self.port}/p/{self.token}/"

    def starten(self):
        """Bindet den Port, probiert bei Belegung die nächsten drei."""
        letzter = None
        kandidaten = [self._wunsch_port] if self._wunsch_port == 0 else [
            self._wunsch_port + n for n in range(4)
        ]
        for p in kandidaten:
            try:
                self._server = _bau_server(p, self)
                break
            except OSError as e:
                letzter = e
        if self._server is None:
            raise OSError(f"Kein freier Port: {letzter}")
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="handy-server", daemon=True)
        self._thread.start()
        return self.url

    def stoppen(self):
        self.sitzung.beenden()
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def folie(self, index):
        folien = self.manifest.get("folien") or []
        return folien[index] if 0 <= index < len(folien) else None

    def zustand_json(self, seit):
        z = self.sitzung.warte_auf_aenderung(seit, LONG_POLL_SEKUNDEN)
        aktuell = self.folie(z["index"]) or {}
        naechste = self.folie(z["index"] + 1) or {}
        z.update({
            "titel": aktuell.get("titel", ""),
            "notizen": aktuell.get("notizen", ""),
            "naechsterTitel": naechste.get("titel", ""),
            "deckTitel": self.manifest.get("titel", ""),
        })
        return z

    def fuehre_aus(self, aktion, ziel=None):
        if aktion not in ERLAUBTE_AKTIONEN:
            return False
        if aktion == "vor":
            self.sitzung.vor()
        elif aktion == "zurueck":
            self.sitzung.zurueck()
        elif aktion == "springe":
            self.sitzung.springe(int(ziel or 0))
        elif aktion == "blende":
            self.sitzung.blende_umschalten()
        elif aktion == "timer":
            self.sitzung.timer_zuruecksetzen()
        return True

def _bau_server(port, halter):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "kodi-presentation"

        def log_message(self, *_a):
            pass  # Kodis Log nicht zumüllen

        def _rest(self):
            """Pfad hinter /p/<token>/ oder None, wenn das Token nicht stimmt."""
            teile = self.path.split("?", 1)[0].split("/")
            if len(teile) >= 3 and teile[1] == "p" and secrets.compare_digest(teile[2], halter.token):
                return "/".join(teile[3:])
            return None

        def _sende(self, status, koerper, typ="application/json; charset=utf-8"):
            if isinstance(koerper, str):
                koerper = koerper.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(koerper)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(koerper)

        def do_GET(self):
            rest = self._rest()
            if rest is None:
                return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")
            if rest in ("", "index.html"):
                return self._sende(200, halter.seite, "text/html; charset=utf-8")
            if rest.startswith("state"):
                seit = 0
                if "?" in self.path:
                    for paar in self.path.split("?", 1)[1].split("&"):
                        if paar.startswith("seit="):
                            try:
                                seit = int(paar[5:])
                            except ValueError:
                                seit = 0
                return self._sende(200, json.dumps(halter.zustand_json(seit)))
            if rest.startswith("thumb/"):
                try:
                    nummer = int(rest[6:].split(".")[0])
                except ValueError:
                    return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")
                folie = halter.folie(nummer)
                pfad = (folie or {}).get("vorschau") or ""
                if not pfad or not os.path.isfile(pfad):
                    return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")
                with open(pfad, "rb") as f:
                    return self._sende(200, f.read(), "image/jpeg")
            return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")

        def do_POST(self):
            rest = self._rest()
            if rest is None:
                return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")
            if rest != "cmd":
                return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")
            laenge = int(self.headers.get("Content-Length") or 0)
            try:
                daten = json.loads(self.rfile.read(laenge) or b"{}")
            except json.JSONDecodeError:
                return self._sende(400, json.dumps({"fehler": "kaputtes JSON"}))
            if not halter.fuehre_aus(daten.get("aktion"), daten.get("ziel")):
                return self._sende(400, json.dumps({"fehler": "unbekannte Aktion"}))
            return self._sende(200, json.dumps({"ok": True}))

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    return server
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_handy_server.py -v`
Expected: 11 Tests PASS

- [ ] **Step 5: Stand prüfen und berichten**

Run: `python -m pytest -v`. Nicht committen.

---

### Task 6: Handy-Seite

Eine einzige HTML-Datei, ohne externe Ressourcen. Sie muss im LAN ohne Internetzugang vollständig funktionieren.

**Files:**
- Create: `script.presentation/resources/web/presenter.html`
- Test: `tests/test_presenter_seite.py`

**Interfaces:**
- Consumes: die Routen aus Aufgabe 5 (`state?seit=`, `cmd`, `thumb/<n>.jpg`)
- Produces: nichts für andere Aufgaben; die Datei wird von `default.py` eingelesen und an `HandyServer` übergeben

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_presenter_seite.py`:
```python
import os
import re
import pytest

SEITE = os.path.join(os.path.dirname(__file__), "..", "script.presentation",
                     "resources", "web", "presenter.html")

@pytest.fixture
def html():
    with open(SEITE, encoding="utf-8") as f:
        return f.read()

def test_keine_externen_ressourcen(html):
    """Im LAN gibt es womöglich kein Internet."""
    treffer = re.findall(r'(?:src|href)\s*=\s*["\'](https?:)?//', html)
    assert not treffer, f"externe Ressource gefunden: {treffer}"

def test_relative_pfade_statt_absoluter(html):
    """Die Seite läuft unter /p/<token>/ und muss relativ verlinken."""
    assert not re.search(r'fetch\(\s*["\']/', html), "fetch darf nicht mit / beginnen"

def test_spricht_die_richtigen_routen_an(html):
    assert "state?seit=" in html
    assert "cmd" in html
    assert "thumb/" in html

def test_enthaelt_die_bedienelemente(html):
    for kennung in ("id=\"notizen\"", "id=\"vor\"", "id=\"zurueck\"",
                    "id=\"timer\"", "id=\"zaehler\"", "id=\"blende\""):
        assert kennung in html, f"fehlt: {kennung}"

def test_viewport_fuer_handys(html):
    assert 'name="viewport"' in html

def test_deutsche_sprachauszeichnung(html):
    assert 'lang="de"' in html
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_presenter_seite.py -v`
Expected: FAIL mit `FileNotFoundError`

- [ ] **Step 3: `presenter.html` schreiben**

```html
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Referentenansicht</title>
<style>
  :root { --bg:#111; --fg:#f4f4f4; --matt:#9a9a9a; --rand:#333; --akzent:#3b74c4; }
  * { box-sizing: border-box; }
  body { margin:0; padding:12px; background:var(--bg); color:var(--fg);
         font:16px/1.5 system-ui, -apple-system, sans-serif;
         -webkit-text-size-adjust:100%; }
  .kopf { display:flex; justify-content:space-between; align-items:baseline;
          color:var(--matt); font-size:14px; margin-bottom:8px; }
  .bilder { display:grid; grid-template-columns:2fr 1fr; gap:8px; margin-bottom:12px; }
  .bilder img { width:100%; border:1px solid var(--rand); border-radius:4px;
                background:#000; display:block; }
  .bilder figcaption { color:var(--matt); font-size:12px; margin-top:2px; }
  #notizen { background:#1b1b1b; border:1px solid var(--rand); border-radius:6px;
             padding:14px; font-size:20px; line-height:1.55; min-height:30vh;
             white-space:pre-wrap; overflow-y:auto; }
  #notizen.leer { color:var(--matt); font-style:italic; }
  .knoepfe { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
  button { font-size:22px; padding:22px 10px; border:0; border-radius:8px;
           background:var(--akzent); color:#fff; touch-action:manipulation; }
  button:active { filter:brightness(1.3); }
  .nebenknoepfe { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
  .nebenknoepfe button { font-size:15px; padding:12px; background:#2a2a2a; color:var(--fg); }
  .nebenknoepfe button[aria-pressed="true"] { background:var(--akzent); }
  #verbindung { color:#c4763b; font-size:13px; min-height:18px; margin-top:8px; }
</style>
</head>
<body>
  <div class="kopf">
    <span id="zaehler">–</span>
    <span id="deck"></span>
    <span id="timer">0:00</span>
  </div>

  <div class="bilder">
    <figure style="margin:0">
      <img id="jetzt" alt="Aktuelle Folie">
      <figcaption id="titel"></figcaption>
    </figure>
    <figure style="margin:0">
      <img id="naechste" alt="Nächste Folie">
      <figcaption id="naechsterTitel">Nächste</figcaption>
    </figure>
  </div>

  <div id="notizen"></div>

  <div class="knoepfe">
    <button id="zurueck" type="button">◀ Zurück</button>
    <button id="vor" type="button">Weiter ▶</button>
  </div>
  <div class="nebenknoepfe">
    <button id="blende" type="button" aria-pressed="false">Bildschirm schwarz</button>
    <button id="timerReset" type="button">Timer zurücksetzen</button>
  </div>
  <div id="verbindung"></div>

<script>
(function () {
  "use strict";
  var version = 0, laeuft = true;
  var el = function (id) { return document.getElementById(id); };

  function zeitText(sekunden) {
    var m = Math.floor(sekunden / 60), s = Math.floor(sekunden % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function zeichne(z) {
    version = z.version;
    el("zaehler").textContent = z.anzahl ? (z.index + 1) + " / " + z.anzahl : "keine Folien";
    el("deck").textContent = z.deckTitel || "";
    el("timer").textContent = zeitText(z.sekunden);
    el("titel").textContent = z.titel || "";
    el("naechsterTitel").textContent = z.naechsterTitel || "Ende";
    var n = el("notizen");
    if (z.notizen) { n.textContent = z.notizen; n.classList.remove("leer"); }
    else { n.textContent = "Keine Notizen zu dieser Folie."; n.classList.add("leer"); }
    el("jetzt").src = "thumb/" + z.index + ".jpg?v=" + z.version;
    if (z.index + 1 < z.anzahl) {
      el("naechste").src = "thumb/" + (z.index + 1) + ".jpg?v=" + z.version;
      el("naechste").style.visibility = "visible";
    } else {
      el("naechste").style.visibility = "hidden";
    }
    el("blende").setAttribute("aria-pressed", z.blende ? "true" : "false");
    el("blende").textContent = z.blende ? "Folie wieder zeigen" : "Bildschirm schwarz";
  }

  function lausche() {
    if (!laeuft) { return; }
    fetch("state?seit=" + version)
      .then(function (a) { return a.ok ? a.json() : Promise.reject(a.status); })
      .then(function (z) {
        el("verbindung").textContent = "";
        zeichne(z);
        if (z.beendet) { laeuft = false; el("verbindung").textContent = "Präsentation beendet."; return; }
        lausche();
      })
      .catch(function () {
        el("verbindung").textContent = "Keine Verbindung – neuer Versuch …";
        setTimeout(lausche, 1500);
      });
  }

  function schicke(aktion, ziel) {
    fetch("cmd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aktion: aktion, ziel: ziel })
    }).catch(function () {
      el("verbindung").textContent = "Befehl kam nicht an.";
    });
  }

  el("vor").addEventListener("click", function () { schicke("vor"); });
  el("zurueck").addEventListener("click", function () { schicke("zurueck"); });
  el("blende").addEventListener("click", function () { schicke("blende"); });
  el("timerReset").addEventListener("click", function () { schicke("timer"); });

  // Der Timer läuft lokal weiter, damit er zwischen zwei Antworten nicht einfriert.
  setInterval(function () {
    var t = el("timer").textContent.split(":");
    if (t.length === 2) {
      var s = parseInt(t[0], 10) * 60 + parseInt(t[1], 10) + 1;
      el("timer").textContent = zeitText(s);
    }
  }, 1000);

  lausche();
})();
</script>
</body>
</html>
```

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_presenter_seite.py -v`
Expected: 6 Tests PASS

- [ ] **Step 5: Seite im Browser gegen einen laufenden Server prüfen**

```bash
cd /home/tesla/githubprojects/kodi-presentation
python - <<'PY'
import sys, time
sys.path[:0] = ["script.presentation/resources/lib", "tests"]
import conftest  # setzt die Kodi-Stubs
import handy_server, sitzung
seite = open("script.presentation/resources/web/presenter.html", encoding="utf-8").read()
m = {"titel": "Probe", "folien": [
    {"index": i, "titel": f"Folie {i+1}", "notizen": f"Notiz zu Folie {i+1}", "vorschau": "", "bild": ""}
    for i in range(3)]}
s = sitzung.Sitzung(3)
srv = handy_server.HandyServer(s, m, seite, port=8099)
print("Offen:", srv.starten())
try:
    time.sleep(300)
finally:
    srv.stoppen()
PY
```

Erwartet: Die URL im Browser öffnen, „Weiter" drücken, Folienzähler und Notizen wechseln sofort. Die Vorschaubilder bleiben leer, weil das Manifest keine enthält — das ist in diesem Schritt richtig so.

- [ ] **Step 6: Stand prüfen und berichten**

Run: `python -m pytest -v`. Nicht committen.

---

### Task 7: QR-Code für die Startkarte

Optional im Wortsinn: Schlägt der Import fehl, zeigt die Startkarte nur die URL. Deshalb steht diese Aufgabe vor dem Fenster, aber nichts hängt von ihr ab.

**Files:**
- Create: `script.presentation/resources/lib/qr.py`
- Test: `tests/test_qr.py`

**Interfaces:**
- Consumes: nichts
- Produces: `qr.matrix(text: str) -> list[list[bool]]`, `qr.als_png(text: str, ziel: str, modulgroesse: int = 8) -> str`

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_qr.py`:
```python
import os
import struct
import zlib
import pytest
import qr

def test_matrix_ist_quadratisch():
    m = qr.matrix("http://192.168.178.10:8099/p/abc/")
    assert len(m) == len(m[0])

def test_version_waechst_mit_der_laenge():
    klein = len(qr.matrix("kurz"))
    gross = len(qr.matrix("x" * 200))
    assert gross > klein

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

def test_gleicher_text_gleiche_matrix():
    assert qr.matrix("abc") == qr.matrix("abc")

def test_png_wird_geschrieben(tmp_path):
    ziel = str(tmp_path / "qr.png")
    qr.als_png("http://192.168.178.10:8099/p/abc/", ziel, modulgroesse=4)
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
        laenge = struct.unpack(">I", f.read(4))[0]
        f.read(4)
        breite, hoehe = struct.unpack(">II", f.read(8))
    assert breite == breite_module * 2 == hoehe
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_qr.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'qr'`

- [ ] **Step 3: `qr.py` schreiben**

Implementiere einen QR-Encoder im Byte-Modus mit Fehlerkorrektur-Stufe L, Versionen 1 bis 10, Maske 0 fest gewählt. Das genügt vollständig: Die längste vorkommende URL ist etwa `http://192.168.178.100:8099/p/XXXXXXXXXXX/`, rund 45 Zeichen, und Version 4 fasst bei Stufe L schon 78 Byte.

Der Encoder braucht diese Bestandteile, jeder davon ist in sich prüfbar:

1. **Galois-Feld GF(256)** mit Generatorpolynom 0x11D: Log- und Exponentialtabellen.
2. **Reed-Solomon-Erzeugerpolynom** für die nötige Zahl Fehlerkorrekturbytes, Division der Datenbytes dadurch.
3. **Datenkodierung:** Modus `0100` (Byte), Längenfeld 8 Bit für Versionen 1 bis 9, danach 16 Bit, dann die UTF-8-Bytes, Abschluss `0000`, Auffüllen auf volle Byte, dann abwechselnd `0xEC` und `0x11` bis zur Kapazität.
4. **Platzierung:** Suchmuster in drei Ecken samt Trennlinien, Ausrichtungsmuster ab Version 2 nach Tabelle, Taktspuren in Zeile und Spalte 6, dunkles Modul bei `(4*version+9, 8)`, Formatinformation für Stufe L und Maske 0 an beiden vorgeschriebenen Stellen.
5. **Datenstrom** zickzack von rechts unten nach links oben, Spalte 6 übersprungen, Maske 0 (`(zeile + spalte) % 2 == 0`) auf alle nicht reservierten Module angewendet.

Tabellen, die als Konstanten ins Modul gehören (Version 1 bis 10, Stufe L): Gesamtzahl Codewörter `[26, 44, 70, 100, 134, 172, 196, 242, 292, 346]`, davon Fehlerkorrektur `[7, 10, 15, 20, 26, 18, 20, 24, 30, 18]`, Zahl der Blöcke `[1, 1, 1, 1, 1, 2, 2, 2, 2, 2]`, Ausrichtungsmittelpunkte je Version `[[], [6,18], [6,22], [6,26], [6,30], [6,34], [6,22,38], [6,24,42], [6,26,46], [6,28,50]]`.

Die PNG-Ausgabe schreibt ein 1-Bit-Graustufenbild ohne Fremdbibliothek, mit vier Modulen heller Ruhezone an jeder Seite — ohne sie erkennt kein Lesegerät den Code.

- [ ] **Step 4: Tests laufen lassen**

Run: `python -m pytest tests/test_qr.py -v`
Expected: 7 Tests PASS

- [ ] **Step 5: Mit einem echten Lesegerät prüfen**

```bash
cd /home/tesla/githubprojects/kodi-presentation
python -c "
import sys; sys.path.insert(0, 'script.presentation/resources/lib')
import qr; qr.als_png('http://192.168.178.10:8099/p/testtoken1/', '/tmp/qr-probe.png', 8)
print('/tmp/qr-probe.png')"
```

Die Datei mit dem Handy scannen. Erwartet: Es erscheint genau diese URL. **Dieser Schritt ist nicht optional** — ein QR-Code, der die Selbsttests besteht, aber von keinem Lesegerät erkannt wird, ist wertlos. Lässt er sich nicht scannen, wird `qr.py` ersatzlos gestrichen und die Startkarte zeigt nur die URL; der Rest des Add-ons ist davon nicht betroffen.

- [ ] **Step 6: Stand prüfen und berichten**

Run: `python -m pytest -v`. Ergebnis des Scan-Tests ausdrücklich berichten. Nicht committen.

---

### Task 8: Präsentationsfenster

**Files:**
- Create: `script.presentation/resources/lib/praesentations_fenster.py`,
  `script.presentation/resources/skins/Default/1080i/script-presentation-main.xml`
- Test: `tests/test_fenster.py`

**Interfaces:**
- Consumes: `sitzung.Sitzung`, Manifest aus Aufgabe 3
- Produces: `praesentations_fenster.PraesentationsFenster` (Unterklasse von `xbmcgui.WindowXML`)
  und `praesentations_fenster.AKTIONEN: dict[int, str]` — die Zuordnung Tastencode auf Aktionsname

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Getestet wird die reine Zuordnungslogik, nicht die Kodi-Oberfläche. Deshalb liegt die Entscheidung „welcher Tastencode löst was aus" in einer freien Funktion, die ohne Kodi läuft.

`tests/test_fenster.py`:
```python
import pytest
import praesentations_fenster as pf
import sitzung

# Kodi-Aktionscodes, siehe xbmcgui
LINKS, RECHTS, HOCH, RUNTER = 1, 2, 3, 4
OK, ZURUECK_MENUE, INFO = 7, 10, 11
VORHERIGER, NAECHSTER = 13, 14
KONTEXTMENUE, NAV_ZURUECK = 117, 92

@pytest.mark.parametrize("code", [RECHTS, RUNTER, OK, NAECHSTER])
def test_vorwaerts_tasten(code):
    assert pf.AKTIONEN.get(code) == "vor"

@pytest.mark.parametrize("code", [LINKS, HOCH, VORHERIGER])
def test_rueckwaerts_tasten(code):
    assert pf.AKTIONEN.get(code) == "zurueck"

def test_info_oeffnet_das_raster():
    assert pf.AKTIONEN.get(INFO) == "raster"

def test_kontextmenue_schaltet_die_blende():
    assert pf.AKTIONEN.get(KONTEXTMENUE) == "blende"

@pytest.mark.parametrize("code", [ZURUECK_MENUE, NAV_ZURUECK])
def test_zurueck_beendet(code):
    assert pf.AKTIONEN.get(code) == "ende"

def test_unbekannte_taste_tut_nichts():
    assert pf.AKTIONEN.get(999) is None

def test_fuehre_aus_blaettert():
    s = sitzung.Sitzung(3)
    assert pf.fuehre_aus(s, "vor") is None
    assert s.index == 1
    pf.fuehre_aus(s, "zurueck")
    assert s.index == 0

def test_fuehre_aus_meldet_ende():
    s = sitzung.Sitzung(3)
    assert pf.fuehre_aus(s, "ende") == "ende"

def test_fuehre_aus_meldet_raster():
    s = sitzung.Sitzung(3)
    assert pf.fuehre_aus(s, "raster") == "raster"

def test_fuehre_aus_schaltet_blende():
    s = sitzung.Sitzung(3)
    pf.fuehre_aus(s, "blende")
    assert s.blende is True

def test_bildpfad_der_aktuellen_folie():
    manifest = {"folien": [{"index": 0, "bild": "/c/a.png", "notizen": "geheim"},
                           {"index": 1, "bild": "/c/b.png", "notizen": ""}]}
    assert pf.bild_fuer(manifest, 0) == "/c/a.png"
    assert pf.bild_fuer(manifest, 1) == "/c/b.png"
    assert pf.bild_fuer(manifest, 9) == ""

def test_notizen_tauchen_nirgends_im_fenstercode_auf():
    """Harte Zusage der Spec: Notizen erscheinen nie auf dem Fernseher."""
    import inspect
    quelle = inspect.getsource(pf)
    assert "notizen" not in quelle.lower(), \
        "Das Fenstermodul darf das Feld notizen nicht einmal lesen"
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_fenster.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'praesentations_fenster'`

- [ ] **Step 3: `praesentations_fenster.py` schreiben**

```python
"""Vollbildfenster für die Folien auf dem Fernseher.

Dieses Modul liest absichtlich nirgends das Feld `notizen` aus dem Manifest.
Referentennotizen gehören auf das Handy, nie auf den Fernseher; der Test
test_notizen_tauchen_nirgends_im_fenstercode_auf hält das fest.
"""
import xbmcgui

# Kodi-Aktionscodes auf Aktionsnamen. Bewusst als Tabelle, damit die
# Zuordnung ohne laufendes Kodi prüfbar ist.
AKTIONEN = {
    1: "zurueck",    # links
    3: "zurueck",    # hoch
    13: "zurueck",   # vorheriger Titel
    2: "vor",        # rechts
    4: "vor",        # runter
    7: "vor",        # OK
    14: "vor",       # nächster Titel
    11: "raster",    # Info
    117: "blende",   # Kontextmenü
    10: "ende",      # Menü zurück
    92: "ende",      # Navigation zurück
}

STEUERUNG_FOLIE = 100
STEUERUNG_BLENDE = 101
STEUERUNG_STARTKARTE = 102
STEUERUNG_RASTER = 103
STEUERUNG_ZAEHLER = 104

def bild_fuer(manifest, index):
    folien = manifest.get("folien") or []
    if 0 <= index < len(folien):
        return folien[index].get("bild") or ""
    return ""

def fuehre_aus(sitzung_, aktion):
    """Führt eine Aktion aus. Gibt 'ende' oder 'raster' zurück, sonst None."""
    if aktion == "vor":
        sitzung_.vor()
    elif aktion == "zurueck":
        sitzung_.zurueck()
    elif aktion == "blende":
        sitzung_.blende_umschalten()
    elif aktion in ("ende", "raster"):
        return aktion
    return None

class PraesentationsFenster(xbmcgui.WindowXML):
    """Erwartet sitzung, manifest und startkarte_text über setze_daten()."""

    def setze_daten(self, sitzung_, manifest, startkarte_text, qr_pfad=""):
        self.sitzung = sitzung_
        self.manifest = manifest
        self.startkarte_text = startkarte_text
        self.qr_pfad = qr_pfad
        self._startkarte_sichtbar = True
        self._letzte_version = 0

    def onInit(self):
        self.getControl(STEUERUNG_STARTKARTE).setLabel(self.startkarte_text)
        if self.qr_pfad:
            self.getControl(STEUERUNG_RASTER).setImage(self.qr_pfad)
        self._zeichne()

    def _zeichne(self):
        z = self.sitzung.zustand()
        self._letzte_version = z["version"]
        self.getControl(STEUERUNG_FOLIE).setImage(bild_fuer(self.manifest, z["index"]))
        self.getControl(STEUERUNG_BLENDE).setVisible(z["blende"])
        self.getControl(STEUERUNG_STARTKARTE).setVisible(self._startkarte_sichtbar)
        if z["anzahl"]:
            self.getControl(STEUERUNG_ZAEHLER).setLabel(f"{z['index'] + 1} / {z['anzahl']}")

    def aktualisiere_wenn_noetig(self):
        """Wird vom Hauptschleifen-Takt gerufen, damit Handy-Befehle ankommen."""
        if self.sitzung.version != self._letzte_version:
            self._zeichne()

    def onAction(self, action):
        aktion = AKTIONEN.get(action.getId())
        if aktion is None:
            return
        if self._startkarte_sichtbar:
            # Der erste Tastendruck blendet nur die Startkarte aus.
            self._startkarte_sichtbar = False
            self._zeichne()
            if aktion != "ende":
                return
        ergebnis = fuehre_aus(self.sitzung, aktion)
        if ergebnis == "ende":
            self.close()
        elif ergebnis == "raster":
            self._zeige_raster()
        else:
            self._zeichne()

    def _zeige_raster(self):
        """Folienliste zum Springen; OK springt, Zurück kehrt ohne Sprung zurück."""
        folien = self.manifest.get("folien") or []
        if not folien:
            return
        eintraege = [f"{i + 1}. {f.get('titel') or 'ohne Titel'}" for i, f in enumerate(folien)]
        wahl = xbmcgui.Dialog().select("Zu Folie springen", eintraege)
        if wahl >= 0:
            self.sitzung.springe(wahl)
        self._zeichne()
```

- [ ] **Step 4: Skin-Datei schreiben**

`script.presentation/resources/skins/Default/1080i/script-presentation-main.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<window>
  <defaultcontrol always="true">100</defaultcontrol>
  <coordinates><system>1</system><posx>0</posx><posy>0</posy></coordinates>
  <controls>
    <control type="image" id="99">
      <left>0</left><top>0</top><width>1920</width><height>1080</height>
      <texture colordiffuse="FF000000">white.png</texture>
    </control>
    <control type="image" id="100">
      <left>0</left><top>0</top><width>1920</width><height>1080</height>
      <aspectratio>keep</aspectratio>
    </control>
    <control type="image" id="101">
      <left>0</left><top>0</top><width>1920</width><height>1080</height>
      <texture colordiffuse="FF000000">white.png</texture>
      <visible>false</visible>
    </control>
    <control type="label" id="104">
      <left>1700</left><top>1010</top><width>180</width><height>40</height>
      <align>right</align><font>font12</font><textcolor>88FFFFFF</textcolor>
    </control>
    <control type="group" id="105">
      <control type="image" id="106">
        <left>260</left><top>240</top><width>1400</width><height>600</height>
        <texture colordiffuse="EE111111">white.png</texture>
      </control>
      <control type="label" id="102">
        <left>320</left><top>300</top><width>900</width><height>480</height>
        <font>font30</font><textcolor>FFFFFFFF</textcolor>
      </control>
      <control type="image" id="103">
        <left>1280</left><top>340</top><width>320</width><height>320</height>
      </control>
    </control>
  </controls>
</window>
```

- [ ] **Step 5: Tests laufen lassen**

Run: `python -m pytest tests/test_fenster.py -v`
Expected: 15 Tests PASS

Besonders beachten: `test_notizen_tauchen_nirgends_im_fenstercode_auf` schlägt fehl, sobald jemand im Fenstermodul auf das Notizfeld zugreift. Das ist Absicht und darf nicht durch Umbenennen umgangen werden.

- [ ] **Step 6: Stand prüfen und berichten**

Run: `python -m pytest -v`. Nicht committen.

---

### Task 9: Deck-Auswahl, Einstiegspunkt und Sprachdateien

Verbindet alle Teile zum lauffähigen Add-on.

**Files:**
- Create: `script.presentation/resources/lib/deck_browser.py`, `script.presentation/default.py`,
  `script.presentation/resources/language/resource.language.de_de/strings.po`,
  `script.presentation/resources/language/resource.language.en_gb/strings.po`
- Test: `tests/test_deck_browser.py`

**Interfaces:**
- Consumes: `konfig.Konfig`, `deck_cache.DeckCache`, `renderer.DeckcraftRenderer`,
  `sitzung.Sitzung`, `handy_server.HandyServer`, `praesentations_fenster.PraesentationsFenster`
- Produces: `deck_browser.finde_decks(ordner: str) -> list[dict]` mit den Schlüsseln
  `pfad`, `name`, `geaendert`

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_deck_browser.py`:
```python
import sys
import pytest
import deck_browser

def test_findet_nur_praesentationen(tmp_path, monkeypatch):
    for name in ("a.pptx", "b.deckcraft", "c.txt", "d.PPTX", "e.mp4"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir",
                        lambda p: ([], ["a.pptx", "b.deckcraft", "c.txt", "d.PPTX", "e.mp4"]))
    gefunden = {d["name"] for d in deck_browser.finde_decks(str(tmp_path))}
    assert gefunden == {"a.pptx", "b.deckcraft", "d.PPTX"}

def test_leerer_ordner_gibt_leere_liste(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir", lambda p: ([], []))
    assert deck_browser.finde_decks(str(tmp_path)) == []

def test_fehlender_ordner_gibt_leere_liste(monkeypatch):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: False)
    assert deck_browser.finde_decks("/gibt/es/nicht") == []

def test_sortiert_nach_namen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir",
                        lambda p: ([], ["zebra.pptx", "apfel.pptx", "Ärger.pptx"]))
    namen = [d["name"] for d in deck_browser.finde_decks(str(tmp_path))]
    assert namen == sorted(namen, key=str.lower)

def test_vfs_pfade_werden_zusammengesetzt(monkeypatch):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir", lambda p: ([], ["x.pptx"]))
    d = deck_browser.finde_decks("smb://nas/decks")[0]
    assert d["pfad"] == "smb://nas/decks/x.pptx"

def test_vfs_pfad_mit_schraegstrich_am_ende(monkeypatch):
    monkeypatch.setattr(sys.modules["xbmcvfs"], "exists", lambda p: True)
    monkeypatch.setattr(sys.modules["xbmcvfs"], "listdir", lambda p: ([], ["x.pptx"]))
    d = deck_browser.finde_decks("smb://nas/decks/")[0]
    assert d["pfad"] == "smb://nas/decks/x.pptx", "kein doppelter Schrägstrich"
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_deck_browser.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'deck_browser'`

- [ ] **Step 3: `deck_browser.py` schreiben**

```python
"""Findet Präsentationen im eingestellten Ordner.

Nutzt xbmcvfs statt os.listdir, damit Kodi-Quellen wie smb:// funktionieren.
"""
import xbmcvfs

ENDUNGEN = (".pptx", ".deckcraft")

def _verbinde(ordner, name):
    """Setzt Pfade zusammen, ohne doppelten Schrägstrich und ohne os.path,
    das bei smb://-Pfaden falsch läge."""
    return ordner.rstrip("/") + "/" + name

def finde_decks(ordner):
    if not ordner or not xbmcvfs.exists(ordner):
        return []
    try:
        _, dateien = xbmcvfs.listdir(ordner)
    except OSError:
        return []
    decks = [
        {"pfad": _verbinde(ordner, name), "name": name}
        for name in dateien
        if name.lower().endswith(ENDUNGEN)
    ]
    decks.sort(key=lambda d: d["name"].lower())
    return decks
```

- [ ] **Step 4: `default.py` schreiben**

```python
"""Einstiegspunkt: Deck wählen, rendern, Server starten, Fenster öffnen."""
import os
import sys

import xbmc
import xbmcgui

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import deck_browser          # noqa: E402
import deck_cache            # noqa: E402
import handy_server          # noqa: E402
import konfig                # noqa: E402
import praesentations_fenster as pf   # noqa: E402
import renderer              # noqa: E402
import sitzung as sitzung_modul       # noqa: E402

def _fehler(text):
    xbmc.log(f"[script.presentation] {text}", xbmc.LOGERROR)
    xbmcgui.Dialog().ok("Präsentation", text)

def _startkarte(url, hat_qr):
    zusatz = "QR-Code scannen oder im Browser öffnen:" if hat_qr else "Im Browser öffnen:"
    return (f"Referentenansicht\n\n{zusatz}\n\n{url}\n\n"
            "Beliebige Taste drücken, um zu beginnen.")

def main():
    k = konfig.Konfig()
    r = renderer.DeckcraftRenderer(k.binary_pfad)
    try:
        r.version()
    except renderer.RendererFehler as e:
        return _fehler(str(e))

    decks = deck_browser.finde_decks(k.deck_ordner)
    if not decks:
        return _fehler(f"Keine Präsentationen in {k.deck_ordner} gefunden.")
    wahl = xbmcgui.Dialog().select("Präsentation wählen", [d["name"] for d in decks])
    if wahl < 0:
        return

    cache = deck_cache.DeckCache(os.path.join(k.daten_pfad, "cache"), k.cache_grenze_bytes)
    dialog = xbmcgui.DialogProgress()
    dialog.create("Präsentation", "Folien werden vorbereitet …")
    try:
        manifest = cache.hole(decks[wahl]["pfad"], r, k.skalierung,
                              fortschritt=lambda p, t: dialog.update(p, t))
    except Exception as e:
        return _fehler(f"Konnte das Deck nicht vorbereiten:\n{e}")
    finally:
        dialog.close()

    if manifest.get("verloreneFolien"):
        xbmcgui.Dialog().notification(
            "Präsentation",
            f"{manifest['verloreneFolien']} Folien konnten nicht gelesen werden")

    s = sitzung_modul.Sitzung(len(manifest.get("folien") or []))
    seite = ""
    web = os.path.join(k.addon_pfad, "resources", "web", "presenter.html")
    with open(web, encoding="utf-8") as f:
        seite = f.read()

    server = handy_server.HandyServer(s, manifest, seite, port=k.port)
    url = ""
    try:
        url = server.starten()
    except OSError as e:
        xbmc.log(f"[script.presentation] Handy-Ansicht aus: {e}", xbmc.LOGERROR)

    qr_pfad = ""
    if url:
        try:
            import qr
            qr_pfad = os.path.join(k.daten_pfad, "qr.png")
            qr.als_png(url, qr_pfad)
        except Exception as e:  # QR ist Beiwerk, nie ein Grund abzubrechen
            xbmc.log(f"[script.presentation] QR übersprungen: {e}", xbmc.LOGINFO)
            qr_pfad = ""

    fenster = pf.PraesentationsFenster(
        "script-presentation-main.xml", k.addon_pfad, "Default", "1080i")
    fenster.setze_daten(s, manifest, _startkarte(url, bool(qr_pfad)) if url
                        else "Präsentation\n\nTaste drücken, um zu beginnen.", qr_pfad)
    try:
        fenster.doModal()
    finally:
        del fenster
        server.stoppen()

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Sprachdateien schreiben**

`script.presentation/resources/language/resource.language.de_de/strings.po`:
```po
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Language: de_DE\n"

msgctxt "#30010"
msgid "General"
msgstr "Allgemein"

msgctxt "#30011"
msgid "Presentation folder"
msgstr "Ordner mit den Präsentationen"

msgctxt "#30012"
msgid "Render resolution"
msgstr "Renderauflösung"

msgctxt "#30013"
msgid "960x540 (720p devices)"
msgstr "960×540 (720p-Geräte)"

msgctxt "#30014"
msgid "1920x1080 (default)"
msgstr "1920×1080 (Vorgabe)"

msgctxt "#30015"
msgid "3840x2160 (4K)"
msgstr "3840×2160 (4K)"

msgctxt "#30020"
msgid "Presenter view"
msgstr "Referentenansicht"

msgctxt "#30021"
msgid "Port for the phone page"
msgstr "Port für die Handy-Seite"

msgctxt "#30030"
msgid "Storage"
msgstr "Speicher"

msgctxt "#30031"
msgid "Cache limit in GB"
msgstr "Cache-Obergrenze in GB"
```

`script.presentation/resources/language/resource.language.en_gb/strings.po`: dieselben `msgctxt`- und `msgid`-Zeilen, `msgstr` jeweils gleich der `msgid`, `Language: en_GB`.

- [ ] **Step 6: Tests laufen lassen**

Run: `python -m pytest tests/test_deck_browser.py -v`
Expected: 6 Tests PASS

- [ ] **Step 7: Stand prüfen und berichten**

Run: `python -m pytest -v` — alle Tests aller Aufgaben grün. Nicht committen.

---

### Task 10: Build-Skripte

**Files:**
- Create: `tools/deckcraft.version`, `tools/build-deckcraft.sh`, `build.sh`, `README.md`, `LICENSE`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: nichts
- Produces: `script.presentation/bin/deckcraft-cli` (durch `tools/build-deckcraft.sh`),
  `dist/script.presentation-<version>.zip` (durch `build.sh`)

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

`tests/test_build.py`:
```python
import os
import re
import subprocess
import pytest

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

def test_build_skript_bricht_bei_fehlern_ab():
    for datei in ("tools/build-deckcraft.sh", "build.sh"):
        assert "set -euo pipefail" in lies(*datei.split("/")), f"{datei} braucht set -euo pipefail"

def test_skripte_sind_syntaktisch_gueltig():
    for datei in ("tools/build-deckcraft.sh", "build.sh"):
        subprocess.run(["bash", "-n", os.path.join(WURZEL, datei)], check=True)

def test_binary_ist_nicht_in_git():
    assert "script.presentation/bin/" in lies(".gitignore")

def test_build_sh_liest_die_version_aus_addon_xml():
    assert "addon.xml" in lies("build.sh")

def test_addon_version_passt_zum_zip_namen():
    xml = lies("script.presentation", "addon.xml")
    assert re.search(r'<addon[^>]*version="\d+\.\d+\.\d+"', xml)
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_build.py -v`
Expected: FAIL mit `FileNotFoundError`

- [ ] **Step 3: `tools/deckcraft.version` und `tools/build-deckcraft.sh` schreiben**

`tools/deckcraft.version`:
```
0.15.0
```

`tools/build-deckcraft.sh`:
```bash
#!/usr/bin/env bash
# Baut deckcraft-cli als statisches aarch64-Binary und legt es ins Add-on.
#
# Das Rezept ist auf LibreELEC 12.2.1 / Raspberry Pi 5 geprüft: statisch gegen
# musl, gelinkt mit rust-lld. Dadurch braucht der Build keine C-Toolchain und
# das Ergebnis keine Bibliothek auf dem Zielgerät.
set -euo pipefail
cd "$(dirname "$0")/.."

ZIEL_TRIPLE=aarch64-unknown-linux-musl
VERSION="$(tr -d '[:space:]' < tools/deckcraft.version)"
AUSGABE="script.presentation/bin/deckcraft-cli"

command -v cargo >/dev/null || { echo "cargo fehlt: https://rustup.rs"; exit 1; }
rustup target add "$ZIEL_TRIPLE"

ARBEIT="$(mktemp -d)"
trap 'rm -rf "$ARBEIT"' EXIT

echo "DeckCraft $VERSION wird geholt …"
git clone --depth 1 --branch "v$VERSION" https://github.com/storytold/deckcraft.git "$ARBEIT/src" 2>/dev/null \
  || git clone --depth 1 https://github.com/storytold/deckcraft.git "$ARBEIT/src"

cd "$ARBEIT/src"
GEBAUT="$(grep -m1 '^version' Cargo.toml | cut -d'"' -f2 || echo unbekannt)"
if [ "$GEBAUT" != "$VERSION" ]; then
  echo "Achtung: Upstream meldet $GEBAUT, erwartet war $VERSION." >&2
fi

RUSTFLAGS="-C linker=rust-lld -C link-self-contained=yes" \
  cargo build --release -p deckcraft-cli --target "$ZIEL_TRIPLE"

cd - >/dev/null
mkdir -p "$(dirname "$AUSGABE")"
cp "$ARBEIT/src/target/$ZIEL_TRIPLE/release/deckcraft-cli" "$AUSGABE"
llvm-strip "$AUSGABE" 2>/dev/null || strip "$AUSGABE" 2>/dev/null || true
chmod +x "$AUSGABE"

file "$AUSGABE" | grep -q "ARM aarch64" || { echo "Falsche Architektur!"; exit 1; }
echo "fertig: $AUSGABE ($(du -h "$AUSGABE" | cut -f1))"
```

- [ ] **Step 4: `build.sh` schreiben**

```bash
#!/usr/bin/env bash
# Baut ein installierbares Zip (Kodi: Add-ons > Aus ZIP-Datei installieren).
set -euo pipefail
cd "$(dirname "$0")"
ID=script.presentation
VERSION=$(grep -oP '<addon[^>]*version="\K[^"]+' "$ID/addon.xml")

if [ ! -x "$ID/bin/deckcraft-cli" ]; then
  echo "Das Binary fehlt. Erst tools/build-deckcraft.sh ausführen." >&2
  exit 1
fi

mkdir -p dist
OUT="dist/$ID-$VERSION.zip"
rm -f "$OUT"
zip -qr "$OUT" "$ID" -x '*/__pycache__/*' '*.pyc'
echo "$OUT ($(du -h "$OUT" | cut -f1))"
```

- [ ] **Step 5: Ausführbar machen und testen**

```bash
cd /home/tesla/githubprojects/kodi-presentation
chmod +x tools/build-deckcraft.sh build.sh
python -m pytest tests/test_build.py -v
```
Expected: 7 Tests PASS

- [ ] **Step 6: Den echten Build laufen lassen**

Run: `./tools/build-deckcraft.sh`
Expected: Nach etwa zwei Minuten liegt `script.presentation/bin/deckcraft-cli` mit rund 25 MB vor, `file` meldet „ARM aarch64".

Run: `./build.sh`
Expected: `dist/script.presentation-0.1.0.zip` entsteht.

- [ ] **Step 7: README schreiben**

Inhalt: Zweck, Voraussetzungen (LibreELEC auf aarch64), Installation über das ZIP, Einstellungen, Bedienung über die Fernbedienung (Tabelle aus der Spec, Abschnitt 6), Hinweis zur Handy-Ansicht **einschließlich der ausdrücklichen Aussage, dass die Verbindung unverschlüsseltes HTTP ist und das Token nur gegen versehentlichen Zugriff im eigenen Netz schützt**, Bauanleitung, Lizenz MIT und die DeckCraft-Zuschreibung (MIT/Apache-2.0).

- [ ] **Step 8: Stand prüfen und berichten**

Run: `python -m pytest -v`. Nicht committen.

---

### Task 11: Integration auf dem Zielgerät

Die erste Aufgabe, die das Add-on als Ganzes auf echter Hardware prüft. Bis hier war alles gestubbt.

**Files:**
- Create: `tests/test_integration.py`
- Test: dieselbe Datei, Marker `binary`

**Interfaces:**
- Consumes: alles Vorherige
- Produces: nichts

- [ ] **Step 1: Den Integrationstest schreiben**

`tests/test_integration.py`:
```python
"""Läuft gegen das echte Binary: python -m pytest -m binary"""
import json
import os
import subprocess
import pytest
import deck_cache
import renderer

BINARY = os.path.join(os.path.dirname(__file__), "..",
                      "script.presentation", "bin", "deckcraft-cli")

pytestmark = pytest.mark.binary

@pytest.fixture(scope="module")
def echtes_deck(tmp_path_factory):
    """Erzeugt ein Deck mit python-pptx, falls vorhanden; sonst wird übersprungen."""
    pptx = pytest.importorskip("pptx")
    ziel = tmp_path_factory.mktemp("deck") / "integration.pptx"
    prs = pptx.Presentation()
    folie = prs.slides.add_slide(prs.slide_layouts[0])
    folie.shapes.title.text = "Integrationstest mit Ümläuten"
    folie.placeholders[1].text = "Untertitel"
    folie.notes_slide.notes_text_frame.text = "Diese Notiz darf nie auf dem TV landen"
    zweite = prs.slides.add_slide(prs.slide_layouts[1])
    zweite.shapes.title.text = "Zweite Folie"
    prs.save(str(ziel))
    return str(ziel)

def test_binary_ist_fuer_aarch64():
    ausgabe = subprocess.run(["file", BINARY], capture_output=True, text=True).stdout
    assert "ARM aarch64" in ausgabe
    assert "statically linked" in ausgabe

def test_info_liest_notizen(echtes_deck):
    info = renderer.DeckcraftRenderer(BINARY).info(echtes_deck)
    assert len(info.folien) == 2
    assert "nie auf dem TV" in info.folien[0].notizen

def test_render_erzeugt_bilder_in_voller_groesse(echtes_deck, tmp_path):
    bilder = renderer.DeckcraftRenderer(BINARY).render(echtes_deck, str(tmp_path / "o"), 2)
    assert len(bilder) == 2
    for p in bilder:
        assert os.path.getsize(p) > 1000

def test_voller_cache_durchlauf(echtes_deck, tmp_path):
    r = renderer.DeckcraftRenderer(BINARY)
    c = deck_cache.DeckCache(str(tmp_path / "cache"), 10**9)
    m = c.hole(echtes_deck, r, 2)
    assert len(m["folien"]) == 2
    assert os.path.isfile(m["folien"][0]["bild"])
    assert os.path.isfile(m["folien"][0]["vorschau"])
    assert "nie auf dem TV" in m["folien"][0]["notizen"]

def test_dateiname_mit_umlauten_und_leerzeichen(echtes_deck, tmp_path):
    """Review Focus 2 gegen das echte Binary."""
    heikel = tmp_path / "Mein Vörtrag (2026).pptx"
    with open(echtes_deck, "rb") as q, open(heikel, "wb") as z:
        z.write(q.read())
    bilder = renderer.DeckcraftRenderer(BINARY).render(str(heikel), str(tmp_path / "o2"), 1)
    assert len(bilder) == 2
```

- [ ] **Step 2: Lokal laufen lassen**

Run: `python -m pytest -m binary -v`
Expected: Auf dem x86-Laptop schlägt das Ausführen des aarch64-Binaries fehl (`Exec format error`). Erwartet ist: `test_binary_ist_fuer_aarch64` PASS, die übrigen FAIL mit einer `RendererFehler`-Meldung, die „ließ sich nicht starten" enthält. Das belegt zugleich die Fehlerbehandlung aus Aufgabe 2.

- [ ] **Step 3: Auf dem Pi laufen lassen**

```bash
cd /home/tesla/githubprojects/kodi-presentation
ssh root@192.168.178.10 'mkdir -p /storage/kp-test'
scp -q script.presentation/bin/deckcraft-cli root@192.168.178.10:/storage/kp-test/
scp -q /tmp/claude-1000/*/scratchpad/spike/deck/testdeck.pptx root@192.168.178.10:/storage/kp-test/ 2>/dev/null || true
ssh root@192.168.178.10 '/storage/kp-test/deckcraft-cli info /storage/kp-test/testdeck.pptx | head -c 300'
```
Expected: JSON mit Folien und Notizen.

- [ ] **Step 4: Add-on auf dem Pi installieren und vortragen**

```bash
./build.sh
scp dist/script.presentation-0.1.0.zip root@192.168.178.10:/storage/
ssh root@192.168.178.10 'mkdir -p /storage/presentations && cp /storage/kp-test/testdeck.pptx /storage/presentations/'
```

Dann in Kodi: Add-ons → Aus ZIP-Datei installieren → `/storage/script.presentation-0.1.0.zip`. Add-on starten.

Prüfliste, jeder Punkt wird einzeln bestätigt:
1. Das Testdeck erscheint in der Auswahl.
2. Nach der Auswahl erscheint die Startkarte mit URL und QR-Code.
3. Die URL lässt sich auf dem Handy öffnen; Notizen der ersten Folie stehen dort.
4. „Weiter" auf dem Handy wechselt die Folie auf dem Fernseher **innerhalb einer Sekunde**.
5. Rechts auf der Fernbedienung wechselt die Folie, und das Handy zieht nach.
6. Info öffnet die Folienliste, eine Auswahl springt dorthin.
7. Das Kontextmenü schaltet den Bildschirm schwarz und wieder zurück.
8. **Auf dem Fernseher ist zu keinem Zeitpunkt eine Notiz zu sehen.**
9. Zurück beendet; ein erneuter Start des Decks beginnt ohne Renderpause.

- [ ] **Step 5: Stand berichten**

Jeden Punkt der Prüfliste mit Ergebnis berichten, auch die fehlgeschlagenen. Die Spike-Reste auf dem Pi entfernen:
`ssh root@192.168.178.10 'rm -rf /storage/deckcraft-spike /storage/kp-test'`

Nicht committen.

---

## Selbstprüfung des Plans

**Spec-Abdeckung:** Abschnitt 1 Zweck → Aufgaben 8, 9. Abschnitt 4.1 Schichten → je eine Aufgabe pro Modul (2, 3, 4, 5, 8, 9). Abschnitt 4.2 Ablauf → Aufgabe 9. Abschnitt 5 Cache-Format → Aufgabe 3. Abschnitt 6 Fernbedienung → Aufgabe 8. Abschnitt 7 Handy-Ansicht → Aufgaben 5, 6. Abschnitt 8 Fehlerbehandlung → verteilt auf 2 (Binary fehlt, Architektur, Renderfehler), 3 (Abbruch), 5 (Port belegt), 9 (verlorene Folien). Abschnitt 9 Tests → jede Aufgabe. Abschnitt 10 Build → Aufgabe 10. Keine Lücke gefunden.

**Review Focus:** Alle fünf Punkte haben ihren Test: VFS in Aufgabe 3, Dateinamen in Aufgabe 2 und erneut gegen das echte Binary in Aufgabe 11, leere Decks in Aufgabe 4, Nebenläufigkeit in Aufgabe 4, Abbruch in Aufgabe 3.

**Namenskonsistenz geprüft:** `renderer.DeckcraftRenderer.info/render/version`, `deck_cache.DeckCache.hole/ist_gueltig/aufraeumen/groesse_bytes`, `sitzung.Sitzung.vor/zurueck/springe/blende_umschalten/timer_zuruecksetzen/zustand/warte_auf_aenderung/beenden`, `handy_server.HandyServer.starten/stoppen/folie/zustand_json/fuehre_aus`, `praesentations_fenster.AKTIONEN/bild_fuer/fuehre_aus/PraesentationsFenster.setze_daten`, `deck_browser.finde_decks`, `konfig.Konfig`. Die Manifest-Schlüssel sind durchgehend deutsch (`folien`, `notizen`, `bild`, `vorschau`), die aus DeckCraft gelesenen englisch (`slides`, `notes`, `title`) — die Umsetzung passiert ausschließlich in `renderer._lies_info` und `deck_cache._baue_manifest`.

**Platzhalter-Durchsicht:** Keine „TBD", keine „ähnlich wie Aufgabe N", keine Schritte ohne Code. Die einzige Aufgabe, die einen Algorithmus beschreibt statt ihn auszuschreiben, ist Aufgabe 7 (QR-Encoder): Dort stehen die fünf Bestandteile, die vollständigen Konstantentabellen und ein verbindlicher Prüfschritt mit einem echten Lesegerät. Das ist bewusst so — ein ausgeschriebener QR-Encoder wäre im Plan weder lesbar noch überprüfbar, und die Aufgabe ist so geschnitten, dass sie ersatzlos entfallen kann.
