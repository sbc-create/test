/* garden-season (month-calendar): чек-лист работы с сохранением отметок и печать. Без JS всё читается. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "gs-plot";
  function read(k, d) { try { var v = localStorage.getItem(ns + ":" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + ":" + k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  var work = document.querySelector(".work[data-slug]");
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

  // Мой участок: помним последний выбор для пустой формы, отмечаем сделанное по месяцам
  var form = document.querySelector("[data-plot-form]");
  var q = new URLSearchParams(location.search);
  // запоминаем только показанный план: неизвестный регион (400) и выбор без работ не перезаписывают последний участок
  var shown = location.pathname === "/moj-uchastok/" && q.get("region") && document.querySelector("[data-plot-region]");
  if (shown) { write("plot", location.search); write("plot-region", shown.getAttribute("data-plot-region")); }
  // регион в шапке (идея из B): берётся из последнего «Моего участка», ссылка ведёт к нему
  var lastPlot = read("plot", ""), lastReg = read("plot-region", "");
  document.querySelectorAll("[data-plot-link]").forEach(function (a) {
    if (lastPlot && lastReg) { a.href = "/moj-uchastok/" + lastPlot; a.textContent = "Мой участок: " + lastReg; }
  });
  if (form && location.pathname === "/" ) {
    var last = read("plot", "");
    if (last) {
      var p = new URLSearchParams(last);
      form.querySelectorAll("input").forEach(function (x) {
        if (x.name === "region") x.checked = x.value === p.get("region");
        else if (x.name === "k") x.checked = p.getAll("k").indexOf(x.value) !== -1;
        else if (x.name === "obshchie") x.checked = p.get("obshchie") === "1";
      });
    }
  }
  var dones = document.querySelectorAll("[data-done]");
  if (dones.length) {
    var prog = document.querySelector("[data-plot-progress]"), d0 = read("done", []);
    var sync = function (save) {
      var d = read("done", []), n = 0;
      dones.forEach(function (b) { var k = b.getAttribute("data-done"), i = d.indexOf(k); if (b.checked) { n++; if (i === -1) d.push(k); } else if (i !== -1) d.splice(i, 1); });
      if (save) write("done", d);
      prog.textContent = n === dones.length ? "Все работы года отмечены." : "Сделано: " + n + " из " + dones.length + ".";
    };
    dones.forEach(function (b) { b.hidden = false; b.checked = d0.indexOf(b.getAttribute("data-done")) !== -1; b.addEventListener("change", function () { sync(true); }); });
    sync(false);
  }
})();
