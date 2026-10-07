#!/usr/bin/env python3
"""Sprawdza podgląd zdjęć tak, jak używa go człowiek: stuknięcia w strzałki
i przesunięcia palcem na telefonie, mysz i klawiatura na komputerze.

Uruchom po każdej zmianie w docs/assets/site.js albo w stylach podglądu (.lb…):

    python3 build.py && python3 tools/check_viewer.py

Wymaga Pythonowego Playwrighta z Chromium. Sam uruchamia lokalny serwer.
Powód istnienia: pierwsza wersja podglądu wyglądała dobrze na zrzutach, ale na
telefonie podpis zasłaniał strzałki, a przeglądarka przejmowała gest przesuwania.
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.async_api import async_playwright

DOCS = Path(__file__).resolve().parent.parent / "docs"


def find_gallery() -> tuple[str, int]:
    """Pierwsza galeria z co najmniej dwoma zdjęciami."""
    for manifest in sorted((DOCS / "zdjecia").rglob("index.json")):
        n = len(json.loads(manifest.read_text(encoding="utf-8")))
        if n >= 2:
            return manifest.parent.relative_to(DOCS / "zdjecia").as_posix(), n
    sys.exit("Brak galerii z co najmniej dwoma zdjęciami, nie ma czego sprawdzać.")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # bez dziennika żądań na ekranie
        pass


def serve() -> str:
    handler = functools.partial(QuietHandler, directory=str(DOCS))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


async def swipe(cdp, x1, y1, x2, y2, steps=8):
    """Prawdziwy gest dotykowy: przeglądarka stosuje do niego touch-action."""
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x1, "y": y1}]})
    for i in range(1, steps + 1):
        point = {"x": x1 + (x2 - x1) * i / steps, "y": y1 + (y2 - y1) * i / steps}
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [point]})
        await asyncio.sleep(0.016)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await asyncio.sleep(0.3)


async def centre(page, selector):
    box = await page.locator(selector).first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def check_touch(browser, url, total, width, height, failures):
    name = f"dotyk {width}×{height}"
    ctx = await browser.new_context(viewport={"width": width, "height": height},
                                    device_scale_factor=2, is_mobile=True, has_touch=True)
    page = await ctx.new_page()
    cdp = await ctx.new_cdp_session(page)
    await page.goto(url, wait_until="networkidle")
    await page.evaluate("document.querySelector('.photos a').dataset.caption = "
                        "'Długi podpis próbny, który na wąskim ekranie zajmuje kilka linii tekstu'")

    async def count():
        return await page.inner_text(".lb__count")

    def expect(step, got, want):
        if got != want:
            failures.append(f"{name}: {step}: jest „{got}”, powinno być „{want}”")

    # W galerii z metryczką pierwsze zdjęcie bywa poniżej dolnej krawędzi niskiego ekranu.
    await page.locator(".photos a").first.scroll_into_view_if_needed()
    await page.touchscreen.tap(*await centre(page, ".photos a"))
    await page.wait_for_timeout(400)
    expect("otwarcie", await count(), f"1 z {total}")
    await page.touchscreen.tap(*await centre(page, ".lb__next"))
    await page.wait_for_timeout(250)
    expect("strzałka następne", await count(), f"2 z {total}")
    await page.touchscreen.tap(*await centre(page, ".lb__prev"))
    await page.wait_for_timeout(250)
    expect("strzałka poprzednie", await count(), f"1 z {total}")
    await swipe(cdp, width * 0.8, height * 0.45, width * 0.2, height * 0.45)
    expect("przesunięcie w lewo", await count(), f"2 z {total}")
    await swipe(cdp, width * 0.2, height * 0.45, width * 0.8, height * 0.45)
    expect("przesunięcie w prawo", await count(), f"1 z {total}")
    await swipe(cdp, width * 0.5, height * 0.3, width * 0.55, height * 0.7)
    expect("ruch pionowy nie zmienia zdjęcia", await count(), f"1 z {total}")
    if await page.locator(".lb__zoom").is_visible():
        failures.append(f"{name}: przycisk Powiększ nie powinien być widoczny na ekranie dotykowym")
    await page.touchscreen.tap(*await centre(page, ".lb__close"))
    await page.wait_for_timeout(250)
    if await page.evaluate("document.querySelector('dialog.lb').open"):
        failures.append(f"{name}: przycisk Zamknij nie zamyka podglądu")
    await ctx.close()


async def check_no_avif(browser, url, failures):
    """Urządzenie, które nie otwiera dużych zdjęć (AVIF), ma zobaczyć w podglądzie miniaturę."""
    page = await browser.new_page(viewport={"width": 1440, "height": 900})
    await page.route("**/*.avif", lambda route: route.abort())
    await page.goto(url, wait_until="networkidle")
    await page.click(".photos a")
    try:
        await page.wait_for_function(
            "(() => { const i = document.querySelector('.lb__img');"
            " return i.complete && i.naturalWidth > 0 && i.src.includes('/mini/'); })()", timeout=5000)
    except Exception:
        failures.append("bez AVIF: podgląd nie pokazuje miniatury zamiast dużego zdjęcia")
    await page.click(".lb__next")
    await page.wait_for_timeout(600)
    if not await page.evaluate("document.querySelector('.lb__img').naturalWidth > 0"):
        failures.append("bez AVIF: po przejściu do następnego zdjęcia podgląd jest pusty")
    await page.close()


async def check_desktop(browser, url, total, failures):
    page = await browser.new_page(viewport={"width": 1440, "height": 900})
    await page.goto(url, wait_until="networkidle")
    await page.click(".photos a")
    # Zaraz po pierwszym otwarciu, zanim zdjęcie trafi do pamięci przeglądarki.
    try:
        await page.wait_for_selector(".lb__zoom", state="visible", timeout=5000)
    except Exception:
        failures.append("komputer: po pierwszym otwarciu zdjęcia nie pojawia się przycisk Powiększ")
    await page.click(".lb__next")
    if await page.inner_text(".lb__count") != f"2 z {total}":
        failures.append("komputer: kliknięcie strzałki następne nie działa")
    await page.keyboard.press("ArrowLeft")
    if await page.inner_text(".lb__count") != f"1 z {total}":
        failures.append("komputer: klawisz strzałki w lewo nie działa")

    # Powiększenie do szerokości okna: przyciskiem i kliknięciem w zdjęcie.
    width = "document.querySelector('.lb__img').getBoundingClientRect().width"
    if await page.locator(".lb__zoom").is_visible():
        fitted = await page.evaluate(width)
        await page.click(".lb__zoom")
        if await page.evaluate(width) < fitted * 1.2:
            failures.append("komputer: przycisk Powiększ nie powiększa zdjęcia")
        if await page.locator(".lb__next").is_visible():
            failures.append("komputer: w powiększeniu strzałki powinny być ukryte")
        await page.click(".lb__img", position={"x": 200, "y": 200})
        if abs(await page.evaluate(width) - fitted) > 2:
            failures.append("komputer: kliknięcie w powiększone zdjęcie nie pomniejsza go")
        await page.click(".lb__img")
        if await page.evaluate(width) < fitted * 1.2:
            failures.append("komputer: kliknięcie w zdjęcie nie powiększa go")
        await page.keyboard.press("ArrowRight")
        if await page.evaluate("document.querySelector('dialog.lb').classList.contains('is-full')"):
            failures.append("komputer: przejście do następnego zdjęcia nie wyłącza powiększenia")
    else:
        failures.append("komputer: brak przycisku Powiększ przy zdjęciu większym niż okno")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)
    if await page.evaluate("document.querySelector('dialog.lb').open"):
        failures.append("komputer: Escape nie zamyka podglądu")
    await page.close()


async def main() -> None:
    gallery, total = find_gallery()
    url = f"{serve()}/{gallery}/"
    failures: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height in [(360, 740), (390, 844), (844, 390), (820, 1180)]:
            await check_touch(browser, url, total, width, height, failures)
        await check_desktop(browser, url, total, failures)
        await check_no_avif(browser, url, failures)
        await browser.close()
    if failures:
        print("Podgląd zdjęć NIE działa poprawnie:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"Podgląd zdjęć działa (galeria „{gallery}”, {total} zdjęcia): strzałki, przesuwanie palcem, mysz, klawiatura, powiększanie, zapas dla urządzeń bez AVIF.")


if __name__ == "__main__":
    asyncio.run(main())
