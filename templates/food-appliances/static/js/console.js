/* food-appliances, вариант B step-console: таймеры по времени из шага источника и отметки шагов
   (localStorage, ключи fab.*). Без этого файла страница полностью читается. */
(function () {
  "use strict";
  document.querySelectorAll(".timer").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () {
      if (b._t) { clearInterval(b._t); b._t = null; b.removeAttribute("data-running"); b.textContent = "Таймер " + b.dataset.minutes + " мин"; return; }
      var left = parseInt(b.dataset.minutes, 10) * 60;
      b.setAttribute("data-running", "");
      var tick = function () {
        var m = Math.floor(left / 60), s = left % 60;
        b.textContent = "Осталось " + m + ":" + (s < 10 ? "0" : "") + s + " · стоп";
        if (left-- <= 0) { clearInterval(b._t); b._t = null; b.textContent = "Время вышло — проверьте блюдо"; b.removeAttribute("data-running"); }
      };
      tick(); b._t = setInterval(tick, 1000);
    });
  });
  var list = document.querySelector("[data-steps]");
  if (list) {
    var key = "fab.steps." + list.getAttribute("data-steps"), checks = list.querySelectorAll("[data-step-done]");
    var prog = document.querySelector("[data-progress]"), reset = document.querySelector("[data-steps-reset]");
    var saved = [];
    try { saved = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { saved = []; }
    var sync = function (save) {
      var d = []; checks.forEach(function (c) { if (c.checked) d.push(c.getAttribute("data-step-done")); });
      if (save) { try { localStorage.setItem(key, JSON.stringify(d)); } catch (e) { /* приватный режим */ } }
      prog.textContent = d.length === checks.length ? "Все шаги отмечены." : d.length ? "Сделано шагов: " + d.length + " из " + checks.length + "." : "";
      reset.hidden = d.length === 0;
    };
    checks.forEach(function (c) { c.closest("label").hidden = false; c.checked = saved.indexOf(c.getAttribute("data-step-done")) >= 0; c.addEventListener("change", function () { sync(true); }); });
    reset.addEventListener("click", function () { checks.forEach(function (c) { c.checked = false; }); sync(true); checks[0].focus(); });
    sync(false);
  }
  /* ---- очередь на прибор (перенесено из C): память выбора, счётчик, пустой выбор не отправляется, отметки «готово» ---- */
  var qread = function (k, d) { try { var v = localStorage.getItem("fab." + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  var qwrite = function (k, v) { try { localStorage.setItem("fab." + k, JSON.stringify(v)); } catch (e) { /* приватный режим */ } };
  var picked = new URLSearchParams(location.search).getAll("r");
  if (location.pathname === "/ochered/" && picked.length) qwrite("queue", picked);
  var saved = qread("queue", []);
  if (saved.length) document.querySelectorAll("[data-q-link]").forEach(function (a) { a.href = "/ochered/?" + saved.map(function (s) { return "r=" + encodeURIComponent(s); }).join("&"); });
  document.querySelectorAll("[data-q-form]").forEach(function (f) {
    var boxes = f.querySelectorAll("input[name=r]"), out = f.querySelector("[data-q-count]");
    if (!picked.length && saved.length) boxes.forEach(function (b) { b.checked = saved.indexOf(b.value) !== -1; });
    var upd = function () { var n = 0; boxes.forEach(function (b) { if (b.checked) n++; }); out.textContent = n ? "Отмечено: " + n : "Отметьте хотя бы один рецепт"; return n; };
    f.addEventListener("change", upd); upd();
    f.addEventListener("submit", function (e) { if (!upd()) { e.preventDefault(); boxes[0].focus(); } });
  });
  var dones = document.querySelectorAll("[data-done]");
  if (dones.length) {
    var d0 = qread("done", []);
    dones.forEach(function (b) {
      b.hidden = false; b.checked = d0.indexOf(b.getAttribute("data-done")) !== -1;
      b.addEventListener("change", function () {
        var d = []; dones.forEach(function (x) { if (x.checked) d.push(x.getAttribute("data-done")); }); qwrite("done", d);
      });
    });
  }
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
