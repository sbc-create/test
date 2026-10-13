/* food-baking, вариант B oven-bench: таймеры по времени из источника, отметки «отвешено» и шагов
   (localStorage, ключи fbb.*). Без этого файла страница полностью читается. */
(function () {
  "use strict";
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  };
  document.querySelectorAll(".timer").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () {
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
  });
  var list = document.querySelector("[data-steps]");
  if (list) {
    var slug = list.getAttribute("data-steps"), key = "fbb.steps." + slug, wkey = "fbb.weigh." + slug;
    var checks = list.querySelectorAll("[data-step-done]"), weigh = document.querySelectorAll("[data-weigh]");
    var prog = document.querySelector("[data-progress]"), reset = document.querySelector("[data-steps-reset]");
    var collect = function (nodes, attr) { var d = []; nodes.forEach(function (c) { if (c.checked) d.push(c.getAttribute(attr)); }); return d; };
    var sync = function (save) {
      var d = collect(checks, "data-step-done"), w = collect(weigh, "data-weigh");
      if (save) { store.set(key, d); store.set(wkey, w); }
      prog.textContent = d.length === checks.length ? "Все шаги отмечены." : d.length ? "Сделано шагов: " + d.length + " из " + checks.length + "." : "";
      reset.hidden = d.length === 0 && w.length === 0;
    };
    var sd = store.get(key, []), sw = store.get(wkey, []);
    checks.forEach(function (c) { c.closest("label").hidden = false; c.checked = sd.indexOf(c.getAttribute("data-step-done")) >= 0; c.addEventListener("change", function () { sync(true); }); });
    weigh.forEach(function (c) { c.checked = sw.indexOf(c.getAttribute("data-weigh")) >= 0; c.addEventListener("change", function () { sync(true); }); });
    reset.addEventListener("click", function () { checks.forEach(function (c) { c.checked = false; }); weigh.forEach(function (c) { c.checked = false; }); sync(true); checks[0].focus(); });
    sync(false);
  }
  var f = document.querySelector("[data-autosubmit]");
  if (f) f.addEventListener("change", function () { f.submit(); });
  /* ---- «Пеку несколько» (перенесено из C): выбор помнится, пустой выбор не отправляется, отметки купленного ---- */
  var picked = new URLSearchParams(location.search).getAll("r");
  if (location.pathname === "/pechem/" && picked.length) store.set("fbb.batch.v1", picked);
  var saved = store.get("fbb.batch.v1", []);
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
    var bkey = "fbb.bought." + location.search, got = store.get(bkey, []);
    bl.querySelectorAll("input").forEach(function (cb) {
      cb.checked = got.indexOf(cb.value) !== -1;
      cb.addEventListener("change", function () { var v = []; bl.querySelectorAll("input:checked").forEach(function (x) { v.push(x.value); }); store.set(bkey, v); });
    });
  }
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
