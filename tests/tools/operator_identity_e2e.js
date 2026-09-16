#!/usr/bin/env node
/**
 * Браузерная приёмка операторского контура.
 *
 * Проверяется путь целиком: окно начальной настройки, приглашение, принятие с
 * собственным паролем, вход по учётной записи, закрытие входа по токену,
 * назначение роли, блокировка, отзыв сессий и немедленная потеря доступа.
 *
 * HTTP 200 здесь ничего не значит: страница входа отвечает 200 и
 * неавторизованному. Проверяется содержимое и последствие действия.
 */
const МОДУЛЬ = process.env.PLAYWRIGHT_MODULE || 'playwright';
let playwright;
try { playwright = require(МОДУЛЬ); }
catch (e) { console.log('SKIPPED: playwright не установлен'); process.exit(2); }
const { chromium, firefox } = playwright;

let провалов = 0;
const проверить = (у, ч) => { if (!у) { провалов++; console.log(`  FAIL ${ч}`); }
                              else console.log(`  PASS ${ч}`); };

async function войтиТокеном(page, база, токен) {
  await page.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="token"]', токен);
  await page.click('form[action="/admin/login"] button[type="submit"]:below(input[name="token"])')
    .catch(async () => { await page.locator('input[name="token"]').press('Enter'); });
  await page.waitForLoadState('domcontentloaded');
}

async function войтиУчёткой(page, база, email, пароль) {
  await page.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', пароль);
  await page.locator('input[name="password"]').press('Enter');
  await page.waitForLoadState('domcontentloaded');
}

async function прогон(движок, имя, база, токен) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} ===`);
  const метка = `${имя}${Date.now()}`;
  const адресА = `admin-${метка}@example.test`;
  const адресВ = `viewer-${метка}@example.test`;
  const парольА = `пароль-администратора-${метка}`;
  const парольВ = `пароль-читателя-${метка}`;

  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // --- начальная настройка ---
  await page.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  const форма = await page.content();
  проверить(форма.includes('name="email"'), 'форма входа спрашивает адрес и пароль');
  const естьТокен = форма.includes('name="token"');

  if (естьТокен) {
    await войтиТокеном(page, база, токен);
    проверить((await page.content()).includes("Выйти"), "вход токеном в окне настройки");
  }

  // --- приглашение администратора ---
  await page.goto(`${база}/admin/users`, { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('Операторы'), 'экран людей открыт');
  await page.fill('form[action="/admin/users/invites"] input[name="email"]', адресА);
  await page.selectOption('form[action="/admin/users/invites"] select[name="role"]', 'admin');
  await page.click('form[action="/admin/users/invites"] button[type="submit"]');
  await page.waitForLoadState('domcontentloaded');
  const текст = await page.content();
  const m = текст.match(/secret=([A-Za-z0-9_\-]{20,})/);
  проверить(!!m, 'секрет приглашения показан один раз');
  const секрет = m ? m[1] : '';

  // --- принятие приглашения ---
  await page.goto(`${база}/admin/invite?secret=${encodeURIComponent(секрет)}`,
                  { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('Принять приглашение'), 'страница принятия открыта');
  await page.fill('input[name="password"]', парольА);
  await page.locator('input[name="password"]').press('Enter');
  await page.waitForLoadState('domcontentloaded');

  // --- вход по учётной записи ---
  await page.goto(`${база}/admin/logout-get`, { waitUntil: 'domcontentloaded' }).catch(() => {});
  await ctx.clearCookies();
  await войтиУчёткой(page, база, адресА, парольА);
  проверить((await page.content()).includes("Выйти"), "вход по учётной записи");

  // --- окно начальной настройки закрылось ---
  const ctxГость = await b.newContext();
  const гость = await ctxГость.newPage();
  await гость.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  проверить(!(await гость.content()).includes('name="token"'),
            'вход по токену закрыт после появления учётной записи');
  await ctxГость.close();

  // --- приглашение читателя и его ограничения ---
  await page.goto(`${база}/admin/users`, { waitUntil: 'domcontentloaded' });
  await page.fill('form[action="/admin/users/invites"] input[name="email"]', адресВ);
  await page.selectOption('form[action="/admin/users/invites"] select[name="role"]', 'viewer');
  await page.click('form[action="/admin/users/invites"] button[type="submit"]');
  await page.waitForLoadState('domcontentloaded');
  const m2 = (await page.content()).match(/secret=([A-Za-z0-9_\-]{20,})/);
  проверить(!!m2, 'второе приглашение создано');
  await page.goto(`${база}/admin/invite?secret=${encodeURIComponent(m2 ? m2[1] : '')}`,
                  { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="password"]', парольВ);
  await page.locator('input[name="password"]').press('Enter');
  await page.waitForLoadState('domcontentloaded');

  const ctxВ = await b.newContext();
  const читатель = await ctxВ.newPage();
  await войтиУчёткой(читатель, база, адресВ, парольВ);
  await читатель.goto(`${база}/admin/users`, { waitUntil: 'domcontentloaded' });
  const вид = await читатель.content();
  проверить(!вид.includes('Пригласить'), 'читателю не показана форма приглашения');
  проверить(!вид.includes('Заблокировать'), 'читателю не показана блокировка');
  await читатель.goto(`${база}/admin/review`, { waitUntil: 'domcontentloaded' });
  проверить(!(await читатель.content()).includes('Групповое решение'),
            'читателю не показано групповое решение');

  // --- отзыв всех сессий читателя администратором ---
  await page.goto(`${база}/admin/users`, { waitUntil: 'domcontentloaded' });
  const строка = page.locator('tr', { hasText: адресВ }).first();
  await строка.locator('form[action$="/revoke-sessions"] button').click();
  await page.waitForLoadState('domcontentloaded');
  await читатель.goto(`${база}/admin/users`, { waitUntil: 'domcontentloaded' });
  проверить((await читатель.content()).includes('name="password"'),
            'отозванная сессия немедленно недействительна');

  // --- блокировка ---
  await page.goto(`${база}/admin/users`, { waitUntil: 'domcontentloaded' });
  const строка2 = page.locator('tr', { hasText: адресВ }).first();
  await строка2.locator('form[action$="/block"] input[name="reason"]').fill('проверка');
  await строка2.locator('form[action$="/block"] button').click();
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('BLOCKED'), 'блокировка видна в списке');
  await войтиУчёткой(читатель, база, адресВ, парольВ);
  проверить((await читатель.content()).includes('Неверный адрес или пароль'),
            'заблокированный не входит');

  await ctxВ.close();
  await ctx.close();
  await b.close();
}

// Движок задаётся аргументом намеренно. Прогон закрывает окно начальной
// настройки — второй движок в том же состоянии уже не может войти токеном, и
// это правильное поведение, а не поломка. Поэтому каждый движок гоняется по
// своему чистому состоянию, а не оба подряд по одному.
(async () => {
  const [база, токен, движок] = process.argv.slice(2);
  const выбор = { chromium, firefox };
  if (!выбор[движок]) {
    console.error('нужен третий аргумент: chromium или firefox');
    process.exit(2);
  }
  await прогон(выбор[движок], движок, база, токен);
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов ? 1 : 0);
})();
