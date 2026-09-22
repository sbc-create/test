/* Ядро интерактивности шаблонных пакетов Lords.
 *
 * Правило, ради которого этот файл существует: на странице не должно быть
 * нарисованных органов управления, которые ничего не делают. Поэтому стрелки
 * полосы, кнопка сброса фильтров и кнопка раскрытия описания не приходят в
 * разметке — их создаёт или показывает этот скрипт, и только тогда, когда им
 * есть что делать. Страница без скриптов остаётся годной: полоса прокручивается
 * пальцем и колесом, вкладки сезонов показывают первый сезон, каталог и
 * пагинация работают целиком на адресах.
 *
 * Внешних зависимостей нет и быть не может: пакет обязан собираться и
 * измеряться без сети.
 */
(function () {
  "use strict";

  var СПОКОЙНО = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ПЛАВНО = СПОКОЙНО ? "auto" : "smooth";

  function все(селектор, корень) {
    return Array.prototype.slice.call((корень || document).querySelectorAll(селектор));
  }

  /* --- полоса --------------------------------------------------------------
   * Стрелки появляются, только если содержимое действительно шире рамки.
   * При одной-двух карточках прокручивать нечего, и стрелок нет вовсе —
   * это и есть корректное поведение, а не «кнопки в состоянии disabled».
   */
  function полоса(секция) {
    var дорожка = секция.querySelector("[data-lx-track]");
    var гнездо = секция.querySelector("[data-lx-nav]");
    if (!дорожка || !гнездо) return;

    var назад = document.createElement("button");
    var вперёд = document.createElement("button");
    назад.type = вперёд.type = "button";
    назад.className = вперёд.className = "rail__b";
    // Метка говорит проверке, что за кнопкой стоит поведение. Без неё кнопка
    // неотличима от нарисованной, и проверка «мёртвых органов управления»
    // обязана считать её мёртвой — она права по своей разметке.
    назад.setAttribute("data-lx-scroll", "prev");
    вперёд.setAttribute("data-lx-scroll", "next");
    назад.setAttribute("aria-label", "Прокрутить назад");
    вперёд.setAttribute("aria-label", "Прокрутить вперёд");
    назад.innerHTML = '<span aria-hidden="true">‹</span>';
    вперёд.innerHTML = '<span aria-hidden="true">›</span>';
    гнездо.appendChild(назад);
    гнездо.appendChild(вперёд);

    function шаг() {
      var первая = дорожка.firstElementChild;
      var ширина = первая ? первая.getBoundingClientRect().width : 240;
      var зазор = parseFloat(getComputedStyle(дорожка).columnGap || "16") || 16;
      var видно = Math.max(1, Math.floor(дорожка.clientWidth / (ширина + зазор)));
      return (ширина + зазор) * видно;
    }

    function обновить() {
      var запас = дорожка.scrollWidth - дорожка.clientWidth;
      // Полтора пикселя — допуск на дробную ширину при масштабировании.
      var прокручиваемо = запас > 1.5;
      гнездо.hidden = !прокручиваемо;
      if (!прокручиваемо) return;
      назад.disabled = дорожка.scrollLeft <= 1;
      вперёд.disabled = дорожка.scrollLeft >= запас - 1;
    }

    назад.addEventListener("click", function () {
      дорожка.scrollBy({ left: -шаг(), behavior: ПЛАВНО });
    });
    вперёд.addEventListener("click", function () {
      дорожка.scrollBy({ left: шаг(), behavior: ПЛАВНО });
    });
    дорожка.addEventListener("scroll", обновить, { passive: true });
    дорожка.addEventListener("keydown", function (е) {
      if (е.key === "ArrowRight") { е.preventDefault(); вперёд.click(); }
      else if (е.key === "ArrowLeft") { е.preventDefault(); назад.click(); }
      else if (е.key === "Home") { е.preventDefault(); дорожка.scrollTo({ left: 0, behavior: ПЛАВНО }); }
      else if (е.key === "End") {
        е.preventDefault();
        дорожка.scrollTo({ left: дорожка.scrollWidth, behavior: ПЛАВНО });
      }
    });
    if (window.ResizeObserver) new ResizeObserver(обновить).observe(дорожка);
    обновить();
  }

  /* --- вкладки сезонов ----------------------------------------------------- */
  function вкладки(секция) {
    var кнопки = все('[role="tab"]', секция);
    if (кнопки.length < 1) return;

    function выбрать(индекс, фокус) {
      кнопки.forEach(function (к, i) {
        var активна = i === индекс;
        к.setAttribute("aria-selected", активна ? "true" : "false");
        к.tabIndex = активна ? 0 : -1;
        var панель = секция.querySelector("#" + к.getAttribute("aria-controls"));
        if (панель) панель.hidden = !активна;
      });
      if (фокус) кнопки[индекс].focus();
    }

    кнопки.forEach(function (к, i) {
      к.addEventListener("click", function () { выбрать(i, false); });
      к.addEventListener("keydown", function (е) {
        var шаг = е.key === "ArrowRight" ? 1 : е.key === "ArrowLeft" ? -1 : 0;
        if (шаг) {
          е.preventDefault();
          выбрать((i + шаг + кнопки.length) % кнопки.length, true);
        } else if (е.key === "Home") { е.preventDefault(); выбрать(0, true); }
        else if (е.key === "End") { е.preventDefault(); выбрать(кнопки.length - 1, true); }
      });
    });
  }

  /* --- фильтры и сортировка -------------------------------------------------
   * Фильтр пересекает группы и объединяет значения внутри группы: выбрать два
   * жанра значит «любой из них», выбрать жанр и страну — «и то, и другое».
   * Число показанного объявляется живой областью, иначе изменение выдачи
   * остаётся незамеченным для тех, кто не видит страницу.
   */
  function инструменты(секция) {
    var перечень = document.querySelector('[data-lx="listing"]');
    if (!перечень) return;
    var сетка = перечень.querySelector(".g");
    if (!сетка) return;
    var карточки = все(".k", сетка);
    var живое = секция.querySelector("[data-lx-live]");
    var сброс = секция.querySelector("[data-lx-reset]");
    var пусто = перечень.querySelector("[data-lx-none]");
    var выбор = { g: [], c: [], k: [] };
    var исходный = карточки.slice();

    function подходит(к) {
      return Object.keys(выбор).every(function (ключ) {
        if (!выбор[ключ].length) return true;
        var значения = (к.getAttribute("data-" + ключ) || "").split("|");
        return выбор[ключ].some(function (v) { return значения.indexOf(v) !== -1; });
      });
    }

    function применить() {
      var видно = 0;
      карточки.forEach(function (к) {
        var годна = подходит(к);
        к.hidden = !годна;
        if (годна) видно++;
      });
      if (живое) живое.textContent = "Показано " + видно + " из " + карточки.length;
      if (пусто) пусто.hidden = видно !== 0;
      var есть = Object.keys(выбор).some(function (к) { return выбор[к].length; });
      if (сброс) сброс.hidden = !есть;
    }

    все("[data-lx-filter]", секция).forEach(function (кнопка) {
      кнопка.addEventListener("click", function () {
        var ключ = кнопка.getAttribute("data-lx-filter");
        var значение = кнопка.getAttribute("data-value");
        var место = выбор[ключ].indexOf(значение);
        if (место === -1) выбор[ключ].push(значение); else выбор[ключ].splice(место, 1);
        кнопка.setAttribute("aria-pressed", место === -1 ? "true" : "false");
        применить();
      });
    });

    if (сброс) сброс.addEventListener("click", function () {
      Object.keys(выбор).forEach(function (к) { выбор[к] = []; });
      все("[data-lx-filter]", секция).forEach(function (к) {
        к.setAttribute("aria-pressed", "false");
      });
      применить();
    });

    var сортировка = секция.querySelector("[data-lx-sort]");
    if (сортировка) сортировка.addEventListener("change", function () {
      var как = сортировка.value;
      var порядок = исходный.slice();
      if (как === "year") порядок.sort(по(число("data-y"), -1));
      else if (как === "title") порядок.sort(по(строка("data-t"), 1));
      else if (как === "rating") порядок.sort(по(число("data-r"), -1));
      else if (как === "added") порядок.sort(по(строка("data-a"), -1));
      порядок.forEach(function (к) { сетка.appendChild(к); });
      if (живое) живое.textContent = "Порядок изменён: " +
        сортировка.options[сортировка.selectedIndex].text;
    });

    function число(атрибут) {
      return function (э) { return parseFloat(э.getAttribute(атрибут)) || 0; };
    }
    function строка(атрибут) {
      return function (э) { return э.getAttribute(атрибут) || ""; };
    }
    function по(взять, знак) {
      return function (a, b) {
        var x = взять(a), y = взять(b);
        return x < y ? -знак : x > y ? знак : 0;
      };
    }
  }

  /* --- поиск на странице выдачи -------------------------------------------- */
  function поиск() {
    var поле = document.querySelector("[data-lx-search]");
    var перечень = document.querySelector('[data-lx="listing"]');
    if (!поле || !перечень) return;
    var карточки = все(".k", перечень);
    var пусто = перечень.querySelector("[data-lx-none]");
    поле.addEventListener("input", function () {
      var запрос = поле.value.trim().toLowerCase();
      var видно = 0;
      карточки.forEach(function (к) {
        var годна = !запрос || (к.getAttribute("data-t") || "").indexOf(запрос) !== -1;
        к.hidden = !годна;
        if (годна) видно++;
      });
      if (пусто) пусто.hidden = видно !== 0;
    });
  }

  /* --- раскрытие описания --------------------------------------------------- */
  function раскрытие() {
    все("[data-lx-more-btn]").forEach(function (кнопка) {
      var тело = document.getElementById(кнопка.getAttribute("aria-controls"));
      if (!тело) return;
      кнопка.addEventListener("click", function () {
        var открыто = кнопка.getAttribute("aria-expanded") === "true";
        кнопка.setAttribute("aria-expanded", открыто ? "false" : "true");
        тело.classList.toggle("ttl__d--cut", открыто);
        кнопка.textContent = открыто ? "Читать полностью" : "Свернуть";
      });
    });
  }

  /* --- плеер ----------------------------------------------------------------
   * Автозапуска нет. До нажатия на странице нет ни одного тяжёлого кадра;
   * после нажатия место плеера переходит в состояние ожидания источника,
   * который подключает ядро витрины. Пакет отвечает за рамку, а не за
   * источник воспроизведения.
   */
  function плеер(секция) {
    var кнопка = секция.querySelector("[data-lx-play]");
    var рамка = секция.querySelector("[data-player-host]");
    var состояние = секция.querySelector("[data-lx-state]");
    if (!кнопка || !рамка) return;
    кнопка.addEventListener("click", function () {
      рамка.setAttribute("data-state", "requested");
      кнопка.hidden = true;
      if (состояние) {
        состояние.textContent = "Запрошен источник воспроизведения. " +
          "Подключение выполняет ядро витрины по своему контракту.";
        состояние.setAttribute("role", "status");
      }
    });
  }

  function запуск() {
    все('[data-lx="rail"]').forEach(полоса);
    все('[data-lx="tabs"]').forEach(вкладки);
    все('[data-lx="tools"]').forEach(инструменты);
    все('[data-lx="player"]').forEach(плеер);
    раскрытие();
    поиск();
    document.documentElement.setAttribute("data-lx-ready", "1");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", запуск);
  } else {
    запуск();
  }
})();
