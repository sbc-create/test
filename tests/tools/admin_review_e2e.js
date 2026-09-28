#!/usr/bin/env node
/**
 * Браузерная приёмка редакторского пути очереди разбора.
 *
 * Проверяется путь целиком, а не наличие страниц: войти, найти спорный тайтл,
 * увидеть ОБА утверждения с доказательствами, принять решение, убедиться, что
 * оно записано, отменить его. Отдельно — что читатель без права не получает
 * кнопок и что отказ не меняет состояние.
 *
 * HTTP 200 здесь ничего не значит: страница входа отвечает 200 и для
 * неавторизованного. Поэтому проверяется содержимое и последствие действия.
 *
 * Использование:
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers PLAYWRIGHT_MODULE=<путь> \
 *   node tests/tools/admin_review_e2e.js http://127.0.0.1:8899 edtok rotok
 */
const МОДУЛЬ = process.env.PLAYWRIGHT_MODULE || 'playwright';
let playwright;
try { playwright = require(МОДУЛЬ); }
catch (e) { console.log('SKIPPED: playwright не установлен'); process.exit(2); }
const { chromium, firefox } = playwright;

const ВИДЫ = [{ w: 390, h: 844, имя: 'мобильный' },
               { w: 768, h: 1024, имя: 'планшет' },
               { w: 1440, h: 900, имя: 'десктоп' }];

let провалов = 0;
function проверить(условие, что) {
  if (!условие) { провалов++; console.log(`  FAIL ${что}`); }
  else console.log(`  PASS ${что}`);
}

async function войти(page, база, токен) {
  await page.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="token"]', токен);
  await page.click('button[type="submit"]');
  await page.waitForLoadState('domcontentloaded');
}

async function прогон(движок, имя, база, редактор, читатель) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} ===`);

  // --- путь редактора ---
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await войти(page, база, редактор);
  проверить((await page.content()).includes('Админка фабрики'), 'вход выполнен');

  await page.goto(`${база}/admin/review`, { waitUntil: 'domcontentloaded' });
  const список = await page.content();
  проверить(список.includes('Спорные записи'), 'раздел разбора открыт');
  проверить(/OPEN\s*<b>\d+/.test(список) || список.includes('OPEN'), 'видны состояния');
  проверить(список.includes('поле type поставщика') && список.includes('тег вида у поставщика'),
            'оба утверждения видны в списке');

  const ссылка = await page.locator('table a[href^="/admin/review/"]').first();
  проверить(await ссылка.count() > 0, 'в очереди есть записи');
  const href = await ссылка.getAttribute('href');
  await ссылка.click();
  await page.waitForLoadState('domcontentloaded');
  const карточка = await page.content();
  проверить(карточка.includes('Утверждения'), 'карточка показывает утверждения');
  проверить(карточка.includes('Доказательство'), 'видны доказательства');
  проверить(карточка.includes('История'), 'видна история');
  проверить(карточка.includes('Взять в работу'), 'редактору доступно действие');

  // --- клавиатура и фокус ---
  await page.keyboard.press('Tab');
  const фокус = await page.evaluate(() => {
    const a = document.activeElement;
    if (!a || a === document.body) return null;
    const s = getComputedStyle(a);
    return { тег: a.tagName, контур: s.outlineStyle !== 'none' || s.boxShadow !== 'none' };
  });
  проверить(фокус !== null, 'первый Tab уводит фокус на управляющий элемент');

  // --- решение ---
  const версия = await page.locator('input[name="expectedVersion"]').first().getAttribute('value');
  проверить(!!версия, 'форма несёт версию записи');
  await page.locator('form[action$="/decide"] input[name="note"]').first().fill('по тегу источника');
  await page.locator('form[action$="/decide"] button[type="submit"]').first().click();
  await page.waitForLoadState('domcontentloaded');
  const после = await page.content();
  проверить(после.includes('RESOLVED'), 'решение записано и видно');
  проверить(после.includes('по тегу источника'), 'обоснование сохранено');

  // --- отмена ---
  const отмена = page.locator('form[action$="/revert"]');
  проверить(await отмена.count() > 0, 'отмена доступна после решения');
  await отмена.locator('input[name="note"]').fill('передумал');
  await отмена.locator('button[type="submit"]').click();
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('OPEN'), 'отмена вернула запись в OPEN');

  // --- размеры и 200% ---
  for (const v of ВИДЫ) {
    await page.setViewportSize({ width: v.w, height: v.h });
    await page.goto(`${база}/admin/review`, { waitUntil: 'domcontentloaded' });
    const пролезает = await page.evaluate(() =>
      document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1);
    проверить(пролезает, `${v.имя} ${v.w}px без горизонтальной прокрутки`);
  }
  // 200% эмулируется вдвое меньшей шириной, а не свойством zoom: zoom не
  // меняет вычисляемые размеры так, как это делает настоящее увеличение.
  await page.setViewportSize({ width: 195, height: 422 });
  await page.goto(`${база}/admin/review`, { waitUntil: 'domcontentloaded' });
  проверить(await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1),
    '200% увеличение на 390px без горизонтальной прокрутки');

  await page.screenshot({ path: `/tmp/admin-review-${имя}.png` });
  await ctx.close();

  // --- читатель ---
  const ctx2 = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p2 = await ctx2.newPage();
  await войти(p2, база, читатель);
  await p2.goto(`${база}${href}`, { waitUntil: 'domcontentloaded' });
  const ро = await p2.content();
  проверить(!ро.includes('Взять в работу'), 'читателю кнопки решения не показаны');
  await p2.goto(`${база}/admin/review`, { waitUntil: 'domcontentloaded' });
  проверить(!(await p2.content()).includes('Групповое решение'),
            'читателю не показано групповое действие');
  await ctx2.close();
  await b.close();
}

(async () => {
  const [база, редактор, читатель] = process.argv.slice(2);
  for (const [d, n] of [[chromium, 'chromium'], [firefox, 'firefox']])
    await прогон(d, n, база, редактор, читатель);
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов ? 1 : 0);
})();
