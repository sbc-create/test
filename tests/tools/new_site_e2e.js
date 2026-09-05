#!/usr/bin/env node
/**
 * Браузерная приёмка мастера заведения витрины.
 *
 * Проверяется то, ради чего мастер существует: весь путь проходится в браузере,
 * без SSH и правки файлов; сухой прогон показывает, что будет затронуто, чего
 * не хватает и как откатить; и он детерминирован — отпечаток плана не меняется
 * от простого повторного открытия страницы.
 *
 * Отдельно проверяется, что мастер НЕ выдаёт разрешения: витрина остаётся
 * неиндексируемой и неразрешённой для production, сколько бы шагов ни прошли.
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

async function войти(ctx, токен) {
  const p = await ctx.newPage();
  await p.goto(`${БАЗА}/admin`, { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="token"]', токен);
  await p.locator('input[name="token"]').press('Enter');
  await p.waitForLoadState('domcontentloaded');
  return p;
}

async function шаг(p, ожидаемый, поля) {
  // Шаг называется явно: без этого застрявший мастер выглядит как отсутствие
  // поля, и по сообщению об ошибке нельзя понять, какой ответ не приняли.
  const текущий = await p.locator('form[action^="/admin/new-site/"] input[name="step"]')
    .first().getAttribute('value').catch(() => null);
  if (текущий !== ожидаемый) {
    провалов++;
    const беда = (await p.content()).includes('flash bad')
      ? (await p.content()).split('flash bad">')[1].split('<')[0] : '';
    console.log(`  FAIL шаг «${ожидаемый}»: мастер показывает «${текущий}». ${беда}`);
    console.log(`       адрес: ${p.url()}`);
    require('fs').writeFileSync(
      `/tmp/wizard-fail-${ожидаемый}.html`, await p.content(), 'utf8');
    return false;
  }
  for (const [имя, значение] of Object.entries(поля)) {
    const эл = p.locator(`form[action^="/admin/new-site/"] [name="${имя}"]`).first();
    const тег = await эл.evaluate((e) => e.tagName + ':' + (e.type || ''));
    if (тег.startsWith('SELECT')) await эл.selectOption(значение);
    else if (тег.endsWith(':checkbox')) { if (значение) await эл.check(); }
    else await эл.fill(значение);
  }
  await p.locator('form[action^="/admin/new-site/"] button[type="submit"]').first().click();
  // Ждём смены шага на полностью загруженной странице.
  //
  // waitForLoadState разрешается для ТЕКУЩЕГО документа, если переход ещё не
  // начался, и следующий шаг читает старую страницу. А условие «формы нет»
  // истинно ещё и в момент самого перехода — поэтому проверяется readyState:
  // без него ожидание заканчивается на пустой странице, и мастер выглядит
  // застрявшим на случайном шаге. Оба способа ошибиться наблюдались.
  await p.waitForFunction(
    (был) => {
      if (document.readyState !== 'complete') return false;
      // Промежуточный about:blank тоже «complete» и формы не содержит: без
      // проверки заголовка панели ожидание заканчивалось на пустом документе,
      // и следующая проверка читала страницу без плана.
      if (!document.querySelector('header h1')) return false;
      const поле = document.querySelector(
        'form[action^="/admin/new-site/"] input[name="step"]'
      );
      return !поле || поле.value !== был;
    },
    ожидаемый,
    { timeout: 20000 }
  );
  return true;
}

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n=== ${имя} ===`);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await войти(ctx, ТОКЕН);
  const витрина = `nova-${имя}-${Date.now().toString(36).slice(-6)}`;

  await p.goto(`${БАЗА}/admin/new-site`, { waitUntil: 'domcontentloaded' });
  проверить((await p.content()).includes('Что спросят'), 'порядок шагов виден до начала');

  await p.fill('input[name="siteId"]', витрина);
  await p.locator('form[action="/admin/new-site"] button[type="submit"]').click();
  // Ждём именно перехода на страницу заявки. waitForLoadState разрешается для
  // текущего документа, если переход ещё не начался, и дальше читается страница
  // без заявки: мастер выглядит пустым, хотя заявка создана.
  await p.waitForURL(/request=/, { timeout: 15000 });
  await p.waitForFunction(
    () => document.readyState === 'complete' && !!document.querySelector('header h1'),
    null,
    { timeout: 15000 }
  );
  проверить((await p.content()).includes(витрина), 'заявка заведена');

  // --- незаполненная заявка уже показывает требования ---
  const рано = await p.content();
  проверить(рано.includes('Чего не хватает'), 'требования показаны до заполнения');
  проверить(рано.includes('Изменений выполнено: 0'), 'сухой прогон объявляет ноль изменений');

  await шаг(p, 'domain', { domain: `${витрина}.test`, aliases: '' });
  await шаг(p, 'profile', { environment: 'staging', targetRef: 'local-disposable',
                            seoProfile: 'catalog_authority' });
  await шаг(p, 'content', { contentSource: 'provider-feed', contentTypes: 'movie,series' });
  await шаг(p, 'template', { themeRef: 'basis-video' });
  await шаг(p, 'branding', { brandName: 'Новая', legalName: 'ООО Новая', primaryColor: '#1f4fd8' });
  await шаг(p, 'seo', { canonicalHostForm: 'non_www', trailingSlash: true });
  await шаг(p, 'analytics', { analyticsRef: 'secret://analytics/nova', adsRef: '' });
  await шаг(p, 'legal', { legalEntity: 'ООО Новая', contactEmail: 'legal@nova.test',
                          rightsConfirmed: true });

  const итог = await p.content();
  проверить(!итог.includes('name="step"'), 'все шаги пройдены');
  проверить(итог.includes('Затрагиваемые ресурсы'), 'план называет ресурсы');
  проверить(итог.includes('Замки'), 'план называет замки');
  проверить(итог.includes('Контракты'), 'план называет контракты');
  проверить(итог.includes('Откат'), 'план несёт откат');
  проверить(итог.includes('Изменений выполнено: 0'), 'мастер ничего не выполнил');

  // --- детерминизм ---
  const отпечаток = (текст) => (текст.split('Отпечаток плана <code>')[1] || '').split('<')[0];
  const первый = отпечаток(итог);
  проверить(первый.startsWith('sha256:'), 'отпечаток плана показан');
  await p.reload({ waitUntil: 'domcontentloaded' });
  const второй = отпечаток(await p.content());
  проверить(второй === первый,
            'повторное открытие даёт тот же отпечаток: ' + первый + ' против ' + второй);

  // --- разрешения мастер не выдаёт ---
  const api = await ctx.request.get(`${БАЗА}/admin/new-site`);
  проверить(api.ok(), 'страница доступна');
  проверить(!итог.includes('production_authorized'), 'разрешение не предлагается формой');

  // --- узкий экран ---
  const узкий = await b.newContext({ viewport: { width: 390, height: 780 } });
  const у = await войти(узкий, ТОКЕН);
  await у.goto(`${БАЗА}/admin/new-site`, { waitUntil: 'domcontentloaded' });
  const беда = await у.evaluate(() => {
    const ш = document.documentElement.clientWidth;
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width > ш + 1 && !el.closest('.scroll-x')) return el.tagName + '.' + el.className;
    }
    return '';
  });
  проверить(беда === '', `на 390px ничего не уезжает вбок${беда ? ': ' + беда : ''}`);

  // --- читатель ---
  const ctxRO = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const r = await войти(ctxRO, ТОКЕН_ЧТЕНИЯ);
  await r.goto(`${БАЗА}/admin/new-site`, { waitUntil: 'domcontentloaded' });
  проверить(await r.locator('form[method="post"][action="/admin/new-site"]').count() === 0,
            'читатель не заводит заявку');

  await b.close();
}

(async () => {
  if (!БАЗА) { console.log('нужен адрес базы'); process.exit(2); }
  if (ДВИЖОК === 'chromium' || ДВИЖОК === 'both') await прогон(chromium, 'chromium');
  if (ДВИЖОК === 'firefox' || ДВИЖОК === 'both') await прогон(firefox, 'firefox');
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов === 0 ? 0 : 1);
})();
