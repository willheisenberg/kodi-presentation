"""QR-Codes ohne Fremdbibliothek, nur für die Startkarte der Präsentation.

Byte-Modus, Fehlerkorrektur-Stufe L, Versionen 1 bis 5, Maske 0. Das genügt
vollständig: Version 5 fasst 108 Byte, die längste erzeugte URL hat etwa 50.
Ab Version 6 bräuchte es mehrere Reed-Solomon-Blöcke mit Verschachtelung --
Komplexität für Kapazität, die hier nie gebraucht wird.

Dieses Modul ist Beiwerk: Schlägt es fehl, zeigt die Startkarte nur die URL.
"""
import struct
import zlib

# Datenbytes und Fehlerkorrekturbytes je Version, Stufe L, ein Block.
DATEN_BYTES = {1: 19, 2: 34, 3: 55, 4: 80, 5: 108}
ECC_BYTES = {1: 7, 2: 10, 3: 15, 4: 20, 5: 26}
AUSRICHTUNG = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30]}

RUHEZONE = 4  # Module heller Rand; ohne sie erkennt kein Lesegerät den Code

# --- Galois-Feld GF(256), Generatorpolynom 0x11D -------------------------

_EXP = [0] * 512
_LOG = [0] * 256


def _baue_tabellen():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_baue_tabellen()


def _mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _generator(grad):
    """Erzeugerpolynom (x - a^0)(x - a^1)...; höchster Grad zuerst, monisch."""
    g = [1]
    for i in range(grad):
        neu = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            neu[j] ^= c                      # c * x
            neu[j + 1] ^= _mul(c, _EXP[i])   # c * a^i
        g = neu
    return g


def _fehlerkorrektur(daten, grad):
    g = _generator(grad)
    rest = list(daten) + [0] * grad
    for i in range(len(daten)):
        koeff = rest[i]
        if koeff:
            for j, gk in enumerate(g):
                rest[i + j] ^= _mul(gk, koeff)
    return rest[len(daten):]


# --- Datenkodierung ------------------------------------------------------

def _version_fuer(anzahl_bytes):
    for v in sorted(DATEN_BYTES):
        # 4 Bit Modus + 8 Bit Längenfeld + Nutzdaten, aufgerundet auf Byte
        if (4 + 8 + anzahl_bytes * 8 + 7) // 8 <= DATEN_BYTES[v]:
            return v
    raise ValueError(
        f"Text zu lang für QR-Version 5: {anzahl_bytes} Byte, höchstens "
        f"{DATEN_BYTES[5] - 2} möglich")


def _codewoerter(text):
    roh = text.encode("utf-8")
    version = _version_fuer(len(roh))
    kapazitaet = DATEN_BYTES[version]

    bits = "0100"                       # Modus: Byte
    bits += format(len(roh), "08b")     # Längenfeld, 8 Bit für Version 1-9
    for b in roh:
        bits += format(b, "08b")
    bits += "0000"                      # Abschluss, ggf. gekürzt
    bits = bits[:kapazitaet * 8]
    bits += "0" * ((8 - len(bits) % 8) % 8)

    bytes_ = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    fuell = [0xEC, 0x11]
    while len(bytes_) < kapazitaet:
        bytes_.append(fuell[(len(bytes_) - len(bits) // 8) % 2])
    return version, bytes_ + _fehlerkorrektur(bytes_, ECC_BYTES[version])


# --- Platzierung ---------------------------------------------------------

def _format_bits():
    """Stufe L (01) und Maske 0 (000), BCH(15,5) plus Maskenwert."""
    daten = 0b01000
    rest = daten << 10
    for i in range(4, -1, -1):
        if rest & (1 << (i + 10)):
            rest ^= 0b10100110111 << i
    return ((daten << 10) | rest) ^ 0b101010000010010


def _muster(m, fest, n, version):
    # Suchmuster: Kern 3x3 dunkel, Ring hell, Rahmen dunkel.
    for zeile, spalte in ((0, 0), (0, n - 7), (n - 7, 0)):
        for dz in range(-1, 8):
            for ds in range(-1, 8):
                z, s = zeile + dz, spalte + ds
                if not (0 <= z < n and 0 <= s < n):
                    continue
                abstand = max(abs(dz - 3), abs(ds - 3))
                m[z][s] = abstand != 2 and abstand <= 3
                fest[z][s] = True

    # Taktspuren
    for i in range(n):
        if not fest[6][i]:
            m[6][i] = (i % 2 == 0)
            fest[6][i] = True
        if not fest[i][6]:
            m[i][6] = (i % 2 == 0)
            fest[i][6] = True

    # Ausrichtungsmuster, nie über einem Suchmuster
    mitten = AUSRICHTUNG[version]
    for z in mitten:
        for s in mitten:
            if fest[z][s]:
                continue
            for dz in range(-2, 3):
                for ds in range(-2, 3):
                    abstand = max(abs(dz), abs(ds))
                    m[z + dz][s + ds] = abstand != 1
                    fest[z + dz][s + ds] = True

    # Dunkles Modul
    m[4 * version + 9][8] = True
    fest[4 * version + 9][8] = True

    # Formatbereiche reservieren
    for i in range(9):
        for z, s in ((8, i), (i, 8)):
            if not fest[z][s]:
                fest[z][s] = True
                m[z][s] = False
    for i in range(8):
        for z, s in ((8, n - 1 - i), (n - 1 - i, 8)):
            if not fest[z][s]:
                fest[z][s] = True
                m[z][s] = False


def _setze_format(m, n):
    bits = _format_bits()

    def bit(i):
        return (bits >> i) & 1 == 1

    for i in range(6):
        m[i][8] = bit(i)
    m[7][8] = bit(6)
    m[8][8] = bit(7)
    m[8][7] = bit(8)
    for i in range(9, 15):
        m[8][14 - i] = bit(i)
    for i in range(8):
        m[8][n - 1 - i] = bit(i)
    for i in range(8, 15):
        m[n - 15 + i][8] = bit(i)


def _setze_daten(m, fest, n, codewoerter):
    bits = []
    for b in codewoerter:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1 == 1)
    k = 0
    spalte = n - 1
    while spalte > 0:
        if spalte == 6:
            spalte = 5
        for schritt in range(n):
            for j in range(2):
                s = spalte - j
                aufwaerts = ((spalte + 1) & 2) == 0
                z = (n - 1 - schritt) if aufwaerts else schritt
                if fest[z][s]:
                    continue
                wert = bits[k] if k < len(bits) else False
                k += 1
                # Maske 0: jedes zweite Modul kippen
                m[z][s] = wert != ((z + s) % 2 == 0)
        spalte -= 2


def matrix(text):
    """Gibt den QR-Code als Liste von Zeilen mit True (dunkel) / False zurück."""
    version, codewoerter = _codewoerter(text)
    n = 17 + 4 * version
    m = [[False] * n for _ in range(n)]
    fest = [[False] * n for _ in range(n)]
    _muster(m, fest, n, version)
    _setze_daten(m, fest, n, codewoerter)
    _setze_format(m, n)
    return m


# --- PNG-Ausgabe ---------------------------------------------------------

def als_png(text, ziel, modulgroesse=8, rahmen=0, leinwand=None):
    """Schreibt den Code als 8-Bit-Graustufen-PNG mit heller Ruhezone.

    `rahmen` legt einen dunklen Rand in Pixeln darum. `leinwand` (Breite, Höhe)
    zentriert das Ganze auf einem schwarzen Vollbild -- damit wird das Bild zur
    fertigen Startkarte, die das Folienbild einfach ersetzt und kein eigenes
    Steuerelement im Fenster braucht.
    """
    m = matrix(text)
    n = len(m)
    innen = (n + 2 * RUHEZONE) * modulgroesse
    seite = innen + 2 * rahmen

    breite, hoehe = leinwand if leinwand else (seite, seite)
    rand_x = max(0, (breite - seite) // 2)
    rand_y = max(0, (hoehe - seite) // 2)

    zeilen = bytearray()
    for bild_y in range(hoehe):
        zeilen.append(0)  # Filtertyp "None"
        if bild_y < rand_y or bild_y >= rand_y + seite:
            zeilen.extend(b"\x00" * breite)       # schwarze Leinwand
            continue
        y = bild_y - rand_y
        if rand_x:
            zeilen.extend(b"\x00" * rand_x)
        if y < rahmen or y >= rahmen + innen:
            zeilen.extend(b"\x10" * seite)          # dunkler Rand
            if rand_x:
                zeilen.extend(b"\x00" * (breite - seite - rand_x))
            continue
        modul_z = (y - rahmen) // modulgroesse - RUHEZONE
        reihe = m[modul_z] if 0 <= modul_z < n else None
        for x in range(seite):
            if x < rahmen or x >= rahmen + innen:
                zeilen.append(0x10)
                continue
            modul_s = (x - rahmen) // modulgroesse - RUHEZONE
            dunkel = reihe is not None and 0 <= modul_s < n and reihe[modul_s]
            zeilen.append(0 if dunkel else 255)
        if rand_x:
            zeilen.extend(b"\x00" * (breite - seite - rand_x))

    def block(tag, daten):
        return (struct.pack(">I", len(daten)) + tag + daten
                + struct.pack(">I", zlib.crc32(tag + daten) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + block(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 0, 0, 0, 0))
           + block(b"IDAT", zlib.compress(bytes(zeilen), 9))
           + block(b"IEND", b""))
    with open(ziel, "wb") as f:
        f.write(png)
    return ziel
