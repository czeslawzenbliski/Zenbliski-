/* zenbliski.pl: menu na telefonie i podgląd zdjęć. Bez zewnętrznych bibliotek. */
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
    '<div class="lb__bar"><span class="lb__count" aria-live="polite"></span>' +
    '<span class="lb__tools"><button class="lb__zoom" type="button" aria-pressed="false" hidden>Powiększ</button>' +
    '<button class="lb__close" type="button">Zamknij</button></span></div>' +
    '<div class="lb__stage"><img class="lb__img" alt=""></div>' +
    '<button class="lb__prev" type="button" aria-label="Poprzednie zdjęcie"></button>' +
    '<button class="lb__next" type="button" aria-label="Następne zdjęcie"></button>' +
    '<p class="lb__caption"></p>';
  document.body.appendChild(dialog);

  var img = dialog.querySelector(".lb__img");
  var count = dialog.querySelector(".lb__count");
  var caption = dialog.querySelector(".lb__caption");
  var prev = dialog.querySelector(".lb__prev");
  var next = dialog.querySelector(".lb__next");
  var stage = dialog.querySelector(".lb__stage");
  var zoomBtn = dialog.querySelector(".lb__zoom");
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

  // Przycisk ma sens tylko wtedy, gdy zdjęcie jest wyraźnie większe niż jego widok.
  function refreshZoom() {
    if (!dialog.open || isFull()) return;
    var can = finePointer && img.clientWidth > 0 && (Number(links[current].dataset.w) || 0) > img.clientWidth * 1.2;
    zoomBtn.hidden = !can;
    dialog.classList.toggle("can-zoom", can);
  }

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
  stage.addEventListener("click", function (e) { if (e.target === stage) dialog.close(); });

  zoomBtn.addEventListener("click", function () { setFull(!isFull()); });
  img.addEventListener("click", function (e) {
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
    if (e.key === "ArrowLeft") show(current - 1);
    if (e.key === "ArrowRight") show(current + 1);
    if (!isFull()) return;
    // W powiększeniu klawisze przewijają zdjęcie w pionie.
    var step = { ArrowDown: 120, ArrowUp: -120, PageDown: stage.clientHeight * 0.9, PageUp: -stage.clientHeight * 0.9 }[e.key];
    if (step) { stage.scrollBy(0, step); e.preventDefault(); }
  });

  dialog.addEventListener("close", function () {
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

  var touch = null;
  dialog.addEventListener("touchstart", function (e) {
    // Jeden palec i brak powiększenia; dwa palce to powiększanie zdjęcia.
    touch = e.touches.length === 1 && !zoomed() && !isFull()
      ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
      : null;
  }, { passive: true });
  dialog.addEventListener("touchend", function (e) {
    if (!touch || e.touches.length) { touch = null; return; }
    var t = e.changedTouches[0];
    var dx = t.clientX - touch.x;
    var dy = t.clientY - touch.y;
    touch = null;
    if (links.length < 2) return;
    // Wyraźny ruch w poziomie: w lewo następne zdjęcie, w prawo poprzednie.
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) show(current + (dx < 0 ? 1 : -1));
  }, { passive: true });
  dialog.addEventListener("touchcancel", function () { touch = null; }, { passive: true });
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

  // ----------------------------------------------------------------- start
  var gridEl = document.querySelector("[data-lightbox]");
  var vaultEl = document.querySelector("[data-vault]");
  if (vaultEl && gridEl) initVault(vaultEl, gridEl);
  else if (gridEl) initGallery(gridEl);
})();
