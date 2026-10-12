/* food-weekly, вариант B agenda-trips: отметки купленного по каждой закупке (localStorage, ключи fwb.*),
   счётчик оставшегося, печать. Без JS всё работает. */
(function () {
  "use strict";
  function plural(n, a, b, c) { n = Math.abs(n) % 100; var m = n % 10; if (n > 10 && n < 20) return c; if (m > 1 && m < 5) return b; if (m === 1) return a; return c; }
  document.querySelectorAll("[data-list]").forEach(function (list) {
    var id = list.getAttribute("data-list"), key = "fwb.bought." + id, saved = [];
    try { saved = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { saved = []; }
    var count = document.querySelector('[data-count="' + id + '"]');
    var boxes = list.querySelectorAll("input[type=checkbox]");
    var upd = function () {
      if (!count) return;
      var left = 0; boxes.forEach(function (b) { if (!b.checked) left++; });
      count.textContent = left ? "Осталось купить: " + left + " " + plural(left, "позиция", "позиции", "позиций") + " из " + boxes.length : "Всё куплено";
    };
    boxes.forEach(function (cb) {
      cb.checked = saved.indexOf(cb.value) >= 0;
      cb.addEventListener("change", function () {
        var v = []; boxes.forEach(function (b) { if (b.checked) v.push(b.value); });
        try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* приватный режим */ }
        upd();
      });
    });
    upd();
  });
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
