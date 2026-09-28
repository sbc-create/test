#!/usr/bin/env node
/**
 * Браузерная приёмка рабочего потока разбора.
 *
 * Проверяется путь решения ДО ВИТРИНЫ: сверка «было/стало» → утверждение
 * вторым человеком → публикация → фактическое изменение вида в каталоге →
 * точечный откат. Плюс конкурентное редактирование: второй редактор обязан
 * получить отказ, а не тихо победить.
 *
 * Изменение вида проверяется по API каталога, а не по строке в очереди:
 * решение, не дошедшее до каталога, — это строка в списке и ничего больше.
 */
const МОДУЛЬ = process.env.PLAYWRIGHT_MODULE || 'playwright';
let playwright;
try { playwright = require(МОДУЛЬ); }
catch (e) { console.log('SKIPPED: playwright не установлен'); process.exit(2); }
const { chromium, firefox } = playwright;

let провалов = 0;
const проверить = (у, ч) => { if (!у) { провалов++; console.log(`  FAIL ${ч}`); }
                              else console.log(`  PASS ${ч}`); };

async function войти(ctx, база, токен) {
  const p = await ctx.newPage();
  await p.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="token"]', токен);
  await p.locator('input[name="token"]').press('Enter');
  await p.waitForLoadState('domcontentloaded');
  return p;
}

async function прогон(движок, имя, база, токенРед, токенВед) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} ===`);
  const ctxРед = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const ctxВед = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const редактор = await войти(ctxРед, база, токенРед);
  const ведущий = await войти(ctxВед, база, токенВед);
  проверить((await редактор.content()).includes('Выйти'), 'редактор вошёл');
  проверить((await ведущий.content()).includes('Выйти'), 'ведущий вошёл');

  // --- находим открытую спорную запись ---
  await редактор.goto(`${база}/admin/review?state=OPEN`, { waitUntil: 'domcontentloaded' });
  const ссылка = редактор.locator('table a[href^="/admin/review/"]').first();
  проверить(await ссылка.count() > 0, 'в очереди есть открытые записи');
  const href = await ссылка.getAttribute('href');
  const itemId = href.split('/').pop();
  await редактор.goto(`${база}${href}`, { waitUntil: 'domcontentloaded' });

  // --- сверка «было/стало» видна до решения ---
  const карточка = await редактор.content();
  проверить(карточка.includes('Что изменится на витрине'), 'сверка показана');

  // --- решение редактора ---
  const версия = await редактор.locator('input[name="expectedVersion"]').first()
    .getAttribute('value');
  await редактор.locator('form[action$="/decide"] input[name="note"]').first()
    .fill('по тегу источника');
  await редактор.locator('form[action$="/decide"] button[type="submit"]').first().click();
  await редактор.waitForLoadState('domcontentloaded');
  проверить((await редактор.content()).includes('RESOLVED'), 'решение записано');

  // --- конкурентное редактирование: второй по устаревшей версии ---
  const конкурент = await ctxВед.request.post(
    `${база}/api/v1/review-queue/${itemId}/decide`,
    { headers: { Authorization: `Bearer ${токенВед}`, 'Content-Type': 'application/json' },
      data: { value: 'MOVIE', expectedVersion: Number(версия) } });
  проверить(конкурент.status() === 409,
            `второй редактор по устаревшей версии получает отказ (${конкурент.status()})`);

  // --- утверждение собственного решения запрещено ---
  const своё = await ctxРед.request.post(
    `${база}/api/v1/review-queue/${itemId}/approve`,
    { headers: { Authorization: `Bearer ${токенРед}`, 'Content-Type': 'application/json' },
      data: {} });
  проверить(своё.status() === 409, 'утвердить собственное решение нельзя');

  // --- утверждение ведущим через панель ---
  await ведущий.goto(`${база}${href}`, { waitUntil: 'domcontentloaded' });
  const форма = ведущий.locator('form[action$="/approve"]');
  проверить(await форма.count() > 0, 'ведущему показано утверждение');
  await форма.locator('input[name="note"]').fill('проверил доказательства');
  await форма.locator('button[type="submit"]').click();
  await ведущий.waitForLoadState('domcontentloaded');
  проверить((await ведущий.content()).includes('APPROVED'), 'решение утверждено');

  // --- публикация ---
  await ведущий.locator('form[action$="/publish"] button').click();
  await ведущий.waitForLoadState('domcontentloaded');
  const после = await ведущий.content();
  проверить(после.includes('PUBLISHED'), 'решение опубликовано');

  // --- проверка на витрине: вид действительно изменился ---
  const запись = await ctxВед.request.get(`${база}/api/v1/review-queue/${itemId}`,
    { headers: { Authorization: `Bearer ${токенВед}` } });
  const тело = await запись.json();
  const [сайт, внешний] = String(тело.internalEntityId).split(':');
  const карточкаApi = await ctxВед.request.get(
    `${база}/api/v1/content/${сайт}/${внешний}`,
    { headers: { Authorization: `Bearer ${токенВед}` } });
  const данные = await карточкаApi.json();
  проверить(данные.contentKind === тело.decidedValue,
            `вид в каталоге стал ${тело.decidedValue} (сейчас ${данные.contentKind})`);
  проверить((данные.kindConflicts || []).length === 0, 'конфликт снят решением');

  // --- точечный откат ---
  const откат = ведущий.locator('form[action$="/unpublish"]');
  проверить(await откат.count() > 0, 'откат доступен после публикации');
  await откат.locator('input[name="note"]').fill('проверка отката');
  await откат.locator('button[type="submit"]').click();
  await ведущий.waitForLoadState('domcontentloaded');
  проверить((await ведущий.content()).includes('APPROVED'), 'снято с витрины');
  const снова = await ctxВед.request.get(`${база}/api/v1/content/${сайт}/${внешний}`,
    { headers: { Authorization: `Bearer ${токенВед}` } });
  проверить((await снова.json()).contentKind === 'UNKNOWN',
            'вид вернулся к неустановленному');

  await b.close();
}

(async () => {
  const [база, токенРед, токенВед, движок] = process.argv.slice(2);
  const выбор = { chromium, firefox };
  if (!выбор[движок]) { console.error('нужен движок'); process.exit(2); }
  await прогон(выбор[движок], движок, база, токенРед, токенВед);
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов ? 1 : 0);
})();
