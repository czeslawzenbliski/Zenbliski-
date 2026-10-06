#!/usr/bin/env python3
"""Dodaje zdjęcia do galerii na stronie.

Zmniejsza oryginały do rozmiaru internetowego, robi miniatury, usuwa dane
EXIF (w tym położenie GPS) i dopisuje zdjęcia do manifestu galerii.
Oryginałów nie zmienia.

Duże zdjęcie zapisuje w formacie AVIF, miniaturę w WebP. Przy tej samej
jakości co JPEG zajmują razem około 40% mniej miejsca. Miniatury są w WebP,
bo otwiera go każda przeglądarka; starsze urządzenia bez obsługi AVIF
pokazują w podglądzie miniaturę zamiast dużego zdjęcia (patrz site.js).

Użycie:
    python3 tools/add_photos.py [--edge=PIKSELE] <ścieżka-galerii> <plik-lub-katalog> [...]

Przykłady:
    python3 tools/add_photos.py archiwalne/gucin ~/Zdjęcia/Gucin
    python3 tools/add_photos.py --edge=2400 materialy-reklamowe/praktica-lb2 ~/Skany/LB2
    python3 build.py

--edge ustawia dłuższy bok dużego zdjęcia (domyślnie 2000). Dla skanów z drobnym
tekstem (prospekty, instrukcje) używaj 2400, żeby tekst był ostry po powiększeniu.

Ścieżka galerii to adres podstrony z content/site.json, np. "cyfrowe"
albo "analogowe/nikon-fa-ilford-hp5-plus". Wymaga biblioteki Pillow.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "docs" / "zdjecia"

FULL_EDGE = 2000   # dłuższy bok zdjęcia w podglądzie
MINI_EDGE = 900    # dłuższy bok miniatury
# Jakość dobrana pomiarem na skanach prospektów i zdjęciach z tej strony tak,
# żeby wierność względem oryginału (SSIM) nie była niższa niż dla JPEG 85 / 78.
FULL_FORMAT, FULL_EXT, FULL_QUALITY = "AVIF", ".avif", 68
MINI_FORMAT, MINI_EXT, MINI_QUALITY = "WEBP", ".webp", 80
EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}

Image.MAX_IMAGE_PIXELS = None  # duże skany są tu czymś normalnym


def slugify(name: str) -> str:
    name = name.replace("ł", "l").replace("Ł", "L")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return name or "zdjecie"


def collect(sources: list[str]) -> list[Path]:
    files: list[Path] = []
    for s in sources:
        p = Path(s).expanduser()
        if p.is_dir():
            files += sorted(f for f in p.iterdir()
                            if f.suffix.lower() in EXTENSIONS and not f.name.startswith("."))
        elif p.is_file():
            files.append(p)
        else:
            print(f"Pominięto (nie znaleziono): {s}")
    return files


def prepare(path: Path) -> Image.Image:
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        im = im.point(lambda v: v / 256).convert("L")
    elif im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    return im


def save(im: Image.Image, target: Path, edge: int, fmt: str, quality: int, icc: bytes | None) -> tuple[int, int]:
    copy = im.convert("RGB")
    copy.thumbnail((edge, edge), Image.LANCZOS)
    extra = {"icc_profile": icc} if icc else {}
    if fmt == "AVIF":
        extra["speed"] = 6  # ok. 2 s na zdjęcie; speed 4 daje pliki o 5% mniejsze, ale trwa 12 s
    elif fmt == "WEBP":
        extra["method"] = 6
    copy.save(target, fmt, quality=quality, **extra)
    return copy.size


def main() -> None:
    args, full_edge = [], FULL_EDGE
    for arg in sys.argv[1:]:
        if arg.startswith("--edge="):
            full_edge = int(arg.split("=", 1)[1])
        else:
            args.append(arg)
    if len(args) < 2:
        sys.exit(__doc__)
    gallery = args[0].strip("/")
    target = PHOTOS / gallery
    mini = target / "mini"
    mini.mkdir(parents=True, exist_ok=True)

    manifest_path = target / "index.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    taken = {Path(p["file"]).stem for p in manifest}

    added = 0
    for src in collect(args[1:]):
        base = slugify(src.stem)
        name, n = base, 2
        while name in taken:
            name, n = f"{base}-{n}", n + 1
        full_name, mini_name = name + FULL_EXT, name + MINI_EXT
        try:
            im = prepare(src)
        except Exception as exc:  # uszkodzony albo nieobsługiwany plik
            print(f"Pominięto {src.name}: {exc}")
            continue
        icc = im.info.get("icc_profile")
        w, h = save(im, target / full_name, full_edge, FULL_FORMAT, FULL_QUALITY, icc)
        mw, mh = save(im, mini / mini_name, MINI_EDGE, MINI_FORMAT, MINI_QUALITY, icc)
        manifest.append({"file": full_name, "mini": mini_name, "w": w, "h": h, "mw": mw, "mh": mh, "caption": ""})
        taken.add(name)
        added += 1
        print(f"  + {full_name}  {w}×{h}")

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    size = sum(f.stat().st_size for f in PHOTOS.rglob("*") if f.is_file() and f.suffix != ".json") / 1e6
    print(f"Dodano do „{gallery}”: {added}. Wszystkie zdjęcia na stronie zajmują {size:.0f} MB (limit GitHub Pages: 1000 MB).")
    print("Teraz uruchom: python3 build.py")


if __name__ == "__main__":
    main()
