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
  var list = document.querySelector("[data-list]");
  if (list) {
    var key = "bought." + location.search, saved = read(key, []);
    list.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      cb.checked = saved.indexOf(cb.value) >= 0;
      cb.addEventListener("change", function () {
        var v = []; list.querySelectorAll("input:checked").forEach(function (x) { v.push(x.value); });
        write(key, v);
      });
    });
  }
  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }
})();
