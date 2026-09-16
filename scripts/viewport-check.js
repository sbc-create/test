#!/usr/bin/env node
/**
 * Проверка вёрстки витрин на трёх ширинах через CDP.
 *
 * Зачем свой сценарий вместо playwright: библиотеки в среде нет, зато есть
 * сам chrome-headless-shell и встроенный в node WebSocket. Протокол CDP —
 * это и есть то, чем playwright пользуется внутри; здесь берётся ровно та его
 * часть, которая нужна для четырёх измерений.
 *
 * Измеряется то, что нельзя измерить без браузера:
 *   - горизонтальная прокрутка страницы (scrollWidth против clientWidth);
 *   - перекрытия карточек и элементов управления;
 *   - большие пустые области после скрытых секций;
 *   - ошибки в консоли.
 *
 * Ничего не изменяется: только загрузка страницы и чтение измерений.
 */

const { spawn } = require("node:child_process");
const { setTimeout: sleep } = require("node:timers/promises");

const BIN =
  process.env.CHROME_SHELL ||
  "/home/claude/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell";
const ШИРИНЫ = [390, 768, 1440];
const ПОРТ = Number(process.env.CDP_PORT || 9223);

// Допуск на горизонтальную прокрутку: субпиксельные округления браузера дают
// расхождение в единицы пикселей на совершенно корректной вёрстке.
const ДОПУСК_ПРОКРУТКИ = 2;
// Пустая область, которую посетитель заметит как «страница оборвалась».
const ПУСТАЯ_ОБЛАСТЬ = 400;

async function запуститьБраузер() {
  const проц = spawn(BIN, [
    `--remote-debugging-port=${ПОРТ}`,
    "--headless",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--disable-dev-shm-usage",
  ]);
  проц.stderr.on("data", () => {});
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${ПОРТ}/json/version`);
      if (r.ok) return { проц, версия: (await r.json())["Browser"] };
    } catch {
      /* ещё не поднялся */
    }
    await sleep(250);
  }
  проц.kill();
  throw new Error("браузер не поднялся");
}

/** Один сеанс CDP: открыть вкладку, выполнить измерение, закрыть. */
async function измерить(url, ширина) {
  const создан = await (
    await fetch(`http://127.0.0.1:${ПОРТ}/json/new?about:blank`, { method: "PUT" })
  ).json();
  const ws = new WebSocket(создан.webSocketDebuggerUrl);
  let id = 0;
  const ждут = new Map();
  const ошибкиКонсоли = [];
  // Ответы 4xx/5xx, которые страница запросила сама. В разметке их нет —
  // их инициирует скрипт, — поэтому проверкой ссылок из HTML они не ловятся.
  const неудачныеЗапросы = [];

  await new Promise((ok, нет) => {
    ws.onopen = ok;
    ws.onerror = () => нет(new Error("CDP не подключился"));
  });
  ws.onmessage = (соб) => {
    const м = JSON.parse(соб.data);
    if (м.id && ждут.has(м.id)) {
      ждут.get(м.id)(м);
      ждут.delete(м.id);
    }
    if (м.method === "Runtime.exceptionThrown") {
      ошибкиКонсоли.push(
        м.params?.exceptionDetails?.exception?.description ||
          м.params?.exceptionDetails?.text ||
          "исключение",
      );
    }
    if (м.method === "Log.entryAdded" && м.params?.entry?.level === "error") {
      ошибкиКонсоли.push(м.params.entry.text);
    }
    if (м.method === "Network.responseReceived" && м.params?.response?.status >= 400) {
      неудачныеЗапросы.push(`${м.params.response.status} ${м.params.response.url}`);
    }
  };

  const зов = (method, params = {}) =>
    new Promise((ok) => {
      const свой = ++id;
      ждут.set(свой, ok);
      ws.send(JSON.stringify({ id: свой, method, params }));
    });

  try {
    await зов("Runtime.enable");
    await зов("Network.enable");
    await зов("Log.enable");
    await зов("Page.enable");
    await зов("Emulation.setDeviceMetricsOverride", {
      width: ширина,
      height: 900,
      deviceScaleFactor: 1,
      mobile: ширина < 768,
    });
    await зов("Page.navigate", { url });

    // Ждём затишья сети: у витрин есть отложенная дорисовка.
    await sleep(3500);

    const выражение = `(() => {
      const de = document.documentElement;
      const прямоугольники = [...document.querySelectorAll(
        'a,button,article,.card,[class*="card"],[class*="rail"],[class*="nav"]')]
        .map(e => e.getBoundingClientRect())
        .filter(r => r.width > 8 && r.height > 8);

      // Перекрытия: пара элементов, площадь пересечения которых заметна.
      let перекрытий = 0;
      for (let i = 0; i < прямоугольники.length && перекрытий < 5; i++) {
        for (let j = i + 1; j < прямоугольники.length; j++) {
          const a = прямоугольники[i], b = прямоугольники[j];
          const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
          const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
          if (w > 12 && h > 12 &&
              !(a.left <= b.left && a.right >= b.right && a.top <= b.top && a.bottom >= b.bottom) &&
              !(b.left <= a.left && b.right >= a.right && b.top <= a.top && b.bottom >= a.bottom)) {
            перекрытий++; break;
          }
        }
      }

      // Элементы, вылезающие за правый край окна.
      const вылезают = прямоугольники.filter(r => r.right > de.clientWidth + 2).length;

      // Самый большой вертикальный разрыв между соседними блоками.
      const верх = [...document.querySelectorAll('section,main > div,article')]
        .map(e => e.getBoundingClientRect())
        .filter(r => r.height > 0)
        .sort((a, b) => a.top - b.top);
      let разрыв = 0;
      for (let i = 1; i < верх.length; i++) {
        разрыв = Math.max(разрыв, верх[i].top - верх[i - 1].bottom);
      }

      // Контейнеры с собственной прокруткой (длинный список серий).
      const прокручиваемых = [...document.querySelectorAll('*')].filter(e => {
        const s = getComputedStyle(e);
        return /(auto|scroll)/.test(s.overflowY + s.overflowX) &&
               (e.scrollHeight > e.clientHeight + 8 || e.scrollWidth > e.clientWidth + 8);
      }).length;

      return {
        scrollWidth: de.scrollWidth,
        clientWidth: de.clientWidth,
        перекрытий, вылезают,
        разрыв: Math.round(разрыв),
        прокручиваемых,
        ссылок: document.querySelectorAll('a[href]').length,
      };
    })()`;

    const ответ = await зов("Runtime.evaluate", {
      expression: выражение,
      returnByValue: true,
      awaitPromise: false,
    });
    const з = ответ.result?.result?.value;
    if (!з) throw new Error("измерение не вернулось: " + JSON.stringify(ответ).slice(0, 200));
    з.ошибкиКонсоли = ошибкиКонсоли.slice(0, 3);
    з.неудачныеЗапросы = неудачныеЗапросы.slice(0, 5);
    з.горизонтальнаяПрокрутка = з.scrollWidth - з.clientWidth > ДОПУСК_ПРОКРУТКИ;
    з.большаяПустота = з.разрыв > ПУСТАЯ_ОБЛАСТЬ;
    return з;
  } finally {
    ws.close();
    await fetch(`http://127.0.0.1:${ПОРТ}/json/close/${создан.id}`).catch(() => {});
  }
}

(async () => {
  const цели = process.argv.slice(2);
  if (!цели.length) {
    console.error("укажите адреса");
    process.exit(2);
  }
  const { проц, версия } = await запуститьБраузер();
  console.log("браузер:", версия);
  const итог = [];
  try {
    for (const url of цели) {
      for (const ширина of ШИРИНЫ) {
        let з;
        try {
          з = await измерить(url, ширина);
        } catch (e) {
          з = { ошибка: String(e.message || e) };
        }
        итог.push({ url, ширина, ...з });
        const метка = з.ошибка
          ? `ОШИБКА ${з.ошибка}`
          : `прокрутка=${з.горизонтальнаяПрокрутка ? "ДА" : "нет"} ` +
            `вылезают=${з.вылезают} перекрытий=${з.перекрытий} ` +
            `разрыв=${з.разрыв} прокручиваемых=${з.прокручиваемых} ` +
            `ошибок_консоли=${з.ошибкиКонсоли.length} ` +
            `неудачных_запросов=${з.неудачныеЗапросы.length}`;
        console.log(`${String(ширина).padStart(4)}  ${url}  ${метка}`);
      }
    }
  } finally {
    проц.kill();
  }
  console.log("\n::JSON::" + JSON.stringify(итог));
})();
