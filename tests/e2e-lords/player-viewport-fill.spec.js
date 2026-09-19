/**
 * P0: Lords player iframe must fill the 16:9 media viewport.
 * Uses a mock <video-player> that injects a fixed 640×360 iframe (SDK habit);
 * production client script must stretch it to 100%×100% of `.pl__frame`.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const SRC = path.join(ROOT, 'automation/host/lords-frontend.py');

function extract(py, startMarker, endMarker) {
  const i = py.indexOf(startMarker);
  if (i < 0) throw new Error(`missing ${startMarker}`);
  const j = py.indexOf(endMarker, i + startMarker.length);
  if (j < 0) throw new Error(`missing end ${endMarker}`);
  return py.slice(i, j);
}

function buildPage(viewportCss, clientScript) {
  return `<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
html,body{margin:0;overflow-x:clip;max-width:100%;font-family:sans-serif}
img,video,iframe,svg{max-width:100%;height:auto;display:block}
.wrap{max-width:1100px;margin:0 auto;padding:12px}
.pl{margin:14px 0}
.pl__bar{display:flex;gap:8px;flex-wrap:wrap;background:#1a1f26;color:#ccc;padding:8px}
.pl__note{margin-left:auto}
${viewportCss}
</style></head><body><div class="wrap">
<section class="pl">
  <div class="pl__bar"><span class="pl__tab" aria-current="true">Смотреть</span>
    <span class="pl__note">Загрузка плеера…</span></div>
  <div class="pl__frame" data-player data-player-layout-contract="full-bleed-v1" data-state="resolving">
    <div data-player-host data-src-candidates='[{"aggregator":"cvh","id":"demo"}]'>
      <video-player ident="demo" season="1" episode="1"
        data-publisher-id="1" data-title-id="demo" data-aggregator="cvh"></video-player>
    </div>
    <div class="pl__state" data-player-state hidden></div>
  </div>
</section>
</div>
<script>
customElements.define('video-player', class extends HTMLElement {
  connectedCallback(){
    const root = this.attachShadow({mode:'open'});
    const box = document.createElement('div');
    box.style.cssText = 'position:relative;width:640px;height:360px;margin:0 auto;background:#000';
    const iframe = document.createElement('iframe');
    iframe.setAttribute('width','640');
    iframe.setAttribute('height','360');
    iframe.style.cssText = 'width:640px;height:360px;border:0;display:block';
    iframe.srcdoc = '<body style="margin:0;background:#111;color:#fff;display:grid;place-items:center;height:100vh;font:14px sans-serif">preview</body>';
    box.appendChild(iframe);
    root.appendChild(box);
    // Simulate late SDK resize back to fixed size.
    setTimeout(() => {
      iframe.setAttribute('width','640');
      iframe.setAttribute('height','360');
      iframe.style.width = '640px';
      iframe.style.height = '360px';
    }, 200);
  }
});
</script>
<script>${clientScript}</script>
</body></html>`;
}

function loadAssets() {
  const py = fs.readFileSync(SRC, 'utf8');
  const css = extract(
    py,
    '/* Плеер: полоса вкладок',
    '/* Сезоны и серии.',
  );
  const start = 'СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """';
  const i = py.indexOf(start);
  if (i < 0) throw new Error('client script missing');
  const from = i + start.length;
  const j = py.indexOf('"""', from);
  if (j < 0) throw new Error('client script end missing');
  return { css, script: py.slice(from, j) };
}

async function measure(page) {
  return page.evaluate(() => {
    const shell = document.querySelector('[data-player]');
    const host = document.querySelector('[data-player-host]');
    const vp = document.querySelector('video-player');
    const note = document.querySelector('.pl__note');
    const iframe = vp && vp.shadowRoot && vp.shadowRoot.querySelector('iframe');
    const sr = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { width: r.width, height: r.height, top: r.top, left: r.left };
    };
    const shellR = sr(shell);
    const iframeR = sr(iframe);
    const hostR = sr(host);
    const wFill = iframeR && shellR ? iframeR.width / Math.max(shellR.width, 1) : 0;
    const hFill = iframeR && shellR ? iframeR.height / Math.max(shellR.height, 1) : 0;
    const pageOverflow = Math.max(0, document.documentElement.scrollWidth - window.innerWidth);
    const playerOverflow = shell
      ? Math.max(0, shell.scrollWidth - shell.clientWidth)
      : 0;
    const centered =
      iframeR && shellR
        ? iframeR.width < shellR.width * 0.9 &&
          Math.abs(iframeR.left + iframeR.width / 2 - (shellR.left + shellR.width / 2)) < 40
        : false;
    return {
      shell_rect: shellR,
      host_rect: hostR,
      iframe_rect: iframeR,
      width_fill_ratio: wFill,
      height_fill_ratio: hFill,
      aspect_ratio: shellR ? shellR.width / Math.max(shellR.height, 1) : 0,
      player_instance_count: document.querySelectorAll('video-player').length,
      state: shell ? shell.getAttribute('data-state') : null,
      note: note ? note.textContent : null,
      visible_unknown: !!(note && /состояние неизвестно/i.test(note.textContent || '')),
      page_horizontal_overflow_px: pageOverflow,
      player_horizontal_overflow_px: playerOverflow,
      small_centered_player: centered && wFill < 0.98 ? 1 : 0,
    };
  });
}

const VIEWPORTS = [
  { name: '1440', width: 1440, height: 900 },
  { name: '768', width: 768, height: 1024 },
  { name: '390', width: 390, height: 844 },
];

test.describe('lords player viewport fill', () => {
  for (const vp of VIEWPORTS) {
    test(`fill gate @${vp.name}`, async ({ page }, testInfo) => {
      const { css, script } = loadAssets();
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.setContent(buildPage(css, script), { waitUntil: 'domcontentloaded' });
      // Wait past mock SDK late resize + client interval.
      await page.waitForTimeout(800);
      await page.waitForFunction(() => {
        const f = document.querySelector('[data-player]');
        return f && (f.getAttribute('data-state') === 'active'
          || f.getAttribute('data-state') === 'ok'
          || f.getAttribute('data-state') === 'resolving');
      });
      const m = await measure(page);
      expect(m.player_instance_count, JSON.stringify(m)).toBeLessThanOrEqual(1);
      expect(m.visible_unknown, JSON.stringify(m)).toBeFalsy();
      expect(m.page_horizontal_overflow_px, JSON.stringify(m)).toBe(0);
      expect(m.player_horizontal_overflow_px, JSON.stringify(m)).toBe(0);
      expect(m.small_centered_player, JSON.stringify(m)).toBe(0);
      expect(m.width_fill_ratio, JSON.stringify(m)).toBeGreaterThanOrEqual(0.98);
      expect(m.height_fill_ratio, JSON.stringify(m)).toBeGreaterThanOrEqual(0.98);
      expect(m.aspect_ratio).toBeGreaterThan(1.6);
      expect(m.aspect_ratio).toBeLessThan(1.9);
      expect(m.note || '').not.toMatch(/состояние неизвестно/i);
      const shotDir = path.join(
        ROOT,
        'artifacts/evidence/lords-default-episode-2026-09-19/PLAYER_VIEWPORT',
      );
      fs.mkdirSync(shotDir, { recursive: true });
      await page.locator('.pl').screenshot({
        path: path.join(shotDir, `lords-player-fixed-${vp.name}.png`),
      });
      testInfo.attachments.push({
        name: `measure-${vp.name}`,
        contentType: 'application/json',
        body: Buffer.from(JSON.stringify(m, null, 2)),
      });
    });
  }

  test('survives late SDK resize regression', async ({ page }) => {
    const { css, script } = loadAssets();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.setContent(buildPage(css, script), { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    const before = await measure(page);
    // Force another SDK-like shrink.
    await page.evaluate(() => {
      const vp = document.querySelector('video-player');
      const iframe = vp.shadowRoot.querySelector('iframe');
      iframe.setAttribute('width', '480');
      iframe.setAttribute('height', '270');
      iframe.style.width = '480px';
      iframe.style.height = '270px';
    });
    await page.waitForTimeout(600);
    const after = await measure(page);
    expect(after.width_fill_ratio).toBeGreaterThanOrEqual(0.98);
    expect(after.height_fill_ratio).toBeGreaterThanOrEqual(0.98);
    expect(after.small_centered_player).toBe(0);
    expect(before.player_instance_count).toBe(1);
    expect(after.player_instance_count).toBe(1);
  });

  test('resize desktop → mobile → desktop keeps fill', async ({ page }) => {
    const { css, script } = loadAssets();
    await page.setContent(buildPage(css, script), { waitUntil: 'domcontentloaded' });
    for (const size of [
      { width: 1440, height: 900 },
      { width: 390, height: 844 },
      { width: 1440, height: 900 },
    ]) {
      await page.setViewportSize(size);
      await page.waitForTimeout(500);
      const m = await measure(page);
      expect(m.width_fill_ratio, JSON.stringify({ size, m })).toBeGreaterThanOrEqual(0.98);
      expect(m.height_fill_ratio, JSON.stringify({ size, m })).toBeGreaterThanOrEqual(0.98);
      expect(m.page_horizontal_overflow_px).toBe(0);
    }
  });
});
