#!/usr/bin/env python3
"""Generator strony zenbliski.pl.

Czyta strukturę z content/site.json, teksty z content/teksty/ i manifesty
zdjęć z docs/zdjecia/<ścieżka>/index.json, a zapisuje gotowe pliki HTML
do docs/ (to ten katalog publikuje GitHub Pages).

Użycie:  python3 build.py
Wymaga tylko biblioteki standardowej Pythona 3.9+.
"""
from __future__ import annotations

import json
import shutil
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
OUT = ROOT / "docs"
PHOTOS = OUT / "zdjecia"
# Katalogi w docs/, których generator nigdy nie usuwa ani nie nadpisuje.
KEEP = {"assets", "zdjecia", ".nojekyll", "CNAME"}


# ---------------------------------------------------------------- pomocnicze

def plural(n: int, one: str, few: str, many: str) -> str:
    """Polska odmiana: 1 galeria, 2 galerie, 5 galerii, 22 galerie."""
    if n == 1:
        word = one
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = few
    else:
        word = many
    return f"{n} {word}"


class Node:
    def __init__(self, data: dict, parent: "Node | None" = None):
        self.data = data
        self.parent = parent
        self.slug: str = data["slug"]
        self.title: str = data["title"]
        self.kind: str = data.get("kind", "gallery")
        self.lead: str = data.get("lead", "")
        self.plate: list = data.get("plate", [])
        self.children = [Node(c, self) for c in data.get("children", [])]

    # ścieżka względem katalogu docs/, np. "analogowe/nikon-fa-ilford-hp5-plus"
    @property
    def path(self) -> str:
        return f"{self.parent.path}/{self.slug}" if self.parent else self.slug

    @property
    def depth(self) -> int:
        return self.path.count("/") + 1

    @property
    def top(self) -> "Node":
        return self.parent.top if self.parent else self

    @property
    def photos(self) -> list[dict]:
        manifest = PHOTOS / self.path / "index.json"
        if not manifest.exists():
            return []
        return json.loads(manifest.read_text(encoding="utf-8"))

    @property
    def body(self) -> str:
        f = CONTENT / "teksty" / (self.path.replace("/", "--") + ".html")
        return f.read_text(encoding="utf-8").strip() if f.exists() else ""

    def cover(self) -> tuple["Node", dict] | None:
        """Zdjęcie okładkowe: własne (pole "cover" albo pierwsze) lub pierwsze z podstron."""
        photos = self.photos
        if photos:
            wanted = self.data.get("cover")
            for p in photos:
                if p["file"] == wanted:
                    return self, p
            return self, photos[0]
        for child in self.children:
            found = child.cover()
            if found:
                return found
        return None

    def count_label(self) -> str:
        if self.children:
            kinds = {c.kind for c in self.children}
            n = len(self.children)
            if kinds == {"gallery"}:
                return plural(n, "galeria", "galerie", "galerii")
            if kinds == {"text"}:
                return plural(n, "wpis", "wpisy", "wpisów")
            return plural(n, "pozycja", "pozycje", "pozycji")
        n = len(self.photos)
        if n:
            return plural(n, "zdjęcie", "zdjęcia", "zdjęć")
        if self.body:
            return ""
        return "w przygotowaniu"


# ------------------------------------------------------------------ szablony

def head(site: dict, title: str, description: str, prefix: str) -> str:
    robots = '<meta name="robots" content="noindex">\n' if site.get("noindex") else ""
    return f"""<!doctype html>
<html lang="{site['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description, quote=True)}">
{robots}<meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:site_name" content="{escape(site['title'], quote=True)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="pl_PL">
<meta name="theme-color" content="#151412">
<link rel="preload" href="{prefix}assets/fonts/playfair-display-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{prefix}assets/style.css">
<script>document.documentElement.classList.add("js")</script>
</head>
"""


def header(site: dict, sections: list[Node], prefix: str, current: Node | None, home: bool) -> str:
    items = []
    for s in sections:
        attrs = ""
        if current is not None and current.top is s:
            attrs = ' aria-current="page"' if current is s else ' class="is-current"'
        items.append(f'<li><a href="{prefix}{s.path}/"{attrs}>{escape(s.title)}</a></li>')
    brand_cls = "brand brand--hidden" if home else "brand"
    brand_cur = ' aria-current="page"' if home else ""
    return f"""<body>
<a class="skip" href="#tresc">Przejdź do treści</a>
<header class="top">
  <a class="{brand_cls}" href="{prefix or './'}"{brand_cur}>{escape(site['title'])}</a>
  <nav class="nav" aria-label="Działy">
    <button class="nav__toggle" type="button" aria-expanded="false" aria-controls="menu">Menu</button>
    <ul id="menu">
      {chr(10).join('      ' + i for i in items).strip()}
    </ul>
  </nav>
</header>
"""


def footer(site: dict, prefix: str) -> str:
    return f"""<footer class="foot">
  <p>{escape(site['footer'])}</p>
</footer>
<script src="{prefix}assets/site.js" defer></script>
</body>
</html>
"""


def frame(node: Node, prefix: str, heading: str = "h2") -> str:
    """Kadr prowadzący do działu lub galerii: okładka, tytuł, liczba pozycji."""
    cover = node.cover()
    if cover:
        owner, p = cover
        src = f"{prefix}zdjecia/{owner.path}/mini/{p['file']}"
        view = (f'<img src="{src}" width="{p["mw"]}" height="{p["mh"]}" '
                f'alt="" loading="lazy" decoding="async">')
        cls = "frame"
    else:
        view = ""
        cls = "frame frame--empty"
    meta = node.count_label()
    meta_html = f'\n  <span class="frame__meta">{escape(meta)}</span>' if meta else ""
    return f"""<a class="{cls}" href="{prefix}{node.path}/">
  <span class="frame__view">{view}</span>
  <{heading} class="frame__title">{escape(node.title)}</{heading}>{meta_html}
</a>"""


def photo_grid(node: Node, prefix: str) -> str:
    out = ['<div class="photos" data-lightbox>']
    for p in node.photos:
        base = f"{prefix}zdjecia/{node.path}/"
        ratio = round(p["w"] / p["h"], 4)
        caption = p.get("caption", "")
        alt = caption or node.title
        cap_attr = f' data-caption="{escape(caption, quote=True)}"' if caption else ""
        out.append(
            f'  <a href="{base}{p["file"]}" style="--r:{ratio}" data-w="{p["w"]}" data-h="{p["h"]}"{cap_attr}>'
            f'<img src="{base}mini/{p["file"]}" width="{p["mw"]}" height="{p["mh"]}" '
            f'alt="{escape(alt, quote=True)}" loading="lazy" decoding="async"></a>'
        )
    out.append("</div>")
    return "\n".join(out)


def empty_state(text: str) -> str:
    return f'<div class="empty"><p>{escape(text)}</p></div>'


def breadcrumb(node: Node, prefix: str) -> str:
    if not node.parent:
        return ""
    trail, n = [], node.parent
    while n:
        trail.append(n)
        n = n.parent
    links = "".join(
        f'<li><a href="{prefix}{t.path}/">{escape(t.title)}</a></li>' for t in reversed(trail)
    )
    return f'<nav class="crumbs" aria-label="Ścieżka"><ol>{links}</ol></nav>\n'


def siblings_nav(node: Node, prefix: str) -> str:
    if not node.parent:
        return ""
    sibs = node.parent.children
    i = sibs.index(node)
    prev_ = sibs[i - 1] if i > 0 else None
    next_ = sibs[i + 1] if i < len(sibs) - 1 else None
    if not (prev_ or next_):
        return ""
    parts = ['<nav class="pager" aria-label="Sąsiednie pozycje">']
    if prev_:
        parts.append(f'  <a class="pager__prev" href="{prefix}{prev_.path}/">'
                     f'<span>Poprzednia</span>{escape(prev_.title)}</a>')
    if next_:
        parts.append(f'  <a class="pager__next" href="{prefix}{next_.path}/">'
                     f'<span>Następna</span>{escape(next_.title)}</a>')
    parts.append("</nav>")
    return "\n".join(parts)


# -------------------------------------------------------------------- strony

def render_home(site: dict, sections: list[Node]) -> str:
    frames = "\n".join(frame(s, "") for s in sections)
    return (
        head(site, f"{site['title']} – fotografia", site["description"], "")
        + header(site, sections, "", None, home=True)
        + f"""<main id="tresc">
  <section class="hero">
    <h1 class="hero__name">{escape(site['title'])}</h1>
    <p class="hero__intro">{escape(site['intro'])}</p>
  </section>
  <section class="index" aria-label="Działy">
{frames}
  </section>
</main>
"""
        + footer(site, "")
    )


def render_node(site: dict, sections: list[Node], node: Node) -> str:
    prefix = "../" * node.depth
    parts = [breadcrumb(node, prefix)]
    parts.append(f'<h1 class="page__title">{escape(node.title)}</h1>')
    if node.lead:
        parts.append(f'<p class="page__lead">{escape(node.lead)}</p>')
    if node.plate:
        rows = "".join(f"<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>" for k, v in node.plate)
        parts.append(f'<dl class="plate">{rows}</dl>')

    body, photos = node.body, node.photos
    if body:
        parts.append(f'<div class="prose">\n{body}\n</div>')
    if node.children:
        frames = "\n".join(frame(c, prefix) for c in node.children)
        parts.append(f'<section class="shelf" aria-label="Zawartość działu">\n{frames}\n</section>')
    if photos:
        parts.append(photo_grid(node, prefix))
    if not (body or node.children or photos):
        default = ("Zdjęcia do tej galerii są w przygotowaniu."
                   if node.kind == "gallery" else "Ta strona jest w przygotowaniu.")
        parts.append(empty_state(node.data.get("empty", default)))
    parts.append(siblings_nav(node, prefix))

    title = f"{node.title} – {site['title']}"
    description = node.lead or f"{node.title}. {site['description']}"
    return (
        head(site, title, description, prefix)
        + header(site, sections, prefix, node, home=False)
        + '<main id="tresc" class="page">\n'
        + "\n".join(p for p in parts if p)
        + "\n</main>\n"
        + footer(site, prefix)
    )


def render_404(site: dict, sections: list[Node]) -> str:
    # Strona błędu może się wyświetlić pod dowolnym adresem, więc używa ścieżek bezwzględnych.
    prefix = site["root_path"]
    return (
        head(site, f"Nie ma takiej strony – {site['title']}", site["description"], prefix)
        + header(site, sections, prefix, None, home=False)
        + f"""<main id="tresc" class="page">
<h1 class="page__title">Nie ma takiej strony</h1>
<p class="page__lead">Adres mógł się zmienić po przebudowie serwisu. Wybierz dział z menu albo wróć na <a href="{prefix}">stronę główną</a>.</p>
</main>
"""
        + footer(site, prefix)
    )


# --------------------------------------------------------------------- start

def walk(nodes: list[Node]):
    for n in nodes:
        yield n
        yield from walk(n.children)


def main() -> None:
    site = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
    sections = [Node(s) for s in site["sections"]]

    # Usuń poprzednio wygenerowane strony, zostaw zasoby i zdjęcia.
    for item in OUT.iterdir():
        if item.name in KEEP:
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink()

    pages = 0
    (OUT / "index.html").write_text(render_home(site, sections), encoding="utf-8")
    (OUT / "404.html").write_text(render_404(site, sections), encoding="utf-8")
    pages += 2
    for node in walk(sections):
        target = OUT / node.path
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(render_node(site, sections, node), encoding="utf-8")
        pages += 1

    photos = sum(len(n.photos) for n in walk(sections))
    print(f"Gotowe: {pages} stron, {photos} zdjęć w galeriach.")


if __name__ == "__main__":
    main()
