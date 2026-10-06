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

  var dialog = document.createElement("dialog");
  dialog.className = "lb";
  dialog.setAttribute("aria-label", "Podgląd zdjęcia");
  dialog.innerHTML =
    '<div class="lb__bar"><span class="lb__count" aria-live="polite"></span>' +
    '<button class="lb__close" type="button">Zamknij</button></div>' +
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
  var current = 0;

  function show(i) {
    current = (i + links.length) % links.length;
    var a = links[current];
    var thumb = a.querySelector("img");
    img.src = a.href;
    img.width = Number(a.dataset.w) || 0;
    img.height = Number(a.dataset.h) || 0;
    img.alt = thumb ? thumb.alt : "";
    caption.textContent = a.dataset.caption || "";
    count.textContent = current + 1 + " z " + links.length;
    var single = links.length < 2;
    prev.hidden = single;
    next.hidden = single;
    // Wczytaj sąsiednie zdjęcie z wyprzedzeniem.
    if (!single) new Image().src = links[(current + 1) % links.length].href;
  }

  function open(i) {
    show(i);
    dialog.showModal();
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

  dialog.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") show(current - 1);
    if (e.key === "ArrowRight") show(current + 1);
  });

  dialog.addEventListener("close", function () {
    img.removeAttribute("src");
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
    touch = e.touches.length === 1 && !zoomed()
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
