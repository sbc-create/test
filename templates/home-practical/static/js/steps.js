/* home-practical (problem-checklists): пошаговый чек-лист, итоговая проверка, прогресс решений по проблеме,
   сохранённое, печать. Хранение только в браузере, ключи в пространстве имён варианта. Без JS всё читается. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "hp";
  function read(key, def) {
    try { var v = localStorage.getItem(ns + ":" + key); return v ? JSON.parse(v) : def; } catch (e) { return def; }
  }
  function write(key, val) {
    try { localStorage.setItem(ns + ":" + key, JSON.stringify(val)); return true; } catch (e) { return false; }
  }
  function saved() { var s = read("saved", []); return Array.isArray(s) ? s : []; }
  function badge() {
    var n = saved().length;
    document.querySelectorAll("[data-saved-count]").forEach(function (b) { b.textContent = n; b.hidden = n === 0; });
  }
  function bindChecks(boxes, key, attr, onChange) {
    var state = read(key, []);
    boxes.forEach(function (b) {
      b.checked = state.indexOf(b.getAttribute(attr)) !== -1;
      b.addEventListener("change", function () {
        var done = [];
        boxes.forEach(function (x) { if (x.checked) done.push(x.getAttribute(attr)); });
        write(key, done); onChange();
      });
    });
    onChange();
  }

  document.querySelectorAll("[data-save]").forEach(function (btn) {
    var slug = btn.getAttribute("data-save");
    function paint() {
      var on = saved().indexOf(slug) !== -1;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "Сохранено — убрать" : "Сохранить";
    }
    btn.hidden = false; paint();
    btn.addEventListener("click", function () {
      var s = saved(), i = s.indexOf(slug);
      if (i === -1) s.push(slug); else s.splice(i, 1);
      if (!write("saved", s)) { btn.textContent = "Не удалось сохранить: хранилище браузера недоступно"; return; }
      paint(); badge();
    });
  });

  var list = document.querySelector("[data-saved-list]");
  if (list) {
    var render = function () {
      var s = saved(), shown = 0;
      list.querySelectorAll("[data-saved-item]").forEach(function (el) {
        var on = s.indexOf(el.getAttribute("data-saved-item")) !== -1; el.hidden = !on; if (on) shown++;
      });
      document.querySelector("[data-saved-empty]").hidden = shown > 0;
      document.querySelector("[data-saved-clear]").hidden = shown === 0;
    };
    document.querySelector("[data-saved-clear]").addEventListener("click", function () { write("saved", []); render(); badge(); });
    render();
  }

  var mat = document.querySelector(".mat[data-slug]");
  if (mat) {
    var id = mat.getAttribute("data-slug") + ":v" + mat.getAttribute("data-version");
    var steps = mat.querySelectorAll("[data-step]");
    var box = mat.querySelector("[data-progress-box]"), bar = mat.querySelector("[data-progress]");
    var text = mat.querySelector("[data-progress-text]"), reset = mat.querySelector("[data-steps-reset]");
    var next = mat.querySelector("[data-next]");
    box.hidden = false;
    var paintSteps = function () {
      var n = 0; steps.forEach(function (b) { if (b.checked) n++; });
      bar.value = n;
      text.textContent = n === steps.length ? "Все шаги выполнены — переходите к итоговой проверке." : "Выполнено " + n + " из " + steps.length;
      next.textContent = n === steps.length ? "К итоговой проверке" : "Следующий шаг";
      reset.hidden = n === 0;
    };
    bindChecks(steps, "steps:" + id, "data-step", paintSteps);
    next.addEventListener("click", function () {
      var target = null;
      steps.forEach(function (b) { if (!target && !b.checked) target = b.closest("li"); });
      target = target || document.getElementById("itog");
      target.setAttribute("tabindex", "-1");
      target.scrollIntoView({ block: "center" });
      target.focus({ preventScroll: true });
    });
    reset.addEventListener("click", function () {
      steps.forEach(function (b) { b.checked = false; }); write("steps:" + id, []); paintSteps();
    });
    var checks = mat.querySelectorAll("[data-check]"), status = mat.querySelector("[data-check-status]");
    bindChecks(checks, "check:" + id, "data-check", function () {
      var n = 0; checks.forEach(function (b) { if (b.checked) n++; });
      status.textContent = n === checks.length ? "Готово: все пункты проверены." : n ? "Проверено " + n + " из " + checks.length + "." : "";
    });
  }

  // Прогресс решений на странице проблемы
  document.querySelectorAll(".seq li[data-slug]").forEach(function (li) {
    var done = read("steps:" + li.getAttribute("data-slug") + ":v" + li.getAttribute("data-version"), []);
    var total = +li.getAttribute("data-steps"), p = li.querySelector("[data-progress]");
    if (done.length) { p.hidden = false; p.textContent = done.length === total ? "Выполнено полностью" : "Выполнено шагов: " + done.length + " из " + total; }
  });

  document.querySelectorAll("[data-print]").forEach(function (b) {
    b.hidden = false; b.addEventListener("click", function () { window.print(); });
  });
  badge();
})();
