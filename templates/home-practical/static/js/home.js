/* home-practical (rooms-cards): сохранённые материалы, чек-лист, печать. Всё хранится только в браузере,
   ключи в пространстве имён варианта (data-ns на <body>). Без JS страницы полностью читаются. */
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
    document.querySelectorAll("[data-saved-count]").forEach(function (b) {
      b.textContent = n; b.hidden = n === 0;
      b.setAttribute("aria-label", n ? "сохранено: " + n : "");
    });
  }

  // Сохранить / убрать материал
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

  // Страница «Сохранённое»
  var list = document.querySelector("[data-saved-list]");
  if (list) {
    var render = function () {
      var s = saved(), shown = 0;
      list.querySelectorAll("[data-saved-item]").forEach(function (el) {
        var on = s.indexOf(el.getAttribute("data-saved-item")) !== -1;
        el.hidden = !on; if (on) shown++;
      });
      document.querySelector("[data-saved-empty]").hidden = shown > 0;
      document.querySelector("[data-saved-clear]").hidden = shown === 0;
    };
    document.querySelector("[data-saved-clear]").addEventListener("click", function () { write("saved", []); render(); badge(); });
    render();
  }

  // Чек-лист материала: отметки привязаны к версии текста
  var mat = document.querySelector(".mat[data-slug]");
  if (mat) {
    var key = "check:" + mat.getAttribute("data-slug") + ":v" + mat.getAttribute("data-version");
    var boxes = mat.querySelectorAll("[data-check]");
    var status = mat.querySelector("[data-check-status]");
    var reset = mat.querySelector("[data-check-reset]");
    var state = read(key, []);
    var sync = function () {
      var done = [];
      boxes.forEach(function (b) { if (b.checked) done.push(b.getAttribute("data-check")); });
      write(key, done);
      status.textContent = done.length === boxes.length ? "Все пункты выполнены." : "Отмечено " + done.length + " из " + boxes.length + ". Отметки сохраняются на этом устройстве.";
      reset.hidden = done.length === 0;
    };
    boxes.forEach(function (b) {
      b.checked = state.indexOf(b.getAttribute("data-check")) !== -1;
      b.addEventListener("change", sync);
    });
    reset.addEventListener("click", function () { boxes.forEach(function (b) { b.checked = false; }); sync(); });
    if (state.length) sync();
  }

  document.querySelectorAll("[data-print]").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () { window.print(); });
  });
  badge();
})();
