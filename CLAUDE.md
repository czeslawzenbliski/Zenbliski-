# zenbliski.pl

Osobista strona fotograficzna Czesława (dawniej fotohobbypl.com na WebWave).
Statyczna, bez zewnętrznych zależności, publikowana przez GitHub Pages z katalogu `docs/` gałęzi `main`.

Właściciel nie jest programistą. Rozmawiaj po polsku, konkretnie, bez żargonu.
Zmiany na stronie wprowadzasz i publikujesz sam; jego rolą jest dostarczyć zdjęcia i teksty oraz obejrzeć efekt.

## Układ repozytorium

- `content/site.json` – cała struktura: działy, galerie, tytuły, opisy. Jedyne źródło prawdy o nawigacji.
- `content/teksty/<ścieżka z "--" zamiast "/">.html` – opcjonalna treść podstrony (fragment HTML), np. `kolekcja--mamiya-c330s.html`.
- `build.py` – generator. Czyta `content/` i manifesty zdjęć, zapisuje HTML do `docs/` oraz spis dla wyszukiwarki `docs/szukaj.json`. Tylko biblioteka standardowa.
- `tools/add_photos.py` – zmniejsza zdjęcia, robi miniatury, usuwa EXIF, dopisuje do manifestu galerii. Duże zdjęcie zapisuje jako AVIF, miniaturę jako WebP. Wymaga Pillow z obsługą AVIF.
- `tools/check_viewer.py` – test podglądu zdjęć (dotyk, mysz, klawiatura). Wymaga Playwrighta.
- `tools/vault.py` – szyfrowanie galerii na hasło; `tools/check_protected.py` – test takiej galerii od początku do końca.
- `tools/check_search.py` – test wyszukiwarki (komputer i telefon). Wymaga Playwrighta.
- `docs/` – to, co widzi świat. HTML jest generowany, nie edytuj go ręcznie.
  - `docs/assets/` – `style.css`, `site.js`, fonty (edytowane ręcznie).
  - `docs/zdjecia/<ścieżka>/` – zdjęcia galerii, miniatury w `mini/`, manifest `index.json` (tu wpisuje się podpisy: pole `caption`).

## Typowe zadania

Dodanie zdjęć do galerii:

    python3 tools/add_photos.py archiwalne/gucin /ścieżka/do/oryginałów
    python3 build.py

Dział Materiały reklamowe ma trzy poddziały: `foldery-i-prospekty` (po 1945 roku, wszystkie firmy, tytuł galerii to marka i model), `reklama-do-1945` (foldery, cenniki i ogłoszenia do 1945 roku; epoka ma pierwszeństwo przed rodzajem materiału) i `gadzety-reklamowe` (przedmioty z logo). Nową galerię dopisz jako dziecko właściwego poddziału, np. `materialy-reklamowe/foldery-i-prospekty/praktica-lb2`.

Dział Kolekcja ma dwa poddziały: `aparaty` (jedna galeria na model, np. `kolekcja/aparaty/nikon-f2a`) i `na-przestrzeni-lat` (zdjęcia witryny z kolekcją, jedna galeria na datę, tytuł np. „Styczeń 2026”, slug `2026-styczen`; nowe daty dopisuj na końcu, kolejność od najstarszej). Panoramy półek dodawaj z `--edge=3600`, bo są bardzo szerokie.

Skany z drobnym tekstem (prospekty w dziale Materiały reklamowe) dodawaj z `--edge=2400`, żeby tekst był ostry po powiększeniu.
Do czytania służy w podglądzie przycisk „Powiększ” (na komputerze) albo powiększenie dwoma palcami (na telefonie).

Pełny ekran w podglądzie: na telefonie i tablecie stuknięcie w miniaturę otwiera zdjęcie od razu na pełnym ekranie (bez przycisków, przesuwanie palcem działa), stuknięcie w zdjęcie wraca do zwykłego podglądu. Na komputerze przycisk z ikoną w prawym górnym rogu (albo klawisz F), powrót kliknięciem w zdjęcie lub Esc. Na pełny ekran przechodzi warstwa `.lb__frame` wewnątrz okna podglądu, nie cała strona (strona przykryłaby zdjęcie). iPhone nie pozwala stronom chować paska Safari, więc tam zdjęcie zajmuje całe okno przeglądarki.

Nowa galeria lub dział: dopisz wpis w `content/site.json`, potem `python3 build.py`.
Pola wpisu: `slug`, `title`, opcjonalnie `lead`, `kind` (`gallery` domyślnie albo `text`), `plate` (metryczka: aparat, obiektyw, film), `cover` (nazwa pliku okładki), `cover_pos` (przesunięcie kadru okładki, np. `50% 20%`), `unit` (`strona` dla skanów prospektów, wtedy licznik pokazuje „8 stron”), `empty` (tekst pustej strony), `keywords` (lista słów, po których stronę ma znajdować wyszukiwarka, niewidoczna na stronie), `children`.

Po każdej zmianie: uruchom `build.py`, obejrzyj wynik w przeglądarce (komputer i telefon), dopiero potem commit i push do `main`.

Po zmianach w `docs/assets/site.js` albo w stylach podglądu zdjęć (`.lb…`) uruchom też `python3 tools/check_viewer.py`.
Skrypt stuka w strzałki i przesuwa palcem tak jak człowiek na telefonie. Sam zrzut ekranu tego nie wykaże: pierwsza wersja podglądu wyglądała dobrze, a na telefonie nie działała.

## Wyszukiwarka

Pole z lupką na stronie głównej. Działa w całości w przeglądarce: `build.py` zapisuje spis `docs/szukaj.json`, a `site.js` (funkcja `initSearch`) go przeszukuje. Żadnej zewnętrznej usługi.

- Szuka tylko w tekście: tytuły, opisy (`lead`), metryczki (`plate`: aparat, obiektyw, film), słowa kluczowe (`keywords`), podpisy zdjęć (`caption` w manifeście galerii) i treść z `content/teksty/`. Tego, co widać wyłącznie na zdjęciu, nie znajdzie.
- Żeby galerię dało się znaleźć po czymś, czego nie ma w tytule (np. po nazwie filmu albo po markach widocznych na zdjęciach), dopisz to w `plate`, w podpisach albo w `keywords`. Słowa podaje właściciel; nie wymyślaj ich.
- Z galerii na hasło do spisu trafia tylko to, co jawne (tytuł, opis). Podpisy jej zdjęć są zaszyfrowane.
- Po zmianach w `initSearch`, w stylach `.search…` albo w `search_index` w `build.py` uruchom `python3 tools/check_search.py`.

## Galerie na hasło

Dla zdjęć, których nie mają oglądać postronni (u właściciela: rodzinne zdjęcia z ludźmi). Repozytorium i strona są publiczne, więc takie zdjęcia trafiają tu wyłącznie zaszyfrowane, a przeglądarka odszyfrowuje je po wpisaniu hasła. Szczegóły w `tools/vault.py`.

    HASLO_GALERII='...' python3 tools/add_photos.py --protect <ścieżka-galerii> /ścieżka/do/oryginałów
    python3 build.py

- Galerię trzeba najpierw dopisać w `content/site.json` jak każdą inną. `--protect` jest potrzebne tylko przy zakładaniu; przy kolejnych dodaniach wystarczy hasło.
- Hasło podaje właściciel w rozmowie. Nigdy nie zapisuj go w repozytorium, w komunikacie commita, w dokumentach projektu ani w pamięci. Bez hasła nie da się dodać zdjęć do istniejącej galerii, więc poproś o nie.
- Hasło musi być długie (kilka przypadkowych słów, minimum 12 znaków). Zaszyfrowane pliki są publiczne i każdy może zgadywać hasło u siebie bez ograniczeń; narzędzie odrzuca krótsze.
- Oryginały i odszyfrowane kopie trzymaj poza repozytorium (katalog roboczy sesji). Przed commitem sprawdź `git status`: w katalogu galerii mają być tylko `lock.json` i pliki `*.bin`.
- Galeria na hasło nie ma okładki ani licznika; na listach widać przy niej „na hasło”. Tytuł, opis i ewentualny tekst z `content/teksty/` pozostają jawne.
- Nie da się mieszać w jednej galerii zdjęć jawnych i zaszyfrowanych.
- Zmiana hasła nie zabezpieczy zdjęć dodanych wcześniej: stare zaszyfrowane pliki zostają w historii repozytorium i otwiera je stare hasło. Powiedz to właścicielowi, jeśli hasło wycieknie.
- Po zmianach w `tools/vault.py`, w trybie `--protect` albo w części „galeria na hasło” pliku `site.js` uruchom `python3 tools/check_protected.py` oraz `python3 tools/check_viewer.py`.

## Zasady

- Format zdjęć: duże w AVIF (jakość 68), miniatury w WebP (jakość 80). Ustawienia dobrane pomiarem tak, żeby wierność nie była niższa niż JPEG 85/78, przy ok. 40% mniejszej wadze. Nie obniżaj jakości „na oko”; właścicielowi zależy na braku widocznej straty. Miniatury zostają w WebP, bo starsze urządzenia nie otwierają AVIF i pokazują wtedy w podglądzie miniaturę.
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
