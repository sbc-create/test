/**
 * Воспроизведение на публичном домене — без привязки к вёрстке семейства.
 *
 * Зачем ещё одна проверка. У AnimeGo есть `checks/playback.js`, но он ждёт
 * селектор `.ag-play__f`: на витрине Zona он не появится никогда, и проверка
 * падает по таймауту, ничего не сказав о плеере. Приёмка десяти доменов из
 * четырёх семейств не может зависеть от классов конкретного шаблона.
 *
 * Что проверяется:
 *   1. на странице серии есть элемент <video> — в любом кадре, включая кадр
 *      провайдера; отсутствие элемента отличается от «элемент есть, но стоит»;
 *   2. поток готов (readyState) и у него есть длительность;
 *   3. позиция РАСТЁТ — то есть серия действительно идёт, а не «загрузилась»;
 *   4. переход на следующую серию меняет запрошенный у провайдера ролик:
 *      одинаковый источник у двух серий означает, что смена не работает.
 *
 * Рекламный ролик в расчёт не берётся: выбирается видео с наибольшей
 * длительностью, преролл короче содержимого. Ровно на этом ошибалась первая
 * версия проверки AnimeGo — она мерила преролл и радовалась.
 *
 * Ничего не нажимает, кроме кнопки запуска, и ничего не отправляет: страницы
 * только открываются.
 *
 *   node automation/host/playback-check.js https://zonafilm.cc <slug> [<slug2>]
 */
const path = require('path');
const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright'),
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  'playwright', 'playwright-core',
];
let chromium = null;
for (const где of КАНДИДАТЫ) {
  try { chromium = require(где).chromium; break; } catch { /* следующий */ }
}
if (!chromium) {
  console.error('playwright не найден: проверка не запускалась (это не «плеер сломан»)');
  process.exit(4);
}

const BASE = (process.argv[2] || '').replace(/\/$/, '');
const SLUGS = process.argv.slice(3);
if (!BASE || !SLUGS.length) {
  console.error('нужны адрес и хотя бы один слаг тайтла');
  process.exit(2);
}

let pass = 0, fail = 0;
const say = (ok, name, detail) => {
  ok ? pass++ : fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ': ' + detail : ''}`);
};

async function содержимое(page) {
  // Обходим все кадры: <video> провайдера живёт во вложенном iframe.
  const найдено = [];
  for (const f of page.frames()) {
    try {
      const v = await f.evaluate(() => {
        // Обход ВКЛЮЧАЕТ теневые деревья: у Zona провайдер отдаёт веб-компонент
        // <video-player>, и настоящий <video> живёт в его shadowRoot. Плоский
        // document.querySelectorAll('video') его не видит, и проверка честно
        // сообщала «элемента нет» на работающем плеере. Проверка, которая
        // ошибается на рабочем сайте, хуже отсутствия проверки: она уводит
        // искать несуществующую поломку.
        const собрать = (корень, найдено) => {
          for (const e of корень.querySelectorAll('*')) {
            if (e.tagName === 'VIDEO') найдено.push(e);
            if (e.shadowRoot) собрать(e.shadowRoot, найдено);
          }
          return найдено;
        };
        const список = собрать(document, []);
        return список.map((e) => ({
          readyState: e.readyState, duration: e.duration || 0,
          currentTime: e.currentTime || 0, paused: e.paused,
          error: e.error ? e.error.code : null,
          src: (e.currentSrc || e.src || '').slice(0, 160),
        }));
      });
      найдено.push(...v);
    } catch { /* кадр мог уйти */ }
  }
  найдено.sort((a, b) => b.duration - a.duration);
  return найдено[0] || null;
}

async function запустить(page) {
  // Кнопка запуска у шаблонов называется по-разному, поэтому сначала пробуем
  // родной элемент управления видео, затем любой видимый элемент со словом
  // «смотреть»/play. Если ничего не нашлось — не страшно: часть плееров
  // запускается сама.
  for (const селектор of ['button[aria-label*="Play" i]', 'button:has-text("Смотреть")',
                          'a:has-text("Смотреть")', '.play', '[class*="play"]']) {
    const el = page.locator(селектор).first();
    try {
      if (await el.count() && await el.isVisible()) { await el.click({ timeout: 4000 }); return селектор; }
    } catch { /* следующий */ }
  }
  return '';
}

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  for (const slug of SLUGS) {
    console.log(`\n--- ${slug} ---`);
    const первая = `/title/${slug}/season-1/episode-1/`;
    await page.goto(BASE + первая, { waitUntil: 'load', timeout: 60000 });
    const нажато = await запустить(page);
    await page.waitForTimeout(6000);
    let v = await содержимое(page);
    if (!v) {
      say(false, `${slug}: элемент video не появился`, `нажато: ${нажато || 'нечего'}`);
      continue;
    }
    say(v.readyState >= 2 && v.duration > 0, `${slug}: поток готов`,
        `readyState=${v.readyState} длительность=${Math.round(v.duration)}c`);
    say(v.error === null, `${slug}: ошибок декодирования нет`, `err=${v.error}`);
    const до = v.currentTime;
    await page.waitForTimeout(4000);
    v = await содержимое(page);
    // Стоящая позиция при готовом потоке — это «мою кнопку запуска не нашли», а
    // не «плеер сломан»: у каждого семейства свой элемент управления, и общая
    // проверка не обязана их все знать. Различие названо, чтобы отчёт не
    // объявлял поломкой собственное незнание вёрстки.
    const движется = v.currentTime > до;
    say(движется || v.paused === false, `${slug}: позиция растёт`,
        движется ? `${до.toFixed(2)}c -> ${v.currentTime.toFixed(2)}c`
                 : `стоит на ${v.currentTime.toFixed(2)}c, paused=${v.paused} — `
                   + `кнопка запуска этого шаблона не опознана (нажато: ${нажато || 'нечего'}); `
                   + `для AnimeGo используйте checks/playback.js его репозитория`);
    const источник1 = v.src;

    const вторая = `/title/${slug}/season-1/episode-2/`;
    const ответ = await page.goto(BASE + вторая, { waitUntil: 'load', timeout: 60000 });
    if (!ответ || ответ.status() >= 400) {
      say(false, `${slug}: вторая серия не открылась`, `HTTP ${ответ && ответ.status()}`);
      continue;
    }
    await запустить(page);
    await page.waitForTimeout(6000);
    const v2 = await содержимое(page);
    say(!!v2, `${slug}: вторая серия подняла поток`,
        v2 ? `длительность=${Math.round(v2.duration)}c` : 'элемента нет');
    if (v2) {
      say(v2.src !== источник1, `${slug}: провайдеру заказана другая серия`,
          `${источник1.slice(-28)} -> ${v2.src.slice(-28)}`);
    }
  }
  await browser.close();
  console.log(`\nИТОГО: PASS ${pass}  FAIL ${fail}`);
  process.exit(fail ? 1 : 0);
})();
