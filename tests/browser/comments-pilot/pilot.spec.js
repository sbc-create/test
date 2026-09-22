// @ts-check
/**
 * Browser acceptance for the animedia.icu pilot, on the shadow contour.
 *
 * This is the half of the owner's list a terminal cannot answer: whether the
 * block actually appears on a real title page, whether it survives 320px,
 * whether the console stays clean, whether a keyboard can reach the form, and
 * — most importantly — whether an ordinary visitor sees no writing surface at
 * all while the owner does.
 *
 * It runs against the same shadow contour as the API checks: the real Animedia
 * runtime with the adapter, the real comments gateway, and a router that
 * mimics the nginx location split. Nothing here touches the live site.
 *
 * CP_PILOT_BASE is the contour's base URL, exported by the runner.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');

const BASE = process.env.CP_PILOT_BASE;
const TITLE = '/title/master-lda-i-plameni-2/';
const SECOND = '/title/nelyud-chast-2/';
const OWNER_COOKIE = process.env.CP_PILOT_COOKIE || '';
const CSRF = process.env.CP_PILOT_CSRF || '';

const AXE = require.resolve('axe-core/axe.min.js');
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

const WIDTHS = [320, 390, 768, 1024, 1440, 1920];

test.skip(!BASE, 'shadow contour not running; start it with comments_shadow_rehearsal.py --keep-up');

/** Give this browser context the owner cohort cookie. */
async function beOwner(context) {
  const url = new URL(BASE);
  await context.addCookies([
    { name: 'cp_cohort', value: OWNER_COOKIE, domain: url.hostname, path: '/' },
    { name: 'cp_csrf', value: CSRF, domain: url.hostname, path: '/' },
  ]);
}

/**
 * Collect console problems, minus the one the design produces on purpose.
 *
 * When the gateway refuses a visitor, the browser logs "Failed to load
 * resource: 503" for the thread request. That line is Chrome reporting a
 * response, not the page misbehaving, and the 503 is the whole point of an
 * owner-only stage: the alternative is not making the request, which would
 * mean the page knowing the answer before it asked.
 *
 * Uncaught exceptions are never excused, and neither is any other console
 * error — including a 5xx or a failed asset.
 */
function watchConsole(page) {
  const problems = [];
  const expected = /Failed to load resource.*503/;
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    if (expected.test(m.text())) return;
    problems.push(m.text());
  });
  page.on('pageerror', (e) => problems.push('pageerror: ' + String(e)));
  return problems;
}

test.describe('the ordinary visitor', () => {
  test('sees the page as before, with no writing surface', async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto(BASE + TITLE);

    // The mount point is in the HTML — that is the adapter doing its job —
    // but nothing inside it may offer a way to write.
    await expect(page.locator('#cp-comments')).toBeAttached();
    await expect(page.locator('.cp-form__input')).toHaveCount(0);
    await expect(page.locator('.cp-form__submit')).toHaveCount(0);

    // And the page around it is intact.
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('[data-player]')).toBeVisible();
    expect(problems).toEqual([]);
  });

  test('sees no comment text anywhere in the delivered HTML', async ({ page }) => {
    await page.goto(BASE + TITLE);
    const html = await page.content();
    expect(html).not.toContain('Тест комментариев Animedia');
  });

  test('the page does not shift more than the budget while comments settle',
    async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(BASE + TITLE);
      await page.evaluate(() => {
        window.__cls = 0;
        new PerformanceObserver((l) => {
          for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value;
        }).observe({ type: 'layout-shift', buffered: true });
      });
      await page.waitForTimeout(1500);
      const cls = await page.evaluate(() => window.__cls);
      expect(cls).toBeLessThan(0.1);
    });
});

test.describe('the owner', () => {
  test.beforeEach(async ({ context }) => {
    await beOwner(context);
  });

  test('sees the comments block and the form', async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto(BASE + TITLE);
    await expect(page.locator('.cp-widget')).toBeVisible();
    await expect(page.locator('.cp-heading')).toContainText('Комментарии');
    await expect(page.locator('.cp-form__input')).toBeVisible();
    expect(problems).toEqual([]);
  });

  test('can type, submit and see the moderation status', async ({ page }) => {
    await page.goto(BASE + TITLE);
    const marker = `Тест комментариев Animedia — владелец — ${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}`;
    await page.locator('.cp-form__input').fill(marker);
    await page.locator('.cp-form__submit').click();

    // Pre-moderation on this site: the comment is accepted and held, and the
    // widget must say so rather than appear to have lost it.
    await expect(page.locator('.cp-status[data-cp-status="pending"]')).toBeVisible();
    await expect(page.locator('.cp-comment__body')).toContainText(marker.slice(0, 30));
  });

  test('a reload keeps what was written', async ({ page }) => {
    await page.goto(BASE + TITLE);
    const marker = `Сохранение после перезагрузки ${Date.now()}`;
    await page.locator('.cp-form__input').fill(marker);
    await page.locator('.cp-form__submit').click();
    await expect(page.locator('.cp-status')).toBeVisible();

    await page.reload();
    await expect(page.locator('.cp-list')).toContainText(marker.slice(0, 24));
  });

  test('the form keeps the text when the API refuses', async ({ page, context }) => {
    await page.goto(BASE + TITLE);
    await expect(page.locator('.cp-form__input')).toBeVisible();

    // Make the next write fail at the network, the way an outage would.
    await context.route('**/api/comments/v1/comments', (r) => r.abort('failed'));
    const typed = 'Текст, который нельзя потерять при ошибке сети';
    await page.locator('.cp-form__input').fill(typed);
    await page.locator('.cp-form__submit').click();

    await expect(page.locator('.cp-status[data-cp-status="error"]')).toBeVisible();
    await expect(page.locator('.cp-form__input')).toHaveValue(typed);
  });

  test('a failed comments API does not break the page', async ({ page, context }) => {
    const problems = watchConsole(page);
    // The data endpoints only. Aborting `/assets/` too would stop the widget
    // script from loading at all, which tests the absence of the widget
    // rather than its behaviour when its API is down.
    await context.route('**/api/comments/v1/threads**', (r) => r.abort('failed'));
    await context.route('**/api/comments/v1/comments**', (r) => r.abort('failed'));
    await page.goto(BASE + TITLE);

    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('[data-player]')).toBeVisible();
    // A network abort is not a 503, so the widget stays and explains itself
    // rather than withdrawing.
    await expect(page.locator('.cp-status[data-cp-status="error"]')).toBeVisible();
    // The failed fetch shows in the console as a net::ERR line; what must not
    // appear is an uncaught exception from the widget.
    expect(problems.filter((p) => p.startsWith('pageerror'))).toEqual([]);
  });

  test('is reachable by keyboard with visible focus', async ({ page }) => {
    await page.goto(BASE + TITLE);
    await expect(page.locator('.cp-form__input')).toBeVisible();

    await page.locator('.cp-form__input').focus();
    const outline = await page.evaluate(() => {
      const s = getComputedStyle(document.activeElement);
      return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
    });
    expect(outline.style).not.toBe('none');
    expect(outline.width).toBeGreaterThan(0);

    const reachable = await page.evaluate(() => {
      const w = document.querySelector('.cp-widget');
      const nodes = w.querySelectorAll('button:not([hidden]), textarea, [tabindex="0"]');
      let count = 0;
      for (const n of nodes) { n.focus(); if (document.activeElement === n) count += 1; }
      return { total: nodes.length, focused: count };
    });
    expect(reachable.focused).toBe(reachable.total);
    expect(reachable.total).toBeGreaterThan(3);
  });
});

test.describe('layout across widths', () => {
  for (const width of WIDTHS) {
    test(`no horizontal overflow at ${width}px`, async ({ page, context }) => {
      await beOwner(context);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(BASE + TITLE);
      await expect(page.locator('.cp-widget')).toBeVisible();

      const overflow = await page.evaluate(() => ({
        doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        widget: (() => {
          const w = document.querySelector('.cp-widget');
          return w.scrollWidth - w.clientWidth;
        })(),
      }));
      expect(overflow.widget).toBeLessThanOrEqual(0);
      // The host page owns its own layout; the widget must not be what pushes
      // it sideways.
      expect(overflow.doc).toBeLessThanOrEqual(0);
    });
  }
});

test.describe('accessibility of the mounted widget', () => {
  for (const width of [320, 768, 1440]) {
    test(`axe finds no WCAG 2.2 AA violation inside the widget at ${width}px`,
      async ({ page, context }) => {
        await beOwner(context);
        await page.setViewportSize({ width, height: 900 });
        await page.goto(BASE + TITLE);
        await expect(page.locator('.cp-widget')).toBeVisible();
        await page.addScriptTag({ path: AXE });

        const results = await page.evaluate(
          async (tags) => axe.run('.cp-widget', { runOnly: { type: 'tag', values: tags } }),
          AXE_TAGS,
        );
        const summary = results.violations.map((v) => `${v.id}: ${v.nodes.length}`);
        expect(summary, JSON.stringify(results.violations, null, 2)).toEqual([]);
        expect(results.passes.length).toBeGreaterThan(5);
      });
  }
});

test.describe('routes that must stay clean', () => {
  for (const [name, route] of [
    ['home', '/'],
    ['catalog', '/catalog/'],
    ['404', '/definitely-not-real-9d2f/'],
  ]) {
    test(`${name} has no comments widget`, async ({ page, context }) => {
      await beOwner(context);
      await page.goto(BASE + route);
      await expect(page.locator('.cp-widget')).toHaveCount(0);
      await expect(page.locator('#cp-comments')).toHaveCount(0);
    });
  }

  test('a second title page also mounts the widget', async ({ page, context }) => {
    await beOwner(context);
    await page.goto(BASE + SECOND);
    await expect(page.locator('.cp-widget')).toBeVisible();
  });
});
