/* games-story (chapter-guides): прогресс по главе, сводка прогресса по главам, плеер по нажатию, печать. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "gst-atlas";
  function read(k, d) { try { var v = localStorage.getItem(ns + ":" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + ":" + k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  var g = document.querySelector(".guide[data-slug]");
  if (g) {
    var key = "check:" + g.getAttribute("data-slug") + ":v" + g.getAttribute("data-version");
    var boxes = g.querySelectorAll("[data-check]"), status = g.querySelector("[data-check-status]"), reset = g.querySelector("[data-check-reset]");
    var state = read(key, []);
    var sync = function (save) {
      var done = []; boxes.forEach(function (b) { if (b.checked) done.push(b.getAttribute("data-check")); });
      if (save && !write(key, done)) { status.textContent = "Прогресс не сохраняется: хранилище браузера недоступно."; return; }
      status.textContent = done.length ? "Отмечено " + done.length + " из " + boxes.length + "." : ""; reset.hidden = done.length === 0;
    };
    boxes.forEach(function (b) { b.checked = state.indexOf(b.getAttribute("data-check")) !== -1; b.addEventListener("change", function () { sync(true); }); });
    reset.addEventListener("click", function () { boxes.forEach(function (b) { b.checked = false; }); sync(true); });
    sync(false);
  }
  document.querySelectorAll(".gc[data-slug]").forEach(function (c) {
    var done = read("check:" + c.getAttribute("data-slug") + ":v" + c.getAttribute("data-version"), []);
    var total = +c.getAttribute("data-total"), p = c.querySelector("[data-progress]");
    if (done.length) { p.hidden = false; p.textContent = done.length === total ? "Пройдено полностью" : "Прогресс: " + done.length + " из " + total; }
  });
  document.querySelectorAll(".vid[data-vid]").forEach(function (f) {
    var b = f.querySelector("[data-play]"); b.hidden = false;
    b.addEventListener("click", function () {
      var i = document.createElement("iframe");
      i.src = "https://www.youtube-nocookie.com/embed/" + f.getAttribute("data-vid");
      i.title = f.querySelector("b").textContent; i.allow = "encrypted-media; picture-in-picture"; i.allowFullscreen = true;
      i.loading = "lazy"; i.className = "vid__frame"; b.replaceWith(i);
    });
  });
  document.querySelectorAll("[data-print]").forEach(function (b) { b.hidden = false; b.addEventListener("click", function () { window.print(); }); });

  // Общий счётчик на главной (идея варианта B): клубники, стороны, главы целиком — из чек-листов глав
  document.querySelectorAll("[data-tally]").forEach(function (box) {
    var rows; try { rows = JSON.parse(box.getAttribute("data-tally")); } catch (e) { return; }
    var red = 0, sides = 0, full = 0;
    rows.forEach(function (r) {
      var done = read("check:" + r.slug + ":v" + r.version, []);
      if (!Array.isArray(done)) return;
      if (r.berry !== null && done.indexOf(String(r.berry)) !== -1) red += r.red;
      r.sides.forEach(function (i) { if (done.indexOf(String(i)) !== -1) sides++; });
      if (r.total && done.length >= r.total) full++;
    });
    box.querySelector("[data-stat=red]").textContent = red;
    box.querySelector("[data-stat=sides]").textContent = sides;
    box.querySelector("[data-stat=full]").textContent = full;
  });

  // «Где я?»: фильтр чекпоинтов на лету (без JS работает форма)
  var f = document.querySelector("[data-cp-filter]");
  if (f) {
    var items = document.querySelectorAll("[data-cp]"), out = document.querySelector("[data-cp-count]");
    var forms = function (n) { var a = n % 100, b = n % 10; return a > 10 && a < 20 ? "чекпоинтов" : b === 1 ? "чекпоинт" : b > 1 && b < 5 ? "чекпоинта" : "чекпоинтов"; };
    f.addEventListener("input", function () {
      var q = f.value.trim().toLowerCase(), n = 0;
      items.forEach(function (li) { var on = !q || li.getAttribute("data-cp").indexOf(q) !== -1; li.hidden = !on; if (on) n++; });
      out.textContent = n + " " + forms(n);
    });
  }
})();
