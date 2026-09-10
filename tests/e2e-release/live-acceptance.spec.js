// REQ-RELEASE-LIVE-ACCEPTANCE: приёмка витрины на живом контуре после переключения.
//
// Проверяется работающий сайт, а не сборка. Разница существенная: сборка может
// быть безупречной, а витрина отдавать её не полностью — из-за рантайма,
// символьной ссылки, прав или кэша. Поэтому каждый факт здесь снимается
// обращением к тому адресу, который увидит зритель.
//
// Адрес берётся из переменной окружения RELEASE_BASE. Значение по умолчанию —
// петлевой порт витрины: боевой домен закрыт Basic Auth, и подставлять сюда
// учётные данные нельзя.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE = process.env.RELEASE_BASE || 'http://127.0.0.1:9102';
const SITE = process.env.RELEASE_SITE || 'lords-02';
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'release', 'live-acceptance');
fs.mkdirSync(OUT, { recursive: true });

// Маршруты витрины. Список закрыт намеренно: «ключевой» значит «его отказ
// зритель увидит сразу», а не «он существует».
const ROUTES = [
  { name: 'home', path: '/' },
  { name: 'catalog', path: '/catalog/' },
  { name: 'catalog-page-2', path: '/catalog/page/2/' },
  { name: 'genres', path: '/genres/' },
  { name: 'years', path: '/years/' },
  { name: 'countries', path: '/countries/' },
  { name: 'search', path: '/search/' },
  { name: 'search-empty', path: '/search/?q=' },
  { name: 'not-found', path: '/такого-адреса-нет-xyz/', expect: [404, 200] },
];

const VIEWPORTS = [390, 768, 1440];

const collected = { base: BASE, site: SITE, routes: {}, vitals: {} };

// Свидетельство пишется ПОСЛЕ КАЖДОЙ проверки, а не один раз в конце.
//
// Первая редакция копила всё в памяти и записывала в afterAll. При падении
// теста Playwright перезапускает рабочий процесс, накопленное теряется, и в
// свидетельстве не оказалось ни страницы произведения, ни списка серий —
// именно тех разделов, ради которых прогон и запускался. Отчёт о релизе,
// теряющий данные при первом же отказе, бесполезен ровно тогда, когда нужен.
function record() {
  // Запись идёт СЛИЯНИЕМ с уже накопленным на диске, а не перезаписью.
  //
  // Причина установлена опытом, а не догадкой: после падения проверки
  // Playwright поднимает новый рабочий процесс, модуль загружается заново, и
  // `collected` в нём пуст. Прежняя редакция перезаписывала файл этим пустым
  // накопителем, и из свидетельства исчезали именно те разделы, что были сняты
  // до отказа, — страница произведения и список серий. Отчёт о релизе,
  // теряющий данные при первом же отказе, бесполезен ровно тогда, когда нужен.
  //
  // Файл удаляется перед прогоном снаружи, поэтому слияние не тащит данные
  // прошлых запусков.
  const file = path.join(OUT, `acceptance-${SITE}.json`);
  let previous = {};
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
    delete previous.captured_at_utc;
  } catch {
    previous = {};
  }
  const merged = { ...previous, ...collected };
  // Маршруты накапливаются по одному и тоже обязаны сливаться, а не заменяться.
  merged.routes = { ...(previous.routes || {}), ...(collected.routes || {}) };
  fs.writeFileSync(file,
    `${JSON.stringify({ captured_at_utc: new Date().toISOString(), ...merged }, null, 2)}\n`);
}

test.afterEach(() => record());
test.afterAll(() => record());

test.describe('маршруты отвечают и не ломают консоль', () => {
  for (const route of ROUTES) {
    test(`${route.name}`, async ({ page }) => {
      const consoleErrors = [];
      const networkErrors = [];
      const allowedStatuses = route.expect || [200];
      // Переход на адрес, которого нет, сам порождает в консоли сообщение
      // «Failed to load resource: 404». Это отчёт браузера о том, что страница
      // отработала как задумано, а не отказ витрины. Считать его ошибкой
      // значило бы требовать, чтобы несуществующий адрес отвечал 200.
      const echoOfExpectedStatus = (text) =>
        /Failed to load resource/i.test(text)
        && allowedStatuses.some((code) => code !== 200 && text.includes(String(code)));
      page.on('console', (m) => {
        if (m.type() !== 'error') return;
        const text = m.text();
        if (echoOfExpectedStatus(text)) return;
        consoleErrors.push(text);
      });
      page.on('requestfailed', (r) => {
        // Отказ внешнего поставщика — не отказ витрины. Считаются только
        // запросы к собственному адресу.
        if (r.url().startsWith(BASE)) networkErrors.push(`${r.url()} ${r.failure()?.errorText}`);
      });
      const response = await page.goto(BASE + route.path, { waitUntil: 'load' });
      const status = response ? response.status() : null;
      const allowed = route.expect || [200];
      collected.routes[route.name] = { status, consoleErrors, networkErrors };
      record();
      expect(allowed, `${route.path} ответил ${status}`).toContain(status);
      // Заголовок обязателен: страница без h1 неотличима от заглушки.
      await expect(page.locator('h1').first()).toBeVisible();
      expect(consoleErrors, `ошибки консоли на ${route.path}`).toEqual([]);
      expect(networkErrors, `отказы запросов к витрине на ${route.path}`).toEqual([]);
    });
  }
});

test.describe('страница произведения', () => {
  // Адрес тайтла не зашит: он берётся из каталога той же витрины. Зашитый
  // адрес живёт ровно до следующего обновления каталога.
  const firstTitle = async (page) => {
    await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
    const href = await page.locator('a[href^="/title/"]').first().getAttribute('href');
    expect(href, 'в каталоге нет ни одной ссылки на произведение').toBeTruthy();
    return href;
  };

  test('открывается, подписана и несёт место плеера', async ({ page }) => {
    const href = await firstTitle(page);
    const response = await page.goto(BASE + href, { waitUntil: 'load' });
    expect(response.status(), href).toBe(200);
    await expect(page.locator('h1')).toBeVisible();

    const shell = await page.evaluate(() => {
      const frame = document.querySelector('[class*="player"]');
      if (!frame) return null;
      const rect = frame.getBoundingClientRect();
      const style = getComputedStyle(frame);
      return { height: Math.round(rect.height), width: Math.round(rect.width),
               ratio: style.aspectRatio, text: (frame.textContent || '').trim().slice(0, 120) };
    });
    collected.title = { href, player: shell };
    record();
    expect(shell, 'посадочного места плеера на странице нет').not.toBeNull();
    // Кадр обязан занимать место до подключения поставщика: иначе включение
    // плеера сдвинет всю раскладку.
    expect(shell.height, `кадр плеера схлопнут: ${shell.height}px`).toBeGreaterThan(50);
  });

  test('серии сгруппированы и не показывают ложную длительность', async ({ page }) => {
    const href = await firstTitle(page);
    await page.goto(BASE + href, { waitUntil: 'load' });
    const episodes = await page.evaluate(() => {
      const items = [...document.querySelectorAll('li.episode')];
      const spans = items.flatMap((li) => [...li.querySelectorAll('span')]
        .map((s) => (s.textContent || '').trim()));
      return {
        count: items.length,
        seasons: document.querySelectorAll('details.season').length,
        durations: spans.filter((t) => /\d+\s*мин/.test(t)),
        zero: spans.filter((t) => /^0\s*мин$/.test(t)).length,
      };
    });
    collected.episodes = episodes;
    record();
    // Ноль минут — не длительность, а её отсутствие. Ради этого собиралась
    // версия 3 артефакта.
    expect(episodes.zero, `«0 мин» на странице: ${episodes.zero}`).toBe(0);
    if (episodes.count > 0) {
      expect(episodes.seasons, 'серии есть, а группировки по сезонам нет')
        .toBeGreaterThan(0);
    }
  });

  test('содержимое приходит с сервера, а не дорисовывается скриптом', async ({ browser }) => {
    // SSR проверяется отключением JavaScript: если каталог виден и без него,
    // страницу отдал сервер.
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto(`${BASE}/catalog/`, { waitUntil: 'load' });
    const cards = await page.locator('a[href^="/title/"]').count();
    const h1 = await page.locator('h1').first().textContent();
    collected.ssr = { cards_without_js: cards, h1: (h1 || '').trim().slice(0, 60) };
    record();
    expect(cards, 'без JavaScript каталог пуст — содержимое дорисовывается скриптом')
      .toBeGreaterThan(0);
    await context.close();
  });
});

test.describe('раскладка не уезжает вбок', () => {
  for (const route of ROUTES.slice(0, 4)) {
    for (const width of VIEWPORTS) {
      test(`${route.name} ${width}px`, async ({ browser }) => {
        const ctx = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await ctx.newPage();
        await page.goto(BASE + route.path, { waitUntil: 'load' });
        const box = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          client: document.documentElement.clientWidth,
        }));
        await page.screenshot({
          path: path.join(OUT, `${SITE}-${route.name}-${width}.png`), fullPage: false });
        expect(box.scroll, `${route.path} на ${width}px: ${box.scroll} > ${box.client}`)
          .toBeLessThanOrEqual(box.client + 1);
        await ctx.close();
      });
    }
  }
});

test.describe('скорость', () => {
  test('сдвиг раскладки в бюджете, замер оснастки проверен', async ({ page }) => {
    // Самопроверка наблюдателя стоит первой: нулевой CLS без неё неотличим от
    // неподключившегося наблюдателя.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      window.__cls = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) if (!e.hadRecentInput) window.__cls += e.value;
      }).observe({ type: 'layout-shift', buffered: true });
      window.__lcp = 0;
      new PerformanceObserver((list) => {
        const last = list.getEntries().pop();
        if (last) window.__lcp = last.startTime;
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    });
    await page.goto(`${BASE}/`, { waitUntil: 'load' });

    // Сдвиг раскладки наблюдаем не везде. `layout-shift` — запись только
    // Chromium: в Firefox `PerformanceObserver.supportedEntryTypes` её не
    // содержит, наблюдатель не подключается, и `window.__cls` навсегда
    // остаётся нулём. Прежде самопроверка честно падала по таймауту, и вся
    // приёмка Firefox объявлялась провалом релиза — хотя провалом был не
    // шаблон, а попытка измерить в движке то, чего он не умеет.
    //
    // Ноль здесь не подставляется: неизмеренное называется неизмеренным с
    // причиной. LCP Firefox поддерживает и замеряется наравне.
    const наблюдаемСдвиг = await page.evaluate(() => Boolean(
      window.PerformanceObserver
      && Array.isArray(PerformanceObserver.supportedEntryTypes)
      && PerformanceObserver.supportedEntryTypes.includes('layout-shift')));

    if (наблюдаемСдвиг) {
      // Самопроверка наблюдателя: нулевой CLS без неё неотличим от
      // неподключившегося наблюдателя.
      const before = await page.evaluate(() => window.__cls);
      await page.evaluate(() => {
        const b = document.createElement('div');
        b.style.height = '400px'; b.style.background = '#333';
        document.body.prepend(b);
      });
      await page.waitForFunction(() => window.__cls > 0, null, { timeout: 10_000 });
      expect(await page.evaluate(() => window.__cls),
        'наблюдатель сдвига не сработал — нули ниже ничего не значат')
        .toBeGreaterThan(before + 0.1);
    }

    // Настоящий замер — на чистой загрузке.
    const clean = await page.context().newPage();
    await clean.addInitScript(() => {
      window.__cls = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) if (!e.hadRecentInput) window.__cls += e.value;
      }).observe({ type: 'layout-shift', buffered: true });
      window.__lcp = 0;
      new PerformanceObserver((list) => {
        const last = list.getEntries().pop();
        if (last) window.__lcp = last.startTime;
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    });
    await clean.setViewportSize({ width: 390, height: 844 });
    await clean.goto(`${BASE}/`, { waitUntil: 'load' });
    await clean.waitForLoadState('networkidle').catch(() => {});
    await clean.waitForTimeout(1500);
    const vitals = await clean.evaluate(() => ({ cls: window.__cls, lcp: window.__lcp }));
    // Отзывчивость на действие. INP по-настоящему считается по полю, а на
    // одном прогоне его нет; здесь берётся ближайшее измеримое — задержка
    // обработки настоящего нажатия на настоящую ссылку. Величина названа
    // своим именем и не выдаётся за полевой INP.
    const interaction = await clean.evaluate(async () => {
      const target = document.querySelector('a[href], button');
      if (!target) return null;
      return await new Promise((resolve) => {
        let started = 0;
        const onDown = () => { started = performance.now(); };
        target.addEventListener('pointerdown', onDown, { once: true });
        requestAnimationFrame(() => {
          const ev = new PointerEvent('pointerdown', { bubbles: true, cancelable: true });
          target.dispatchEvent(ev);
          requestAnimationFrame(() => requestAnimationFrame(() => {
            resolve(started ? performance.now() - started : null);
          }));
        });
      });
    });

    collected.vitals = {
      ...vitals,
      cls: наблюдаемСдвиг ? vitals.cls : null,
      cls_unmeasured_reason: наблюдаемСдвиг ? null
        : 'PerformanceObserver не поддерживает layout-shift в этом движке',
      interaction_ms: interaction === null ? null : Math.round(interaction * 100) / 100,
      limitation: 'петлевой контур без сети: LCP — нижняя граница, не замер продукта; '
        + 'interaction_ms — задержка обработки нажатия на одном прогоне, а не полевой INP',
    };
    if (наблюдаемСдвиг) {
      expect(vitals.cls, `сдвиг раскладки ${vitals.cls.toFixed(3)}`).toBeLessThanOrEqual(0.1);
    }
    if (interaction !== null) {
      expect(interaction, `задержка обработки нажатия ${interaction.toFixed(1)} мс`)
        .toBeLessThanOrEqual(200);
    }
    await clean.close();
  });
});
