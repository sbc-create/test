// REQ-LORDS-STAGING: три публичных стенда Lords в браузере.
// Проверяются распакованные пакеты, запущенные своим рантаймом.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const registry = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', '..', 'config', 'directions', 'lords.json'), 'utf8'),
);

const SITES = registry.domains.map((d) => ({
  id: d.site_id,
  profile: d.profile,
  apex: d.apex,
  www: d.www,
  port: d.staging_port,
  base: `http://127.0.0.1:${d.staging_port}`,
}));

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 390, height: 844 },
];

const OUT = path.join(__dirname, '..', '..', 'var', 'artifacts', 'lords-staging-screenshots');
fs.mkdirSync(OUT, { recursive: true });

const FORBIDDEN = ['CDNVIDEOHUB_API_TOKEN', 'CDNVIDEOHUB_PUBLISHER_ID', 'NEXT_PUBLIC', 'secret://'];

test.describe.configure({ mode: 'serial' });

test.describe('маршруты трёх стендов', () => {
  for (const site of SITES) {
    test(`[${site.id}] обязательные маршруты отвечают`, async ({ page }) => {
      const routes = ['/', '/catalog/', '/movies/', '/series/', '/new/', '/genres/', '/search/'];
      for (const route of routes) {
        const response = await page.goto(site.base + route);
        expect(response.status(), `${site.id}${route}`).toBe(200);
        expect(response.headers()['x-robots-tag']).toBe('noindex, nofollow');
        await expect(page.locator('h1')).toHaveCount(1);
      }
    });

    test(`[${site.id}] robots и sitemap закрыты`, async ({ page }) => {
      const robots = await page.goto(`${site.base}/robots.txt`);
      expect(robots.status()).toBe(200);
      const robotsBody = await robots.text();
      expect(robotsBody).toContain('Disallow: /');
      expect(robotsBody).not.toContain('Sitemap:');

      const sitemap = await page.goto(`${site.base}/sitemap.xml`);
      expect(sitemap.status()).toBe(200);
      const sitemapBody = await sitemap.text();
      // Ни одного индексируемого адреса, пока индексация выключена.
      expect(sitemapBody).not.toContain('<loc>');
      for (const other of SITES) {
        expect(sitemapBody).not.toContain(other.apex);
      }
    });

    test(`[${site.id}] 404 и 308`, async ({ page }) => {
      const missing = await page.goto(`${site.base}/no-such-address/`);
      expect(missing.status()).toBe(404);
      await expect(page.locator('h1')).toContainText('не найдена');

      // Выключенный тип не отдаёт пустую двухсотку.
      const disabled = await page.goto(`${site.base}/anime/`);
      expect(disabled.status()).toBe(404);

      const normalized = await page.goto(`${site.base}/catalog`);
      expect(normalized.url()).toContain('/catalog/');
      expect(normalized.status()).toBe(200);
    });

    test(`[${site.id}] canonical ведёт на свой домен и только на свой`, async ({ page }) => {
      await page.goto(`${site.base}/catalog/`);
      const canonical = await page.locator('link[rel="canonical"]').getAttribute('href');
      expect(canonical).toBe(`https://${site.apex}/catalog/`);
      const robots = await page.locator('meta[name="robots"]').getAttribute('content');
      expect(robots).toBe('noindex, nofollow');

      const html = await page.content();
      for (const other of SITES) {
        if (other.apex === site.apex) continue;
        expect(html, `${site.id}: чужой домен ${other.apex}`).not.toContain(other.apex);
      }
    });
  }
});

test.describe('поведение каталога', () => {
  for (const site of SITES) {
    test(`[${site.id}] фильтры, сортировка, пагинация и поиск`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`${site.base}/catalog/`);

      // Пагинация
      await expect(page.locator('.pagination')).toBeVisible();
      await page.locator('.pagination a[rel="next"]').click();
      await expect(page).toHaveURL(/\/catalog\/page\/2\/$/);

      // Фильтр
      await page.goto(`${site.base}/catalog/`);
      const before = await page.locator('.card').count();
      const genre = await page.locator('#f-genre option').nth(1).getAttribute('value');
      await page.selectOption('#f-genre', genre);
      await page.waitForFunction((n) => document.querySelectorAll('.card').length !== n, before);
      expect(await page.locator('.card').count()).toBeGreaterThan(0);

      // Сортировка
      await page.goto(`${site.base}/catalog/`);
      const first = (await page.locator('.card__title').first().innerText()).trim();
      await page.selectOption('#f-sort', 'name');
      await page.waitForFunction((name) => {
        const node = document.querySelector('.card__title');
        return node && node.textContent.trim() !== name;
      }, first);

      // Поиск
      await page.goto(`${site.base}/catalog/`);
      const name = (await page.locator('.card__title').first().innerText()).trim();
      await page.goto(`${site.base}/search/?q=${encodeURIComponent(name)}`);
      await expect(page.locator('#grid .card').first()).toBeVisible();
    });

    test(`[${site.id}] тайтл, сезоны и серии, плеер`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });

      // Сериал: сезоны и серии
      await page.goto(`${site.base}/series/`);
      await page.locator('.card__title').first().click();
      await expect(page.locator('.seasons details.season').first()).toBeVisible();
      await expect(page.locator('.episode').first()).toBeVisible();
      const season = page.locator('details.season').first();
      await season.locator('summary').click();
      await expect(page.locator('.breadcrumbs')).toBeVisible();

      // Фильм: сезонов нет
      await page.goto(`${site.base}/movies/`);
      await page.locator('.card__title').first().click();
      await expect(page.locator('details.season')).toHaveCount(0);

      // Плеер — заглушка, а не настоящий плеер
      await expect(page.locator('.player__status'))
        .toHaveText('BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS');
      expect(await page.locator('iframe').count()).toBe(0);
      await expect(page.locator('.comments button')).toBeDisabled();
    });
  }
});

test.describe('раскладка на трёх ширинах', () => {
  for (const site of SITES) {
    test(`[${site.id}] нет горизонтальной прокрутки`, async ({ page }) => {
      for (const view of VIEWPORTS) {
        await page.setViewportSize({ width: view.width, height: view.height });
        for (const route of ['/', '/catalog/', '/genres/', '/search/']) {
          await page.goto(site.base + route);
          const box = await page.evaluate(() => ({
            scroll: document.documentElement.scrollWidth,
            client: document.documentElement.clientWidth,
          }));
          expect(box.scroll, `${site.id}${route} @${view.width}`)
            .toBeLessThanOrEqual(box.client + 1);
        }
      }
    });
  }
});

test.describe('изоляция и секреты', () => {
  test('три стенда не делят ни одной индексируемой страницы', async ({ page }) => {
    const indexable = {};
    for (const site of SITES) {
      await page.goto(`${site.base}/sitemap.xml`);
      // Sitemap пуст, поэтому «общность» проверяется по canonical главных
      // разделов: у каждого сайта они обязаны вести на его собственный домен.
      const seen = new Set();
      for (const route of ['/', '/catalog/', '/new/', '/genres/', '/collections/']) {
        const response = await page.goto(site.base + route);
        if (response.status() !== 200) continue;
        const canonical = await page.locator('link[rel="canonical"]').getAttribute('href');
        if (canonical) seen.add(canonical);
      }
      indexable[site.id] = seen;
    }
    const all = Object.values(indexable).flatMap((s) => [...s]);
    expect(new Set(all).size, 'два стенда объявили один и тот же canonical').toBe(all.length);
  });

  test('в HTML и JS нет секретов', async ({ page }) => {
    const bodies = [];
    page.on('response', async (response) => {
      const type = response.headers()['content-type'] || '';
      if (!/html|javascript|json/.test(type)) return;
      try { bodies.push([response.url(), await response.text()]); } catch (e) { /* тело недоступно */ }
    });
    for (const site of SITES) {
      await page.goto(`${site.base}/`);
      await page.goto(`${site.base}/catalog/`);
    }
    expect(bodies.length).toBeGreaterThan(0);
    for (const [href, text] of bodies) {
      for (const marker of FORBIDDEN) {
        expect(text.includes(marker), `${href}: найдено «${marker}»`).toBe(false);
      }
    }
  });

  test('страницы не ходят за внешними ресурсами', async ({ page }) => {
    const external = [];
    page.on('request', (request) => {
      const host = new URL(request.url()).hostname;
      if (!['127.0.0.1', 'localhost'].includes(host)) external.push(request.url());
    });
    for (const site of SITES) {
      await page.goto(`${site.base}/`);
      await page.goto(`${site.base}/catalog/`);
    }
    expect(external, `внешние запросы: ${external.join(', ')}`).toHaveLength(0);
  });
});

test.describe('снимки экрана', () => {
  for (const site of SITES) {
    test(`[${site.id}] снимки трёх ширин`, async ({ page }) => {
      for (const view of VIEWPORTS) {
        await page.setViewportSize({ width: view.width, height: view.height });
        for (const [name, route] of [['home', '/'], ['catalog', '/catalog/']]) {
          await page.goto(site.base + route);
          await page.screenshot({
            path: path.join(OUT, `${site.id}-${name}-${view.width}.png`),
          });
        }
      }
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`${site.base}/movies/`);
      await page.locator('.card__title').first().click();
      await page.screenshot({ path: path.join(OUT, `${site.id}-title-1440.png`) });
    });
  }
});
