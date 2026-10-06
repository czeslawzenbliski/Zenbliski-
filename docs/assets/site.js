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
  var grid = document.querySelector("[data-lightbox]");
  if (!grid || typeof HTMLDialogElement === "undefined") return;

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

  function show(i) {
    current = (i + links.length) % links.length;
    var a = links[current];
    var thumb = a.querySelector("img");
    dialog.classList.remove("is-fallback");
    img.src = a.href;
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
    if (!single) new Image().src = links[(current + 1) % links.length].href;
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
    var thumb = links[current].querySelector("img");
    var fallback = thumb && (thumb.currentSrc || thumb.src);
    if (fallback && img.getAttribute("src") && img.src !== fallback) {
      dialog.classList.add("is-fallback");
      img.src = fallback;
    }
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
})();
