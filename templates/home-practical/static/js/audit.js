/* home-practical (home-audit): обход квартиры (выбор помнится), план с отметками, сохранённые материалы, чек-лист, печать. Всё хранится только в браузере,
   ключи в пространстве имён варианта (data-ns на <body>). Без JS страницы полностью читаются. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "hp-audit";
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

  // Обход: выбор хранится в адресе; дополнительно помним его, чтобы вернуться к плану
  function planHref(list) { return "/obhod/plan/" + (list.length ? "?" + list.map(function (s) { return "m=" + encodeURIComponent(s); }).join("&") : ""); }
  var fromUrl = new URLSearchParams(location.search).getAll("m");
  if (fromUrl.length && /^\/obhod\//.test(location.pathname)) write("picked", fromUrl);
  var audit = document.querySelector("[data-audit]");
  if (audit) {
    var room = audit.querySelectorAll("input[type=checkbox][name=m]");
    if (!fromUrl.length) {
      var saved0 = read("picked", []);
      room.forEach(function (b) { b.checked = saved0.indexOf(b.value) !== -1; });
      saved0.forEach(function (s) {
        var mine = Array.prototype.some.call(room, function (b) { return b.value === s; });
        if (!mine) { var h = document.createElement("input"); h.type = "hidden"; h.name = "m"; h.value = s; audit.appendChild(h); }
      });
    }
    var count = audit.querySelector("[data-audit-count]");
    var upd = function () {
      var all = Array.prototype.map.call(audit.querySelectorAll("input[name=m]"), function (x) { return x.type === "hidden" || x.checked ? x.value : null; }).filter(Boolean);
      write("picked", all);
      count.textContent = all.length ? "Отмечено всего: " + all.length : "";
    };
    audit.addEventListener("change", upd); upd();
    // Переход по номерам комнат и «Назад» уносит и свежие, ещё не отправленные отметки этой страницы
    document.querySelectorAll(".steps-bar a, .audit__go a").forEach(function (a) {
      a.addEventListener("click", function () {
        var cur = read("picked", []);
        a.href = a.pathname + (cur.length ? "?" + cur.map(function (s) { return "m=" + encodeURIComponent(s); }).join("&") : "");
      });
    });
  }
  var stored = read("picked", []);
  if (stored.length) document.querySelectorAll("[data-plan-link]").forEach(function (a) { a.href = planHref(stored); });
  var restore = document.querySelector("[data-restore]");
  if (restore && stored.length) {
    restore.hidden = false;
    restore.textContent = "Открыть сохранённый выбор (" + stored.length + ")";
    restore.addEventListener("click", function () { location.href = planHref(stored); });
  }
  // План: отметки «сделано»
  var dones = document.querySelectorAll("[data-done]");
  if (dones.length) {
    var prog = document.querySelector("[data-plan-progress]"), done0 = read("done", []);
    var syncp = function (save) {
      var d = read("done", []);
      dones.forEach(function (b) { var s = b.getAttribute("data-done"), i = d.indexOf(s); if (b.checked && i === -1) d.push(s); if (!b.checked && i !== -1) d.splice(i, 1); });
      if (save) write("done", d);
      var n = 0; dones.forEach(function (b) { if (b.checked) n++; });
      prog.textContent = n === dones.length ? "Всё из плана сделано." : "Сделано: " + n + " из " + dones.length + ".";
    };
    dones.forEach(function (b) { b.hidden = false; b.checked = done0.indexOf(b.getAttribute("data-done")) !== -1; b.addEventListener("change", function () { syncp(true); }); });
    syncp(false);
  }
  // Прогресс решений на странице проблемы (перенесено из B): по отметкам чек-листа инструкции
  document.querySelectorAll(".seq li[data-slug]").forEach(function (li) {
    var done = read("check:" + li.getAttribute("data-slug") + ":v" + li.getAttribute("data-version"), []);
    var total = +li.getAttribute("data-checks"), p = li.querySelector("[data-progress]");
    if (Array.isArray(done) && done.length) { p.hidden = false; p.textContent = done.length >= total ? "Чек-лист выполнен полностью" : "Отмечено в чек-листе: " + done.length + " из " + total; }
  });
})();
