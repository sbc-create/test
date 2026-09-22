// @ts-check
/**
 * Browser acceptance for the shared comments widget.
 *
 * Run in a real Chromium against a real DOM, because the properties under test
 * — layout at 320px, focus visibility, what a screen reader is told, whether
 * loading comments shifts the page — are not observable from a string.
 *
 * The API is mocked at the network layer rather than by patching `fetch`, so
 * the widget's own request code (headers, credentials, abort) is exercised.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

// Injected as a script, the way the rest of this repository runs axe — see
// tests/e2e-lords/accessibility.spec.js. WCAG 2.2 AA inherits the 2.0 and 2.1
// criteria of the same level, so every tag is listed: `wcag22aa` alone would
// cover only what 2.2 added.
const AXE = require.resolve('axe-core/axe.min.js');
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

const FIXTURE = '/tests/browser/comments-widget/fixture.html';

// The fixture loads the real artifact from its one home. Copying the widget
// next to the test would be the very duplication this module exists to stop,
// and would let the suite pass against a stale copy.
const WIDGET_DIR = path.join(__dirname, '..', '..', '..', 'factory', 'comments_platform', 'widget');
const WIDGET_CSS = path.join(WIDGET_DIR, 'comments-widget.css');

const WIDTHS = [320, 390, 768, 1024, 1440, 1920];

function comment(id, overrides = {}) {
  return Object.assign(
    {
      comment_id: id,
      anchor: 'comment-' + id,
      parent_id: null,
      depth: 0,
      author: { subject_id: 'g_' + id + 'abcdef0123456789' },
      state: 'published',
      is_own: false,
      body_html: 'Комментарий ' + id + ' с достаточно длинным текстом, чтобы занять строку.',
      created_at: '2026-09-22T10:00:00Z',
      edited_at: null,
      revision: 1,
      reaction_count: 3,
      reply_count: 0
    },
    overrides
  );
}

const PAGE = {
  thread_id: 'th_1',
  resource_type: 'title',
  canonical_content_id: 'tt-0001',
  total_count: 3,
  items: [comment('c1'), comment('c2', { depth: 1 }), comment('c3', { depth: 2 })],
  next_cursor: '',
  has_more: false,
  sort: 'new'
};

/** Serve a thread page; optionally fail, delay, or vary the payload. */
async function mockApi(page, options = {}) {
  const { body = PAGE, status = 200, delayMs = 0, onRequest } = options;
  await page.route('**/api/comments/v1/**', async (route) => {
    if (onRequest) onRequest(route.request());
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await route.fulfill({
      status,
      contentType: 'application/json',
      headers: { 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify(body)
    });
  });
}

async function mount(page, overrides) {
  await page.evaluate((o) => window.__mountWidget(o), overrides || {});
  await page.waitForSelector('.cp-widget');
}

test.describe('rendering and structure', () => {
  test('renders the thread returned by the API', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    await expect(page.locator('.cp-comment')).toHaveCount(3);
    await expect(page.locator('.cp-count')).toHaveText('3');
  });

  test('shows the empty state when there are no comments', async ({ page }) => {
    await mockApi(page, { body: { ...PAGE, items: [], total_count: 0 } });
    await page.goto(FIXTURE);
    await mount(page);
    await expect(page.locator('.cp-empty')).toBeVisible();
  });

  test('each comment has a stable anchor', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    const ids = await page.locator('.cp-comment').evaluateAll((els) => els.map((e) => e.id));
    expect(ids).toEqual(['comment-c1', 'comment-c2', 'comment-c3']);
  });

  test('a moderation state is announced on the comment', async ({ page }) => {
    await mockApi(page, {
      body: { ...PAGE, items: [comment('c1', { state: 'pending', is_own: true })] }
    });
    await page.goto(FIXTURE);
    await mount(page);
    await expect(page.locator('.cp-comment__status')).toBeVisible();
  });
});

test.describe('the page survives a broken comments service', () => {
  test('a 500 leaves the host page intact and says so', async ({ page }) => {
    await mockApi(page, { status: 500, body: { error: { code: 'InternalError' } } });
    await page.goto(FIXTURE);
    await mount(page);

    await expect(page.locator('.cp-status[data-cp-status="error"]')).toBeVisible();
    // The host page is untouched.
    await expect(page.locator('h1')).toHaveText('Фильм');
    await expect(page.locator('#after')).toBeVisible();
  });

  test('a network failure does not throw into the page', async ({ page }) => {
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));
    await page.route('**/api/comments/v1/**', (route) => route.abort('failed'));
    await page.goto(FIXTURE);
    await mount(page);
    await expect(page.locator('.cp-status')).toBeVisible();
    expect(pageErrors).toEqual([]);
  });

  test('a retry control is offered and works', async ({ page }) => {
    let fail = true;
    await page.route('**/api/comments/v1/**', async (route) => {
      if (fail) {
        fail = false;
        return route.abort('failed');
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PAGE)
      });
    });
    await page.goto(FIXTURE);
    await mount(page);
    await page.locator('.cp-retry').click();
    await expect(page.locator('.cp-comment')).toHaveCount(3);
  });
});

test.describe('composing', () => {
  test('the typed text survives a failed submit', async ({ page }) => {
    await page.route('**/api/comments/v1/threads**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PAGE) })
    );
    await page.route('**/api/comments/v1/comments', (route) =>
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'RateLimited', retry_after_seconds: 60 } })
      })
    );
    await page.goto(FIXTURE);
    await mount(page);

    const typed = 'Длинный комментарий, который я не хочу потерять из-за ошибки сети.';
    await page.locator('.cp-form__input').fill(typed);
    await page.locator('.cp-form__submit').click();

    await expect(page.locator('.cp-status')).toBeVisible();
    // The single most enraging failure mode of a comment box.
    await expect(page.locator('.cp-form__input')).toHaveValue(typed);
  });

  test('a rate limit is explained, not shown as a generic error', async ({ page }) => {
    await page.route('**/api/comments/v1/threads**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PAGE) })
    );
    await page.route('**/api/comments/v1/comments', (route) =>
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'RateLimited', retry_after_seconds: 60 } })
      })
    );
    await page.goto(FIXTURE);
    await mount(page);
    await page.locator('.cp-form__input').fill('снова и снова');
    await page.locator('.cp-form__submit').click();
    await expect(page.locator('.cp-status')).toContainText('часто');
  });

  test('a held comment tells the author it is awaiting moderation', async ({ page }) => {
    await page.route('**/api/comments/v1/threads**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PAGE) })
    );
    await page.route('**/api/comments/v1/comments', (route) =>
      route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          comment: comment('c9', { state: 'pending' }),
          moderation: { state: 'pending', held: true, degraded: false }
        })
      })
    );
    await page.goto(FIXTURE);
    await mount(page);
    await page.locator('.cp-form__input').fill('комментарий на модерацию');
    await page.locator('.cp-form__submit').click();
    await expect(page.locator('.cp-status[data-cp-status="pending"]')).toBeVisible();
  });

  test('the box is cleared only after the server accepted the text', async ({ page }) => {
    await page.route('**/api/comments/v1/threads**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PAGE) })
    );
    await page.route('**/api/comments/v1/comments', (route) =>
      route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          comment: comment('c9'),
          moderation: { state: 'published', held: false, degraded: false }
        })
      })
    );
    await page.goto(FIXTURE);
    await mount(page);
    await page.locator('.cp-form__input').fill('принятый комментарий');
    await page.locator('.cp-form__submit').click();
    await expect(page.locator('.cp-form__input')).toHaveValue('');
  });
});

test.describe('lifecycle', () => {
  test('mounting twice returns one widget, not two', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    await mount(page);
    await expect(page.locator('.cp-widget')).toHaveCount(1);
  });

  test('destroy removes the widget and leaves the host node', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await page.evaluate(() => {
      window.__handle = window.__mountWidget();
    });
    await page.waitForSelector('.cp-widget');
    await page.evaluate(() => window.__handle.destroy());
    await expect(page.locator('.cp-widget')).toHaveCount(0);
    await expect(page.locator('#comments')).toBeAttached();
  });

  test('destroy twice is a no-op', async ({ page }) => {
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));
    await mockApi(page);
    await page.goto(FIXTURE);
    await page.evaluate(() => {
      window.__handle = window.__mountWidget();
    });
    await page.waitForSelector('.cp-widget');
    await page.evaluate(() => {
      window.__handle.destroy();
      window.__handle.destroy();
    });
    expect(pageErrors).toEqual([]);
  });

  test('remounting after destroy works', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await page.evaluate(() => {
      window.__handle = window.__mountWidget();
    });
    await page.waitForSelector('.cp-widget');
    await page.evaluate(() => window.__handle.destroy());
    await mount(page);
    await expect(page.locator('.cp-comment')).toHaveCount(3);
  });

  test('two instances on one page stay independent', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await page.evaluate(() => {
      const second = document.createElement('div');
      second.id = 'comments-2';
      document.querySelector('.page').appendChild(second);
      window.__a = window.SiteFactoryComments.mount('#comments', {
        apiBase: '', resourceType: 'title', canonicalContentId: 'tt-0001', onEvent: () => {}
      });
      window.__b = window.SiteFactoryComments.mount('#comments-2', {
        apiBase: '', resourceType: 'title', canonicalContentId: 'tt-0002', onEvent: () => {}
      });
    });
    await expect(page.locator('.cp-widget')).toHaveCount(2);
    await page.evaluate(() => window.__a.destroy());
    await expect(page.locator('.cp-widget')).toHaveCount(1);
  });
});

test.describe('server-rendered comments', () => {
  test('prerendered markup is adopted, not discarded', async ({ page }) => {
    await mockApi(page, { delayMs: 400 });
    await page.goto(FIXTURE);
    await page.evaluate(() => {
      document.querySelector('#comments').innerHTML =
        '<div class="cp-thread">' +
        '<article class="cp-comment" id="comment-ssr1">' +
        '<div class="cp-comment__body">Отрисовано сервером</div></article>' +
        '</div>';
    });
    await mount(page);
    // Before the fetch resolves, the server-rendered comment is still readable.
    await expect(page.locator('#comment-ssr1')).toBeVisible();
  });
});

test.describe('responsive matrix', () => {
  for (const width of WIDTHS) {
    test(`no horizontal overflow at ${width}px`, async ({ page }) => {
      await mockApi(page, {
        body: {
          ...PAGE,
          items: [
            comment('c1', {
              body_html:
                'Оченьдлинноесловобезпробеловкотороеобязанопереноситься' +
                'ещёдлиннеечтобыгарантированнонепоместилосьвстроку ' +
                '<a href="https://example.test/очень/длинный/адрес/который/тоже/не/помещается">ссылка</a>'
            }),
            comment('c2', { depth: 1 }),
            comment('c3', { depth: 2 }),
            comment('c4', { depth: 3 }),
            comment('c5', { depth: 4 })
          ]
        }
      });
      await page.setViewportSize({ width, height: 900 });
      await page.goto(FIXTURE);
      await mount(page);

      const overflow = await page.evaluate(() => ({
        doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        widget: (() => {
          const w = document.querySelector('.cp-widget');
          return w.scrollWidth - w.clientWidth;
        })()
      }));
      expect(overflow.doc).toBeLessThanOrEqual(0);
      expect(overflow.widget).toBeLessThanOrEqual(0);
    });

    test(`touch targets are at least 44px at ${width}px`, async ({ page }) => {
      await mockApi(page);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(FIXTURE);
      await mount(page);
      const small = await page.evaluate(() => {
        const controls = document.querySelectorAll(
          '.cp-widget button, .cp-widget [role="button"]'
        );
        return Array.from(controls)
          .filter((c) => !c.hasAttribute('hidden'))
          .map((c) => {
            const r = c.getBoundingClientRect();
            return { text: c.textContent.trim().slice(0, 20), w: Math.round(r.width), h: Math.round(r.height) };
          })
          .filter((m) => m.w < 44 || m.h < 44);
      });
      expect(small).toEqual([]);
    });
  }
});

test.describe('accessibility', () => {
  for (const width of [320, 768, 1440]) {
    test(`axe reports no WCAG 2.2 A/AA violations at ${width}px`, async ({ page }) => {
      await mockApi(page);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(FIXTURE);
      await mount(page);
      await page.addScriptTag({ path: AXE });

      const results = await page.evaluate(
        async (tags) => axe.run('.cp-widget', { runOnly: { type: 'tag', values: tags } }),
        AXE_TAGS
      );
      const summary = results.violations.map((v) => `${v.id}: ${v.nodes.length} node(s)`);
      expect(summary, JSON.stringify(results.violations, null, 2)).toEqual([]);
      // A run that checked nothing would also report no violations.
      expect(results.passes.length).toBeGreaterThan(5);
    });
  }

  test('the whole widget is reachable by keyboard', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    const reached = await page.evaluate(async () => {
      const seen = [];
      const widget = document.querySelector('.cp-widget');
      const focusables = widget.querySelectorAll(
        'button:not([hidden]), textarea, [tabindex="0"]'
      );
      for (const node of focusables) {
        node.focus();
        if (document.activeElement === node) seen.push(node.className || node.tagName);
      }
      return { total: focusables.length, focused: seen.length };
    });
    expect(reached.focused).toBe(reached.total);
    expect(reached.total).toBeGreaterThan(3);
  });

  test('focus is visible, not suppressed', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    await page.locator('.cp-sort__button').first().focus();
    const outline = await page.evaluate(() => {
      const el = document.activeElement;
      const s = getComputedStyle(el);
      return { style: s.outlineStyle, width: s.outlineWidth };
    });
    expect(outline.style).not.toBe('none');
    expect(parseFloat(outline.width)).toBeGreaterThan(0);
  });

  test('status messages sit in a live region', async ({ page }) => {
    await mockApi(page, { status: 500, body: { error: { code: 'InternalError' } } });
    await page.goto(FIXTURE);
    await mount(page);
    const status = page.locator('.cp-status');
    await expect(status).toHaveAttribute('aria-live', 'polite');
    await expect(status).toHaveAttribute('role', 'status');
  });

  test('the textarea has a real label', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    const labelled = await page.evaluate(() => {
      const ta = document.querySelector('.cp-form__input');
      const label = document.querySelector(`label[for="${ta.id}"]`);
      return { hasLabel: !!label, describedBy: ta.getAttribute('aria-describedby') };
    });
    expect(labelled.hasLabel).toBe(true);
    expect(labelled.describedBy).toBeTruthy();
  });

  test('spoilers are operable by keyboard', async ({ page }) => {
    await mockApi(page, {
      body: {
        ...PAGE,
        items: [
          comment('c1', {
            body_html:
              '<span class="cp-spoiler" data-cp-spoiler="1" tabindex="0" role="button" ' +
              'aria-expanded="false"><span class="cp-spoiler__body">концовка</span></span>'
          })
        ]
      }
    });
    await page.goto(FIXTURE);
    await mount(page);
    const spoiler = page.locator('[data-cp-spoiler]');
    await spoiler.focus();
    await page.keyboard.press('Enter');
    await expect(spoiler).toHaveAttribute('aria-expanded', 'true');
  });

  test('reduced motion is respected', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    const durations = await page.evaluate(() =>
      Array.from(document.querySelectorAll('.cp-widget *')).map(
        (el) => getComputedStyle(el).transitionDuration
      )
    );
    for (const d of durations) {
      expect(parseFloat(d)).toBeLessThan(0.01);
    }
  });
});

test.describe('layout stability', () => {
  test('loading comments does not shift the page', async ({ page }) => {
    await mockApi(page, { delayMs: 300 });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(FIXTURE);

    await page.evaluate(() => {
      window.__cls = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) window.__cls += entry.value;
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });

    await mount(page);
    await page.locator('.cp-comment').first().waitFor();
    await page.waitForTimeout(400);

    const cls = await page.evaluate(() => window.__cls);
    // 0.1 is the "good" threshold; the widget's own contribution should be a
    // fraction of that since it reserves its rows before filling them.
    expect(cls).toBeLessThan(0.1);
  });
});

test.describe('style isolation', () => {
  test('the widget does not restyle the host page', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);

    const before = await page.evaluate(() => {
      const h1 = getComputedStyle(document.querySelector('h1'));
      const body = getComputedStyle(document.body);
      return { h1: h1.fontSize + '|' + h1.color, body: body.margin + '|' + body.fontFamily };
    });
    await mount(page);
    const after = await page.evaluate(() => {
      const h1 = getComputedStyle(document.querySelector('h1'));
      const body = getComputedStyle(document.body);
      return { h1: h1.fontSize + '|' + h1.color, body: body.margin + '|' + body.fontFamily };
    });
    expect(after).toEqual(before);
  });

  test('the stylesheet contains no global selectors', () => {
    // Strip comments first. The prose in this stylesheet explains that it
    // carries no `!important` and no global selectors, and a naive scan of the
    // raw file flags that explanation as the very thing it denies.
    const css = fs.readFileSync(WIDGET_CSS, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    const rules = css
      .split('}')
      .map((block) => block.split('{')[0].trim())
      .filter((selector) => selector && !selector.startsWith('@') && !selector.startsWith('/*'));

    // Exactly one selector may target something the widget did not create:
    // the mount point, which reserves height before any JavaScript runs. It is
    // named here rather than pattern-matched, so a second such rule appearing
    // later fails this test instead of slipping in under a loosened regex.
    const ALLOWED_HOST_SELECTORS = ['[data-cp-comments]'];

    const global = rules.filter((selector) =>
      selector
        .split(',')
        .map((s) => s.trim())
        .some(
          (s) =>
            s &&
            !s.startsWith('.cp-') &&
            !ALLOWED_HOST_SELECTORS.includes(s)
        )
    );
    expect(global, `global selectors: ${global.join(' | ')}`).toEqual([]);
    expect(css).not.toContain('!important');
  });
});

test.describe('telemetry carries no content', () => {
  test('events contain no comment text, ids or tokens', async ({ page }) => {
    await mockApi(page);
    await page.goto(FIXTURE);
    await mount(page);
    await page.waitForTimeout(200);
    const events = await page.evaluate(() => window.__events);
    expect(events.length).toBeGreaterThan(0);
    const flat = JSON.stringify(events);
    expect(flat).not.toContain('Комментарий');
    expect(flat).not.toContain('g_c1');
    expect(flat).not.toContain('test-csrf');
    for (const event of events) {
      for (const key of Object.keys(event)) {
        expect(
          ['event', 'version', 'phase', 'ms', 'count', 'status', 'code', 'sort', 'instance']
        ).toContain(key);
      }
    }
  });
});

test.describe('external links', () => {
  test('links in a comment body carry ugc nofollow', async ({ page }) => {
    await mockApi(page, {
      body: {
        ...PAGE,
        items: [
          comment('c1', {
            body_html:
              '<a href="https://example.test/x" rel="ugc nofollow noopener noreferrer" ' +
              'target="_blank">пример</a>'
          })
        ]
      }
    });
    await page.goto(FIXTURE);
    await mount(page);
    const rel = await page.locator('.cp-comment__body a').getAttribute('rel');
    expect(rel).toContain('ugc');
    expect(rel).toContain('nofollow');
    expect(rel).toContain('noopener');
  });
});
