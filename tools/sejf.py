#!/usr/bin/env python3
"""Dział na hasło z galeriami w środku („sejf”). Szczegóły w tools/vault.py.

Hasło podaje się w zmiennej HASLO_GALERII (albo wpisuje na pytanie). Nie wolno go zapisywać.

    python3 tools/sejf.py lista  <dział>                      # galerie w sejfie (odszyfrowane tytuły)
    python3 tools/sejf.py nowa   <dział> "Tytuł"              # nowa pusta galeria, wypisuje jej adres
    python3 tools/sejf.py tytul  <dział> <slug> "Nowy tytuł"
    python3 tools/sejf.py przenies <dział> <galeria-na-haslo> "Tytuł"
        # osobną galerię na hasło (to samo hasło) przenosi do sejfu; zdjęć nie szyfruje od nowa

Zdjęcia do galerii w sejfie dodaje się zwykłym add_photos.py, np.:
    HASLO_GALERII='...' python3 tools/add_photos.py archiwalne/gucin-zdjecia-rodzinne/galeria-1 ~/Zdjęcia
"""
from __future__ import annotations

import getpass
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault  # noqa: E402

PHOTOS = Path(__file__).resolve().parent.parent / "docs" / "zdjecia"


def password() -> str:
    return os.environ.get("HASLO_GALERII") or getpass.getpass("Hasło: ")


def next_slug(section_dir: Path, children: list[dict]) -> str:
    used = {c["slug"] for c in children} | {p.name for p in section_dir.iterdir() if p.is_dir()}
    n = 1
    while f"galeria-{n}" in used:
        n += 1
    return f"galeria-{n}"


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, section = sys.argv[1], PHOTOS / sys.argv[2].strip("/")
    if not vault.is_section(section):
        sys.exit("To nie jest dział na hasło (sejf).")
    try:
        key, children = vault.unlock(section, password())
    except vault.WrongPassword as exc:
        sys.exit(str(exc))

    if cmd == "lista":
        for c in children:
            _, m = vault.unlock_child(section / c["slug"], key)
            print(f'{c["slug"]}: {c["title"]} ({len(m)} zdjęć)')
    elif cmd == "nowa":
        slug = next_slug(section, children)
        vault.create_child(section / slug, key)
        children.append({"slug": slug, "title": sys.argv[3]})
        vault.save_manifest(section, key, children)
        print(slug)
    elif cmd == "tytul":
        for c in children:
            if c["slug"] == sys.argv[3]:
                c["title"] = sys.argv[4]
                break
        else:
            sys.exit("Nie ma takiej galerii w sejfie.")
        vault.save_manifest(section, key, children)
    elif cmd == "przenies":
        old = PHOTOS / sys.argv[3].strip("/")
        try:
            data_key, manifest = vault.unlock(old, password())
        except vault.WrongPassword as exc:
            sys.exit(str(exc))
        slug = next_slug(section, children)
        shutil.move(str(old), str(section / slug))
        vault.write_child(section / slug, key, data_key, manifest)
        children.append({"slug": slug, "title": sys.argv[4]})
        vault.save_manifest(section, key, children)
        print(slug)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
