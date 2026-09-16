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

/* Поиск по указателю.
 *
 * Работает поверх серверного, а не вместо него: где движок отвечает сам, он и
 * отвечает — скрипт видит выдачу и не трогает её. Смысл в другом: в
 * статической выгрузке движка нет, и без указателя поиска не существовало
 * вовсе. Зритель вводил запрос и не получал ничего.
 *
 * Сопоставление нестрогое, потому что строгое для зрителя почти бесполезно:
 * набирают с опечаткой, без «ё», в чужой раскладке и латиницей. Правила те же,
 * что у поиска каталога Lords, и по той же причине.
 */
(function () {
  var hint = document.getElementById("search-hint");
  var field = document.getElementById("q-main");
  var results = document.getElementById("search-results");
  if (!hint || !field || !results) { return; }
  var source = hint.getAttribute("data-search-index");
  if (!source) { return; }
  /* Серверная выдача уже на странице — вмешиваться незачем. */
  if (results.children.length) { return; }

  var LAYOUT = {
    q: "й", w: "ц", e: "у", r: "к", t: "е", y: "н", u: "г", i: "ш", o: "щ", p: "з",
    a: "ф", s: "ы", d: "в", f: "а", g: "п", h: "р", j: "о", k: "л", l: "д",
    z: "я", x: "ч", c: "с", v: "м", b: "и", n: "т", m: "ь"
  };
  var TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya"
  };
  var MIN_QUERY = 2;

  var index = null;
  var loading = false;
  var initialHint = hint.innerHTML;

  function normalize(value) {
    return (value || "").toLowerCase().replace(/ё/g, "е")
      .replace(/[^\wа-я\s]/gi, " ").replace(/\s+/g, " ").trim();
  }

  function fromLayout(value) {
    var out = "";
    for (var i = 0; i < value.length; i += 1) {
      out += LAYOUT[value[i]] || value[i];
    }
    return out;
  }

  function translit(value) {
    var out = "";
    for (var i = 0; i < value.length; i += 1) {
      out += TRANSLIT[value[i]] !== undefined ? TRANSLIT[value[i]] : value[i];
    }
    return out;
  }

  function variants(query) {
    var base = normalize(query);
    if (!base) { return []; }
    var all = [base, normalize(fromLayout(base)), translit(base)];
    var seen = {};
    return all.filter(function (v) {
      if (!v || seen[v]) { return false; }
      seen[v] = true;
      return true;
    });
  }

  /* Расстояние Дамерау — Левенштейна с ранним выходом: перестановка соседних
     букв — самая частая опечатка, и считать её двумя правками неверно. */
  function distance(a, b, limit) {
    if (Math.abs(a.length - b.length) > limit) { return limit + 1; }
    var prev2 = [];
    var prev = [];
    var cur = [];
    for (var j = 0; j <= b.length; j += 1) { prev[j] = j; }
    for (var i = 1; i <= a.length; i += 1) {
      cur = [i];
      var best = i;
      for (var k = 1; k <= b.length; k += 1) {
        var cost = a[i - 1] === b[k - 1] ? 0 : 1;
        var value = Math.min(cur[k - 1] + 1, prev[k] + 1, prev[k - 1] + cost);
        if (i > 1 && k > 1 && a[i - 1] === b[k - 2] && a[i - 2] === b[k - 1]) {
          value = Math.min(value, prev2[k - 2] + 1);
        }
        cur[k] = value;
        if (value < best) { best = value; }
      }
      if (best > limit) { return limit + 1; }
      prev2 = prev;
      prev = cur;
    }
    return prev[b.length];
  }

  function score(form, query) {
    if (!form || !query) { return 0; }
    if (form === query) { return 100; }
    if (form.indexOf(query) === 0) { return 80; }
    if (form.indexOf(query) >= 0) { return 60; }
    var limit = Math.max(1, Math.floor(query.length / 4));
    var words = form.split(" ");
    for (var i = 0; i < words.length; i += 1) {
      if (Math.abs(words[i].length - query.length) > limit) { continue; }
      var d = distance(words[i], query, limit);
      if (d <= limit) { return 40 - d; }
    }
    return 0;
  }

  function render(query) {
    var forms = variants(query);
    if (!forms.length || normalize(query).length < MIN_QUERY) {
      results.hidden = true;
      results.innerHTML = "";
      hint.innerHTML = initialHint;
      return;
    }
    var found = [];
    for (var i = 0; i < index.length; i += 1) {
      var item = index[i];
      var title = normalize(item.t);
      var best = 0;
      for (var v = 0; v < forms.length; v += 1) {
        var value = score(title, forms[v]);
        if (value > best) { best = value; }
      }
      if (best) { found.push([best, title, i, item]); }
    }
    found.sort(function (a, b) {
      if (a[0] !== b[0]) { return b[0] - a[0]; }
      if (a[1] !== b[1]) { return a[1] < b[1] ? -1 : 1; }
      return a[2] - b[2];
    });
    if (!found.length) {
      results.hidden = true;
      results.innerHTML = "";
      hint.textContent = "По запросу «" + query + "» ничего не нашлось. "
        + "Попробуйте другое написание или откройте разделы каталога.";
      return;
    }
    var shown = found.slice(0, 30);
    hint.textContent = "Найдено: " + found.length
      + (found.length > shown.length ? ". Показаны первые " + shown.length + "." : ".");
    var html = "";
    for (var j = 0; j < shown.length; j += 1) {
      var entry = shown[j][3];
      html += '<li><a href="' + entry.u + '">'
        + entry.t.replace(/[<>&]/g, "") + "</a></li>";
    }
    results.innerHTML = html;
    results.hidden = false;
  }

  function ensure(query) {
    if (index) { render(query); return; }
    if (loading) { return; }
    loading = true;
    hint.textContent = "Загружается указатель поиска…";
    var request = new XMLHttpRequest();
    request.open("GET", source, true);
    request.onreadystatechange = function () {
      if (request.readyState !== 4) { return; }
      loading = false;
      if (request.status !== 200) {
        /* Отказ называется отказом: молчание здесь неотличимо от «ничего не
           найдено», а это разные вещи с разными действиями зрителя. */
        hint.textContent = "Указатель поиска не загрузился. "
          + "Воспользуйтесь разделами каталога.";
        return;
      }
      try { index = JSON.parse(request.responseText); } catch (e) { index = null; }
      if (!index) {
        hint.textContent = "Указатель поиска повреждён. Воспользуйтесь разделами каталога.";
        return;
      }
      render(query);
    };
    request.send();
  }

  var timer = null;
  field.addEventListener("input", function () {
    if (timer) { window.clearTimeout(timer); }
    timer = window.setTimeout(function () { ensure(field.value); }, 200);
  });

  var form = field.closest("form");
  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      /* Запрос остаётся в адресе: страницу можно перезагрузить, послать
         ссылкой и вернуться к ней кнопкой «назад». */
      var url = new URL(window.location.href);
      if (field.value.trim()) { url.searchParams.set("q", field.value.trim()); }
      else { url.searchParams.delete("q"); }
      history.replaceState(null, "", url.toString());
      ensure(field.value);
    });
  }

  var initial = new URLSearchParams(window.location.search).get("q");
  if (initial) { field.value = initial; ensure(initial); }
})();
