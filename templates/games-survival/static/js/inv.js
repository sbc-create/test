/* games-survival (inventory-first): отметки шагов плана (localStorage, пространство варианта), сброс, печать. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "gsv-inv";
  function read(k) { try { var v = localStorage.getItem(ns + ":" + k); return v ? JSON.parse(v) : []; } catch (e) { return []; } }
  function write(k, v) { try { localStorage.setItem(ns + ":" + k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  var box = document.querySelector("[data-plan]");
  if (box) {
    var key = "steps:" + box.getAttribute("data-plan"), boxes = box.querySelectorAll("[data-step]");
    var status = box.querySelector("[data-status]"), reset = box.querySelector("[data-steps-reset]");
    var sync = function (save) {
      var done = []; boxes.forEach(function (b) { if (b.checked) done.push(b.getAttribute("data-step")); });
      if (save && !write(key, done)) { status.textContent = "Отметки не сохраняются: хранилище браузера недоступно."; return; }
      status.textContent = done.length === boxes.length ? "Все шаги выполнены." : done.length ? "Готово шагов: " + done.length + " из " + boxes.length + "." : "";
      reset.hidden = done.length === 0;
    };
    var state = read(key);
    boxes.forEach(function (b) { b.checked = state.indexOf(b.getAttribute("data-step")) !== -1; b.addEventListener("change", function () { sync(true); }); });
    reset.addEventListener("click", function () { boxes.forEach(function (b) { b.checked = false; }); sync(true); boxes[0].focus(); });
    sync(false);
  }
  document.querySelectorAll("[data-print]").forEach(function (b) { b.hidden = false; b.addEventListener("click", function () { window.print(); }); });

  // Инвентарь: выбор в адресе; помним его для пустой формы и ссылки в шапке
  var inv = new URLSearchParams(location.search).getAll("est");
  if (location.pathname === "/iz-togo-chto-est/" && inv.length) write("inv", inv);
  var saved = read("inv", []);
  if (saved.length) document.querySelectorAll("[data-inv-link]").forEach(function (a) { a.href = "/iz-togo-chto-est/?" + saved.map(function (s) { return "est=" + encodeURIComponent(s); }).join("&"); });
  document.querySelectorAll("[data-inv-form]").forEach(function (f) {
    var boxes = f.querySelectorAll("input[name=est]"), out = f.querySelector("[data-inv-count]");
    if (!inv.length && saved.length) boxes.forEach(function (b) { b.checked = saved.indexOf(b.value) !== -1; });
    var upd = function () { var n = 0; boxes.forEach(function (b) { if (b.checked) n++; }); out.textContent = n ? "Отмечено: " + n : "Отметьте хотя бы один материал"; return n; };
    f.addEventListener("change", upd); upd();
    f.addEventListener("submit", function (e) { if (!upd()) { e.preventDefault(); boxes[0].focus(); } });
  });
})();
