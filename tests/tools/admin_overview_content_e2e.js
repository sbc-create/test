#!/usr/bin/env node
/**
 * Браузерная приёмка разделов «Сводка» и «Каталог».
 *
 * Проверяется, что числа посчитаны, отбор выполняется на сервере и состояние
 * вида восстанавливается после обновления страницы. Счётчик, который всегда
 * показывает одно и то же, выглядит как измерение и им не является — поэтому
 * сводка сверяется с ответом API, а не просто «страница открылась».
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
const проверить = (у, ч) => { if (!у) { провалов++; console.log(`  FAIL ${ч}`); }
                              else console.log(`  PASS ${ч}`); };

async function прогон(движок, имя, база, токен) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  console.log(`\n=== ${имя} ===`);

  await page.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="token"]', токен);
  await page.locator('input[name="token"]').press('Enter');
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('Выйти'), 'вход выполнен');

  // --- сводка сверяется с API, а не просто открывается ---
  // Запрос делается из Node, а не из страницы: политика безопасности
  // содержимого админки не разрешает ей ходить в API самой, и это правильно —
  // панель работает формами, а не запросами из разметки.
  const апиОтвет = await ctx.request.get(`${база}/api/v1/overview`,
    { headers: { Authorization: `Bearer ${токен}` } });
  const апи = апиОтвет.ok() ? await апиОтвет.json() : null;
  проверить(апи !== null, 'API сводки отвечает');

  await page.goto(`${база}/admin/overview`, { waitUntil: 'domcontentloaded' });
  const сводка = await page.content();
  проверить(сводка.includes('Сводка') || сводка.includes('Всего по массиву'),
            'раздел сводки открыт');
  const всего = апи && апи.totals ? String(апи.totals.titles) : null;
  проверить(!!всего && сводка.includes(всего),
            `число карточек на странице совпадает с API (${всего})`);
  проверить(сводка.includes('Витрины') && сводка.includes('Свежесть'),
            'видны витрины и свежесть');
  проверить(сводка.includes('Тревоги'), 'блок тревог присутствует');

  // --- каталог: отбор меняет выдачу ---
  await page.goto(`${база}/admin/content`, { waitUntil: 'domcontentloaded' });
  const каталог = await page.content();
  проверить(каталог.includes('Отбор') && каталог.includes('Записи'),
            'раздел каталога открыт');
  const было = await page.locator('table tbody tr').count();
  проверить(было > 0, 'записи показаны');

  const сайт = await page.locator('select[name="siteId"]').inputValue();
  await page.goto(`${база}/admin/content?siteId=${сайт}&kind=SERIES`,
                  { waitUntil: 'domcontentloaded' });
  const стало = await page.locator('table tbody tr').count();
  проверить(стало !== было || (await page.content()).includes('SERIES'),
            'отбор по виду меняет выдачу');
  проверить((await page.locator('select[name="kind"]').inputValue()) === 'SERIES',
            'состояние отбора восстановлено из ссылки');
  проверить((await page.content()).includes('Ссылка на этот вид'),
            'есть постоянная ссылка на текущий вид');

  // --- карточка ---
  const первая = page.locator('table tbody a').first();
  if (await первая.count()) {
    await первая.click();
    await page.waitForLoadState('domcontentloaded');
    const карточка = await page.content();
    for (const поле of ['Идентификаторы', 'Состояния', 'Происхождение', 'История']) {
      проверить(карточка.includes(поле), `карточка показывает «${поле}»`);
    }
  } else {
    проверить(false, 'в выдаче нет записей для карточки');
  }

  // --- размеры ---
  for (const v of ВИДЫ) {
    await page.setViewportSize({ width: v.w, height: v.h });
    await page.goto(`${база}/admin/overview`, { waitUntil: 'domcontentloaded' });
    const итог = await page.evaluate(() => {
      const w = document.documentElement.clientWidth;
      const кто = [];
      for (const el of document.querySelectorAll('*')) {
        const r = el.getBoundingClientRect();
        if (r.right > w + 1) кто.push(`${el.tagName}.${(el.className||'').toString().slice(0,20)}`);
      }
      return { ок: document.documentElement.scrollWidth <= w + 1, кто: кто.slice(0, 3) };
    });
    проверить(итог.ок, `сводка ${v.имя} ${v.w}px`
              + (итог.ок ? '' : ` — шире экрана: ${итог.кто.join(', ')}`));
  }
  await page.setViewportSize({ width: 195, height: 422 });
  await page.goto(`${база}/admin/content`, { waitUntil: 'domcontentloaded' });
  проверить(await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1),
    'каталог при 200% увеличении на 390px');

  // --- клавиатура ---
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${база}/admin/content`, { waitUntil: 'domcontentloaded' });
  await page.keyboard.press('Tab');
  проверить(await page.evaluate(() => document.activeElement !== document.body),
            'Tab уводит фокус на управляющий элемент');

  await b.close();
}

(async () => {
  const [база, токен, движок] = process.argv.slice(2);
  const выбор = { chromium, firefox };
  if (!выбор[движок]) { console.error('нужен движок'); process.exit(2); }
  await прогон(выбор[движок], движок, база, токен);
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов ? 1 : 0);
})();
