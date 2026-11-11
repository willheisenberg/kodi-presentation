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
