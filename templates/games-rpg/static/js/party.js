/* games-rpg (party-planner): последний отряд, отметки этапов квеста, печать. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "grpg";
  function read(k, d) { try { var v = localStorage.getItem(ns + ":" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + ":" + k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  var g = document.querySelector(".entry[data-slug]");
  if (g) {
    var key = "check:" + g.getAttribute("data-slug") + ":v" + g.getAttribute("data-version");
    var boxes = g.querySelectorAll("[data-check]"), status = g.querySelector("[data-check-status]"), reset = g.querySelector("[data-check-reset]");
    var state = read(key, []);
    var sync = function (save) {
      var done = []; boxes.forEach(function (b) { if (b.checked) done.push(b.getAttribute("data-check")); });
      if (save && !write(key, done)) { status.textContent = "Прогресс не сохраняется: хранилище браузера недоступно."; return; }
      status.textContent = done.length ? "Отмечено " + done.length + " из " + boxes.length + "." : ""; reset.hidden = done.length === 0;
    };
    boxes.forEach(function (b) { b.checked = state.indexOf(b.getAttribute("data-check")) !== -1; b.addEventListener("change", function () { sync(true); }); });
    reset.addEventListener("click", function () { boxes.forEach(function (b) { b.checked = false; }); sync(true); });
    sync(false);
  }
  document.querySelectorAll(".gc[data-slug]").forEach(function (c) {
    var done = read("check:" + c.getAttribute("data-slug") + ":v" + c.getAttribute("data-version"), []);
    var total = +c.getAttribute("data-total"), p = c.querySelector("[data-progress]");
    if (done.length) { p.hidden = false; p.textContent = done.length === total ? "Пройдено полностью" : "Прогресс: " + done.length + " из " + total; }
  });
  document.querySelectorAll(".vid[data-vid]").forEach(function (f) {
    var b = f.querySelector("[data-play]"); b.hidden = false;
    b.addEventListener("click", function () {
      var i = document.createElement("iframe");
      i.src = "https://www.youtube-nocookie.com/embed/" + f.getAttribute("data-vid");
      i.title = f.querySelector("b").textContent; i.allow = "encrypted-media; picture-in-picture"; i.allowFullscreen = true;
      i.loading = "lazy"; i.className = "vid__frame"; b.replaceWith(i);
    });
  });
  var sum = document.querySelector("[data-party]");
  if (sum) write("party", sum.getAttribute("data-party"));
  var last = document.querySelector("[data-last-party]"), lp = read("party", "");
  if (last && lp) {
    var a = document.createElement("a");
    a.href = "/otryad/?" + lp.split(",").map(function (s) { return "p=" + encodeURIComponent(s); }).join("&");
    a.textContent = "Открыть ваш последний отряд"; last.appendChild(a); last.hidden = false;
  }
  document.querySelectorAll("[data-print]").forEach(function (b) { b.hidden = false; b.addEventListener("click", function () { window.print(); }); });
})();
