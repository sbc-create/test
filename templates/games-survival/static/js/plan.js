/* games-survival (craft-planner): отметки шагов плана (localStorage, пространство варианта), сброс, печать. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "gsv-plan";
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
})();
