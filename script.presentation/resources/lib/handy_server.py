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

# DeckCraft liefert PNG; die Endung in der URL sagt nichts über die Datei.
BILD_TYPEN = {".png": "image/png", ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg", ".webp": "image/webp"}


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
    def __init__(self, sitzung_, manifest, seiten_html, port=8099, token=None,
                 anstupsen=None):
        """`anstupsen` wird nach jedem angenommenen Befehl gerufen.

        Kodi nimmt Oberflächenänderungen nur aus seinem eigenen Thread an. Der
        HTTP-Thread zeichnet deshalb nichts selbst, sondern stupst das Fenster
        über Kodis thread-sicheren Dispatch an.
        """
        self.anstupsen = anstupsen
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
        kandidaten = [0] if self._wunsch_port == 0 else [
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
        """Gibt False zurück, wenn die Eingabe unbrauchbar ist -- der Aufrufer
        antwortet dann mit 400, statt die Ausnahme bis in socketserver fliegen
        zu lassen, wo der Request ohne Antwort stirbt."""
        if aktion not in ERLAUBTE_AKTIONEN:
            return False
        if aktion == "springe":
            try:
                ziel = int(ziel or 0)
            except (TypeError, ValueError):
                return False
        if aktion == "vor":
            self.sitzung.vor()
        elif aktion == "zurueck":
            self.sitzung.zurueck()
        elif aktion == "springe":
            self.sitzung.springe(ziel)
        elif aktion == "blende":
            self.sitzung.blende_umschalten()
        elif aktion == "timer":
            self.sitzung.timer_zuruecksetzen()
        if self.anstupsen:
            try:
                self.anstupsen()
            except Exception:
                pass          # ein Fehler hier darf den Vortrag nie stoppen
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
            if len(teile) < 3 or teile[1] != "p":
                return None
            # compare_digest wirft bei Nicht-ASCII; über Bytes ist das sicher.
            if not secrets.compare_digest(teile[2].encode("utf-8", "surrogateescape"),
                                          halter.token.encode("utf-8")):
                return None
            return "/".join(teile[3:])

        def _sende(self, status, koerper, typ="application/json; charset=utf-8"):
            if isinstance(koerper, str):
                koerper = koerper.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(koerper)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(koerper)

        def _nicht_gefunden(self):
            return self._sende(404, "nicht gefunden", "text/plain; charset=utf-8")

        def do_GET(self):
            rest = self._rest()
            if rest is None:
                return self._nicht_gefunden()
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
                return self._sende_vorschau(rest)
            return self._nicht_gefunden()

        def _sende_vorschau(self, rest):
            try:
                nummer = int(rest[6:].split(".")[0])
            except ValueError:
                return self._nicht_gefunden()
            folie = halter.folie(nummer)
            pfad = (folie or {}).get("vorschau") or ""
            if not pfad or not os.path.isfile(pfad):
                return self._nicht_gefunden()
            endung = os.path.splitext(pfad)[1].lower()
            typ = BILD_TYPEN.get(endung, "application/octet-stream")
            with open(pfad, "rb") as f:
                return self._sende(200, f.read(), typ)

        def do_POST(self):
            rest = self._rest()
            if rest is None or rest != "cmd":
                return self._nicht_gefunden()
            laenge = int(self.headers.get("Content-Length") or 0)
            try:
                daten = json.loads(self.rfile.read(laenge) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._sende(400, json.dumps({"fehler": "kaputtes JSON"}))
            if not isinstance(daten, dict):
                return self._sende(400, json.dumps({"fehler": "Objekt erwartet"}))
            if not halter.fuehre_aus(daten.get("aktion"), daten.get("ziel")):
                return self._sende(400, json.dumps({"fehler": "unbekannte Aktion"}))
            return self._sende(200, json.dumps({"ok": True}))

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    return server
