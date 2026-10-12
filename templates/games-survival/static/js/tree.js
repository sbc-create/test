/* games-survival (craft-tree): печать. Без JS страница полная, кнопка печати скрыта. */
(function () {
  "use strict";
  document.querySelectorAll("[data-print]").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () { window.print(); });
  });
})();
