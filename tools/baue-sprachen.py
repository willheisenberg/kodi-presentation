#!/usr/bin/env python3
"""Erzeugt beide strings.po aus tools/texte.json.

Eine einzige Quelle, damit Deutsch und Englisch nicht auseinanderlaufen:
Ein fehlender Text in einer Sprache ist dann unmöglich, nicht nur unwahrscheinlich.
"""
import json
import pathlib

WURZEL = pathlib.Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "tools" / "texte.json"
SPRACHEN = [
    ("resource.language.de_de", "de_DE", 0),
    ("resource.language.en_gb", "en_GB", 1),
]
KOPF = ('msgid ""\nmsgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Language: {code}\\n"\n')


def main():
    texte = json.loads(QUELLE.read_text(encoding="utf-8"))
    for ordner, code, spalte in SPRACHEN:
        ziel = WURZEL / "script.presentation" / "resources" / "language" / ordner
        ziel.mkdir(parents=True, exist_ok=True)
        teile = [KOPF.format(code=code)]
        for nummer in sorted(texte, key=int):
            deutsch, englisch = texte[nummer]
            # msgid ist immer der englische Text (Kodi-Konvention),
            # msgstr die jeweilige Sprache.
            teile.append(f'\nmsgctxt "#{nummer}"\n'
                         f'msgid "{englisch}"\n'
                         f'msgstr "{texte[nummer][spalte]}"\n')
        (ziel / "strings.po").write_text("".join(teile), encoding="utf-8")
        print(f"{ordner}/strings.po: {len(texte)} Texte")


if __name__ == "__main__":
    main()
