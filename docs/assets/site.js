/* zenbliski.pl: menu na telefonie, podgląd zdjęć, wyszukiwarka. Bez zewnętrznych bibliotek. */
(function () {
  "use strict";

  // ------------------------------------------------------------------ menu
  var toggle = document.querySelector(".nav__toggle");
  var menu = document.getElementById("menu");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "Zamknij" : "Menu";
    });
  }

  // ------------------------------------------------------- podgląd zdjęcia
  // resolve(a, "full" | "mini") jest podawane tylko dla galerii na hasło:
  // zwraca obietnicę adresu odszyfrowanego zdjęcia zamiast zwykłego a.href.
  function initGallery(grid, resolve) {
  if (typeof HTMLDialogElement === "undefined") return;

  var links = Array.prototype.slice.call(grid.querySelectorAll("a"));
  if (!links.length) return;

  // Ostatni rząd miniatur: ta sama wysokość co rząd wyżej. Bez skryptu rząd
  // jest po prostu trochę niższy (reguła .photos::after w arkuszu stylów).
  function evenLastRow() {
    if (grid.classList.contains("photos--few")) return;
    grid.classList.remove("photos--fill");
    links.forEach(function (a) { a.style.flex = ""; });
    var lastTop = links[links.length - 1].offsetTop;
    var first = 0;
    while (links[first].offsetTop !== lastTop) first++;
    if (first === 0) return; // jest tylko jeden rząd
    var height = links[first - 1].offsetHeight;
    var gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
    var widths = links.slice(first).map(function (a) {
      return (parseFloat(getComputedStyle(a).getPropertyValue("--r")) || 1.5) * height;
    });
    var total = widths.reduce(function (sum, w) { return sum + w; }, 0) + gap * (widths.length - 1);
    if (total >= grid.clientWidth * 0.97) {
      grid.classList.add("photos--fill"); // rząd prawie pełny: niech wypełni szerokość
    } else {
      links.slice(first).forEach(function (a, i) { a.style.flex = "0 0 " + widths[i] + "px"; });
    }
  }
  var evenTimer;
  evenLastRow();
  window.addEventListener("resize", function () {
    cancelAnimationFrame(evenTimer);
    evenTimer = requestAnimationFrame(evenLastRow);
  });

  var dialog = document.createElement("dialog");
  dialog.className = "lb";
  dialog.setAttribute("aria-label", "Podgląd zdjęcia");
  dialog.innerHTML =
    '<div class="lb__frame"><div class="lb__bar"><span class="lb__count" aria-live="polite"></span>' +
    '<span class="lb__tools"><button class="lb__zoom" type="button" aria-pressed="false" hidden>Powiększ</button>' +
    '<button class="lb__fs" type="button" aria-pressed="false" aria-label="Pełny ekran" title="Pełny ekran">' +
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="square" aria-hidden="true">' +
    '<path class="lb__fs-on" d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>' +
    '<path class="lb__fs-off" d="M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5"/></svg></button>' +
    '<button class="lb__close" type="button">Zamknij</button></span></div>' +
    '<div class="lb__stage"><img class="lb__img" alt=""></div>' +
    '<button class="lb__prev" type="button" aria-label="Poprzednie zdjęcie"></button>' +
    '<button class="lb__next" type="button" aria-label="Następne zdjęcie"></button>' +
    '<p class="lb__caption"></p></div>';
  document.body.appendChild(dialog);

  var img = dialog.querySelector(".lb__img");
  var count = dialog.querySelector(".lb__count");
  var caption = dialog.querySelector(".lb__caption");
  var prev = dialog.querySelector(".lb__prev");
  var next = dialog.querySelector(".lb__next");
  var stage = dialog.querySelector(".lb__stage");
  var zoomBtn = dialog.querySelector(".lb__zoom");
  var fsBtn = dialog.querySelector(".lb__fs");
  var current = 0;

  // Powiększenie do szerokości okna, do czytania skanów z drobnym tekstem.
  // Tylko dla myszy; na ekranie dotykowym powiększa się dwoma palcami.
  var finePointer = !!window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  function isFull() { return dialog.classList.contains("is-full"); }

  function setFull(on, at) {
    dialog.classList.toggle("is-full", on);
    zoomBtn.textContent = on ? "Pomniejsz" : "Powiększ";
    zoomBtn.setAttribute("aria-pressed", String(on));
    // Po powiększeniu pokaż to miejsce, w które kliknięto.
    stage.scrollTop = on ? Math.max(0, (at || 0) * img.offsetHeight - stage.clientHeight / 2) : 0;
  }

  // Przycisk ma sens tylko wtedy, gdy powiększenie da wyraźnie większy obraz.
  // Powiększone zdjęcie ma szerokość okna (albo swoją własną, jeśli jest węższe),
  // więc szerokie zdjęcie, które już prawie wypełnia okno, nic by nie zyskało.
  function refreshZoom() {
    if (!dialog.open || isFull()) return;
    if (isImmersive()) { zoomBtn.hidden = true; dialog.classList.remove("can-zoom"); return; }
    var enlarged = Math.min(Number(links[current].dataset.w) || 0, dialog.clientWidth);
    var can = finePointer && img.clientWidth > 0 && enlarged > img.clientWidth * 1.2;
    zoomBtn.hidden = !can;
    dialog.classList.toggle("can-zoom", can);
  }

  // Pełny ekran: samo zdjęcie, bez napisów i przycisków. Kolejność jak chce właściciel:
  // miniatura → zwykły podgląd → pełny ekran → zwykły podgląd. Na telefonie i tablecie
  // pełny ekran włącza stuknięcie w zdjęcie, na komputerze przycisk w rogu.
  // Ponowne stuknięcie (kliknięcie) w zdjęcie wraca do zwykłego podglądu.
  // Gdzie przeglądarka pozwala, chowamy też jej pasek adresu (Fullscreen API).
  // iPhone na to nie pozwala: tam zdjęcie zajmuje całe okno przeglądarki.
  var root = dialog.querySelector(".lb__frame");
  var canFullscreen = !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
  var touchFirst = !finePointer;

  function fsElement() { return document.fullscreenElement || document.webkitFullscreenElement || null; }
  function quiet(result) { if (result && result.catch) result.catch(function () {}); }
  function enterFs() {
    if (!canFullscreen || fsElement()) return;
    // Na pełny ekran przechodzi warstwa wewnątrz okna podglądu: samego okna
    // dialogowego przeglądarki nie wpuszczają na pełny ekran, a cała strona
    // przykryłaby podgląd.
    try { quiet((root.requestFullscreen || root.webkitRequestFullscreen).call(root)); } catch (err) {}
  }
  function exitFs() {
    if (!fsElement()) return;
    try { quiet((document.exitFullscreen || document.webkitExitFullscreen).call(document)); } catch (err) {}
  }

  function isImmersive() { return dialog.classList.contains("is-immersive"); }
  function setImmersive(on) {
    if (on) setFull(false);
    resetZoom();
    dialog.classList.toggle("is-immersive", on);
    fsBtn.setAttribute("aria-pressed", String(on));
    fsBtn.setAttribute("aria-label", on ? "Zamknij pełny ekran" : "Pełny ekran");
    fsBtn.title = fsBtn.getAttribute("aria-label");
    if (on) enterFs(); else exitFs();
    refreshZoom();
  }
  // Wyjście z pełnego ekranu klawiszem Esc albo gestem „wstecz" na Androidzie.
  function syncFs() {
    if (!fsElement() && isImmersive()) {
      resetZoom();
      dialog.classList.remove("is-immersive");
      fsBtn.setAttribute("aria-pressed", "false");
      fsBtn.setAttribute("aria-label", "Pełny ekran");
      fsBtn.title = "Pełny ekran";
      refreshZoom();
    }
  }
  document.addEventListener("fullscreenchange", syncFs);
  document.addEventListener("webkitfullscreenchange", syncFs);

  // Zamiast dużego zdjęcia pokaż miniaturę (brak obsługi AVIF albo zerwane połączenie).
  function useThumb() {
    if (dialog.classList.contains("is-fallback")) return;
    dialog.classList.add("is-fallback");
    var token = shown;
    var thumb = links[current].querySelector("img");
    function set(url) { if (url && token === shown && dialog.open) img.src = url; }
    if (resolve) resolve(links[current], "mini").then(set, function () {});
    else set(thumb && (thumb.currentSrc || thumb.src));
  }

  var shown = 0; // numer kolejnego wyświetlenia; spóźnione odszyfrowanie nie podmieni nowszego zdjęcia

  function show(i) {
    current = (i + links.length) % links.length;
    var a = links[current];
    var thumb = a.querySelector("img");
    var token = ++shown;
    resetZoom();
    dialog.classList.remove("is-fallback");
    if (resolve) {
      img.removeAttribute("src");
      resolve(a, "full").then(
        function (url) { if (token === shown && dialog.open) img.src = url; },
        function () { if (token === shown) useThumb(); }
      );
    } else {
      img.src = a.href;
    }
    img.width = Number(a.dataset.w) || 0;
    img.height = Number(a.dataset.h) || 0;
    img.alt = thumb ? thumb.alt : "";
    img.style.setProperty("--natural", (Number(a.dataset.w) || 0) + "px");
    setFull(false);
    caption.textContent = a.dataset.caption || "";
    count.textContent = current + 1 + " z " + links.length;
    var single = links.length < 2;
    prev.hidden = single;
    next.hidden = single;
    // Wczytaj sąsiednie zdjęcie z wyprzedzeniem.
    if (!single) {
      var following = links[(current + 1) % links.length];
      if (resolve) resolve(following, "full").catch(function () {});
      else new Image().src = following.href;
    }
    refreshZoom();
  }

  function open(i) {
    show(i);
    dialog.showModal();
    refreshZoom();
  }

  links.forEach(function (a, i) {
    a.addEventListener("click", function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      open(i);
    });
  });

  prev.addEventListener("click", function () { show(current - 1); });
  next.addEventListener("click", function () { show(current + 1); });
  dialog.querySelector(".lb__close").addEventListener("click", function () { dialog.close(); });
  stage.addEventListener("click", function (e) { if (e.target === stage && !isImmersive() && !justTapped()) dialog.close(); });

  zoomBtn.addEventListener("click", function () { setFull(!isFull()); });
  fsBtn.addEventListener("click", function () { setImmersive(!isImmersive()); });
  // W pełnym ekranie stuknięcie w dowolne miejsce poza przyciskami wraca do zwykłego podglądu.
  // Stuknięcie obsłużone już przy zdarzeniu dotykowym (patrz niżej) nie może przełączyć drugi raz.
  var tapHandled = 0;
  function justTapped() { return Date.now() - tapHandled < 800; }
  dialog.addEventListener("click", function (e) {
    if (justTapped()) return;
    if (!isImmersive() || (e.target.closest && e.target.closest("button"))) return;
    if (Date.now() - dragEnded < 300) return; // koniec przeciągania myszą to nie kliknięcie
    if (magnified()) { resetZoom(); return; }
    setImmersive(false);
  });
  img.addEventListener("click", function (e) {
    if (isImmersive() || justTapped()) return; // obsługuje to słuchacz na całym podglądzie
    if (touchFirst) { e.stopPropagation(); setImmersive(true); return; }
    if (isFull()) { setFull(false); return; }
    if (!dialog.classList.contains("can-zoom")) return;
    var box = img.getBoundingClientRect();
    setFull(true, (e.clientY - box.top) / box.height);
  });
  window.addEventListener("resize", refreshZoom);
  // Zdjęcie ma znany rozmiar dopiero po wczytaniu, więc sprawdzamy jeszcze raz.
  img.addEventListener("load", refreshZoom);
  // Duże zdjęcia są w formacie AVIF. Urządzenie, które go nie otwiera (albo zerwane
  // połączenie), dostaje w podglądzie miniaturę, żeby nie zobaczyć pustego ekranu.
  img.addEventListener("error", function () {
    if (img.getAttribute("src")) useThumb();
  });

  dialog.addEventListener("keydown", function (e) {
    if ((e.key === "f" || e.key === "F") && !e.ctrlKey && !e.metaKey && !e.altKey) setImmersive(!isImmersive());
    if (isImmersive() && !e.ctrlKey && !e.metaKey) {
      var c = centreOf();
      if (e.key === "+" || e.key === "=") zoomAt(zs * 1.5, c.x, c.y);
      if (e.key === "-") zoomAt(zs / 1.5, c.x, c.y);
      if (e.key === "0") resetZoom();
    }
    if (e.key === "ArrowLeft") show(current - 1);
    if (e.key === "ArrowRight") show(current + 1);
    if (!isFull()) return;
    // W powiększeniu klawisze przewijają zdjęcie w pionie.
    var step = { ArrowDown: 120, ArrowUp: -120, PageDown: stage.clientHeight * 0.9, PageUp: -stage.clientHeight * 0.9 }[e.key];
    if (step) { stage.scrollBy(0, step); e.preventDefault(); }
  });

  dialog.addEventListener("close", function () {
    if (isImmersive()) setImmersive(false);
    shown++;
    img.removeAttribute("src");
    setFull(false);
    links[current].focus();
  });

  // Przesunięcie palcem w lewo lub w prawo. Używamy zdarzeń dotykowych, nie
  // wskaźnikowych: gdy przeglądarka uzna ruch za przewijanie, pointerup nie przychodzi.
  var viewport = window.visualViewport;
  function zoomed() { return !!viewport && viewport.scale > 1.05; }
  if (viewport) {
    viewport.addEventListener("resize", function () {
      dialog.classList.toggle("is-zoomed", zoomed());
    });
  }

  // ------------------------------------------ powiększanie na pełnym ekranie
  // Na pełnym ekranie przeglądarka nie powiększa strony dwoma palcami, a na
  // komputerze kliknięcie służy do wyjścia, więc zdjęcie powiększamy sami:
  // dwoma palcami albo kółkiem myszy; powiększone przesuwa się palcem lub myszą.
  // Stuknięcie (kliknięcie) w powiększone zdjęcie wraca do całego zdjęcia,
  // dopiero następne wychodzi z pełnego ekranu.
  var zs = 1, zx = 0, zy = 0; // skala i przesunięcie zdjęcia względem środka ekranu
  var ZOOM_MAX = 6;
  function magnified() { return zs > 1.01; }
  function applyZoom() {
    // Zdjęcie nie może odjechać tak, żeby z boku zostało puste pole.
    var mx = Math.max(0, (img.offsetWidth * zs - stage.clientWidth) / 2);
    var my = Math.max(0, (img.offsetHeight * zs - stage.clientHeight) / 2);
    zx = Math.max(-mx, Math.min(mx, zx));
    zy = Math.max(-my, Math.min(my, zy));
    img.style.transform = magnified() ? "translate(" + zx + "px," + zy + "px) scale(" + zs + ")" : "";
    dialog.classList.toggle("is-magnified", magnified());
  }
  function resetZoom() { zs = 1; zx = 0; zy = 0; applyZoom(); }
  function centreOf() {
    var r = stage.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }
  // Nowa skala s; punkt ekranu (px, py) zostaje pod palcem albo kursorem.
  function zoomAt(s, px, py) {
    s = Math.max(1, Math.min(ZOOM_MAX, s));
    var c = centreOf(), cx = px - c.x, cy = py - c.y;
    zx = cx - (cx - zx) * (s / zs);
    zy = cy - (cy - zy) * (s / zs);
    zs = s;
    if (!magnified()) { zs = 1; zx = 0; zy = 0; }
    applyZoom();
  }
  window.addEventListener("resize", function () { if (magnified()) applyZoom(); });

  // Kółko myszy.
  dialog.addEventListener("wheel", function (e) {
    if (!isImmersive()) return;
    e.preventDefault();
    var step = e.deltaMode ? e.deltaY * 33 : e.deltaY;
    zoomAt(zs * Math.exp(-step * 0.0015), e.clientX, e.clientY);
  }, { passive: false });

  // Przeciąganie powiększonego zdjęcia myszą.
  var drag = null, dragEnded = 0;
  img.addEventListener("mousedown", function (e) {
    if (!isImmersive() || !magnified() || e.button !== 0) return;
    e.preventDefault();
    drag = { x: e.clientX, y: e.clientY, zx: zx, zy: zy, moved: false };
  });
  window.addEventListener("mousemove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
    zx = drag.zx + dx;
    zy = drag.zy + dy;
    applyZoom();
  });
  window.addEventListener("mouseup", function () {
    if (drag && drag.moved) dragEnded = Date.now();
    drag = null;
  });

  // Gesty dotykowe na pełnym ekranie: dwa palce powiększają, jeden przesuwa
  // powiększone zdjęcie albo (gdy nie jest powiększone) zmienia zdjęcie.
  var g = null;
  function dist(a, b) { return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1; }
  function mid(a, b) { return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 }; }
  function pan(t, afterPinch) {
    return { pinch: false, sx: t.clientX, sy: t.clientY, x: zx, y: zy, at: Date.now(), moved: afterPinch, afterPinch: afterPinch };
  }
  function gestureStart(e) {
    var t = e.touches;
    if (t.length >= 2) g = { pinch: true, d: dist(t[0], t[1]), s: zs, m: mid(t[0], t[1]), x: zx, y: zy };
    else if (t.length === 1) g = pan(t[0], false);
  }
  function gestureMove(e) {
    var t = e.touches;
    if (g.pinch && t.length >= 2) {
      var s = Math.max(1, Math.min(ZOOM_MAX, g.s * dist(t[0], t[1]) / g.d));
      var c = centreOf(), m = mid(t[0], t[1]);
      zx = (m.x - c.x) - (g.m.x - c.x - g.x) * (s / g.s);
      zy = (m.y - c.y) - (g.m.y - c.y - g.y) * (s / g.s);
      zs = s;
      applyZoom();
    } else if (!g.pinch && t.length === 1) {
      var dx = t[0].clientX - g.sx, dy = t[0].clientY - g.sy;
      if (Math.abs(dx) > 10 || Math.abs(dy) > 10) g.moved = true;
      if (magnified()) { zx = g.x + dx; zy = g.y + dy; applyZoom(); }
    }
  }
  function gestureEnd(e) {
    if (e.touches.length === 1) { g = pan(e.touches[0], true); return; } // z dwóch palców został jeden
    if (e.touches.length) return;
    var was = g;
    g = null;
    if (zs < 1.05) resetZoom();
    if (was.pinch || was.afterPinch) return;
    var t = e.changedTouches[0];
    var dx = t.clientX - was.sx, dy = t.clientY - was.sy;
    if (!was.moved && Date.now() - was.at < 500) {
      if (t.target && t.target.closest && t.target.closest("button")) return;
      tapHandled = Date.now();
      if (magnified()) resetZoom(); else setImmersive(false);
      return;
    }
    if (magnified() || links.length < 2) return;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) show(current + (dx < 0 ? 1 : -1));
  }
  dialog.addEventListener("touchmove", function (e) { if (g) gestureMove(e); }, { passive: true });

  var touch = null;
  dialog.addEventListener("touchstart", function (e) {
    if (isImmersive()) { touch = null; gestureStart(e); return; }
    // Jeden palec i brak powiększenia; dwa palce to powiększanie zdjęcia.
    touch = e.touches.length === 1 && !zoomed() && !isFull()
      ? { x: e.touches[0].clientX, y: e.touches[0].clientY, at: Date.now() }
      : null;
  }, { passive: true });
  dialog.addEventListener("touchend", function (e) {
    if (g) { gestureEnd(e); return; }
    if (!touch || e.touches.length) { touch = null; return; }
    var t = e.changedTouches[0];
    var dx = t.clientX - touch.x;
    var dy = t.clientY - touch.y;
    var quick = Date.now() - touch.at < 500;
    touch = null;
    // Krótkie stuknięcie bez ruchu przełącza pełny ekran już tutaj. Samo zdarzenie
    // „click" przeglądarka potrafi pominąć, gdy stuknięcie wypada tuż po przesunięciu.
    if (quick && Math.abs(dx) < 10 && Math.abs(dy) < 10) {
      var el = t.target;
      if (el && el.closest && el.closest("button")) return;
      if (isImmersive()) { tapHandled = Date.now(); setImmersive(false); }
      else if (el === img) { tapHandled = Date.now(); setImmersive(true); }
      return;
    }
    if (links.length < 2) return;
    // Wyraźny ruch w poziomie: w lewo następne zdjęcie, w prawo poprzednie.
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) show(current + (dx < 0 ? 1 : -1));
  }, { passive: true });
  dialog.addEventListener("touchcancel", function () { touch = null; g = null; }, { passive: true });
  } // initGallery

  // ------------------------------------------------------ galeria na hasło
  // Zdjęcia leżą na serwerze zaszyfrowane (tools/vault.py). Hasło nie opuszcza
  // przeglądarki: służy do odszyfrowania klucza, a klucz do odszyfrowania zdjęć.
  function initVault(vault, grid) {
    var form = vault.querySelector("form");
    if (!form) return;
    var input = form.querySelector("#haslo");
    var reveal = form.querySelector("#pokaz-haslo");
    var button = form.querySelector('button[type="submit"]');
    var msg = form.querySelector(".vault__msg");
    var base = vault.dataset.vault;
    var title = vault.dataset.title || "";

    function say(text) { msg.textContent = text; msg.hidden = !text; }
    function busy(on) {
      button.disabled = on;
      button.textContent = on ? "Otwieram…" : "Otwórz galerię";
    }

    if (!window.crypto || !window.crypto.subtle || !window.TextEncoder || !window.fetch) {
      say("Ta przeglądarka nie potrafi otworzyć zaszyfrowanej galerii. Zaktualizuj ją albo użyj innej.");
      input.disabled = true;
      button.disabled = true;
      return;
    }
    var subtle = window.crypto.subtle;

    reveal.addEventListener("change", function () { input.type = reveal.checked ? "text" : "password"; });

    function bytes(b64) {
      var bin = atob(b64);
      var out = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    }
    // Każdy blok: 12 bajtów wartości jednorazowej, potem szyfrogram AES-GCM.
    function unseal(key, data) {
      return subtle.decrypt({ name: "AES-GCM", iv: data.subarray(0, 12) }, key, data.subarray(12));
    }
    function download(file) {
      return fetch(base + file, { cache: "no-cache" }).then(function (r) {
        if (!r.ok) throw new Error("network");
        return r;
      });
    }

    var lock = null;
    function loadLock() {
      if (lock) return Promise.resolve(lock);
      return download("lock.json").then(function (r) { return r.json(); }).then(function (json) { return (lock = json); });
    }

    function unlock(password) {
      var stage = "network";
      return loadLock().then(function (l) {
        stage = "password";
        return subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"])
          .then(function (material) {
            return subtle.deriveKey(
              { name: "PBKDF2", hash: "SHA-256", salt: bytes(l.salt), iterations: l.iter },
              material, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
          })
          .then(function (kek) { return unseal(kek, bytes(l.key)); })
          .then(function (raw) { return subtle.importKey("raw", raw, "AES-GCM", false, ["decrypt"]); })
          .then(function (key) {
            stage = "data";
            return unseal(key, bytes(l.manifest)).then(function (buf) {
              return { key: key, items: JSON.parse(new TextDecoder().decode(buf)) };
            });
          });
      }).catch(function (err) { err.stage = stage; throw err; });
    }

    function build(key, items) {
      vault.hidden = true;
      if (!items.length) {
        var empty = document.createElement("div");
        empty.className = "empty";
        empty.innerHTML = "<p>Zdjęcia do tej galerii są w przygotowaniu.</p>";
        vault.parentNode.insertBefore(empty, vault);
        return;
      }

      var cache = {};
      function blobUrl(file, type) {
        if (!cache[file]) {
          cache[file] = download(file)
            .then(function (r) { return r.arrayBuffer(); })
            .then(function (buf) { return unseal(key, new Uint8Array(buf)); })
            .then(function (plain) { return URL.createObjectURL(new Blob([plain], { type: type })); });
          cache[file].catch(function () { delete cache[file]; });
        }
        return cache[file];
      }
      function resolve(a, which) {
        var p = a._photo;
        return which === "mini" ? blobUrl(p.mini, p.mtype) : blobUrl(p.file, p.type);
      }

      items.forEach(function (p) {
        var a = document.createElement("a");
        a.href = "#";
        a._photo = p;
        a.style.setProperty("--r", (p.w / p.h).toFixed(4));
        a.style.aspectRatio = p.w + " / " + p.h;
        a.dataset.w = p.w;
        a.dataset.h = p.h;
        if (p.caption) a.dataset.caption = p.caption;
        var thumb = document.createElement("img");
        thumb.width = p.mw;
        thumb.height = p.mh;
        thumb.alt = p.caption || title;
        thumb.decoding = "async";
        a.appendChild(thumb);
        grid.appendChild(a);
      });
      if (items.length <= 3) grid.classList.add("photos--few");
      grid.hidden = false;

      // Miniatury odszyfrowujemy dopiero, gdy zbliżają się do ekranu.
      function loadThumb(a) {
        resolve(a, "mini").then(function (url) { a.firstChild.src = url; }, function () {});
      }
      var anchors = Array.prototype.slice.call(grid.children);
      if ("IntersectionObserver" in window) {
        var watcher = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            watcher.unobserve(entry.target);
            loadThumb(entry.target);
          });
        }, { rootMargin: "600px" });
        anchors.forEach(function (a) { watcher.observe(a); });
      } else {
        anchors.forEach(loadThumb);
      }

      initGallery(grid, resolve);
      anchors[0].focus({ preventScroll: true });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var password = input.value.normalize("NFC").trim();
      if (!password) return;
      say("");
      busy(true);
      unlock(password).then(
        function (opened) { input.value = ""; build(opened.key, opened.items); },
        function (err) {
          busy(false);
          if (err.stage === "password") {
            say("To hasło nie pasuje. Sprawdź wielkie i małe litery i spróbuj jeszcze raz.");
            input.select();
          } else if (err.stage === "data") {
            say("Galeria jest uszkodzona i nie da się jej otworzyć. Daj znać właścicielowi strony.");
          } else {
            say("Nie udało się pobrać galerii. Sprawdź połączenie z internetem i spróbuj ponownie.");
          }
        }
      );
    });
  }

  // ---------------------------------------------------------- wyszukiwarka
  // Szuka w spisie szukaj.json, który build.py układa z tytułów, opisów,
  // metryczek, podpisów zdjęć i treści wpisów. Wszystko dzieje się w przeglądarce.
  function initSearch(form) {
    if (!window.fetch || !window.Promise) return; // bardzo stara przeglądarka: pole zostaje ukryte
    var input = form.querySelector("input");
    var status = form.querySelector(".search__status");
    var list = form.querySelector(".search__results");
    var index = null, loading = null, failed = false;
    var LIMIT = 20;

    // Małe litery i bez polskich znaków, znak w znak (długość tekstu się nie zmienia).
    function fold(s) {
      s = String(s).toLowerCase().replace(/ł/g, "l");
      return s.normalize ? s.normalize("NFD").replace(/[\u0300-\u036f]/g, "") : s;
    }
    // Do porównywania: dodatkowo wszystko poza literami i cyframi staje się odstępem,
    // żeby „FED-Atlas", „fed atlas" i „3,5" / „3.5" znaczyły to samo.
    function norm(s) { return fold(s).replace(/[^a-z0-9]+/g, " ").trim(); }

    function load() {
      if (!loading) {
        loading = fetch(form.getAttribute("data-search"))
          .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
          .then(function (data) {
            index = data.map(function (e) {
              return { u: e.u, t: e.t, p: e.p, x: e.x, nt: norm(e.t), np: norm(e.p), nx: e.x.map(norm) };
            });
          })
          .catch(function () { failed = true; });
      }
      return loading;
    }

    // Każde wpisane słowo musi gdzieś wystąpić. Tytuł liczy się najbardziej,
    // potem teksty strony, na końcu nazwa działu nadrzędnego.
    function find(tokens) {
      var hits = [];
      index.forEach(function (e, order) {
        var score = 0, where = -1;
        for (var i = 0; i < tokens.length; i++) {
          var t = tokens[i], s = 0, at = e.nt.indexOf(t);
          if (at !== -1) {
            s = (at === 0 || e.nt.charAt(at - 1) === " ") ? 8 : 6;
          } else {
            for (var j = 0; j < e.nx.length && !s; j++) {
              if (e.nx[j].indexOf(t) !== -1) { s = 3; if (where === -1) where = j; }
            }
            if (!s && e.np.indexOf(t) !== -1) s = 1;
          }
          if (!s) return;
          score += s;
        }
        hits.push({ e: e, score: score, where: where, order: order });
      });
      hits.sort(function (a, b) { return b.score - a.score || a.order - b.order; });
      return hits;
    }

    // Fragment tekstu wokół znalezionego słowa.
    function excerpt(text, tokens) {
      if (text.length <= 110) return text;
      var folded = fold(text), at = -1;
      for (var i = 0; i < tokens.length && at === -1; i++) at = folded.indexOf(tokens[i]);
      var from = Math.max(0, (at === -1 ? 0 : at) - 45), to = Math.min(text.length, from + 110);
      if (from > 0) from = text.indexOf(" ", from) + 1;
      if (to < text.length) to = text.lastIndexOf(" ", to);
      return (from > 0 ? "… " : "") + text.slice(from, to) + (to < text.length ? " …" : "");
    }

    function remember(q) {
      if (!window.history || !history.replaceState) return;
      try { history.replaceState(null, "", q ? "?q=" + encodeURIComponent(q) : location.pathname); } catch (err) {}
    }

    function render() {
      var q = input.value.trim(), tokens = norm(q).split(" ").filter(Boolean);
      list.textContent = "";
      if (norm(q).length < 2) { status.textContent = ""; remember(""); return; }
      if (failed) { status.textContent = "Wyszukiwarka jest chwilowo niedostępna. Spróbuj ponownie za chwilę."; return; }
      if (!index) { status.textContent = "Szukam…"; load().then(render); return; }
      remember(q);

      var hits = find(tokens);
      if (!hits.length) { status.textContent = "Nic nie znaleziono dla „" + q + "”."; return; }
      status.textContent = "Znaleziono: " + hits.length +
        (hits.length > LIMIT ? ", poniżej pierwsze " + LIMIT + "." : "");
      hits.slice(0, LIMIT).forEach(function (h) {
        var a = document.createElement("a"), title = document.createElement("span");
        a.href = h.e.u;
        title.className = "search__title";
        title.textContent = h.e.t;
        a.appendChild(title);
        var meta = [h.e.p, h.where === -1 ? "" : excerpt(h.e.x[h.where], tokens)].filter(Boolean).join(" · ");
        if (meta) {
          var line = document.createElement("span");
          line.className = "search__meta";
          line.textContent = meta;
          a.appendChild(line);
        }
        var li = document.createElement("li");
        li.appendChild(a);
        list.appendChild(li);
      });
    }

    form.hidden = false;
    input.addEventListener("focus", load);
    input.addEventListener("input", render);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && input.value) { input.value = ""; render(); }
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      render();
      // Na telefonie schowaj klawiaturę, żeby było widać wyniki.
      if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) input.blur();
    });

    // Powrót z wyniku na stronę główną: pokaż to samo wyszukiwanie.
    var saved = /[?&]q=([^&]*)/.exec(location.search);
    if (saved) {
      try { input.value = decodeURIComponent(saved[1].replace(/\+/g, " ")); } catch (err) {}
    }
    if (input.value) render();
  }

  // ----------------------------------------------------------------- start
  var searchEl = document.querySelector("[data-search]");
  if (searchEl) initSearch(searchEl);
  var gridEl = document.querySelector("[data-lightbox]");
  var vaultEl = document.querySelector("[data-vault]");
  if (vaultEl && gridEl) initVault(vaultEl, gridEl);
  else if (gridEl) initGallery(gridEl);
})();
