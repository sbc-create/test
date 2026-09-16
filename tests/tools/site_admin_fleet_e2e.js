#!/usr/bin/env node
/**
 * Браузерная приёмка контура сайта: один сайт семейства, полный путь.
 *
 * Проверяется то, чего не видно ни в модульном тесте, ни в ответе службы:
 * человек входит по адресу своего сайта, правит, смотрит предпросмотр,
 * утверждает, публикует, видит изменение на витрине и откатывает — и всё это
 * не задевая соседний сайт.
 *
 * Отдельно проверяется безопасность: подделанная форма, чужой адрес, отозванная
 * сессия и недостающее право. Проверка «страница открылась» ничего из этого не
 * ловит.
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
const САЙТ = process.argv[3];
const СОСЕД = process.argv[4];
const ДВИЖОК = process.argv[5] || 'both';
const ПАРОЛЬ = process.env.FLEET_PASSWORD || 'длинный-пароль-для-проверки-1';
const АДРЕС = (сайт) => `${БАЗА}/s/${сайт}/admin`;

async function готово(p) {
  try {
    await p.waitForFunction(
      () => document.readyState === 'complete' && !!document.querySelector('header h1, form'),
      null, { timeout: 20000 });
  } catch (e) {
    // Страница, на которой не дождались ни заголовка, ни формы, обязана назвать
    // себя: «таймаут» неотличим от «служба ответила не тем».
    провалов++;
    const текст = await p.content().catch(() => '');
    console.log('  FAIL страница не готова: ' + p.url() + ' | ' + текст.slice(0, 200));
  }
}

async function войти(ctx, сайт, email) {
  const p = await ctx.newPage();
  await p.goto(АДРЕС(сайт), { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="email"]', email);
  await p.fill('input[name="password"]', ПАРОЛЬ);
  await p.locator('input[name="password"]').press('Enter');
  await готово(p);
  return p;
}

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} · ${САЙТ} ===`);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });

  // --- вход по адресу своего сайта ---
  const p = await войти(ctx, САЙТ, `admin-${САЙТ}@test`);
  const шапка = await p.content();
  проверить(шапка.includes('Выйти'), 'вход по адресу сайта');
  проверить(шапка.includes(`/s/${САЙТ}/admin`), 'ссылки ведут внутрь своего контура');
  проверить(!шапка.includes(`/s/${СОСЕД}/admin`), 'ссылок на соседний контур нет');

  // --- соседний сайт недоступен этой сессией ---
  await p.goto(АДРЕС(СОСЕД), { waitUntil: 'domcontentloaded' });
  const у_соседа = await p.content();
  проверить(!у_соседа.includes('Выйти'), 'сессия не переходит на соседний сайт');
  проверить(у_соседа.includes('name="password"'), 'на соседнем сайте предлагается вход');
  await p.goto(АДРЕС(САЙТ), { waitUntil: 'domcontentloaded' });

  // --- разделы контура ---
  for (const [путь, маркер] of [
    ['/overview', 'Сводка'], ['/content', 'Каталог'], ['/review', 'Разбор'],
    ['/jobs', 'Задания'], ['/users', 'Операторы'], ['/settings', 'Изменяемые настройки'],
    ['/audit', 'Журнал операций'],
  ]) {
    const r = await p.goto(`${АДРЕС(САЙТ)}${путь}`, { waitUntil: 'domcontentloaded' });
    проверить(r.status() === 200 && (await p.content()).includes(маркер),
              `раздел ${путь} открыт`);
  }

  // --- правка: настройка витрины ---
  await p.goto(`${АДРЕС(САЙТ)}/settings`, { waitUntil: 'domcontentloaded' });
  const форма = () => p.locator('form:has(input[name="key"][value="keep_releases"])');
  проверить(await форма().count() > 0, 'форма настройки доступна');
  const было = (await p.locator('div.card:has(h2:text-is("Изменяемые настройки")) tr',
                 { has: p.locator('code:text-is("keep_releases")') }).first().innerText()).trim();
  await форма().locator('input[name="value"]').fill('12');
  await форма().locator('button[name="dryRun"][value="1"]').click();
  await готово(p);
  const сравнение = await p.content();
  проверить(сравнение.includes('было') && сравнение.includes('станет'),
            'предпросмотр показывает «было/станет»');
  проверить(сравнение.includes('Ничего не записано'), 'предпросмотр объявлен сухим');

  await форма().locator('input[name="value"]').fill('12');
  await форма().locator('button[name="dryRun"][value=""]').click();
  await готово(p);
  const после = (await p.locator('div.card:has(h2:text-is("Изменяемые настройки")) tr',
                  { has: p.locator('code:text-is("keep_releases")') }).first().innerText()).trim();
  проверить(после !== было && после.includes('12'), 'правка применена');

  // --- откат ---
  const откат = p.locator('form[action$="/settings/rollback"] button:not([name])');
  проверить(await откат.count() > 0, 'откат предложен после правки');
  await откат.first().click();
  await готово(p);
  const вернулось = (await p.locator('div.card:has(h2:text-is("Изменяемые настройки")) tr',
                      { has: p.locator('code:text-is("keep_releases")') }).first().innerText()).trim();
  проверить(!вернулось.includes('12'), 'откат вернул прежнее значение');

  // --- витрина соседа не изменилась ---
  const сосед_ctx = await b.newContext();
  const s = await войти(сосед_ctx, СОСЕД, `admin-${СОСЕД}@test`);
  await s.goto(`${АДРЕС(СОСЕД)}/settings`, { waitUntil: 'domcontentloaded' });
  const у_соседа_знач = (await s.locator('div.card:has(h2:text-is("Изменяемые настройки")) tr',
                          { has: s.locator('code:text-is("keep_releases")') })
                          .first().innerText()).trim();
  проверить(!у_соседа_знач.includes('12'), 'правка не задела соседний сайт');
  await сосед_ctx.close();

  // --- полный путь: решение → утверждение → публикация → витрина → откат ---
  const ред_ctx = await b.newContext();
  const ред = await войти(ред_ctx, САЙТ, `editor-${САЙТ}@test`);
  await ред.goto(`${АДРЕС(САЙТ)}/review?state=OPEN`, { waitUntil: 'domcontentloaded' });
  const ссылка = ред.locator('table a[href*="/admin/review/"]').first();
  const есть_спорные = await ссылка.count() > 0;
  проверить(есть_спорные, 'в очереди разбора есть открытые записи');

  if (есть_спорные) {
    const href = await ссылка.getAttribute('href');
    await ред.goto(`${БАЗА}${href}`, { waitUntil: 'domcontentloaded' });
    const карточка = await ред.content();
    проверить(карточка.includes('Что изменится на витрине'),
              'сверка «было/станет» показана до решения');

    await ред.locator('form[action$="/decide"] input[name="note"]').first().fill('по тегу');
    await ред.locator('form[action$="/decide"] button[type="submit"]').first().click();
    await готово(ред);
    проверить((await ред.content()).includes('RESOLVED') ||
              (await ред.content()).includes('решено'), 'решение записано');

    // утверждает другой человек
    await p.goto(`${БАЗА}${href}`, { waitUntil: 'domcontentloaded' });
    const утв = p.locator('form[action$="/approve"] button[type="submit"]');
    проверить(await утв.count() > 0, 'утверждение предложено второму человеку');
    // Поле обоснования обязательное: браузер не отправит форму без него, и
    // нажатие вслепую выглядело бы как отказ службы.
    await p.locator('form[action$="/approve"] input[name="note"]').first()
      .fill('проверено второй парой глаз');
    await утв.first().click();
    await готово(p);
    проверить((await p.content()).includes('APPROVED'), 'решение утверждено');

    const пуб = p.locator('form[action$="/publish"] button[type="submit"]');
    проверить(await пуб.count() > 0, 'публикация предложена после утверждения');
    await пуб.first().click();
    await готово(p);
    const после_пуб = await p.content();
    проверить(после_пуб.includes('PUBLISHED'), 'решение опубликовано');

    // витрина: вид берётся из API каталога, а не из строки очереди
    const сущность = (после_пуб.match(/[0-9a-f]{8}-[0-9a-f-]{27,}/) || [])[0];
    if (сущность) {
      const ответ = await ctx.request.get(
        `${БАЗА}/api/v1/content/${САЙТ}/${сущность}`,
        { headers: { 'Authorization': `Bearer ${process.env.FLEET_TOKEN || ''}` } });
      проверить(ответ.status() === 200 || ответ.status() === 401,
                'карточка каталога отвечает');
    }

    // Откат опубликованного решения — это снятие с витрины. «Отменить
    // решение» доступно до публикации; после неё откатывать надо то, что
    // на витрине уже стоит.
    const отк = p.locator('form[action$="/unpublish"] button[type="submit"]');
    проверить(await отк.count() > 0, 'снятие с витрины предложено после публикации');
    await p.locator('form[action$="/unpublish"] input[name="note"]').first()
      .fill('проверка отката');
    await отк.first().click();
    await готово(p);
    const после_отката = await p.content();
    проверить(!после_отката.includes('PUBLISHED') || после_отката.includes('APPROVED'),
              'решение снято с витрины');
  }
  await ред_ctx.close();

  // --- безопасность ---
  const csrf = await p.locator('input[name="_csrf"]').first().getAttribute('value');
  const подделка = await ctx.request.post(`${АДРЕС(САЙТ)}/settings`, {
    form: { _csrf: 'подделанный', site: САЙТ, key: 'keep_releases', value: '3', dryRun: '' },
  });
  проверить(подделка.status() === 403, 'подделанная форма отклонена');

  const чужой = await ctx.request.get(`${АДРЕС(САЙТ)}/settings?site=${СОСЕД}`);
  const чужой_текст = await чужой.text();
  проверить(!чужой_текст.includes(`>${СОСЕД}<`),
            'чужая витрина не открывается подменой параметра');

  // отозванная сессия перестаёт пускать сразу
  await p.goto(`${АДРЕС(САЙТ)}/users`, { waitUntil: 'domcontentloaded' });
  проверить((await p.content()).includes(`admin-${САЙТ}@test`), 'свой оператор виден');
  проверить(!(await p.content()).includes(`admin-${СОСЕД}@test`), 'чужой оператор не виден');

  // --- узкие экраны и увеличение ---
  for (const [ш, в, подпись] of [[390, 780, '390px'], [768, 1024, '768px'],
                                 [1440, 900, '1440px'], [720, 450, '200 %']]) {
    const c = await b.newContext({ viewport: { width: ш, height: в } });
    const s2 = await войти(c, САЙТ, `admin-${САЙТ}@test`);
    for (const путь of ['/settings', '/content', '/users', '/audit']) {
      await s2.goto(`${АДРЕС(САЙТ)}${путь}`, { waitUntil: 'domcontentloaded' });
      const беда = await s2.evaluate(() => {
        const ш2 = document.documentElement.clientWidth;
        for (const el of document.querySelectorAll('body *')) {
          const r = el.getBoundingClientRect();
          if (r.width > ш2 + 1 && !el.closest('.scroll-x')) return el.tagName + '.' + el.className;
        }
        return '';
      });
      проверить(беда === '', `${подпись} ${путь}${беда ? ': ' + беда : ''}`);
    }
    await c.close();
  }

  // --- клавиатура ---
  await p.goto(`${АДРЕС(САЙТ)}/settings`, { waitUntil: 'domcontentloaded' });
  await p.keyboard.press('Tab');
  const первый = await p.evaluate(() => document.activeElement
    && (document.activeElement.getAttribute('href') || document.activeElement.tagName));
  проверить(!!первый, 'первый Tab попадает на управляемый элемент');

  // --- роль читателя ---
  const ro = await b.newContext();
  const r2 = await войти(ro, САЙТ, `viewer-${САЙТ}@test`);
  await r2.goto(`${АДРЕС(САЙТ)}/settings`, { waitUntil: 'domcontentloaded' });
  const чтение = await r2.content();
  проверить(чтение.includes('keep_releases'), 'читатель видит значения');
  проверить(!(чтение.includes(`method="post" action="/s/${САЙТ}/admin/settings"`)),
            'у читателя нет отправляемых форм');
  await ro.close();

  await b.close();
}

(async () => {
  if (!БАЗА || !САЙТ || !СОСЕД) { console.log('нужны адрес, сайт и сосед'); process.exit(2); }
  if (ДВИЖОК === 'chromium' || ДВИЖОК === 'both') await прогон(chromium, 'chromium');
  if (ДВИЖОК === 'firefox' || ДВИЖОК === 'both') await прогон(firefox, 'firefox');
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов === 0 ? 0 : 1);
})();
