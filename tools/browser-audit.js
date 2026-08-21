/**
 * Браузерная проверка сборки: рендер, доступность, лабораторные метрики, консоль.
 *
 * Запускается фабрикой (`factory seo-render` и `factory verify`). Вывод — JSON в stdout,
 * чтобы результат попадал в машиночитаемый отчёт задания без ручной интерпретации.
 *
 * Аргументы: --base <url> --routes <routes.json> --out <dir> [--auth user:pass]
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require(path.join(__dirname, '..', 'node_modules', 'playwright-core'));

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const BASE = arg('--base');
const ROUTES = arg('--routes');
const OUT = arg('--out', '.');
const AUTH = arg('--auth', '');
const EXECUTABLE = arg('--executable', process.env.FACTORY_CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome');
const VIEWPORTS = [
  { name: 'mobile-360', width: 360, height: 780, isMobile: true },
  { name: 'mobile-390', width: 390, height: 844, isMobile: true },
  { name: 'tablet-768', width: 768, height: 1024, isMobile: false },
  { name: 'laptop-1024', width: 1024, height: 768, isMobile: false },
  { name: 'desktop-1440', width: 1440, height: 900, isMobile: false },
];

async function main() {
  const config = JSON.parse(fs.readFileSync(ROUTES, 'utf8'));
  const sample = pickSample(config.routes);
  const axeSource = fs.readFileSync(path.join(__dirname, '..', 'node_modules', 'axe-core', 'axe.min.js'), 'utf8');
  const browser = await chromium.launch({ executablePath: EXECUTABLE });
  const findings = [];
  const metrics = [];
  const screenshots = [];
  const a11y = [];

  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.isMobile,
      hasTouch: viewport.isMobile,
      httpCredentials: AUTH ? { username: AUTH.split(':')[0], password: AUTH.slice(AUTH.indexOf(':') + 1) } : undefined,
      ignoreHTTPSErrors: false,
    });
    // axe-core внедряется init-скриптом: addScriptTag справедливо блокируется CSP сайта,
    // и ослаблять CSP ради теста нельзя — проверяем ровно ту политику, что уедет в прод.
    await context.addInitScript({ content: axeSource });
    for (const route of sample) {
      const page = await context.newPage();
      const consoleErrors = [];
      const failedRequests = [];
      const expectedStatusNoise = new RegExp(`Failed to load resource.*(${route.status})`);
      page.on('console', (m) => {
        if (m.type() !== 'error') return;
        const text = m.text();
        // Сам документ со статусом 404/410 браузер логирует как ошибку загрузки —
        // это ожидаемое поведение проверяемой страницы, а не дефект.
        if (route.status !== 200 && expectedStatusNoise.test(text)) return;
        consoleErrors.push(text.slice(0, 300));
      });
      page.on('requestfailed', (r) => failedRequests.push(`${r.url()} ${r.failure() && r.failure().errorText}`));

      const response = await page.goto(BASE + route.path, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(350);

      if (consoleErrors.length) findings.push({ check: 'console', severity: 'critical', url: route.path, viewport: viewport.name, message: consoleErrors.join(' | ') });
      if (failedRequests.length) findings.push({ check: 'network', severity: 'critical', url: route.path, viewport: viewport.name, message: failedRequests.join(' | ') });

      // Основной контент виден в отрендеренном DOM, а не только в исходнике.
      const rendered = await page.evaluate(() => ({
        h1: document.querySelectorAll('h1').length,
        h1Text: (document.querySelector('h1') || {}).textContent || '',
        cards: document.querySelectorAll('.card, .linked-list li, .body p, .facts .fact, .lead, .availability, .status-page p').length,
        mainTextLength: ((document.querySelector('main') || {}).innerText || '').trim().length,
        canonical: (document.querySelector('link[rel=canonical]') || {}).href || null,
        robots: (document.querySelector('meta[name=robots]') || {}).content || '',
        paginationLinks: document.querySelectorAll('.pagination a[href]').length,
        player: !!document.querySelector('.player-frame'),
        availability: !!document.querySelector('.availability'),
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        lazyLcpCandidate: (() => {
          const first = document.querySelector('main img');
          return first ? first.getAttribute('loading') === 'lazy' : false;
        })(),
        imagesWithoutAlt: Array.from(document.querySelectorAll('img')).filter((i) => !i.getAttribute('alt')).length,
        imagesWithoutSize: Array.from(document.querySelectorAll('img')).filter((i) => !i.getAttribute('width') || !i.getAttribute('height')).length,
        interactive: document.querySelectorAll('main form, main a[href], main button').length,
      }));

      if (rendered.h1 !== 1) findings.push({ check: 'rendered-h1', severity: 'critical', url: route.path, viewport: viewport.name, message: `H1 в отрендеренном DOM: ${rendered.h1}` });
      const contentPage = route.status === 200 && !['search', 'service', 'not_found', 'gone'].includes(route.page_type);
      // Функциональная страница (поиск, служебная) полезна формой и ссылками,
      // а не объёмом текста: пустой её считаем только при отсутствии и того и другого.
      const functionalOk = !contentPage && rendered.interactive > 0;
      if (rendered.cards === 0 && rendered.mainTextLength < 60 && !functionalOk) {
        findings.push({ check: 'rendered-content', severity: 'critical', url: route.path, viewport: viewport.name, message: `После рендера основной контент пуст: блоков ${rendered.cards}, текста ${rendered.mainTextLength} символов` });
      } else if (contentPage && rendered.mainTextLength < 200) {
        findings.push({ check: 'thin-content', severity: 'major', url: route.path, viewport: viewport.name, message: `Мало видимого текста: ${rendered.mainTextLength} символов` });
      }
      if (rendered.horizontalOverflow) findings.push({ check: 'layout', severity: 'critical', url: route.path, viewport: viewport.name, message: 'Горизонтальная прокрутка на этом брейкпоинте' });
      if (rendered.lazyLcpCandidate) findings.push({ check: 'lcp', severity: 'major', url: route.path, viewport: viewport.name, message: 'Первое изображение основного блока помечено loading=lazy' });
      if (rendered.imagesWithoutAlt) findings.push({ check: 'alt', severity: 'critical', url: route.path, viewport: viewport.name, message: `Изображений без alt: ${rendered.imagesWithoutAlt}` });
      if (rendered.imagesWithoutSize) findings.push({ check: 'cls', severity: 'major', url: route.path, viewport: viewport.name, message: `Изображений без width/height: ${rendered.imagesWithoutSize}` });
      if (route.page_type === 'episode' && !rendered.player && !rendered.availability) {
        findings.push({ check: 'player', severity: 'critical', url: route.path, viewport: viewport.name, message: 'Ни плеера, ни блока недоступности на странице эпизода' });
      }
      if (response && response.status() !== route.status) {
        findings.push({ check: 'status', severity: 'critical', url: route.path, viewport: viewport.name, message: `Браузер получил ${response.status()}, ожидался ${route.status}` });
      }

      // Лабораторные метрики. Это НЕ полевые Core Web Vitals — так и подписано.
      const lab = await page.evaluate(() => new Promise((resolve) => {
        let lcp = 0, cls = 0;
        try {
          new PerformanceObserver((list) => { for (const e of list.getEntries()) lcp = Math.max(lcp, e.startTime); }).observe({ type: 'largest-contentful-paint', buffered: true });
          new PerformanceObserver((list) => { for (const e of list.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
        } catch (e) { /* метрика недоступна в этом движке */ }
        setTimeout(() => {
          const nav = performance.getEntriesByType('navigation')[0] || {};
          const bytes = performance.getEntriesByType('resource').reduce((s, r) => s + (r.transferSize || 0), 0);
          resolve({ lcp_ms: Math.round(lcp), cls: Number(cls.toFixed(4)), dcl_ms: Math.round(nav.domContentLoadedEventEnd || 0), transfer_bytes: bytes });
        }, 600);
      }));
      metrics.push({ url: route.path, viewport: viewport.name, ...lab });

      // Доступность: axe-core на репрезентативных брейкпоинтах (мобильный и десктопный),
      // чтобы прогон оставался в разумном времени, но покрывал обе раскладки.
      const axeViewports = ['mobile-390', 'desktop-1440'];
      const axeResult = axeViewports.includes(viewport.name)
        ? await page.evaluate(async () => await window.axe.run(document, { resultTypes: ['violations'] }))
        : { violations: [] };
      for (const violation of axeResult.violations) {
        if (['critical', 'serious'].includes(violation.impact)) {
          a11y.push({
            url: route.path, viewport: viewport.name, id: violation.id, impact: violation.impact,
            help: violation.help, nodes: violation.nodes.length,
            targets: violation.nodes.slice(0, 3).map((n) => ({ target: String(n.target), summary: String(n.failureSummary || '').slice(0, 300) })),
          });
        }
      }

      // Клавиатура: skip-link достижим первым Tab и получает видимый фокус.
      if (route.path === '/') {
        await page.keyboard.press('Tab');
        const focus = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el) return null;
          const style = getComputedStyle(el);
          return { tag: el.tagName, cls: el.className, outline: style.outlineStyle, visible: el.getBoundingClientRect().top >= 0 };
        });
        if (!focus || !String(focus.cls).includes('skip-link')) {
          findings.push({ check: 'keyboard', severity: 'critical', url: route.path, viewport: viewport.name, message: `Первый Tab не попал на skip-link (${focus && focus.cls})` });
        }
      }

      if (['/', '/lekcii/', '/praktikum/serial-fikstura/season-1/episode-1/'].includes(route.path)) {
        const file = path.join(OUT, `screenshot-${viewport.name}-${route.path.replace(/[^a-z0-9]+/gi, '_')}.png`);
        await page.screenshot({ path: file, fullPage: false });
        screenshots.push(path.basename(file));
      }
      await page.close();
    }
    await context.close();
  }

  // «Показать ещё» — только поверх работающей серверной пагинации.
  const enhance = await checkProgressiveEnhancement(browser, BASE, AUTH, findings);
  await browser.close();

  const result = { base: BASE, viewports: VIEWPORTS.map((v) => v.name), sample: sample.map((r) => r.path), findings, metrics, a11y, screenshots, enhance };
  fs.writeFileSync(path.join(OUT, 'browser-audit.json'), JSON.stringify(result, null, 2));
  process.stdout.write(JSON.stringify({ findings: findings.length, a11y: a11y.length, screenshots: screenshots.length, criticals: findings.filter((f) => f.severity === 'critical').length + a11y.length }));
  process.exit(findings.some((f) => f.severity === 'critical') || a11y.length ? 1 : 0);
}

async function checkProgressiveEnhancement(browser, base, auth, findings) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    httpCredentials: auth ? { username: auth.split(':')[0], password: auth.slice(auth.indexOf(':') + 1) } : undefined,
  });
  const page = await context.newPage();
  await page.goto(base + '/lekcii/', { waitUntil: 'load' });
  const before = await page.locator('#items > li').count();
  const hasButton = await page.locator('.load-more').count();
  let after = before;
  if (hasButton) {
    await page.locator('.load-more').click();
    await page.waitForTimeout(1200);
    after = await page.locator('#items > li').count();
    if (after <= before) findings.push({ check: 'load-more', severity: 'major', url: '/lekcii/', viewport: 'mobile-390', message: 'Кнопка «Показать ещё» не добавила материалов' });
  }
  // Без JS серверная пагинация обязана работать: проверяем прямым открытием.
  const noJs = await browser.newContext({ javaScriptEnabled: false, httpCredentials: auth ? { username: auth.split(':')[0], password: auth.slice(auth.indexOf(':') + 1) } : undefined });
  const noJsPage = await noJs.newPage();
  const resp = await noJsPage.goto(base + '/lekcii/page/2/', { waitUntil: 'load' });
  const itemsNoJs = await noJsPage.locator('#items > li').count();
  const linksNoJs = await noJsPage.locator('.pagination a[href]').count();
  if (!resp || resp.status() !== 200 || itemsNoJs === 0 || linksNoJs === 0) {
    findings.push({ check: 'pagination-nojs', severity: 'critical', url: '/lekcii/page/2/', viewport: 'no-js', message: `Без JS: статус ${resp && resp.status()}, материалов ${itemsNoJs}, ссылок пагинации ${linksNoJs}` });
  }
  await noJs.close();
  await context.close();
  return { items_before: before, items_after: after, has_button: !!hasButton, items_without_js: itemsNoJs, pagination_links_without_js: linksNoJs };
}

function pickSample(routes) {
  const byType = new Map();
  for (const route of routes) {
    if (!byType.has(route.page_type)) byType.set(route.page_type, route);
  }
  return Array.from(byType.values());
}

main().catch((err) => { process.stderr.write(String(err)); process.exit(2); });
