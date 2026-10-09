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


def find_gallery() -> tuple[str, list[dict]]:
    """Pierwsza galeria z co najmniej dwoma zdjęciami. Zwraca ścieżkę i listę zdjęć."""
    for manifest in sorted((DOCS / "zdjecia").rglob("index.json")):
        photos = json.loads(manifest.read_text(encoding="utf-8"))
        if len(photos) >= 2:
            return manifest.parent.relative_to(DOCS / "zdjecia").as_posix(), photos
    sys.exit("Brak galerii z co najmniej dwoma zdjęciami, nie ma czego sprawdzać.")


def split_by_zoom(photos: list[dict], width: int = 1440, height: int = 900) -> tuple[int | None, int | None]:
    """Numery zdjęć: pierwszego, które w oknie komputera powinno dać się powiększyć,
    i pierwszego, które nie powinno (szerokie, prawie wypełnia okno).

    Rachunek z dużym zapasem, żeby nie zależał od dokładnych marginesów podglądu."""
    zoomable = flat = None
    for i, p in enumerate(photos):
        fitted = min(width, height * p["w"] / p["h"])     # górne oszacowanie szerokości w oknie
        gain = min(p["w"], width) / fitted
        if zoomable is None and gain > 1.6:
            zoomable = i
        if flat is None and p["w"] / p["h"] > 1.7:
            flat = i
    return zoomable, flat


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


async def pinch(cdp, cx, cy, start, end, steps=8):
    """Rozsunięcie (albo zsunięcie) dwóch palców wokół punktu (cx, cy)."""
    def points(gap):
        return [{"x": cx - gap / 2, "y": cy, "id": 0}, {"x": cx + gap / 2, "y": cy, "id": 1}]
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": points(start)})
    for i in range(1, steps + 1):
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": points(start + (end - start) * i / steps)})
        await asyncio.sleep(0.016)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await asyncio.sleep(0.3)


IMG_WIDTH = "document.querySelector('.lb__img').getBoundingClientRect().width"


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

    async def immersive():
        return await page.evaluate("document.querySelector('dialog.lb').classList.contains('is-immersive')")

    def expect(step, got, want):
        if got != want:
            failures.append(f"{name}: {step}: jest „{got}”, powinno być „{want}”")

    # W galerii z metryczką pierwsze zdjęcie bywa poniżej dolnej krawędzi niskiego ekranu.
    await page.locator(".photos a").first.scroll_into_view_if_needed()
    await page.touchscreen.tap(*await centre(page, ".photos a"))
    await page.wait_for_timeout(400)
    expect("otwarcie", await count(), f"1 z {total}")

    # Stuknięcie w miniaturę otwiera zwykły podgląd (pełny ekran dopiero po stuknięciu w zdjęcie).
    if await immersive():
        failures.append(f"{name}: stuknięcie w miniaturę powinno otworzyć zwykły podgląd, a nie pełny ekran")
        await ctx.close()
        return

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
    # Stuknięcie w zdjęcie: pełny ekran, bez przycisków, zdjęcie na cały ekran.
    await page.touchscreen.tap(*await centre(page, ".lb__img"))
    await page.wait_for_timeout(300)
    if not await immersive():
        failures.append(f"{name}: stuknięcie w zdjęcie w zwykłym podglądzie nie włącza pełnego ekranu")
    else:
        if await page.locator(".lb__next").is_visible() or await page.locator(".lb__close").is_visible():
            failures.append(f"{name}: na pełnym ekranie widać przyciski")
        box = await page.locator(".lb__img").bounding_box()
        if box and max(box["width"] / width, box["height"] / height) < 0.97:
            failures.append(f"{name}: na pełnym ekranie zdjęcie nie wypełnia ekranu")
        await swipe(cdp, width * 0.8, height * 0.45, width * 0.2, height * 0.45)
        expect("przesunięcie w lewo na pełnym ekranie", await count(), f"2 z {total}")
        if not await immersive():
            failures.append(f"{name}: przesunięcie palcem wyłącza pełny ekran")

        # Powiększanie dwoma palcami na pełnym ekranie (przeglądarka sama tego tam nie robi).
        whole = await page.evaluate(IMG_WIDTH)
        await pinch(cdp, width / 2, height / 2, 60, 260)
        bigger = await page.evaluate(IMG_WIDTH)
        if bigger < whole * 1.8:
            failures.append(f"{name}: na pełnym ekranie nie da się powiększyć zdjęcia dwoma palcami")
        else:
            # Powiększone zdjęcie przesuwa się palcem zamiast zmieniać na następne.
            before = await page.evaluate("document.querySelector('.lb__img').getBoundingClientRect().left")
            await swipe(cdp, width * 0.6, height * 0.5, width * 0.3, height * 0.5)
            expect("przesuwanie powiększonego zdjęcia nie zmienia zdjęcia", await count(), f"2 z {total}")
            after = await page.evaluate("document.querySelector('.lb__img').getBoundingClientRect().left")
            if abs(after - before) < 20:
                failures.append(f"{name}: powiększonego zdjęcia nie da się przesunąć palcem")
            # Stuknięcie w powiększone zdjęcie wraca do całego zdjęcia, nadal na pełnym ekranie.
            await page.touchscreen.tap(width / 2, height / 2)
            await page.wait_for_timeout(300)
            if abs(await page.evaluate(IMG_WIDTH) - whole) > 2:
                failures.append(f"{name}: stuknięcie w powiększone zdjęcie nie wraca do całego zdjęcia")
            if not await immersive():
                failures.append(f"{name}: stuknięcie w powiększone zdjęcie wychodzi z pełnego ekranu (powinno najpierw pomniejszyć)")
        # Ponowne stuknięcie w zdjęcie wraca do zwykłego podglądu (nie zamyka go).
        await page.touchscreen.tap(*await centre(page, ".lb__img"))
        await page.wait_for_timeout(300)
        if await immersive():
            failures.append(f"{name}: stuknięcie w zdjęcie na pełnym ekranie nie wraca do zwykłego podglądu")
        if not await page.evaluate("document.querySelector('dialog.lb').open"):
            failures.append(f"{name}: stuknięcie na pełnym ekranie zamyka podgląd zamiast wrócić do niego")
            await ctx.close()
            return
    # Na pełnym ekranie stuknięcie w czarne pole obok zdjęcia też wraca do podglądu, nie zamyka go.
    await page.touchscreen.tap(*await centre(page, ".lb__img"))
    await page.wait_for_timeout(300)
    await page.touchscreen.tap(width / 2, 12)
    await page.wait_for_timeout(400)
    if not await page.evaluate("document.querySelector('dialog.lb').open"):
        failures.append(f"{name}: stuknięcie obok zdjęcia na pełnym ekranie zamyka podgląd")
        await ctx.close()
        return
    if await immersive():
        failures.append(f"{name}: na końcu podgląd nadal jest na pełnym ekranie")
        await ctx.close()
        return
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


async def check_desktop(browser, url, photos, failures):
    total = len(photos)
    zoomable, flat = split_by_zoom(photos)
    width = "document.querySelector('.lb__img').getBoundingClientRect().width"
    page = await browser.new_page(viewport={"width": 1440, "height": 900})
    await page.goto(url, wait_until="networkidle")

    # Powiększenie do szerokości okna: przyciskiem i kliknięciem w zdjęcie.
    # Sprawdzane zaraz po pierwszym otwarciu, zanim zdjęcie trafi do pamięci przeglądarki.
    if zoomable is None:
        print("Uwaga: w tej galerii nie ma zdjęcia, które dałoby się powiększyć; powiększanie niesprawdzone.")
    else:
        await page.click(f".photos a >> nth={zoomable}")
        try:
            await page.wait_for_selector(".lb__zoom", state="visible", timeout=5000)
        except Exception:
            failures.append("komputer: po pierwszym otwarciu zdjęcia nie pojawia się przycisk Powiększ")
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
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)

    # Szerokie zdjęcie prawie wypełnia okno; przycisk, który nic nie daje, ma się nie pokazywać.
    if flat is not None:
        await page.click(f".photos a >> nth={flat}")
        await page.wait_for_function(
            "(() => { const i = document.querySelector('.lb__img'); return i.complete && i.naturalWidth > 0; })()", timeout=5000)
        await page.wait_for_timeout(200)
        if await page.locator(".lb__zoom").is_visible():
            fitted = await page.evaluate(width)
            await page.click(".lb__zoom")
            if await page.evaluate(width) < fitted * 1.2:
                failures.append("komputer: przycisk Powiększ pokazuje się przy zdjęciu, którego prawie nie powiększa")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)

    # Pełny ekran przyciskiem w rogu, powrót kliknięciem w zdjęcie.
    fs_on = ("(() => !!(document.fullscreenElement || document.webkitFullscreenElement)"
             " && document.querySelector('dialog.lb').classList.contains('is-immersive'))()")
    await page.click(".photos a")
    if not await page.locator(".lb__fs").is_visible():
        failures.append("komputer: brak przycisku pełnego ekranu")
    else:
        await page.click(".lb__fs")
        try:
            await page.wait_for_function(fs_on, timeout=3000)
        except Exception:
            failures.append("komputer: przycisk w rogu nie włącza pełnego ekranu")
        else:
            if not await page.locator(".lb__fs").is_visible() or not await page.locator(".lb__next").is_visible():
                failures.append("komputer: na pełnym ekranie brakuje przycisku w rogu albo strzałek")
            if await page.locator(".lb__close").is_visible():
                failures.append("komputer: na pełnym ekranie nie powinno być paska z napisami")
            # Na pełny ekran ma przejść warstwa wewnątrz podglądu. Gdy przechodziła cała
            # strona, przeglądarka rysowała ją na wierzchu i zasłaniała zdjęcie, choć
            # wszystkie inne sprawdzenia przechodziły.
            if not await page.evaluate("document.querySelector('dialog.lb').contains(document.fullscreenElement)"):
                failures.append("komputer: na pełny ekran przechodzi cała strona i przykrywa zdjęcie")
            await page.click(".lb__next")
            if await page.inner_text(".lb__count") != f"2 z {total}":
                failures.append("komputer: na pełnym ekranie strzałka następne nie działa")
            # Kółko myszy powiększa, kliknięcie w powiększone zdjęcie wraca do całego.
            await page.wait_for_timeout(300)
            whole = await page.evaluate(IMG_WIDTH)
            await page.mouse.move(720, 450)
            for _ in range(6):
                await page.mouse.wheel(0, -120)
                await page.wait_for_timeout(30)
            if await page.evaluate(IMG_WIDTH) < whole * 1.5:
                failures.append("komputer: na pełnym ekranie kółko myszy nie powiększa zdjęcia")
            else:
                await page.mouse.down()
                await page.mouse.move(520, 450, steps=5)
                await page.mouse.up()
                if not await page.evaluate(fs_on):
                    failures.append("komputer: przeciągnięcie powiększonego zdjęcia wychodzi z pełnego ekranu")
                await page.wait_for_timeout(350)
                await page.mouse.click(720, 450)
                await page.wait_for_timeout(200)
                if abs(await page.evaluate(IMG_WIDTH) - whole) > 2:
                    failures.append("komputer: kliknięcie w powiększone zdjęcie nie wraca do całego zdjęcia")
                if not await page.evaluate(fs_on):
                    failures.append("komputer: kliknięcie w powiększone zdjęcie wychodzi z pełnego ekranu (powinno najpierw pomniejszyć)")
            await page.click(".lb__img")
            try:
                await page.wait_for_function(f"!{fs_on}", timeout=3000)
            except Exception:
                failures.append("komputer: kliknięcie w zdjęcie na pełnym ekranie nie wraca do zwykłego podglądu")
            if not await page.evaluate("document.querySelector('dialog.lb').open"):
                failures.append("komputer: kliknięcie na pełnym ekranie zamyka podgląd zamiast wrócić do niego")
            # Zamknięcie podglądu na pełnym ekranie wyłącza też pełny ekran przeglądarki.
            await page.click(".lb__fs")
            await page.wait_for_function(fs_on, timeout=3000)
            await page.evaluate("document.querySelector('dialog.lb').close()")
            await page.wait_for_timeout(300)
            if await page.evaluate("!!document.fullscreenElement"):
                failures.append("komputer: po zamknięciu podglądu przeglądarka zostaje na pełnym ekranie")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)

    await page.click(".photos a")
    await page.click(".lb__next")
    if await page.inner_text(".lb__count") != f"2 z {total}":
        failures.append("komputer: kliknięcie strzałki następne nie działa")
    await page.keyboard.press("ArrowLeft")
    if await page.inner_text(".lb__count") != f"1 z {total}":
        failures.append("komputer: klawisz strzałki w lewo nie działa")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)
    if await page.evaluate("document.querySelector('dialog.lb').open"):
        failures.append("komputer: Escape nie zamyka podglądu")
    await page.close()


async def main() -> None:
    gallery, photos = find_gallery()
    total = len(photos)
    url = f"{serve()}/{gallery}/"
    failures: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height in [(360, 740), (390, 844), (844, 390), (820, 1180)]:
            await check_touch(browser, url, total, width, height, failures)
        await check_desktop(browser, url, photos, failures)
        await check_no_avif(browser, url, failures)
        await browser.close()
    if failures:
        print("Podgląd zdjęć NIE działa poprawnie:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print(f"Podgląd zdjęć działa (galeria „{gallery}”, {total} zdjęcia): pełny ekran z powiększaniem, strzałki, przesuwanie palcem, mysz, klawiatura, powiększanie, zapas dla urządzeń bez AVIF.")


if __name__ == "__main__":
    asyncio.run(main())
