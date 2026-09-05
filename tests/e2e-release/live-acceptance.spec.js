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

test.afterAll(() => {
  fs.writeFileSync(path.join(OUT, `acceptance-${SITE}.json`),
    `${JSON.stringify({ captured_at_utc: new Date().toISOString(), ...collected }, null, 2)}\n`);
});

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
      expect(allowed, `${route.path} ответил ${status}`).toContain(status);
      // Заголовок обязателен: страница без h1 неотличима от заглушки.
      await expect(page.locator('h1').first()).toBeVisible();
      expect(consoleErrors, `ошибки консоли на ${route.path}`).toEqual([]);
      expect(networkErrors, `отказы запросов к витрине на ${route.path}`).toEqual([]);
    });
  }
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
    collected.vitals = {
      ...vitals,
      limitation: 'петлевой контур без сети: LCP — нижняя граница, не замер продукта',
    };
    expect(vitals.cls, `сдвиг раскладки ${vitals.cls.toFixed(3)}`).toBeLessThanOrEqual(0.1);
    await clean.close();
  });
});
