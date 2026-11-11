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

from texte import T

MANIFEST = "deck.json"
VORSCHAU_SKALIERUNG = 0.5  # 960x540 Punkte * 0.5 = 480x270
_SCHEMA = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def ist_vfs(pfad):
    """True für Kodi-Quellen wie smb:// oder nfs://, die kein Dateisystempfad sind."""
    return bool(_SCHEMA.match(pfad or ""))


def _vfs_stempel(pfad):
    """Änderungszeit und Größe einer Kodi-Quelle über xbmcvfs.Stat.

    Lässt sich das nicht ermitteln, wird bewusst ein stets neuer Wert geliefert:
    Ein Fehltreffer kostet Zehntelsekunden, eine veraltete Folie den Vortrag.
    """
    try:
        s = xbmcvfs.Stat(pfad)
        return f"{int(s.st_mtime())}|{s.st_size()}"
    except Exception:
        return f"unbekannt-{time.time_ns()}"


def schluessel(pfad):
    """Hash aus Pfad, Änderungszeit und Größe. Ändert sich das Deck, ändert sich der Schlüssel."""
    if ist_vfs(pfad):
        roh = f"{pfad}|{_vfs_stempel(pfad)}"
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
            try:
                with open(self._manifest_pfad(pfad), encoding="utf-8") as f:
                    manifest = json.load(f)
                os.utime(self._ordner(pfad), None)  # für das Aufräumen nach Zugriff
                return manifest
            except (ValueError, OSError):
                # Halbes Manifest, etwa nach einem Stromausfall mitten im
                # Schreiben: wegräumen und neu rendern, statt bei jedem Start
                # dieselbe Fehlermeldung zu zeigen (Spec §8).
                shutil.rmtree(self._ordner(pfad), ignore_errors=True)
        return self._rendere(pfad, renderer_, skalierung, fortschritt)

    def _rendere(self, pfad, renderer_, skalierung, fortschritt):
        ziel = self._ordner(pfad)
        shutil.rmtree(ziel, ignore_errors=True)
        os.makedirs(ziel, exist_ok=True)
        lokal, aufraeumen = self._lokaler_pfad(pfad)
        try:
            if fortschritt:
                fortschritt(10, T(30113))
            info = renderer_.info(lokal)
            if fortschritt:
                fortschritt(30, T(30114))
            bilder = renderer_.render(lokal, os.path.join(ziel, "tv"), skalierung)
            if fortschritt:
                fortschritt(70, T(30115))
            vorschau = renderer_.render(lokal, os.path.join(ziel, "thumb"), VORSCHAU_SKALIERUNG)
            manifest = self._baue_manifest(pfad, info, bilder, vorschau)
            # Zuletzt und atomar schreiben: erst das vollständige Manifest an
            # seinem Platz macht den Eintrag gültig.
            vorlaeufig = os.path.join(ziel, MANIFEST + ".neu")
            with open(vorlaeufig, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(vorlaeufig, os.path.join(ziel, MANIFEST))
            if fortschritt:
                fortschritt(100, T(30116))
            self.aufraeumen(schone=ziel)
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
        fehlende = max(0, len(info.folien) - len(bilder))
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
            "hash": schluessel(quelle),
            "gerendert": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "folienGroesse": list(info.folien_groesse),
            "titel": info.titel,
            "verloreneFolien": info.verlorene_folien,
            "fehlendeBilder": fehlende,
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

    def aufraeumen(self, schone=None):
        """Entfernt die am längsten nicht benutzten Einträge, bis die Grenze
        eingehalten ist.

        `schone` bleibt immer liegen: das gerade gerenderte Deck darf nicht
        weggeräumt werden, nur weil es allein die Obergrenze reißt -- sonst
        kommt ein gültiges Manifest zurück, dessen Bilder gelöscht sind.
        """
        if self.groesse_bytes() <= self._grenze:
            return 0
        geschont = os.path.abspath(schone) if schone else None
        eintraege = []
        for name in os.listdir(self._wurzel):
            ordner = os.path.join(self._wurzel, name)
            if os.path.isdir(ordner) and os.path.abspath(ordner) != geschont:
                eintraege.append((os.path.getmtime(ordner), ordner))
        eintraege.sort()
        entfernt = 0
        for _, ordner in eintraege:
            if self.groesse_bytes() <= self._grenze:
                break
            shutil.rmtree(ordner, ignore_errors=True)
            entfernt += 1
        return entfernt
