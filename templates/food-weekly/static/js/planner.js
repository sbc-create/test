/* food-weekly: отметки купленного (localStorage) и печать. Без JS всё работает. */
(function () {
  "use strict";
  var list = document.querySelector("[data-list]");
  if (list) {
    var key = "fw.bought." + list.getAttribute("data-list");
    var saved = [];
    try { saved = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { saved = []; }
    list.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      cb.checked = saved.indexOf(cb.value) >= 0;
      cb.addEventListener("change", function () {
        var v = Array.prototype.filter.call(list.querySelectorAll("input:checked"), function () { return true; }).map(function (x) { return x.value; });
        try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* приватный режим */ }
      });
    });
  }
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
