/* plants-home (pick-and-diagnose): чек-лист ухода с сохранением отметок и печать. Без JS всё читается. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "ph";
  function read(k, d) { try { var v = localStorage.getItem(ns + ":" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + ":" + k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  var work = document.querySelector(".plant[data-slug]");
  if (work) {
    var key = "check:" + work.getAttribute("data-slug") + ":v" + work.getAttribute("data-version");
    var boxes = work.querySelectorAll("[data-check]"), status = work.querySelector("[data-check-status]");
    var reset = work.querySelector("[data-check-reset]"), state = read(key, []);
    var sync = function (save) {
      var done = [];
      boxes.forEach(function (b) { if (b.checked) done.push(b.getAttribute("data-check")); });
      if (save && !write(key, done)) { status.textContent = "Отметки не сохраняются: хранилище браузера недоступно."; return; }
      status.textContent = done.length === boxes.length ? "Всё сделано." : "Отмечено " + done.length + " из " + boxes.length + ". Отметки сохраняются на этом устройстве.";
      reset.hidden = done.length === 0;
    };
    boxes.forEach(function (b) {
      b.checked = state.indexOf(b.getAttribute("data-check")) !== -1;
      b.addEventListener("change", function () { sync(true); });
    });
    reset.addEventListener("click", function () { boxes.forEach(function (b) { b.checked = false; }); sync(true); });
    if (state.length) sync(false);
  }
  document.querySelectorAll("[data-print]").forEach(function (b) {
    b.hidden = false; b.addEventListener("click", function () { window.print(); });
  });
})();
