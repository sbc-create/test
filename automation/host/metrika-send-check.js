/**
 * Отправка события Метрики из браузера — измеряется, а не предполагается.
 *
 * Считаются ТРИ разные вещи, которые легко слить в одну и потом ошибиться:
 *   1. счётчик инициализирован ровно один раз (иначе визит посчитается дважды);
 *   2. браузер отправил запрос на приёмник Метрики (mc.yandex.ru/watch/...);
 *   3. приёмник ответил кодом 2xx/3xx, то есть запрос не заблокирован.
 *
 * Приём данных в кабинете этим не проверяется и здесь не заявляется: между
 * отправкой и появлением визита в отчётах проходит время, и утверждать приём
 * по факту отправки — ровно та ошибка, из-за которой «подключено» и «работает»
 * перестают различаться.
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
if (!chromium) { console.error('playwright не найден'); process.exit(4); }

const ЦЕЛИ = process.argv.slice(2);
if (!ЦЕЛИ.length) { console.error('нужны адреса витрин'); process.exit(2); }

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  let плохих = 0;
  for (const база of ЦЕЛИ) {
    const page = await browser.newPage();
    const запросы = [];
    page.on('request', r => {
      const u = r.url();
      if (/mc\.yandex\.(ru|com)\/(watch|metrika)/.test(u)) запросы.push({ url: u, status: null });
    });
    page.on('response', async r => {
      const u = r.url();
      if (/mc\.yandex\.(ru|com)\/(watch|metrika)/.test(u)) {
        const з = запросы.find(x => x.url === u && x.status === null);
        if (з) з.status = r.status();
      }
    });
    let счётчиков = 0, инициализаций = 0;
    try {
      await page.goto(база, { waitUntil: 'load', timeout: 60000 });
      const разметка = await page.content();
      const найдено = [...разметка.matchAll(/ym\((\d{6,10})\s*,\s*['"]init/g)].map(m => m[1]);
      счётчиков = new Set(найдено).size;
      инициализаций = найдено.length;
      await page.waitForTimeout(7000);
    } catch (ош) {
      console.log(`${база}: страница не открылась — ${(ош.message || ош).toString().split('\n')[0]}`);
      плохих++; await page.close(); continue;
    }
    const коды = запросы.map(з => з.status).filter(с => с !== null);
    const принятых = коды.filter(с => с >= 200 && с < 400).length;
    const ок = счётчиков === 1 && инициализаций === 1 && запросы.length > 0 && принятых > 0;
    if (!ок) плохих++;
    console.log(`${ок ? 'PASS' : 'FAIL'}  ${база}`);
    console.log(`   счётчиков в разметке ${счётчиков}, инициализаций ${инициализаций}`);
    console.log(`   запросов к приёмнику ${запросы.length}, ответов 2xx/3xx ${принятых}`
      + (коды.length ? ` (коды ${[...new Set(коды)].join(',')})` : ''));
    await page.close();
  }
  await browser.close();
  process.exit(плохих ? 1 : 0);
})();
