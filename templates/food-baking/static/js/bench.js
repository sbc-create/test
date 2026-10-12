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
})();
