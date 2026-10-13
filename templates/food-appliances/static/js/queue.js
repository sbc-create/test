/* food-appliances, вариант device-queue: память выбранных рецептов и отметки «готово» (localStorage, ключи fac.*),
   счётчик, печать. Без этого файла очередь строится формой. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "fac";
  function read(k, d) { try { var v = localStorage.getItem(ns + "." + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + "." + k, JSON.stringify(v)); } catch (e) { /* приватный режим */ } }
  var picked = new URLSearchParams(location.search).getAll("r");
  if (location.pathname === "/ochered/" && picked.length) write("queue", picked);
  var saved = read("queue", []);
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
    var d0 = read("done", []);
    dones.forEach(function (b) {
      b.hidden = false; b.checked = d0.indexOf(b.getAttribute("data-done")) !== -1;
      b.addEventListener("change", function () {
        var d = []; dones.forEach(function (x) { if (x.checked) d.push(x.getAttribute("data-done")); }); write("done", d);
      });
    });
  }
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
