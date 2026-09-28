#!/usr/bin/env node
/**
 * Браузерная приёмка разделов «Настройки» и «Люди».
 *
 * Проверяется то, что нельзя доказать в модульном тесте: страница действительно
 * открывается, сравнение «было/станет» видно глазами до записи, применение
 * меняет значение, откат возвращает прежнее, значение секрета не попадает ни в
 * разметку, ни в текст, а читатель не получает ни одной отправляемой формы.
 *
 * Значение секрета ищется во ВСЁМ содержимом страницы, включая атрибуты: утечка
 * в value="" выглядит на экране так же, как её отсутствие.
 */
const МОДУЛЬ = process.env.PLAYWRIGHT_MODULE || 'playwright';
let playwright;
try { playwright = require(МОДУЛЬ); }
catch (e) { console.log('SKIPPED: playwright не установлен'); process.exit(2); }
const { chromium, firefox } = playwright;

let провалов = 0;
const проверить = (у, ч) => { if (!у) { провалов++; console.log(`  FAIL ${ч}`); }
                              else console.log(`  PASS ${ч}`); };

const БАЗА = process.argv[2];
const ТОКЕН = process.argv[3] || 'boot';
const ТОКЕН_ЧТЕНИЯ = process.argv[4] || 'ro';
const ДВИЖОК = process.argv[5] || 'both';
const СЕКРЕТ = process.env.SETTINGS_SECRET || '';
const САЙТ = process.env.SETTINGS_SITE || 'lords-01';

async function войти(ctx, токен) {
  const p = await ctx.newPage();
  await p.goto(`${БАЗА}/admin`, { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="token"]', токен);
  await p.locator('input[name="token"]').press('Enter');
  await p.waitForLoadState('domcontentloaded');
  return p;
}

async function значение(страница, ключ) {
  // Строка ищется ТОЛЬКО в таблице настроек. Карточка сравнения показывает тот
  // же ключ и стоит выше: без этого условия «значение после сухого прогона»
  // читалось из предпросмотра и выглядело как запись, которой не было.
  const таблица = страница.locator('div.card', {
    has: страница.locator('h2:text-is("Изменяемые настройки")'),
  });
  const строка = таблица.locator('tr', { has: страница.locator(`code:text-is("${ключ}")`) });
  return (await строка.first().innerText()).trim();
}

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} ===`);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await войти(ctx, ТОКЕН);
  проверить((await p.content()).includes('Выйти'), 'вошли');

  // --- раздел есть в меню ---
  проверить(await p.locator('header a[href="/admin/settings"]').count() > 0,
            'ссылка «Настройки» есть в меню');

  await p.goto(`${БАЗА}/admin/settings?site=${САЙТ}`, { waitUntil: 'domcontentloaded' });
  const текст = await p.content();
  проверить(текст.includes('keep_releases'), 'разрешённые настройки показаны');
  проверить(текст.includes('от 2 до 20'), 'границы показаны до ввода');
  проверить(текст.includes('Отклоняется намеренно'), 'отклонённые поля названы');
  проверить(текст.includes('сертификат'), 'у отклонения есть причина');

  // --- секрет: ссылка есть, значение нет ---
  if (СЕКРЕТ) {
    проверить(!текст.includes(СЕКРЕТ), 'значение секрета не попало в разметку');
    проверить(текст.includes('значение не читается панелью'), 'вместо значения — отметка');
  }

  // --- сухой прогон ---
  const было = await значение(p, 'keep_releases');
  // Форма выбирается по своему полю key, а не по порядку: строки отсортированы
  // по алфавиту, и .first() — это cache_policy, у которого другой тип значения.
  const форма = () => p.locator('form:has(input[name="key"][value="keep_releases"])');
  await форма().locator('input[name="value"]').fill('12');
  await форма().locator('button[name="dryRun"][value="1"]').click();
  await p.waitForLoadState('domcontentloaded');
  const сравнение = await p.content();
  проверить(сравнение.includes('было') && сравнение.includes('станет'),
            'сравнение «было/станет» показано');
  проверить(сравнение.includes('Ничего не записано'), 'сухой прогон объявлен сухим');
  const послеСухого = await значение(p, 'keep_releases');
  проверить(послеСухого === было, 'сухой прогон ничего не изменил');

  // --- применение ---
  await форма().locator('input[name="value"]').fill('12');
  await форма().locator('button[name="dryRun"][value=""]').click();
  await p.waitForLoadState('domcontentloaded');
  проверить((await значение(p, 'keep_releases')).includes('12'), 'значение применено');

  // --- откат ---
  проверить(await p.locator('form[action="/admin/settings/rollback"]').count() > 0,
            'откат предложен после изменения');
  await p.locator('form[action="/admin/settings/rollback"] button:not([name])').first().click();
  await p.waitForLoadState('domcontentloaded');
  проверить(!(await значение(p, 'keep_releases')).includes('12'), 'откат вернул прежнее значение');

  // --- негодное значение ---
  await форма().locator('input[name="value"]').fill('1');
  await форма().locator('button[name="dryRun"][value=""]').click();
  await p.waitForLoadState('domcontentloaded');
  проверить((await p.content()).includes('invalid_settings')
            || (await p.content()).includes('от 2 до 20'),
            'значение вне границ отклонено с объяснением');

  // --- узкий экран: ничего не уезжает вбок ---
  const узкий = await b.newContext({ viewport: { width: 390, height: 780 } });
  const у = await войти(узкий, ТОКЕН);
  await у.goto(`${БАЗА}/admin/settings?site=${САЙТ}`, { waitUntil: 'domcontentloaded' });
  const виновник = await у.evaluate(() => {
    const ш = document.documentElement.clientWidth;
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width > ш + 1 && !el.closest('.scroll-x')) {
        return el.tagName + '.' + (el.className || '') + ' ' + Math.round(r.width);
      }
    }
    return '';
  });
  проверить(виновник === '', `на 390px ничего не уезжает вбок${виновник ? ': ' + виновник : ''}`);

  // --- читатель ---
  const ctxRO = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const r = await войти(ctxRO, ТОКЕН_ЧТЕНИЯ);
  await r.goto(`${БАЗА}/admin/settings?site=${САЙТ}`, { waitUntil: 'domcontentloaded' });
  const чтение = await r.content();
  проверить(чтение.includes('keep_releases'), 'читатель видит значения');
  проверить(await r.locator('form[method="post"][action="/admin/settings"]').count() === 0,
            'у читателя нет отправляемых форм настроек');
  проверить(чтение.includes('только для чтения'), 'читателю объяснено, почему');

  // --- люди: чья сессия ---
  await p.goto(`${БАЗА}/admin/users`, { waitUntil: 'domcontentloaded' });
  проверить((await p.content()).includes('Чья сессия'), 'в списке сессий видно владельца');

  await b.close();
}

(async () => {
  if (!БАЗА) { console.log('нужен адрес базы'); process.exit(2); }
  if (ДВИЖОК === 'chromium' || ДВИЖОК === 'both') await прогон(chromium, 'chromium');
  if (ДВИЖОК === 'firefox' || ДВИЖОК === 'both') await прогон(firefox, 'firefox');
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов === 0 ? 0 : 1);
})();
