/* food-weekly, вариант own-week: отметки купленного (localStorage, ключи fwc.*), счётчик выбранных блюд,
   память последней своей недели для ссылки в шапке, печать. Без JS всё работает. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "fwc";
  function read(k, d) { try { var v = localStorage.getItem(ns + "." + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + "." + k, JSON.stringify(v)); } catch (e) { /* приватный режим */ } }
  if (location.pathname === "/svoya-nedelya/" && location.search.length > 1) write("week", location.search);
  var last = read("week", "");
  if (last) document.querySelectorAll("[data-own-link]").forEach(function (a) { a.href = "/svoya-nedelya/" + last; });
  var form = document.querySelector("[data-own-form]");
  if (form) {
    var out = form.querySelector("[data-own-count]"), sels = form.querySelectorAll("select");
    var upd = function () { var n = 0; sels.forEach(function (s) { if (s.value) n++; }); out.textContent = "Выбрано блюд: " + n + " из " + sels.length; };
    form.addEventListener("change", upd); upd();
  }
  /* отметки купленного: у каждого списка свой ключ; у закупок плана (перенесено из B) — счётчик оставшегося */
  function plural(n, a, b, c) { n = Math.abs(n) % 100; var m = n % 10; if (n > 10 && n < 20) return c; if (m > 1 && m < 5) return b; if (m === 1) return a; return c; }
  document.querySelectorAll("[data-list]").forEach(function (list) {
    var id = list.getAttribute("data-list");
    var key = "bought." + (id === "own" ? "" : id + ".") + location.search, saved = read(key, []);
    var count = document.querySelector('[data-count="' + id + '"]'), boxes = list.querySelectorAll("input[type=checkbox]");
    var upd = function () {
      if (!count) return;
      var left = 0; boxes.forEach(function (b) { if (!b.checked) left++; });
      count.textContent = left ? "Осталось купить: " + left + " " + plural(left, "позиция", "позиции", "позиций") + " из " + boxes.length : "Всё куплено";
    };
    boxes.forEach(function (cb) {
      cb.checked = saved.indexOf(cb.value) >= 0;
      cb.addEventListener("change", function () {
        var v = []; boxes.forEach(function (x) { if (x.checked) v.push(x.value); });
        write(key, v); upd();
      });
    });
    upd();
  });
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
