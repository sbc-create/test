/** Содержимое именованной полки: названия, ссылки, даты, постеры. */
const path = require('path');
let chromium = null;
for (const где of [path.join('/srv/site-factory/repo','node_modules','playwright'),
                   path.join('/srv/site-factory/repo','node_modules','playwright-core'),
                   'playwright','playwright-core']) {
  try { chromium = require(где).chromium; break; } catch {}
}
if (!chromium) { console.error('playwright не найден'); process.exit(4); }
const ПОЛКА = process.argv[2];
(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  for (const база of process.argv.slice(3)) {
    const page = await browser.newPage();
    await page.goto(база, { waitUntil: 'networkidle', timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(3000);
    const данные = await page.evaluate((имя) => {
      const секции = [...document.querySelectorAll('section, div')];
      for (const э of секции) {
        const h = э.querySelector('h1,h2,h3');
        if (!h || h.innerText.trim().toUpperCase() !== имя.toUpperCase()) continue;
        const ссылки = [...э.querySelectorAll('a[href*="/anime/"]')];
        if (!ссылки.length) continue;
        return ссылки.slice(0, 20).map(a => ({
          href: a.getAttribute('href'),
          текст: (a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70),
          постер: !!a.querySelector('img'),
          время: (a.querySelector('time') || {}).getAttribute
            ? a.querySelector('time').getAttribute('datetime') : null,
        }));
      }
      return null;
    }, ПОЛКА);
    console.log(`\n=== ${база} — ${ПОЛКА} ===`);
    if (!данные) { console.log('   полка не найдена или пуста'); }
    else {
      console.log('   карточек:', данные.length);
      данные.slice(0, 8).forEach(к => console.log(
        `   ${(к.время || '—').slice(0, 16).padEnd(18)} постер ${к.постер ? 'да' : 'НЕТ'}  ${к.текст}`));
    }
    await page.close();
  }
  await browser.close();
})();
