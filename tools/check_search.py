#!/usr/bin/env python3
"""Sprawdza wyszukiwarkę ze strony głównej tak, jak używa jej człowiek:
wpisuje słowa na komputerze i na telefonie, czyta wyniki, klika w wynik.

Uruchom po każdej zmianie w części „wyszukiwarka" pliku docs/assets/site.js,
w stylach .search… albo w funkcji search_index w build.py:

    python3 build.py && python3 tools/check_search.py

Pytania układa z bieżącej treści strony (content/site.json), więc nie trzeba go
poprawiać po dodaniu czy zmianie nazw galerii. Wymaga Playwrighta z Chromium.
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import json
import re
import socketserver
import sys
import threading
import unicodedata
from pathlib import Path

from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def serve() -> str:
    handler = functools.partial(QuietHandler, directory=str(DOCS))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


def plain(text: str) -> str:
    """Bez polskich znaków i małymi literami, tak jak ktoś pisze na telefonie."""
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def walk(nodes: list[dict], parents: tuple[str, ...] = ()):
    for n in nodes:
        path = parents + (n["slug"],)
        yield "/".join(path) + "/", n
        yield from walk(n.get("children", []), path)


def cases() -> list[tuple[str, str, str]]:
    """(opis, pytanie, adres strony, która musi być wśród wyników)."""
    site = json.loads((REPO / "content" / "site.json").read_text(encoding="utf-8"))
    pages = list(walk(site["sections"]))
    out = []

    # Tytuł z polskimi znakami, wpisany bez nich.
    for url, n in pages:
        if plain(n["title"]) != n["title"].lower() and "/" in url.rstrip("/"):
            out.append(("tytuł wpisany bez polskich znaków", plain(n["title"]), url))
            break
    # Wartość z metryczki, której nie ma w tytule własnej strony (np. obiektyw).
    for url, n in pages:
        for _, value in n.get("plate", []):
            words = [w for w in re.findall(r"[a-z0-9]+", plain(value)) if len(w) >= 4]
            words = [w for w in words if w not in plain(n["title"])]
            if words:
                out.append(("słowo z metryczki", words[0], url))
                break
        else:
            continue
        break
    # Dwa słowa z tytułu w odwróconej kolejności.
    for url, n in pages:
        words = [w for w in re.findall(r"[a-z0-9]+", plain(n["title"])) if len(w) >= 3]
        if len(words) >= 2:
            out.append(("dwa słowa w odwrotnej kolejności", f"{words[-1]} {words[0]}", url))
            break
    # Słowo z opisu działu.
    for url, n in pages:
        words = [w for w in re.findall(r"[a-z0-9]+", plain(n.get("lead", ""))) if len(w) >= 7]
        words = [w for w in words if w not in plain(n["title"])]
        if words:
            out.append(("słowo z opisu działu", words[0], url))
            break
    return out


def check_index(failures: list[str]) -> None:
    """Spis nie może zdradzać niczego z galerii na hasło poza jej jawnym tytułem."""
    index = json.loads((DOCS / "szukaj.json").read_text(encoding="utf-8"))
    by_url = {e["u"]: e for e in index}
    for lock in (DOCS / "zdjecia").rglob("lock.json"):
        url = lock.parent.relative_to(DOCS / "zdjecia").as_posix() + "/"
        entry = by_url.get(url)
        if entry is None:
            failures.append(f"spis: brak galerii na hasło „{url}” (tytuł jest jawny i powinien dać się wyszukać)")
            continue
        site = json.loads((REPO / "content" / "site.json").read_text(encoding="utf-8"))
        node = dict(walk(site["sections"]))[url]
        public = set(filter(None, [node.get("lead", "")] + [f"{k}: {v}" for k, v in node.get("plate", [])]
                                   + ([", ".join(node["keywords"])] if node.get("keywords") else [])))
        body = REPO / "content" / "teksty" / (url.rstrip("/").replace("/", "--") + ".html")
        extra = [x for x in entry["x"] if x not in public]
        if extra and not body.exists():
            failures.append(f"spis: przy galerii na hasło „{url}” są teksty spoza jawnych pól: {extra}")
    text = (DOCS / "szukaj.json").read_text(encoding="utf-8")
    if ".bin" in text or "lock.json" in text:
        failures.append("spis: zawiera nazwy zaszyfrowanych plików")


async def results(page) -> list[str]:
    return await page.eval_on_selector_all(".search__results a", "els => els.map(a => a.getAttribute('href'))")


async def ask(page, question: str) -> list[str]:
    await page.fill(".search input", question)
    await page.wait_for_function(
        "(() => { const s = document.querySelector('.search__status').textContent;"
        " return s !== '' && s !== 'Szukam…'; })()", timeout=5000)
    return await results(page)


async def check_browser(url: str, failures: list[str]) -> None:
    tests = cases()
    if not tests:
        failures.append("nie udało się ułożyć żadnego pytania z treści strony")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, kwargs in [
            ("komputer", dict(viewport={"width": 1440, "height": 900})),
            ("telefon", dict(viewport={"width": 360, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True)),
        ]:
            ctx = await browser.new_context(**kwargs)
            page = await ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(url, wait_until="networkidle")

            if not await page.locator(".search input").is_visible():
                failures.append(f"{name}: pole wyszukiwania nie jest widoczne")
                await ctx.close()
                continue
            if await page.locator(".search__results a").count():
                failures.append(f"{name}: wyniki są widoczne, zanim cokolwiek wpisano")

            for what, question, wanted in tests:
                found = await ask(page, question)
                if wanted not in found:
                    failures.append(f"{name}: {what}: „{question}” nie znajduje strony {wanted} (wyniki: {found})")
                elif what.startswith("tytuł") and found[0] != wanted:
                    failures.append(f"{name}: {what}: „{question}” powinno dać {wanted} na pierwszym miejscu, jest {found[0]}")

            overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if overflow > 0:
                failures.append(f"{name}: strona z wynikami przewija się w poziomie")

            if await ask(page, "qzxwv jkpd"):
                failures.append(f"{name}: wymyślone słowo daje wyniki")
            if "Nic nie znaleziono" not in await page.inner_text(".search__status"):
                failures.append(f"{name}: brak komunikatu, że nic nie znaleziono")

            await page.fill(".search input", "a")
            await page.wait_for_timeout(150)
            if await page.locator(".search__results a").count():
                failures.append(f"{name}: jedna litera nie powinna jeszcze dawać wyników")

            # Wejście w wynik i powrót: to samo wyszukiwanie ma być nadal widoczne.
            what, question, wanted = tests[0]
            if not await ask(page, question):
                failures.append(f"{name}: nie ma wyniku, w który można wejść (pytanie „{question}”)")
                await ctx.close()
                continue
            link = page.locator(".search__results a").first
            if name == "telefon":
                await link.scroll_into_view_if_needed()
                box = await link.bounding_box()
                await page.touchscreen.tap(box["x"] + 20, box["y"] + box["height"] / 2)
            else:
                await link.click()
            try:
                await page.wait_for_url(f"**/{wanted}", timeout=5000)
            except Exception:
                failures.append(f"{name}: wynik nie prowadzi do strony {wanted} (jest {page.url})")
            else:
                await page.go_back(wait_until="networkidle")
                try:
                    await page.wait_for_selector(".search__results a", timeout=5000)
                except Exception:
                    failures.append(f"{name}: po powrocie ze strony wyniku wyszukiwanie znika")

            if errors:
                failures.append(f"{name}: błędy skryptu: {errors}")
            await ctx.close()

        # Bez skryptów pole ma być niewidoczne, a nie martwe.
        ctx = await browser.new_context(java_script_enabled=False)
        page = await ctx.new_page()
        await page.goto(url)
        if await page.locator(".search").is_visible():
            failures.append("bez skryptów: pole wyszukiwania jest widoczne, choć nie może działać")
        await ctx.close()
        await browser.close()


def main() -> None:
    failures: list[str] = []
    check_index(failures)
    asyncio.run(check_browser(serve() + "/", failures))
    if failures:
        print("Wyszukiwarka NIE działa poprawnie:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("Wyszukiwarka działa: " + "; ".join(f"{what} („{q}”)" for what, q, _ in cases())
          + "; brak wyników, powrót z wyniku, telefon, spis bez treści galerii na hasło.")


if __name__ == "__main__":
    main()
