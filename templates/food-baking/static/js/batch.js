/* food-baking, вариант bake-batch: таймеры из источника, выбор рецептов и отметки купленного (ключи fbc.*).
   Без этого файла страница полностью читается. */
(function () {
  "use strict";
  var box = document.querySelector("[data-timers]");
  if (box) {
    box.hidden = false;
    box.addEventListener("click", function (e) {
      var b = e.target.closest(".timer"); if (!b) return;
      if (b._t) { clearInterval(b._t); b._t = null; b.removeAttribute("data-running"); b.textContent = "Таймер " + b.dataset.minutes + " мин"; return; }
      var left = parseInt(b.dataset.minutes, 10) * 60;
      b.setAttribute("data-running", "");
      var tick = function () {
        var m = Math.floor(left / 60), s = left % 60;
        b.textContent = "Осталось " + m + ":" + (s < 10 ? "0" : "") + s + " · стоп";
        if (left-- <= 0) { clearInterval(b._t); b._t = null; b.textContent = "Время вышло — проверьте выпечку"; b.removeAttribute("data-running"); }
      };
      tick(); b._t = setInterval(tick, 1000);
    });
  }
  var f = document.querySelector("[data-autosubmit]");
  if (f) f.addEventListener("change", function () { f.submit(); });
  var ns = document.body.getAttribute("data-ns") || "fbc";
  function read(k, d) { try { var v = localStorage.getItem(ns + "." + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + "." + k, JSON.stringify(v)); } catch (e) { /* приватный режим */ } }
  var picked = new URLSearchParams(location.search).getAll("r");
  if (location.pathname === "/pechem/" && picked.length) write("batch", picked);
  var saved = read("batch", []);
  if (saved.length) document.querySelectorAll("[data-b-link]").forEach(function (a) { a.href = "/pechem/?" + saved.map(function (s) { return "r=" + encodeURIComponent(s); }).join("&"); });
  document.querySelectorAll("[data-b-form]").forEach(function (fm) {
    var boxes = fm.querySelectorAll("input[name=r]"), out = fm.querySelector("[data-b-count]");
    if (!picked.length && saved.length) boxes.forEach(function (b) { b.checked = saved.indexOf(b.value) !== -1; });
    var upd = function () { var n = 0; boxes.forEach(function (b) { if (b.checked) n++; }); out.textContent = n ? "Отмечено: " + n : "Отметьте хотя бы один рецепт"; return n; };
    fm.addEventListener("change", upd); upd();
    fm.addEventListener("submit", function (e) { if (!upd()) { e.preventDefault(); boxes[0].focus(); } });
  });
  var bl = document.querySelector("[data-blist]");
  if (bl) {
    var key = "bought." + location.search, got = read(key, []);
    bl.querySelectorAll("input").forEach(function (cb) {
      cb.checked = got.indexOf(cb.value) !== -1;
      cb.addEventListener("change", function () { var v = []; bl.querySelectorAll("input:checked").forEach(function (x) { v.push(x.value); }); write(key, v); });
    });
  }
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
