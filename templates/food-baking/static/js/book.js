/* food-baking: таймеры по времени из источника и отметки «отвешено».
   Без этого файла страница полностью читается. */
(function () {
  "use strict";
  var box = document.querySelector("[data-timers]");
  if (box) {
    box.hidden = false;
    box.addEventListener("click", function (e) {
      var b = e.target.closest(".timer"); if (!b) return;
      if (b._t) { clearInterval(b._t); b._t = null; b.removeAttribute("data-running"); b.textContent = "Таймер " + b.dataset.minutes + " мин"; return; }
      var left = parseInt(b.dataset.minutes, 10) * 60;
      b.setAttribute("data-running", "");
      var tick = function () {
        var m = Math.floor(left / 60), s = left % 60;
        b.textContent = "Осталось " + m + ":" + (s < 10 ? "0" : "") + s + " · стоп";
        if (left-- <= 0) { clearInterval(b._t); b._t = null; b.textContent = "Время вышло — проверьте выпечку"; b.removeAttribute("data-running"); }
      };
      tick(); b._t = setInterval(tick, 1000);
    });
  }
  var f = document.querySelector("[data-autosubmit]");
  if (f) f.addEventListener("change", function () { f.submit(); });
})();
