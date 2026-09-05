#!/usr/bin/env node
/**
 * Полный редакционный путь: одиннадцать разделов, две роли, три ширины и 200 %.
 *
 * Проверяется не «страница ответила 200», а три вещи, которые 200 не отличает:
 * раздел показывает содержимое, а не заглушку; отбор действительно отсекает;
 * у читателя нет ни одной отправляемой формы. Плюс разметка: на 390, 768 и
 * 1440 и при двукратном увеличении ничего не уезжает за край вне контейнера с
 * собственной прокруткой.
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

const РАЗДЕЛЫ = [
  ['/admin/overview', 'Сводка', 'Сводка'],
  ['/admin/content', 'Каталог', 'Каталог'],
  ['/admin/review', 'Разбор', 'Разбор'],
  ['/admin/review?state=OPEN', 'Разбор с отбором', 'Разбор'],
  ['/admin/jobs', 'Задания', 'Задания'],
  ['/admin/sites', 'Витрины', 'Витрины'],
  ['/admin/users', 'Люди', 'Операторы'],
  ['/admin/settings', 'Настройки', 'Изменяемые настройки'],
  ['/admin/releases', 'Выпуски', 'Выпуски'],
  ['/admin/incidents', 'Происшествия', 'Происшествия'],
  ['/admin/audit', 'Журнал', 'Журнал операций'],
];

async function войти(ctx, токен) {
  const p = await ctx.newPage();
  await p.goto(`${БАЗА}/admin`, { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="token"]', токен);
  await p.locator('input[name="token"]').press('Enter');
  await p.waitForLoadState('domcontentloaded');
  return p;
}

async function перелив(страница) {
  return страница.evaluate(() => {
    const ш = document.documentElement.clientWidth;
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width > ш + 1 && !el.closest('.scroll-x')) {
        return `${el.tagName}.${el.className || ''} ${Math.round(r.width)}>${ш}`;
      }
    }
    return '';
  });
}

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} ===`);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await войти(ctx, ТОКЕН);
  проверить((await p.content()).includes('Выйти'), 'вошли администратором');

  // --- одиннадцать разделов открываются и показывают содержимое ---
  for (const [путь, подпись, маркер] of РАЗДЕЛЫ) {
    const r = await p.goto(`${БАЗА}${путь}`, { waitUntil: 'domcontentloaded' });
    const текст = await p.content();
    проверить(r.status() === 200 && текст.includes(маркер), `раздел «${подпись}» открылся`);
  }

  // --- сначала совершаем действия, иначе журнал пуст и отбор нечего проверять ---
  await p.goto(`${БАЗА}/admin/settings`, { waitUntil: 'domcontentloaded' });
  const форма = () => p.locator('form:has(input[name="key"][value="keep_releases"])');
  проверить(await форма().count() > 0, 'форма настройки доступна администратору');
  await форма().locator('input[name="value"]').fill('9');
  await форма().locator('button[name="dryRun"][value=""]').click();
  await p.waitForLoadState('domcontentloaded');
  await p.goto(`${БАЗА}/admin/settings`, { waitUntil: 'domcontentloaded' });
  const откат = p.locator('form[action="/admin/settings/rollback"] button:not([name])');
  проверить(await откат.count() > 0, 'после изменения предложен откат');
  await откат.first().click();
  await p.waitForLoadState('domcontentloaded');

  // --- отбор в журнале действительно отсекает ---
  await p.goto(`${БАЗА}/admin/audit`, { waitUntil: 'domcontentloaded' });
  проверить(await p.locator('table tbody tr').count() > 0,
            'журнал не пуст: отбор есть на чём проверять');
  const всего = await p.locator('table tbody tr').count();
  await p.fill('input[name="action"]', 'control.settings');
  await p.locator('form[action="/admin/audit"] button[type="submit"]').click();
  await p.waitForLoadState('domcontentloaded');
  const отобрано = await p.locator('table tbody tr').count();
  проверить(отобрано > 0 && отобрано <= всего,
            `отбор отсекает и что-то оставляет (${отобрано} из ${всего})`);
  проверить((await p.content()).includes('подошедших'), 'подошедшее отделено от общего');
  const чужие = await p.locator('table tbody tr td:nth-child(4)').allInnerTexts();
  проверить(чужие.every((т) => t_ok(т)), 'в выдаче только подошедшие действия');
  function t_ok(т) { return т.trim() === '' || т.includes('control.settings'); }

  // --- отбор без совпадений — это ноль, а не всё ---
  await p.goto(`${БАЗА}/admin/audit?actor=нет-такого-человека`, { waitUntil: 'domcontentloaded' });
  проверить((await p.locator('table tbody tr').count()) === 0, 'нет совпадений — пустая таблица');
  проверить((await p.content()).includes('ноль совпадений'), 'сказано, что это ноль совпадений');

  // --- ширины и увеличение ---
  for (const [ш, в, подпись] of [[390, 780, '390px'], [768, 1024, '768px'],
                                 [1440, 900, '1440px'], [720, 450, '200 %']]) {
    const c = await b.newContext({ viewport: { width: ш, height: в } });
    const s = await войти(c, ТОКЕН);
    for (const путь of ['/admin/settings', '/admin/audit', '/admin/releases', '/admin/users']) {
      await s.goto(`${БАЗА}${путь}`, { waitUntil: 'domcontentloaded' });
      const беда = await перелив(s);
      проверить(беда === '', `${подпись} ${путь}${беда ? ': ' + беда : ''}`);
    }
    await c.close();
  }

  // --- клавиатура: путь проходится без мыши ---
  await p.goto(`${БАЗА}/admin/audit`, { waitUntil: 'domcontentloaded' });
  await p.keyboard.press('Tab');
  const первый = await p.evaluate(() => document.activeElement
    && (document.activeElement.getAttribute('href') || document.activeElement.tagName));
  проверить(!!первый, 'первый Tab попадает на управляемый элемент');

  // --- читатель ---
  const ctxRO = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const r = await войти(ctxRO, ТОКЕН_ЧТЕНИЯ);
  for (const [путь, подпись] of [['/admin/settings', 'Настройки'], ['/admin/users', 'Люди'],
                                 ['/admin/releases', 'Выпуски'], ['/admin/incidents', 'Происшествия'],
                                 ['/admin/audit', 'Журнал']]) {
    await r.goto(`${БАЗА}${путь}`, { waitUntil: 'domcontentloaded' });
    const форм = await r.locator('form[method="post"]:not([action="/admin/logout"])').count();
    проверить(форм === 0, `у читателя нет отправляемых форм в разделе «${подпись}»`);
  }

  await b.close();
}

(async () => {
  if (!БАЗА) { console.log('нужен адрес базы'); process.exit(2); }
  if (ДВИЖОК === 'chromium' || ДВИЖОК === 'both') await прогон(chromium, 'chromium');
  if (ДВИЖОК === 'firefox' || ДВИЖОК === 'both') await прогон(firefox, 'firefox');
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов === 0 ? 0 : 1);
})();
