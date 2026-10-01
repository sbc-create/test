/** Главная в браузере: что показывает блок новинок и что падает по сети. */
const path = require('path');
const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright'),
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  'playwright', 'playwright-core',
];
let chromium = null;
for (const где of КАНДИДАТЫ) { try { chromium = require(где).chromium; break; } catch {} }
if (!chromium) { console.error('playwright не найден'); process.exit(4); }

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  for (const база of process.argv.slice(2)) {
    const page = await browser.newPage();
    const плохие = [];
    const ошибки = [];
    page.on('response', r => { if (r.status() >= 400) плохие.push(`${r.status()} ${r.url().slice(0, 110)}`); });
    page.on('requestfailed', r => плохие.push(`FAILED ${r.url().slice(0, 110)} ${r.failure()?.errorText || ''}`));
    page.on('console', m => { if (m.type() === 'error') ошибки.push(m.text().slice(0, 160)); });
    page.on('pageerror', e => ошибки.push(('pageerror: ' + (e.message || e)).slice(0, 160)));
    try {
      await page.goto(база, { waitUntil: 'networkidle', timeout: 90000 });
    } catch (e) { console.log(`${база}: навигация — ${(e.message || e).toString().split('\n')[0]}`); }
    await page.waitForTimeout(4000);
    const свод = await page.evaluate(() => {
      const текст = document.body.innerText || '';
      const секции = [...document.querySelectorAll('section, [class*="shelf"], [class*="portal-"]')]
        .map(э => {
          const h = э.querySelector('h1,h2,h3');
          const карт = э.querySelectorAll('a[href*="/anime/"]').length;
          return h ? { заголовок: h.innerText.trim().slice(0, 40), карточек: карт } : null;
        })
        .filter(Boolean);
      const уник = [];
      for (const с of секции) if (!уник.some(u => u.заголовок === с.заголовок)) уник.push(с);
      return {
        всегоКарточек: document.querySelectorAll('a[href*="/anime/"]').length,
        загрузок: (текст.match(/Загрузка/g) || []).length,
        секции: уник.slice(0, 14),
      };
    });
    console.log(`\n=== ${база} ===`);
    console.log('   карточек на странице:', свод.всегоКарточек, '| надписей «Загрузка»:', свод.загрузок);
    for (const с of свод.секции) console.log(`   ${с.заголовок.padEnd(42)} карточек ${с.карточек}`);
    if (плохие.length) { console.log('   сетевые отказы:'); плохие.slice(0, 6).forEach(п => console.log('     ', п)); }
    if (ошибки.length) { console.log('   ошибки в консоли:'); ошибки.slice(0, 5).forEach(п => console.log('     ', п)); }
    await page.close();
  }
  await browser.close();
})();
