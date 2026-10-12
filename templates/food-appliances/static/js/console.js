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
})();
