#!/usr/bin/env node
/**
 * Браузерная приёмка публичного контура учётной записи.
 *
 * Путь целиком: регистрация → подтверждение по ссылке из письма → вход →
 * профиль → выход → вход → смена пароля → повторный вход → восстановление →
 * завершение сессий → выгрузка данных → удаление.
 *
 * Ссылка подтверждения читается из складывающего адаптера почты: настоящего
 * поставщика нет, и подменять его выдуманным токеном значило бы проверять
 * не тот путь.
 */
const МОДУЛЬ = process.env.PLAYWRIGHT_MODULE || 'playwright';
let playwright;
try { playwright = require(МОДУЛЬ); }
catch (e) { console.log('SKIPPED: playwright не установлен'); process.exit(2); }
const { chromium, firefox } = playwright;
const fs = require('fs');
const path = require('path');

let провалов = 0;
const проверить = (у, ч) => { if (!у) { провалов++; console.log(`  FAIL ${ч}`); }
                              else console.log(`  PASS ${ч}`); };

function ссылкаИзПисьма(каталог, назначение, адрес) {
  const файлы = fs.readdirSync(каталог)
    .filter(f => f.endsWith(`-${назначение}.json`))
    .map(f => ({ f, t: fs.statSync(path.join(каталог, f)).mtimeMs }))
    .sort((a, b) => b.t - a.t);
  for (const { f } of файлы) {
    const письмо = JSON.parse(fs.readFileSync(path.join(каталог, f), 'utf8'));
    if (письмо.to !== адрес) continue;
    const m = (письмо.body || '').match(/token=([A-Za-z0-9_\-]+)/);
    if (m) return m[1];
  }
  return '';
}

const ВИДЫ = [{ w: 390, h: 844, имя: 'мобильный' },
               { w: 768, h: 1024, имя: 'планшет' },
               { w: 1440, h: 900, имя: 'десктоп' }];

async function прогон(движок, имя, база, каталогПисем) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  const page = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  console.log(`\n=== ${имя} ===`);
  const метка = `${имя}${Date.now()}`;
  const адрес = `viewer-${метка}@example.test`;
  const пароль = `пароль-зрителя-${метка}`;
  const новый = `новый-пароль-${метка}`;

  // --- регистрация ---
  await page.goto(`${база}/account/register`, { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('Регистрация'), 'страница регистрации открыта');
  проверить((await page.content()).includes('noindex'), 'публичные страницы помечены noindex');
  await page.fill('input[name="email"]', адрес);
  await page.fill('input[name="displayName"]', 'Зритель');
  await page.fill('input[name="password"]', пароль);
  await page.check('input[name="consent"]');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('письмо'), 'регистрация принята');

  // --- вход до подтверждения ---
  await page.goto(`${база}/account/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="email"]', адрес);
  await page.fill('input[name="password"]', пароль);
  await page.locator('input[name="password"]').press('Enter');
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('Неверный адрес или пароль'),
            'до подтверждения вход невозможен');

  // --- подтверждение по ссылке из письма ---
  const токен = ссылкаИзПисьма(каталогПисем, 'verify', адрес);
  проверить(!!токен, 'ссылка подтверждения пришла письмом');
  await page.goto(`${база}/account/verify?token=${encodeURIComponent(токен)}`,
                  { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('подтверждён'), 'адрес подтверждён');

  await page.goto(`${база}/account/verify?token=${encodeURIComponent(токен)}`,
                  { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('не подходит'),
            'повторное использование ссылки отклонено');

  // --- вход и профиль ---
  const войти = async (пар) => {
    await page.goto(`${база}/account/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="email"]', адрес);
    await page.fill('input[name="password"]', пар);
    await page.locator('input[name="password"]').press('Enter');
    await page.waitForLoadState('domcontentloaded');
  };
  await войти(пароль);
  проверить((await page.content()).includes('Профиль'), 'вход выполнен, профиль открыт');
  проверить((await page.content()).includes(адрес), 'адрес виден в профиле');

  await page.fill('input[name="displayName"]', 'Другое имя');
  await page.locator('form[action="/account/profile"] button').click();
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('Другое имя'), 'профиль сохранён');

  // --- размеры ---
  for (const v of ВИДЫ) {
    await page.setViewportSize({ width: v.w, height: v.h });
    await page.goto(`${база}/account`, { waitUntil: 'domcontentloaded' });
    // При отказе называется конкретный переполняющий элемент: «где-то шире
    // экрана» невозможно исправить, не измерив, где именно.
    const итог = await page.evaluate(() => {
      const w = document.documentElement.clientWidth;
      const виноватые = [];
      for (const el of document.querySelectorAll('*')) {
        const r = el.getBoundingClientRect();
        if (r.right > w + 1)
          виноватые.push(`${el.tagName}.${(el.className || '').toString().slice(0, 24)}`
                         + `@${Math.round(r.right)}`);
      }
      return { ок: document.documentElement.scrollWidth <= w + 1,
               кто: виноватые.slice(0, 4) };
    });
    проверить(итог.ок, `${v.имя} ${v.w}px без горизонтальной прокрутки`
              + (итог.ок ? '' : ` — шире экрана: ${итог.кто.join(', ')}`));
  }
  await page.setViewportSize({ width: 195, height: 422 });
  await page.goto(`${база}/account`, { waitUntil: 'domcontentloaded' });
  проверить(await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1),
    '200% увеличение на 390px');
  await page.setViewportSize({ width: 1440, height: 900 });

  // --- выгрузка ---
  await page.goto(`${база}/account`, { waitUntil: 'domcontentloaded' });
  await page.locator('form[action="/account/export"] button').click();
  await page.waitForLoadState('domcontentloaded');
  const выгрузка = await page.content();
  проверить(выгрузка.includes('Мои данные'), 'выгрузка данных открылась');
  проверить(!выгрузка.includes('scrypt'), 'в выгрузке нет хэша пароля');

  // --- выход и повторный вход ---
  await page.goto(`${база}/account`, { waitUntil: 'domcontentloaded' });
  await page.locator('header form button').click();
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('Вход'), 'выход выполнен');
  await войти(пароль);
  проверить((await page.content()).includes('Профиль'), 'повторный вход выполнен');

  // --- смена пароля завершает сессии ---
  await page.fill('input[name="current"]', пароль);
  await page.fill('input[name="new"]', новый);
  await page.locator('form[action="/account/password"] button').click();
  await page.waitForLoadState('domcontentloaded');
  await page.goto(`${база}/account`, { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('Вход'), 'смена пароля завершила сессию');
  await войти(новый);
  проверить((await page.content()).includes('Профиль'), 'вход новым паролем');

  // --- восстановление пароля ---
  await page.goto(`${база}/account/forgot`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="email"]', адрес);
  await page.locator('form button').click();
  await page.waitForLoadState('domcontentloaded');
  const сброс = ссылкаИзПисьма(каталогПисем, 'reset', адрес);
  проверить(!!сброс, 'ссылка восстановления пришла письмом');
  await page.goto(`${база}/account/reset?token=${encodeURIComponent(сброс)}`,
                  { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="password"]', пароль);
  await page.locator('form button').click();
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('Пароль изменён'), 'пароль восстановлен');

  // --- завершение всех сессий ---
  await войти(пароль);
  await page.locator('form[action="/account/sessions/revoke-all"] button').click();
  await page.waitForLoadState('domcontentloaded');
  await page.goto(`${база}/account`, { waitUntil: 'domcontentloaded' });
  проверить((await page.content()).includes('Вход'), 'все сессии завершены');

  // --- удаление ---
  await войти(пароль);
  await page.fill('input[name="confirm"]', 'нет');
  await page.locator('form[action="/account/delete"] button').click();
  await page.waitForLoadState('domcontentloaded');
  проверить((await page.content()).includes('Профиль'),
            'без точного подтверждения ничего не удалено');
  await page.fill('input[name="confirm"]', 'УДАЛИТЬ');
  await page.locator('form[action="/account/delete"] button').click();
  await page.waitForLoadState('domcontentloaded');
  await войти(пароль);
  проверить((await page.content()).includes('Неверный адрес или пароль'),
            'удалённая запись не входит');

  await b.close();
}

(async () => {
  const [база, каталогПисем, движок] = process.argv.slice(2);
  const выбор = { chromium, firefox };
  if (!выбор[движок]) { console.error('нужен движок: chromium или firefox'); process.exit(2); }
  await прогон(выбор[движок], движок, база, каталогПисем);
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов ? 1 : 0);
})();
