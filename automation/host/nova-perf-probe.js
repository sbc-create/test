/**
 * Замер скорости публичной страницы настоящим браузером.
 *
 * Зачем не curl. `curl` измеряет ответ сервера и ничего не знает ни о LCP, ни
 * о сдвигах вёрстки, ни о том, сколько запросов страница делает дальше. Часть
 * задержки, которую видит посетитель, появляется уже после последнего байта
 * HTML, и без браузера она невидима.
 *
 * Что снимается за один проход:
 *   сеть      DNS, соединение, TLS, перенаправления, TTFB, полный HTML, размер
 *   страница  LCP (и его элемент), CLS, число запросов, вес по типам,
 *             длинные задачи (>50 мс) и их сумма
 *
 * Условия задаются явно и пишутся в отчёт: профиль (desktop|mobile),
 * ограничение CPU и сети, холодный или повторный визит. Без записанных условий
 * число не сравнимо ни с чем, а «стало быстрее» превращается в «замерили в
 * другой раз».
 *
 * Повторы: --runs N. В отчёт идут все значения, медиана и разброс. Одиночный
 * прогон не выдаётся за статистику.
 *
 * Аргументы:
 *   --urls <json>       [{url, name}] или ["url", …]
 *   --profile desktop|mobile
 *   --runs N            повторов на адрес (по умолчанию 3)
 *   --warm              второй визит в том же контексте (кэш прогрет)
 *   --out <json>
 */
const fs = require('fs');
const path = require('path');

const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  '/home/claude/node_modules/playwright-core',
];
let chromium = null;
for (const к of КАНДИДАТЫ) {
  try { chromium = require(к).chromium; break; } catch (e) { /* следующий */ }
}
if (!chromium) { console.error('playwright-core не найден'); process.exit(2); }

function arg(имя, по) { const i = process.argv.indexOf(имя); return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : по; }
function флаг(имя) { return process.argv.includes(имя); }

// Профили названы числами, а не словами «медленный телефон»: в отчёте обязано
// быть видно, что именно ограничивалось.
const ПРОФИЛИ = {
  desktop: { viewport: { width: 1440, height: 900 }, cpu: 1, сеть: null,
             ua: null, описание: '1440x900, CPU x1, сеть без ограничения' },
  mobile:  { viewport: { width: 390, height: 844 }, cpu: 4,
             сеть: { downloadThroughput: 1.6 * 1024 * 1024 / 8,
                     uploadThroughput: 750 * 1024 / 8, latency: 150 },
             ua: 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
                 + '(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
             описание: '390x844, CPU x4 замедление, 1.6 Мбит/с, RTT 150 мс' },
};

const СБОР = `(() => new Promise((готово) => {
  const итог = { lcp: null, lcpЭлемент: '', cls: 0, длинные: [], запросов: 0, вес: {} };
  try {
    new PerformanceObserver((l) => {
      const e = l.getEntries(); const п = e[e.length - 1];
      if (п) { итог.lcp = п.startTime; итог.lcpЭлемент = п.element ? (п.element.tagName + (п.element.currentSrc ? ' ' + п.element.currentSrc.slice(-60) : '')) : (п.url || '').slice(-60); }
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (e) {}
  try {
    new PerformanceObserver((l) => {
      for (const п of l.getEntries()) if (!п.hadRecentInput) итог.cls += п.value;
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) {}
  try {
    new PerformanceObserver((l) => {
      for (const п of l.getEntries()) итог.длинные.push(Math.round(п.duration));
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) {}
  setTimeout(() => {
    const н = performance.getEntriesByType('navigation')[0] || {};
    итог.навигация = {
      dns: н.domainLookupEnd - н.domainLookupStart,
      соединение: н.connectEnd - н.connectStart,
      tls: н.secureConnectionStart > 0 ? н.connectEnd - н.secureConnectionStart : 0,
      перенаправления: н.redirectEnd - н.redirectStart,
      ttfb: н.responseStart - н.startTime,
      htmlПолностью: н.responseEnd - н.startTime,
      размерHtml: н.encodedBodySize || 0,
      domReady: н.domContentLoadedEventEnd - н.startTime,
      загрузка: н.loadEventEnd > 0 ? н.loadEventEnd - н.startTime : null,
    };
    const р = performance.getEntriesByType('resource');
    итог.запросов = р.length;
    for (const п of р) {
      const т = п.initiatorType || 'прочее';
      итог.вес[т] = (итог.вес[т] || 0) + (п.encodedBodySize || 0);
    }
    итог.суммаДлинных = итог.длинные.reduce((a, b) => a + b, 0);
    итог.cls = Math.round(итог.cls * 1000) / 1000;
    готово(итог);
  }, 3500);
}))()`;

function медиана(значения) {
  const с = значения.filter((x) => typeof x === 'number' && !Number.isNaN(x)).sort((a, b) => a - b);
  if (!с.length) return null;
  const i = Math.floor(с.length / 2);
  return с.length % 2 ? с[i] : (с[i - 1] + с[i]) / 2;
}

(async () => {
  const профиль = ПРОФИЛИ[arg('--profile', 'desktop')] || ПРОФИЛИ.desktop;
  const повторов = parseInt(arg('--runs', '3'), 10);
  const прогрев = флаг('--warm');
  const цели = JSON.parse(fs.readFileSync(arg('--urls'), 'utf8'))
    .map((ц) => (typeof ц === 'string' ? { url: ц, name: ц } : ц));

  const браузер = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const отчёт = { профиль: arg('--profile', 'desktop'), условия: профиль.описание,
                  повторов, визит: прогрев ? 'повторный (кэш прогрет)' : 'первый (кэш пуст)',
                  снято: new Date().toISOString(), цели: [] };

  for (const цель of цели) {
    const прогоны = [];
    for (let i = 0; i < повторов; i += 1) {
      const контекст = await браузер.newContext({
        viewport: профиль.viewport, userAgent: профиль.ua || undefined,
        ignoreHTTPSErrors: true,
      });
      const страница = await контекст.newPage();
      const cdp = await контекст.newCDPSession(страница);
      if (профиль.cpu > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: профиль.cpu });
      if (профиль.сеть) await cdp.send('Network.emulateNetworkConditions', { offline: false, ...профиль.сеть });
      let ошибка = null;
      try {
        if (прогрев) {
          await страница.goto(цель.url, { waitUntil: 'load', timeout: 90000 });
          await страница.waitForTimeout(500);
        }
        const ответ = await страница.goto(цель.url, { waitUntil: 'load', timeout: 90000 });
        const снимок = await страница.evaluate(СБОР);
        снимок.код = ответ ? ответ.status() : null;
        прогоны.push(снимок);
      } catch (e) { ошибка = String(e).split('\n')[0]; прогоны.push({ ошибка }); }
      await контекст.close();
    }
    const удачные = прогоны.filter((п) => !п.ошибка);
    отчёт.цели.push({
      name: цель.name, url: цель.url, прогоны,
      медианы: {
        ttfb: медиана(удачные.map((п) => п.навигация && п.навигация.ttfb)),
        htmlПолностью: медиана(удачные.map((п) => п.навигация && п.навигация.htmlПолностью)),
        lcp: медиана(удачные.map((п) => п.lcp)),
        cls: медиана(удачные.map((п) => п.cls)),
        суммаДлинных: медиана(удачные.map((п) => п.суммаДлинных)),
        запросов: медиана(удачные.map((п) => п.запросов)),
      },
      разброс: {
        ttfbМин: Math.min(...удачные.map((п) => (п.навигация || {}).ttfb || Infinity)),
        ttfbМакс: Math.max(...удачные.map((п) => (п.навигация || {}).ttfb || 0)),
        lcpМин: Math.min(...удачные.map((п) => п.lcp || Infinity)),
        lcpМакс: Math.max(...удачные.map((п) => п.lcp || 0)),
      },
      отказов: прогоны.length - удачные.length,
    });
    const м = отчёт.цели[отчёт.цели.length - 1].медианы;
    console.log(`${цель.name}: TTFB ${м.ttfb === null ? '—' : Math.round(м.ttfb)} мс, `
      + `HTML ${м.htmlПолностью === null ? '—' : Math.round(м.htmlПолностью)} мс, `
      + `LCP ${м.lcp === null ? '—' : Math.round(м.lcp)} мс, CLS ${м.cls}, `
      + `запросов ${м.запросов}, длинных задач ${м.суммаДлинных} мс`
      + (отчёт.цели[отчёт.цели.length - 1].отказов ? `, ОТКАЗОВ ${отчёт.цели[отчёт.цели.length - 1].отказов}` : ''));
  }
  await браузер.close();
  if (arg('--out')) fs.writeFileSync(arg('--out'), JSON.stringify(отчёт, null, 1), 'utf8');
})();
