# zenbliski.pl

Osobista strona fotograficzna Czesława (dawniej fotohobbypl.com na WebWave).
Statyczna, bez zewnętrznych zależności, publikowana przez GitHub Pages z katalogu `docs/` gałęzi `main`.

Właściciel nie jest programistą. Rozmawiaj po polsku, konkretnie, bez żargonu.
Zmiany na stronie wprowadzasz i publikujesz sam; jego rolą jest dostarczyć zdjęcia i teksty oraz obejrzeć efekt.

## Układ repozytorium

- `content/site.json` – cała struktura: działy, galerie, tytuły, opisy. Jedyne źródło prawdy o nawigacji.
- `content/teksty/<ścieżka z "--" zamiast "/">.html` – opcjonalna treść podstrony (fragment HTML), np. `kolekcja--stan-kolekcji.html`.
- `build.py` – generator. Czyta `content/` i manifesty zdjęć, zapisuje HTML do `docs/`. Tylko biblioteka standardowa.
- `tools/add_photos.py` – zmniejsza zdjęcia, robi miniatury, usuwa EXIF, dopisuje do manifestu galerii. Wymaga Pillow.
- `tools/check_viewer.py` – test podglądu zdjęć (dotyk, mysz, klawiatura). Wymaga Playwrighta.
- `docs/` – to, co widzi świat. HTML jest generowany, nie edytuj go ręcznie.
  - `docs/assets/` – `style.css`, `site.js`, fonty (edytowane ręcznie).
  - `docs/zdjecia/<ścieżka>/` – zdjęcia galerii, miniatury w `mini/`, manifest `index.json` (tu wpisuje się podpisy: pole `caption`).

## Typowe zadania

Dodanie zdjęć do galerii:

    python3 tools/add_photos.py archiwalne/gucin /ścieżka/do/oryginałów
    python3 build.py

Skany z drobnym tekstem (prospekty w dziale Materiały reklamowe) dodawaj z `--edge=2400`, żeby tekst był ostry po powiększeniu.
Do czytania służy w podglądzie przycisk „Powiększ” (na komputerze) albo powiększenie dwoma palcami (na telefonie).

Nowa galeria lub dział: dopisz wpis w `content/site.json`, potem `python3 build.py`.
Pola wpisu: `slug`, `title`, opcjonalnie `lead`, `kind` (`gallery` domyślnie albo `text`), `plate` (metryczka: aparat, obiektyw, film), `cover` (nazwa pliku okładki), `cover_pos` (przesunięcie kadru okładki, np. `50% 20%`), `unit` (`strona` dla skanów prospektów, wtedy licznik pokazuje „8 stron”), `empty` (tekst pustej strony), `children`.

Po każdej zmianie: uruchom `build.py`, obejrzyj wynik w przeglądarce (komputer i telefon), dopiero potem commit i push do `main`.

Po zmianach w `docs/assets/site.js` albo w stylach podglądu zdjęć (`.lb…`) uruchom też `python3 tools/check_viewer.py`.
Skrypt stuka w strzałki i przesuwa palcem tak jak człowiek na telefonie. Sam zrzut ekranu tego nie wykaże: pierwsza wersja podglądu wyglądała dobrze, a na telefonie nie działała.

## Zasady

- Do repozytorium trafiają tylko zdjęcia po `add_photos.py`, nigdy oryginały ani skany w pełnej rozdzielczości. Limit GitHub Pages to 1 GB na całą stronę; skrypt wypisuje bieżące zużycie.
- Nie wymyślaj treści w imieniu właściciela: opisów zdjęć, dat, historii sprzętu. Jeśli czegoś brakuje, zostaw stan „w przygotowaniu” i zapytaj.
- Wszystkie linki wewnętrzne są względne, więc strona działa i pod adresem tymczasowym, i pod własną domeną. Wyjątkiem jest `404.html`, który korzysta z `root_path`.
- Wygląd: ciemne tło, mosiężne akcenty, nagłówki Playfair Display, tekst Jost. Fonty są hostowane lokalnie, strona nie łączy się z żadnym zewnętrznym serwerem i nie używa ciasteczek. Tak ma zostać.
- Narożniki ramki celownika (na pustych kadrach i po najechaniu na zdjęcie) to jedyny ozdobnik. Nie dokładaj kolejnych.

## Uruchomienie pod własną domeną (jeszcze niewykonane)

Do czasu przepięcia domeny strona działa pod adresem tymczasowym `https://czeslawzenbliski.github.io/Zenbliski-/` i ma wyłączone indeksowanie.
Przy przepięciu na zenbliski.pl:

1. W `content/site.json` ustaw `"root_path": "/"` i `"noindex": false`.
2. Dodaj plik `docs/CNAME` z treścią `zenbliski.pl`.
3. `python3 build.py`, commit, push.
4. Właściciel ustawia rekordy DNS u rejestratora i włącza „Enforce HTTPS” w ustawieniach Pages.
5. Rozważ strony przekierowujące ze starych adresów WebWave (`/o-nas`, `/galeria`, `/kontakt`, `/archiwum`, `/akcesoria-foto`, `/akcesoria-foto-2`, `/artykuly`, `/foto-ciekawostki`).
