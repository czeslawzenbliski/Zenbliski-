#!/usr/bin/env python3
"""Sprawdza galerie na hasło od początku do końca, na próbnej galerii.

Buduje w katalogu tymczasowym kopię strony z jedną zaszyfrowaną galerią
(sztuczne obrazy, próbne hasło) i sprawdza:

  - że na serwerze nie leży żaden plik, który da się otworzyć jako obraz,
    a strona i lock.json nie zdradzają nazw plików ani hasła,
  - że narzędzie odrzuca złe i za krótkie hasło,
  - w przeglądarce: złe hasło niczego nie pokazuje, dobre otwiera galerię,
    miniatury i duże zdjęcia się odszyfrowują, podgląd działa myszą i dotykiem,
    a gdy dużego zdjęcia nie da się pobrać, podgląd pokazuje miniaturę.

Uruchom po każdej zmianie w tools/vault.py, w trybie --protect narzędzia
add_photos.py albo w części „galeria na hasło" pliku docs/assets/site.js:

    python3 tools/check_protected.py

Niczego nie zmienia w repozytorium. Wymaga Pillow, cryptography i Playwrighta.
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parent.parent
PASSWORD = "żółw-lampa-kajak-71"   # hasło próbne, tylko do tego testu
GALLERY = "test-na-haslo"
COUNT = 5


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def serve(root: Path) -> str:
    handler = functools.partial(QuietHandler, directory=str(root))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


def run(tmp: Path, *args: str, password: str | None = PASSWORD) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("HASLO_GALERII", None)
    if password is not None:
        env["HASLO_GALERII"] = password
    return subprocess.run([sys.executable, *args], cwd=tmp, env=env, capture_output=True, text=True)


def prepare(tmp: Path) -> Path:
    """Kopia generatora z jedną próbną galerią na hasło. Zwraca katalog galerii."""
    shutil.copy(REPO / "build.py", tmp / "build.py")
    shutil.copytree(REPO / "tools", tmp / "tools")
    shutil.copytree(REPO / "content", tmp / "content")
    (tmp / "docs").mkdir()
    shutil.copytree(REPO / "docs" / "assets", tmp / "docs" / "assets")

    site_path = tmp / "content" / "site.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))
    site["sections"].insert(0, {"slug": GALLERY, "title": "Test na hasło"})
    site_path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")

    src = tmp / "src"
    src.mkdir()
    for i, (w, h) in enumerate([(3000, 2000), (2000, 3000), (3000, 2000), (2400, 2400), (3000, 1800)][:COUNT]):
        im = Image.new("RGB", (w, h), (40 + 40 * i, 90, 140 - 20 * i))
        ImageDraw.Draw(im).ellipse((w * 0.3, h * 0.3, w * 0.7, h * 0.7), fill=(230, 200, 130))
        im.save(src / f"tajne-zdjecie-{i + 1}.jpg", quality=85)
    return tmp / "docs" / "zdjecia" / GALLERY


def check_files(tmp: Path, gallery_dir: Path, failures: list[str]) -> list[dict]:
    short = run(tmp, "tools/add_photos.py", "--protect", GALLERY, "src", password="1234")
    if short.returncode == 0 or gallery_dir.exists() and any(gallery_dir.iterdir()):
        failures.append("narzędzie przyjęło za krótkie hasło")

    made = run(tmp, "tools/add_photos.py", "--protect", GALLERY, "src")
    if made.returncode != 0:
        failures.append(f"nie udało się założyć galerii na hasło: {made.stderr.strip() or made.stdout.strip()}")
        return []

    wrong = run(tmp, "tools/add_photos.py", GALLERY, "src", password="zupełnie-inne-hasło")
    if wrong.returncode == 0:
        failures.append("narzędzie dopisało zdjęcia do galerii mimo złego hasła")

    files = sorted(f.name for f in gallery_dir.iterdir())
    if "index.json" in files or any(not (n == "lock.json" or n.endswith(".bin")) for n in files):
        failures.append(f"w galerii leżą pliki inne niż lock.json i *.bin: {files}")
    if len([n for n in files if n.endswith(".bin")]) != COUNT * 2:
        failures.append(f"oczekiwano {COUNT * 2} zaszyfrowanych plików, jest {len(files) - 1}")
    for f in gallery_dir.glob("*.bin"):
        try:
            Image.open(f).verify()
            failures.append(f"plik {f.name} da się otworzyć jako obraz, czyli nie jest zaszyfrowany")
        except Exception:
            pass

    lock_text = (gallery_dir / "lock.json").read_text(encoding="utf-8")
    for secret in (PASSWORD, "tajne-zdjecie", ".bin", "avif"):
        if secret in lock_text:
            failures.append(f"lock.json zawiera jawnie „{secret}”")

    built = run(tmp, "build.py", password=None)
    if built.returncode != 0:
        failures.append(f"build.py nie zadziałał: {built.stderr.strip()}")
        return []
    page = (tmp / "docs" / GALLERY / "index.html").read_text(encoding="utf-8")
    if ".bin" in page or "tajne-zdjecie" in page or "<img" in page.split("<main", 1)[1]:
        failures.append("strona galerii zdradza nazwy plików albo zawiera zdjęcia przed podaniem hasła")
    home = (tmp / "docs" / "index.html").read_text(encoding="utf-8")
    if "na hasło" not in home:
        failures.append("na liście działów brakuje oznaczenia „na hasło”")

    sys.path.insert(0, str(tmp / "tools"))
    import vault
    return vault.unlock(gallery_dir, PASSWORD)[1]


async def unlock_in_page(page, password: str) -> None:
    await page.fill("#haslo", password)
    await page.click(".vault button[type=submit]")


async def check_browser(url: str, manifest: list[dict], failures: list[str]) -> None:
    thumbs_ready = ("(() => { const t = [...document.querySelectorAll('.photos img')];"
                    f" return t.length === {COUNT} && t.every(i => i.src.startsWith('blob:') && i.complete && i.naturalWidth > 0); }})()")
    big = "(() => { const i = document.querySelector('.lb__img'); return i.complete ? i.naturalWidth : 0; })()"

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ---- komputer
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(url, wait_until="networkidle")
        if not await page.locator(".vault form").is_visible() or await page.locator(".photos a").count():
            failures.append("komputer: przed podaniem hasła powinien być widoczny tylko formularz")

        await unlock_in_page(page, "to-nie-jest-to-hasło")
        try:
            await page.wait_for_selector(".vault__msg:not([hidden])", timeout=15000)
        except Exception:
            failures.append("komputer: po złym haśle nie pojawia się komunikat")
        if await page.locator(".photos a").count():
            failures.append("komputer: złe hasło otworzyło galerię")

        await unlock_in_page(page, f"  {PASSWORD} ")   # spacje na końcach nie powinny przeszkadzać
        try:
            await page.wait_for_function(thumbs_ready, timeout=20000)
        except Exception:
            failures.append("komputer: po dobrym haśle galeria się nie otworzyła albo miniatury się nie odszyfrowały")
            await browser.close()
            return  # dalsze kroki wymagają otwartej galerii
        if await page.locator(".vault").is_visible():
            failures.append("komputer: formularz hasła nie znika po otwarciu galerii")

        await page.click(".photos a >> nth=0")
        try:
            await page.wait_for_function(f"{big} === {manifest[0]['w']}", timeout=15000)
        except Exception:
            failures.append("komputer: duże zdjęcie nie odszyfrowało się w podglądzie")
        await page.keyboard.press("ArrowRight")
        try:
            await page.wait_for_function(f"{big} === {manifest[1]['w']}", timeout=15000)
        except Exception:
            failures.append("komputer: następne zdjęcie nie odszyfrowało się w podglądzie")
        if await page.inner_text(".lb__count") != f"2 z {COUNT}":
            failures.append("komputer: licznik podglądu nie pokazuje drugiego zdjęcia")
        await page.keyboard.press("Escape")
        if errors:
            failures.append(f"komputer: błędy skryptu: {errors}")
        await page.close()

        # ---- duże zdjęcie niedostępne: w podglądzie ma się pojawić miniatura
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        blocked = manifest[0]["file"]
        await page.route(f"**/{blocked}", lambda route: route.abort())
        await page.goto(url, wait_until="networkidle")
        await unlock_in_page(page, PASSWORD)
        await page.wait_for_selector(".photos a", timeout=20000)
        await page.click(".photos a >> nth=0")
        try:
            await page.wait_for_function(f"{big} === {manifest[0]['mw']}", timeout=15000)
        except Exception:
            failures.append("zapas: gdy dużego zdjęcia nie da się pobrać, podgląd nie pokazuje miniatury")
        await page.close()

        # ---- telefon
        ctx = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                        is_mobile=True, has_touch=True)
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await page.goto(url, wait_until="networkidle")
        overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if overflow > 0:
            failures.append("telefon: strona z formularzem przewija się w poziomie")
        await page.fill("#haslo", PASSWORD)
        await page.tap(".vault button[type=submit]")
        try:
            await page.wait_for_selector(".photos a", timeout=20000)
        except Exception:
            failures.append("telefon: galeria nie otwiera się po podaniu hasła")
        else:
            first = page.locator(".photos a").first
            await first.scroll_into_view_if_needed()
            box = await first.bounding_box()
            await page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            await page.wait_for_timeout(500)
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 320, "y": 400}]})
            for x in (260, 200, 140, 80):
                await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": 400}]})
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            await page.wait_for_timeout(400)
            if await page.inner_text(".lb__count") != f"2 z {COUNT}":
                failures.append("telefon: przesunięcie palcem nie zmienia zdjęcia w galerii na hasło")
        await ctx.close()
        await browser.close()


def main() -> None:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        gallery_dir = prepare(tmp)
        manifest = check_files(tmp, gallery_dir, failures)
        if manifest:
            asyncio.run(check_browser(f"{serve(tmp / 'docs')}/{GALLERY}/", manifest, failures))
    if failures:
        print("Galeria na hasło NIE działa poprawnie:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("Galeria na hasło działa: pliki są zaszyfrowane, złe hasło nic nie pokazuje, "
          "dobre otwiera miniatury i podgląd (komputer i telefon).")


if __name__ == "__main__":
    main()
