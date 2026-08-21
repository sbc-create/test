/* Progressive enhancement поверх серверной пагинации.
 *
 * Инвариант: кнопка «Показать ещё» появляется ТОЛЬКО если на странице уже есть
 * рабочая серверная пагинация с обычными <a href>. Ссылки не удаляются — робот и
 * пользователь без JS продолжают ходить по ним, каждый chunk открывается прямым URL.
 */
(function () {
  "use strict";
  var pagination = document.querySelector(".pagination");
  var list = document.getElementById("items");
  if (!pagination || !list) return;
  var nextLink = pagination.querySelector(".page-next");
  if (!nextLink) return;

  var button = document.createElement("button");
  button.type = "button";
  button.className = "load-more";
  button.textContent = "Показать ещё";
  button.setAttribute("aria-controls", "items");

  var status = document.createElement("p");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.className = "load-more-status";

  function currentNext() {
    return pagination.querySelector(".page-next");
  }

  button.addEventListener("click", function () {
    var link = currentNext();
    if (!link) return;
    button.disabled = true;
    status.textContent = "Загружаем следующую страницу…";
    fetch(link.href, { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var newItems = doc.querySelectorAll("#items > li");
        if (!newItems.length) throw new Error("empty page");
        Array.prototype.forEach.call(newItems, function (li) { list.appendChild(li); });
        var newPagination = doc.querySelector(".pagination");
        if (newPagination) pagination.innerHTML = newPagination.innerHTML;
        history.replaceState(null, "", link.href);
        status.textContent = "Добавлено материалов: " + newItems.length + ".";
        if (!currentNext()) { button.remove(); status.textContent += " Это последняя страница."; }
        else { button.disabled = false; }
      })
      .catch(function () {
        status.textContent = "Не удалось подгрузить. Откройте следующую страницу по ссылке ниже.";
        button.disabled = false;
      });
  });

  pagination.insertAdjacentElement("afterend", status);
  pagination.insertAdjacentElement("afterend", button);
})();
