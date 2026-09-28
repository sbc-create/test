// Браузерная приёмка витрины после переключения.
//
// Проверяется то, чего не видно из curl: ошибки в консоли, неудавшиеся
// запросы, горизонтальная прокрутка, геометрия места плеера. Страница может
// отдавать 200 и при этом ехать вбок на телефоне или молча ронять скрипт —
// первое видно только в браузере, второе только в консоли.
//
// Снимки на трёх ширинах кладутся рядом: они и есть предмет визуальной
// проверки владельцем.
//
// Запуск:
//   BASE=http://127.0.0.1:9102 OUT=<каталог> node canary-smoke.cjs
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE || "http://127.0.0.1:9102";
const OUT = process.env.OUT || "/tmp/canary-smoke";
const WIDTHS = [390, 768, 1440];

// Маршруты выбраны по тому, что ломается по-разному: список, разбитый на
// страницы, поиск с результатом и без него, страница произведения с местом
// плеера, и несуществующий адрес.
const ROUTES = [
  ["home", "/"],
  ["catalog", "/catalog/"],
  ["catalog-page2", "/catalog/page/2/"],
  ["search", "/search/?q=%D0%B0"],
  ["search-empty", "/search/?q=zzzzzzzzzzzz"],
  ["not-found", "/nope-canary-probe/"],
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const report = [];
  let titleHref = null;

  for (const width of WIDTHS) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    const errors = [];
    let expecting404 = false;

    // Считаются только отказы САМОЙ витрины.
    //
    // Две вещи пришлось исключить, и обе выяснились пробным прогоном на
    // текущем боевом релизе — то есть до всякого canary:
    //
    //   * страница 404 сама по себе пишет в консоль «Failed to load resource:
    //     404». Это её собственный ответ, а не ошибка: считать его отказом
    //     значит объявлять дефектом работающую страницу;
    //   * страница произведения обращается к внешнему API плеера
    //     (plapi.cdnvideohub.com). В этой среде он отвечает 404 и рвёт
    //     соединение. Состояние провайдера к выкладке шаблона отношения не
    //     имеет, и приёмка на нём падать не должна.
    //
    // Всё, что идёт не с адреса витрины, записывается отдельно — как
    // наблюдение, а не как отказ.
    const external = [];
    page.on("console", (m) => {
      if (m.type() !== "error") return;
      const text = m.text().slice(0, 140);
      // «Failed to load resource: …» — эхо неудавшегося запроса, и адреса в
      // нём нет. Отличить свой ресурс от чужого по такой строке невозможно, а
      // тот же отказ уже приходит событием запроса, где адрес есть. Считать
      // обе записи — считать один отказ дважды и приписать витрине чужой.
      if (text.startsWith("Failed to load resource")) return;
      errors.push("console: " + text);
    });
    page.on("requestfailed", (r) => {
      const line = "request: " + r.url().slice(0, 120);
      (r.url().startsWith(BASE) ? errors : external).push(line);
    });
    page.on("response", (r) => {
      if (r.status() < 400 || !r.url().startsWith(BASE)) return;
      if (expecting404 && r.status() === 404) return;
      errors.push(`response ${r.status()}: ` + r.url().slice(0, 120));
    });

    const routes = titleHref ? [...ROUTES, ["title", titleHref]] : ROUTES;
    for (const [name, route] of routes) {
      const expect404 = name === "not-found";
      expecting404 = expect404;
      const response = await page.goto(BASE + route, { waitUntil: "load" }).catch(() => null);
      await page.evaluate(() => document.fonts.ready).catch(() => {});
      const shot = path.join(OUT, `${name}-${width}.png`);
      await page.screenshot({ path: shot });

      const m = await page.evaluate(() => {
        const doc = document.documentElement;
        const player = document.querySelector("video-player, .player, [class*='player']");
        const box = player ? player.getBoundingClientRect() : null;
        return {
          h1: document.querySelectorAll("h1").length,
          titleLinks: document.querySelectorAll('a[href^="/title/"]').length,
          overflow: doc.scrollWidth > doc.clientWidth + 1,
          scrollWidth: doc.scrollWidth,
          clientWidth: doc.clientWidth,
          playerVisible: box ? box.width > 0 && box.height > 0 : false,
          playerRatio: box && box.height > 0 ? Math.round((box.width / box.height) * 100) / 100 : null,
          firstTitle: document.querySelector('a[href^="/title/"]')?.getAttribute("href") || null,
        };
      });
      if (!titleHref && m.firstTitle) titleHref = m.firstTitle;

      report.push({
        route: name, width, path: route,
        status: response ? response.status() : "нет ответа",
        expected: expect404 ? 404 : 200,
        ...m,
        errors: [...errors],
        external: [...external],
        screenshot: shot,
      });
      errors.length = 0;
      external.length = 0;
    }
    await context.close();
  }
  await browser.close();

  fs.writeFileSync(path.join(OUT, "smoke.json"),
    JSON.stringify({ base: BASE, captured_at_utc: new Date().toISOString(), report }, null, 2));

  let failed = 0;
  for (const r of report) {
    const statusBad = r.status !== r.expected;
    const bad = statusBad || r.overflow || r.errors.length > 0 || (r.route === "home" && r.h1 !== 1);
    if (bad) failed += 1;
    console.log(
      `${bad ? "ОТКАЗ " : "  ок  "} ${r.route.padEnd(14)} ${String(r.width).padStart(4)}  ` +
      `${String(r.status).padStart(3)}/${r.expected}  h1=${r.h1} ссылок=${String(r.titleLinks).padStart(3)} ` +
      `вбок=${r.overflow ? r.scrollWidth + ">" + r.clientWidth : "нет"} ошибок=${r.errors.length}`);
    for (const e of r.errors.slice(0, 2)) console.log("        " + e);
    if (r.external.length) console.log(`        (внешних отказов ${r.external.length} — провайдер, не витрина)`);
  }
  console.log(`\nпроверок ${report.length}, с отказом ${failed}`);
  process.exit(failed ? 1 : 0);
})();
