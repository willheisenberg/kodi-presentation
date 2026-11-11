# kodi-presentation — Entwurf

Stand: 2026-11-10 · Status: zur Abnahme

## 1. Zweck

Ein Kodi-Add-on, mit dem auf einem LibreELEC-Gerät Präsentationen vorgetragen
werden. Die `.pptx` liegt auf dem Gerät, das Add-on rendert sie dort selbst und
zeigt die Folien im Vollbild auf dem Fernseher. Der Vortragende steuert per
Fernbedienung und sieht Referentennotizen, nächste Folie und Timer auf dem
eigenen Handy.

**Zielsituation:** Jemand steht vor dem Fernseher und hält einen Vortrag. Das
Publikum sieht ausschließlich die Folie. Niemand muss einen Laptop anschließen.

**Erfolgskriterien:**

1. Eine `.pptx` in den Präsentationsordner legen, Add-on starten, vortragen —
   ohne Vorbereitungsschritt an einem anderen Rechner.
2. Referentennotizen erscheinen auf dem Handy und **niemals** auf dem Fernseher.
3. Folienwechsel per Fernbedienung ohne wahrnehmbare Verzögerung.
4. Das Add-on läuft eigenständig: keine Netzwerkdienste, keine Container, keine
   Bibliotheken, die auf LibreELEC nachinstalliert werden müssten.

## 2. Nicht-Ziele

- **Bearbeiten** von Präsentationen. Das Add-on zeigt nur an.
- **Folienübergänge und Animationen.** Version 1 schneidet hart. Begründung in
  Abschnitt 11.
- **Referentenansicht auf einem zweiten Bildschirm.** Kodi auf LibreELEC bedient
  nur einen Ausgang; der zweite Schirm ist das Handy.
- **PDF als Eingabeformat.** PDFs transportieren keine Notizen und machen die
  Handy-Ansicht wertlos.
- **Dauerschleife / Digital Signage.** Bewusst verworfen, um die erste Version
  auf die Vortragssituation zu fokussieren.

## 3. Gemessene Grundlage

Alle Zahlen stammen aus einer Probe vom 2026-11-09 auf dem Zielgerät
(Raspberry Pi 5, LibreELEC 12.2.1, aarch64, Kodi 21, Python 3.11.13):

| Messung | Ergebnis |
|---|---|
| `deckcraft-cli`, statisch gegen musl, aarch64 | 24,9 MB, keine Systembibliothek nötig |
| Buildzeit (Cross-Compile, 176 Crates) | 1 min 40 s |
| 5 Folien nach 1920×1080 rendern | 0,1 s gesamt |
| Deck öffnen / alle Folien zeichnen (Median) | 9,8 ms / 16,0 ms |
| Spitzenspeicher | 124 MiB |
| Notizen über `deckcraft-cli info` | vollständig, Umlaute korrekt |
| Schriftdarstellung ohne Systemschriften | korrekt, DeckCraft bringt eigene mit |

Entscheidend für die Architektur: `deckcraft-render` benutzt `vello_cpu`, einen
reinen CPU-Rasterizer. Kein Vulkan, kein X11, keine GPU. Die Hinweise auf
Vulkan und ALSA im DeckCraft-README betreffen nur die Desktop-App, nicht die
CLI. Der Abhängigkeitsbaum von `deckcraft-cli` umfasst 176 Crates, davon keines
mit C-Anteil außer `zlib-rs`, das reines Rust ist.

## 4. Architektur

Ein einzelnes Script-Add-on, ein Prozess, kein Hintergrunddienst. Der
HTTP-Server für die Handy-Ansicht läuft als Thread innerhalb der laufenden
Präsentation — gestartet beim Öffnen des Decks, beendet beim Verlassen. Damit
entfällt jede Kommunikation zwischen getrennten Prozessen.

```
         ┌──────────────────────── script.presentation ───────────────────────┐
         │                                                                    │
  .pptx ─┼─→ renderer.py ──→ deck_cache.py ──→ deck.json + slide-NN.png       │
         │   (Binary-Wrapper)                       │                         │
         │                                          ├──→ presenter_window.py  │ ──→ TV
         │                                          │    (WindowXML, Vollbild)│
         │                                   session.py                       │
         │                              (Zustand: Index, Timer,               │
         │                               Schwarzblende, Version)              │
         │                                          │                         │
         │                                          └──→ phone_server.py      │ ──→ Handy
         │                                               (HTTP-Thread)        │
         └────────────────────────────────────────────────────────────────────┘
```

### 4.1 Schichten

**`renderer.py` — Renderer-Schnittstelle.** Abstrahiert das Rendern hinter zwei
Methoden: `info(pfad) -> DeckInfo` und `render(pfad, zielordner, skalierung)
-> list[Path]`. Die einzige Implementierung ist `DeckcraftRenderer`, die das
mitgelieferte Binary aufruft. Die Schnittstelle existiert, weil DeckCraft Alpha
ist: sollte sich die Wiedergabetreue bei echten Decks als unzureichend
erweisen, wird ein anderes Backend eingehängt, ohne dass Fenster oder
Handy-Ansicht angefasst werden.

**`deck_cache.py` — Cache.** Schlüssel ist ein Hash aus absolutem Pfad,
Änderungszeit und Dateigröße. Ein bereits gerendertes Deck startet sofort.
Liegt kein Treffer vor, wird gerendert; bei 20 ms pro Folie genügt ein
Fortschrittsdialog ohne Hintergrundprozess. Der Cache liegt unter
`<addon_data>/cache/<hash>/` und wird nach konfigurierbarer Obergrenze
(Vorgabe 2 GB) nach ältestem Zugriff aufgeräumt.

**`session.py` — Zustand.** Hält Folienindex, Startzeit des Timers,
Schwarzblende und einen Versionszähler. Fenster und HTTP-Thread greifen darauf
zu; jede Änderung erhöht die Version und weckt wartende Anfragen. Einziger
geteilter Zustand, bewusst klein und unter einem Lock.

**`praesentations_fenster.py` — TV-Ausgabe.** `xbmcgui.WindowXML` im Vollbild mit
einem Bildelement, einem Folienraster zum Springen und einer Schwarzblende.
Kodis eigene Diashow wird nicht benutzt: sie lässt weder eigene Tastenbelegung
noch Raster noch Blende zu.

Das Fenster zeigt **ausschließlich Bilder** — Folie, QR-Startkarte, Schwarzblende.
Am Gerät hat sich gezeigt, dass Kodi in einem Add-on-Fenster keine Textelemente
zeichnet (Label und Textbox bleiben unsichtbar, mit und ohne Schriftangabe),
Bilder dagegen zuverlässig. Alles Geschriebene gehört ohnehin auf das Handy;
die Startkarte trägt deshalb nur den QR-Code, und die URL erscheint davor als
gewöhnlicher Kodi-Dialog.

**`phone_server.py` — Handy-Ansicht.** `ThreadingHTTPServer` aus der
Standardbibliothek, gebunden an alle Schnittstellen, Port konfigurierbar
(Vorgabe 8099). Liefert eine einzelne HTML-Seite ohne Fremdbibliotheken, dazu
Zustand als JSON und Folienvorschauen als JPEG.

**`deck_browser.py` — Auswahl.** Listet `.pptx` und `.deckcraft` aus dem
konfigurierten Ordner (Vorgabe `/storage/presentations`; Netzwerkfreigaben
funktionieren, da Kodi sie einhängt) und zeigt sie mit Titel, Folienzahl und
Änderungsdatum zur Auswahl.

### 4.2 Ablauf

1. Benutzer startet das Add-on → `deck_browser` listet Decks.
2. Deck gewählt → `deck_cache` prüft Treffer. Bei Fehltreffer: `renderer.info()`
   für Metadaten, `renderer.render()` zweimal — einmal für den TV, einmal in
   480×270 als Vorschau fürs Handy. Beides zusammen unter einer Sekunde für
   übliche Decks.

   Die TV-Auflösung ergibt sich aus `--scale`: DeckCraft rechnet in Punkten auf
   einer 960×540-Folie, `--scale 2` ergibt also 1920×1080. Vorgabe ist 2;
   in den Einstellungen wählbar sind 1 (720p-Geräte), 2 (Vorgabe) und 4 (4K).
   Höher als die Ausgabeauflösung zu rendern kostet nur Platz, nicht Schärfe.
3. `session` wird angelegt, `phone_server` startet, `presenter_window` öffnet.
4. Ein Dialog nennt die URL der Referentenansicht. Nach dem Bestätigen öffnet
   das Fenster mit der ersten Folie und der QR-Startkarte darüber; sie
   verschwindet beim ersten Tastendruck.
5. Vor- und Zurückblättern setzt den Index in `session`; Fenster und Handy
   ziehen nach.
6. Verlassen → Fenster schließt, HTTP-Server wird beendet, Cache bleibt.

## 5. Datenformat des Cache

`deck.json` je Deck:

```json
{
  "quelle": "/storage/presentations/vortrag.pptx",
  "hash": "a3f2…",
  "gerendert": "2026-11-10T20:14:03",
  "folienGroesse": [960.0, 540.0],
  "breite": 1920,
  "hoehe": 1080,
  "folien": [
    {
      "index": 0,
      "titel": "Präsentationen auf dem Fernseher",
      "notizen": "Begrüßung. Kurz sagen, worum es geht…",
      "bild": "slide-01.png",
      "vorschau": "thumb-01.jpg"
    }
  ]
}
```

Die Felder `titel` und `notizen` stammen unverändert aus `deckcraft-cli info`.
Folien ohne Notiz bekommen einen leeren String, nicht `null`.

## 6. Bedienung über die Fernbedienung

| Aktion | Tasten |
|---|---|
| Nächste Folie | Rechts, Runter, OK, Nächster Titel |
| Vorherige Folie | Links, Hoch, Vorheriger Titel |
| Folienraster | Info |
| Schwarzblende an/aus | Kontextmenü |
| Beenden | Zurück |

Das Raster zeigt alle Folien als Kacheln; OK springt zur gewählten Folie,
Zurück kehrt ohne Sprung zurück. Gewählt wurde das Kontextmenü für die
Schwarzblende, weil es auf praktisch jeder Fernbedienung und jeder CEC-Belegung
vorhanden ist.

## 7. Handy-Ansicht

### 7.1 Schnittstelle

Alle Pfade tragen das Sitzungstoken:

| Pfad | Zweck |
|---|---|
| `GET /p/<token>/` | HTML-Seite, einmal geladen |
| `GET /p/<token>/state?seit=<version>` | Zustand als JSON; hält die Verbindung bis zu 25 s offen, bis sich die Version ändert (Long Poll) |
| `POST /p/<token>/cmd` | `{"aktion": "vor"\|"zurueck"\|"springe"\|"blende"\|"timer"}` |
| `GET /p/<token>/thumb/<n>.jpg` | Vorschaubild der Folie `n` |

Long Poll statt Polling im Sekundentakt: der Folienwechsel erscheint ohne
spürbare Verzögerung auf dem Handy, ohne dass dauernd Anfragen laufen.

### 7.2 Seite

Oben die aktuelle Folie als Vorschau, daneben klein die nächste. Darunter die
Notizen in großer, gut lesbarer Schrift — das ist der eigentliche Zweck der
Seite. Darunter Vor/Zurück als großflächige Schaltflächen, dazu Folienzähler,
verstrichene Zeit und eine Schaltfläche für die Schwarzblende. Kein JavaScript-
Framework, keine externen Ressourcen: die Seite muss auch ohne Internetzugang
im lokalen Netz vollständig funktionieren.

### 7.3 Absicherung

Beim Start der Präsentation wird ein Token (`secrets.token_urlsafe(8)`)
erzeugt. Ohne gültiges Token antwortet der Server mit 404 — nicht mit 403, um
die Existenz des Dienstes nicht zu bestätigen. Das Token gilt nur für die
laufende Präsentation und wird beim Verlassen verworfen.

Dies ist bewusst eine Absicherung gegen versehentlichen Zugriff im eigenen
Netz, kein Schutz gegen einen Angreifer im selben WLAN: die Verbindung ist
unverschlüsseltes HTTP. Das ist für den Zweck angemessen und wird in der
README ausdrücklich so benannt.

## 8. Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| Binary fehlt oder ist nicht ausführbar | Verständliche Meldung mit Pfad, Add-on beendet sich |
| Architektur passt nicht (z. B. x86-Build auf aarch64) | Wird beim Start einmal über `--version` geprüft, Meldung nennt erwartete Architektur |
| `render` schlägt fehl | Meldung mit stderr-Auszug; Deck wird nicht geöffnet; kaputter Cache-Eintrag wird entfernt |
| `info` meldet verlorene Folien oder Medien | Präsentation startet trotzdem, Hinweis erscheint einmalig im Auswahldialog |
| Port belegt | Nächste drei Ports werden probiert, dann Meldung; Präsentation läuft ohne Handy-Ansicht weiter |
| Deck während der Präsentation geändert | Wird ignoriert; der Cache-Stand bleibt bis zum Verlassen gültig |

Der Grundsatz: ein Fehler in der Handy-Ansicht darf den Vortrag nie stoppen.
Die TV-Ausgabe ist die kritische Funktion, alles andere ist Beiwerk.

## 9. Tests

Nach dem Muster der bestehenden Projekte: `pytest.ini` mit `pythonpath` auf
`script.presentation/resources/lib`, Kodi-Module in `tests/conftest.py` über
`sys.modules` gestubbt.

| Datei | Inhalt |
|---|---|
| `test_cache.py` | Cache-Schlüssel, Treffer und Fehltreffer, Aufräumen nach Größe |
| `test_renderer.py` | Aufrufzeile ans Binary, Auswertung von `info`, Fehlerpfade — mit einem Skript als Binary-Attrappe |
| `test_session.py` | Index-Grenzen, Versionszähler, Timer, Nebenläufigkeit |
| `test_phone_server.py` | Routen, Token-Prüfung, Long Poll, Kommandos — gegen einen echten Server auf Port 0 |
| `test_window.py` | Tastenzuordnung auf Aktionen, Verhalten an den Folienenden |

Dazu ein Integrationstest mit dem echten Binary und dem Testdeck, markiert als
`binary`, der nur mit `-m binary` läuft — so bleibt die normale Testrunde ohne
Build lauffähig.

## 10. Build und Auslieferung

```
kodi-presentation/
├── script.presentation/
│   ├── addon.xml                  (Deutsch und Englisch, MIT)
│   ├── default.py
│   ├── icon.png
│   ├── bin/deckcraft-cli          (nicht in Git, von build.sh erzeugt)
│   └── resources/
│       ├── lib/                   (renderer, deck_cache, session, …)
│       ├── skins/.../1080i/       (WindowXML)
│       ├── language/
│       └── settings.xml
├── tools/build-deckcraft.sh       (Cross-Compile)
├── build.sh                       (ZIP fürs Add-on)
├── tests/
├── docs/
└── README.md
```

`tools/build-deckcraft.sh` klont DeckCraft in einen temporären Ordner, prüft das
Tag, baut `deckcraft-cli` für `aarch64-unknown-linux-musl` mit
`RUSTFLAGS="-C linker=rust-lld -C link-self-contained=yes"`, strippt das Ergebnis
und legt es unter `script.presentation/bin/` ab. Das Binary ist in `.gitignore`;
die Git-Historie bleibt von 25-MB-Blobs frei. `build.sh` prüft, ob das Binary
vorhanden ist, und packt das ZIP.

Die verwendete DeckCraft-Version wird in `tools/deckcraft.version` festgehalten,
damit ein Build reproduzierbar bleibt und ein Upstream-Wechsel eine bewusste
Änderung ist.

## 11. Bewusst verschobene Punkte

**Folienübergänge.** `deckcraft-cli render-transition` kann Frames eines
Übergangs einzeln rendern. Damit ließen sich Wischen und Morph als Framefolge
abspielen. Für Version 1 verworfen: es vervielfacht Renderzeit und Cache, und
der Nutzen beim Vortrag ist gering. Die Cache-Struktur lässt Platz dafür.

**Dauerschleife / Signage.** Technisch ein Timer auf `session.vor()`. Später
nachrüstbar, ohne die Architektur zu berühren.

**Weitere Renderer-Backends.** Die Schnittstelle in `renderer.py` ist dafür da.
Erst wenn sich an echten Decks zeigt, dass DeckCraft nicht reicht.

## 12. Offene Risiken

1. **DeckCraft ist Alpha.** Laut eigenem README etwa 55 % einsatzreif. Die Probe
   deckte Titel, Aufzählungen, Tabelle, Bild und Umlaute ab — nicht SmartArt,
   Diagramme, eingebettete Schriften oder Firmentemplates. Gegenmaßnahme: die
   austauschbare Renderer-Schnittstelle und ein früher Test mit einem echten
   Deck.
2. **Bindung an eine Fremdversion.** Ein DeckCraft-Update kann die Ausgabe von
   `info` ändern. Gegenmaßnahme: feste Version in `tools/deckcraft.version`,
   und `info` wird defensiv ausgewertet statt strikt.
3. **Nur aarch64.** Das Binary wird für den Pi gebaut. Andere Kodi-Plattformen
   bräuchten einen eigenen Build. Bewusst akzeptiert: das Add-on zielt auf
   dieses Gerät.
