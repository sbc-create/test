// Браузерная приёмка боевой витрины Lords: два движка, реальный домен.
//
// HTTP-приёмка уже отвечает на вопрос «что отдаёт сервер». Здесь другой
// вопрос: что получает посетитель после того, как страница отработала в
// браузере. Разница не теоретическая — разметка может быть верной, а страница
// пустой из-за ошибки скрипта, и curl этого не увидит.
const path = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium, firefox } = require(path);

const БАЗА = process.argv[2] || 'https://1lordserials1.online';
const СОСЕДИ = ['lordfilm47.space', 'lordserial33.biz', 'yummyani.site',
                'yummyani.org', 'yummyani.biz'];
const ШИРИНЫ = [[390, 780, '390px'], [768, 1024, '768px'], [1440, 900, '1440px']];

let провалов = 0;
const проверить = (у, ч) => {
  if (!у) { провалов++; console.log(`  FAIL ${ч}`); } else console.log(`  PASS ${ч}`);
};

const хост = new URL(БАЗА).host;

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n### движок ${имя}`);
  const ctx = await b.newContext();
  const page = await ctx.newPage();

  // Ошибки страницы копятся на весь прогон: одна из них могла бы опустошить
  // выдачу, оставив разметку внешне исправной.
  const ошибки = [];
  page.on('pageerror', (e) => ошибки.push(String(e.message).slice(0, 120)));

  // --- личность релиза ---
  const health = await (await ctx.request.get(`${БАЗА}/healthz`)).json();
  проверить(health.site_id === 'lords-03', `витрина названа: ${health.site_id}`);
  проверить(!!health.release, `релиз назван: ${health.release}`);
  проверить(String(health.renderer_revision || '').length === 40,
            `ревизия отрисовщика полная: ${String(health.renderer_revision).slice(0, 12)}`);
  проверить(health.indexing === 'disabled', `индексация: ${health.indexing}`);

  // --- разделы ---
  for (const адрес of ['/', '/catalog/', '/catalog/page/2/', '/genres/',
                       '/countries/', '/movies/', '/series/', '/new/',
                       '/schedule/', '/years/']) {
    const r = await page.goto(`${БАЗА}${адрес}`, { waitUntil: 'domcontentloaded' });
    const текст = (await page.locator('body').innerText()).trim();
    проверить(r && r.status() === 200 && текст.length > 400,
              `${адрес}: статус ${r && r.status()}, текста ${текст.length} симв.`);

    // SEO-инварианты проверяются на каждой странице, а не на одной: запрет
    // индексации, потерянный на одной странице из шести, — это утечка.
    const robots = await page.locator('meta[name="robots"]').getAttribute('content')
      .catch(() => null);
    проверить(!!robots && robots.includes('noindex'), `${адрес}: robots «${robots}»`);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute('href')
      .catch(() => null);
    проверить(!!canonical && new URL(canonical).host === хост,
              `${адрес}: канонический адрес на своём домене`);
  }

  // --- межтенантные утечки ---
  await page.goto(`${БАЗА}/catalog/`, { waitUntil: 'domcontentloaded' });
  const разметка = await page.content();
  const чужие = СОСЕДИ.filter((д) => разметка.includes(д));
  проверить(чужие.length === 0, `чужих доменов в разметке: ${чужие.join(', ') || 'нет'}`);

  // --- объявленная навигация против построенной ---
  //
  // Пакет витрины объявляет `navigation.primary`, и это выглядит как
  // настройка. Отрисовщик её не читает: шапка строится из каталога. Проверка
  // называет расхождение, а не молчит о нём.
  const объявлено = (process.env.LORDS_NAV || '').split(',').filter(Boolean);
  if (объявлено.length) {
    await page.goto(`${БАЗА}/`, { waitUntil: 'domcontentloaded' });
    const шапка = await page.locator('header a').evaluateAll(
      (узлы) => узлы.map((у) => у.getAttribute('href')));
    const непостроенные = [];
    for (const адрес of объявлено) {
      const r = await ctx.request.get(`${БАЗА}${адрес}`);
      if (r.status() !== 200 || !шапка.includes(адрес)) {
        непостроенные.push(`${адрес}(${r.status()}${шапка.includes(адрес) ? '' : ', нет в шапке'})`);
      }
    }
    console.log(`  ПРИМЕЧАНИЕ объявленная навигация не построена: ${
      непостроенные.join(', ') || 'расхождений нет'}`);
  }

  // --- поиск глазами посетителя ---
  const выдача = {};
  for (const запрос of ['матрица', 'матрца', 'vfnhbwf', 'ведьмак', 'zzzqqqxxx']) {
    await page.goto(`${БАЗА}/search/`, { waitUntil: 'domcontentloaded' });
    const поле = page.locator('input[type="search"], input[name="q"]').first();
    проверить(await поле.count() > 0, `поле поиска на месте (${запрос})`);
    await поле.fill(запрос);
    await поле.press('Enter');
    await page.waitForLoadState('domcontentloaded');
    const ссылки = await page.locator('a[href^="/title/"]').evaluateAll(
      (узлы) => узлы.map((у) => у.getAttribute('href')).slice(0, 5));
    выдача[запрос] = ссылки.join(',');
    if (запрос === 'zzzqqqxxx') {
      проверить(ссылки.length === 0, 'мусорный запрос честно ничего не находит');
    } else {
      проверить(ссылки.length > 0, `«${запрос}»: найдено ${ссылки.length}`);
    }
  }
  проверить(выдача['матрица'] !== выдача['ведьмак'],
            'разные слова дают разные ответы, а не общий каталог');
  проверить(выдача['матрица'] === выдача['vfnhbwf'],
            'запрос в латинской раскладке приводится к той же выдаче');
  проверить(выдача['матрца'].length > 0, 'опечатка не обнуляет выдачу');

  // --- карточка произведения ---
  const первая = (выдача['матрица'] || '').split(',')[0];
  проверить(!!первая, `карточка для проверки найдена: ${первая}`);
  if (первая) {
    const r = await page.goto(`${БАЗА}${первая}`, { waitUntil: 'domcontentloaded' });
    проверить(r && r.status() === 200, `карточка отвечает ${r && r.status()}`);
    const текст = await page.locator('body').innerText();
    проверить(!текст.includes('PTNoneM'), 'на карточке нет PTNoneM');
    проверить(!/\b0 мин\b/.test(текст), 'на карточке нет «0 мин»');
    const плеер = await page.locator('[data-player], iframe, .player').count();
    проверить(плеер > 0, `элемент плеера на карточке: ${плеер}`);
    const h1 = await page.locator('h1').first().innerText().catch(() => '');
    проверить(h1.trim().length > 0, `заголовок карточки: ${h1.trim().slice(0, 40)}`);
  }

  // --- ширины ---
  for (const [ш, в, подпись] of ШИРИНЫ) {
    const c2 = await b.newContext({ viewport: { width: ш, height: в } });
    const p2 = await c2.newPage();
    await p2.goto(`${БАЗА}/catalog/`, { waitUntil: 'domcontentloaded' });
    const беда = await p2.evaluate(() => {
      const ш2 = document.documentElement.clientWidth;
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.width > ш2 + 1) return el.tagName + '.' + (el.className || '');
      }
      return '';
    });
    проверить(беда === '', `${подпись} без горизонтальной прокрутки${беда ? ': ' + беда : ''}`);
    await c2.close();
  }

  проверить(ошибки.length === 0, `ошибок страницы: ${ошибки.length}${
    ошибки.length ? ' — ' + ошибки[0] : ''}`);

  await ctx.close();
  await b.close();
}

(async () => {
  for (const [движок, имя] of [[chromium, 'chromium'], [firefox, 'firefox']]) {
    await прогон(движок, имя);
  }
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов > 0 ? 1 : 0);
})().catch((e) => { console.error(String(e && e.message || e)); process.exit(1); });
