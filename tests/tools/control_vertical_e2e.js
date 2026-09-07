// Вертикальный путь центра управления в браузере, одним прогоном.
//
// Проверяется не наличие экранов, а то, что путь проходится целиком: человек
// входит, выбирает витрину, видит её состояние, готовит изменение, видит
// разницу до применения, применяет, находит запись в журнале и возвращает как
// было. Разорванный путь — это набор экранов, а не управление.
const path = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium, firefox } = require(path);

const БАЗА = process.argv[2];
const ДВИЖОК = process.argv[3] || 'both';
const ПАРОЛЬ = process.env.STAND_PASSWORD || 'длинный-пароль-для-проверки-1';
const САЙТ = process.env.STAND_SITE || 'lords-01';

let провалов = 0;
const проверить = (у, ч) => {
  if (!у) { провалов++; console.log(`  FAIL ${ч}`); } else console.log(`  PASS ${ч}`);
};

async function войти(ctx, email, база) {
  const p = await ctx.newPage();
  await p.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="email"]', email);
  await p.fill('input[name="password"]', ПАРОЛЬ);
  await p.locator('input[name="password"]').press('Enter');
  await p.waitForLoadState('domcontentloaded');
  return p;
}

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n### движок ${имя}`);
  const ctx = await b.newContext();

  // 1. Вход
  const p = await войти(ctx, 'super@test', БАЗА);
  проверить((await p.content()).includes('Выйти'), '1. вход выполнен');

  // 2. Флот и выбор витрины
  await p.goto(`${БАЗА}/admin/fleet`, { waitUntil: 'domcontentloaded' });
  const флот = await p.content();
  проверить(флот.includes(САЙТ), '2. витрина видна во флоте');
  проверить(/release-manifest|site-profile|observations/.test(флот),
            '2. у показателей виден источник');

  // 3. Состояние витрины
  //
  // Супер-администратор управляет из общего контура: печенье сессии привязано
  // к витрине, и вход в её контур — отдельное явное переключение, а не
  // побочный эффект открытия адреса. Проверять «настройки витрины по её
  // адресу» значило бы требовать, чтобы изоляция протекала.
  await p.goto(`${БАЗА}/admin/settings?site=${САЙТ}`, { waitUntil: 'domcontentloaded' });
  const настройки = await p.content();
  проверить(настройки.includes('keep_releases'), '3. состояние витрины показано');
  проверить(настройки.includes(САЙТ), '3. видно, о какой витрине речь');

  // 4. Подготовка изменения и разница до применения
  //
  // На экране по форме на настройку: скрытое поле `key` называет настройку,
  // `value` несёт новое значение. Проверка ищет форму по имени настройки, а не
  // по порядку на странице: порядок меняется от состава настроек, и тест,
  // держащийся за него, однажды начнёт править не то.
  const форма = p.locator('form[action$="/admin/settings"]')
    .filter({ has: p.locator('input[name="key"][value="keep_releases"]') }).first();
  проверить(await форма.count() > 0, '4. форма изменения найдена по имени настройки');

  await форма.locator('input[name="value"]').fill('12');
  await форма.locator('button[name="dryRun"][value="1"]').click();
  await p.waitForLoadState('domcontentloaded');
  const разница = await p.content();
  проверить(разница.includes('было') && разница.includes('станет'),
            '5. разница показана до применения');
  проверить(разница.includes('Ничего не записано'),
            '5. предпросмотр объявлен не меняющим состояние');

  // 6. Применение
  const форма2 = p.locator('form[action$="/admin/settings"]')
    .filter({ has: p.locator('input[name="key"][value="keep_releases"]') }).first();
  await форма2.locator('input[name="value"]').fill('12');
  await форма2.locator('button[name="dryRun"][value=""]').click();
  await p.waitForLoadState('domcontentloaded');
  проверить((await p.content()).includes('12'), '6. изменение применено и видно');

  // 7. Журнал
  await p.goto(`${БАЗА}/admin/audit`, { waitUntil: 'domcontentloaded' });
  const журнал = await p.content();
  проверить(/settings|настрой/i.test(журнал), '7. изменение попало в журнал');
  проверить(журнал.includes(САЙТ), '7. в журнале названа витрина');

  // 8. Возврат
  //
  // Форма отката появляется только тогда, когда есть куда возвращаться: до
  // первого изменения её нет, и это верно — кнопка «вернуть» без прежнего
  // значения обещала бы то, чего нет.
  await p.goto(`${БАЗА}/admin/settings?site=${САЙТ}`, { waitUntil: 'domcontentloaded' });
  const формаОтката = p.locator('form[action$="/settings/rollback"]');
  проверить(await формаОтката.count() > 0, '8. возврат предложен после изменения');
  if (await формаОтката.count() > 0) {
    await формаОтката.locator('button[name="dryRun"][value="1"]').first().click();
    await p.waitForLoadState('domcontentloaded');
    проверить((await p.content()).includes('было'), '8. разница отката показана до отката');
    const формаОтката2 = p.locator('form[action$="/settings/rollback"]');
    await формаОтката2.locator('button:not([name="dryRun"])').first().click();
    await p.waitForLoadState('domcontentloaded');
    await p.goto(`${БАЗА}/admin/settings?site=${САЙТ}`, { waitUntil: 'domcontentloaded' });
    const после = await p.content();
    проверить(!/value="12"/.test(после), '8. возврат вернул прежнее значение');
  }

  // 9. Изоляция: местный администратор не видит флот
  const местный = await войти(await b.newContext(), `admin-${САЙТ}@test`, `${БАЗА}/s/${САЙТ}`);
  const ответ = await местный.goto(`${БАЗА}/admin/fleet`, { waitUntil: 'domcontentloaded' });
  проверить(ответ.status() === 403 || (await местный.content()).includes('password'),
            '9. флот закрыт серверным отказом для местного администратора');

  await b.close();
}

(async () => {
  if (!БАЗА) { console.log('нужен адрес'); process.exit(2); }
  if (ДВИЖОК === 'chromium' || ДВИЖОК === 'both') await прогон(chromium, 'chromium');
  if (ДВИЖОК === 'firefox' || ДВИЖОК === 'both') await прогон(firefox, 'firefox');
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов === 0 ? 0 : 1);
})();
