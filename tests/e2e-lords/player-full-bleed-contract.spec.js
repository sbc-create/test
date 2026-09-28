/**
 * Release-blocking viewport gate for Lords full-bleed player contract.
 * Simulates SDK 640×360 insert → async replacement under global iframe{height:auto}.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const SRC = path.join(ROOT, 'automation/host/lords-frontend.py');
const CONTRACT = 'full-bleed-v1';

function loadAssets() {
  const py = fs.readFileSync(SRC, 'utf8');
  const css = py.slice(
    py.indexOf('/* Плеер: полоса вкладок'),
    py.indexOf('/* Сезоны и серии.'),
  );
  const start = 'СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """';
  const i = py.indexOf(start);
  const script = py.slice(i + start.length, py.indexOf('"""', i + start.length));
  if (!py.includes(`data-player-layout-contract="${CONTRACT}"`)) {
    throw new Error('contract marker missing from source');
  }
  return { css, script };
}

function buildPage(css, script, { replaceAsync = true } = {}) {
  return `<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}html,body{margin:0;overflow-x:clip}
img,video,iframe,svg{max-width:100%;height:auto;display:block}
.wrap{max-width:1100px;margin:0 auto;padding:12px}
.pl{margin:14px 0}
.pl__bar{display:flex;background:#111;color:#ccc;padding:8px}
${css}
</style></head><body><div class=wrap>
<section class=pl>
<div class="pl__frame" data-player data-player-layout-contract="${CONTRACT}" data-state="resolving">
  <div data-player-host data-src-candidates='[{"aggregator":"cvh","id":"demo"}]'>
    <video-player ident="demo" season="1" episode="1"
      data-publisher-id="1" data-title-id="demo" data-aggregator="cvh"></video-player>
  </div>
  <div data-player-state hidden></div>
</div>
</section></div>
<script>
customElements.define('video-player', class extends HTMLElement {
  connectedCallback(){
    const root = this.attachShadow({mode:'open'});
    const wrap = document.createElement('div');
    wrap.style.cssText = 'width:640px;height:360px;margin:0 auto;background:#000;display:flex;align-items:center;justify-content:center';
    const iframe = document.createElement('iframe');
    iframe.setAttribute('width','640');
    iframe.setAttribute('height','360');
    iframe.style.cssText = 'width:640px;height:360px;border:0;display:block';
    iframe.srcdoc = '<body style="margin:0;background:#222;color:#fff;display:grid;place-items:center;height:100vh">v1</body>';
    wrap.appendChild(iframe);
    root.appendChild(wrap);
    ${replaceAsync ? `
    setTimeout(() => {
      const wrap2 = document.createElement('div');
      wrap2.style.cssText = 'width:640px;height:360px;margin:40px auto;background:#100';
      const iframe2 = document.createElement('iframe');
      iframe2.setAttribute('width','640');
      iframe2.setAttribute('height','360');
      iframe2.style.cssText = 'width:640px;height:360px;border:0';
      iframe2.srcdoc = '<body style="margin:0;background:#333;color:#fff;display:grid;place-items:center;height:100vh">v2</body>';
      wrap2.appendChild(iframe2);
      root.innerHTML = '';
      root.appendChild(wrap2);
    }, 250);
    ` : ''}
  }
});
</script>
<script>${script}</script>
</body></html>`;
}

async function measure(page) {
  return page.evaluate(() => {
    const shell = document.querySelector('[data-player]');
    const vp = document.querySelector('video-player');
    const iframe = vp && vp.shadowRoot && vp.shadowRoot.querySelector('iframe');
    const sr = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { width: r.width, height: r.height };
    };
    const shellR = sr(shell);
    const iframeR = sr(iframe);
    const w = iframeR && shellR ? iframeR.width / Math.max(shellR.width, 1) : 0;
    const h = iframeR && shellR ? iframeR.height / Math.max(shellR.height, 1) : 0;
    return {
      contract: shell && shell.getAttribute('data-player-layout-contract'),
      shell: shellR,
      iframe: iframeR,
      width_fill_ratio: w,
      height_fill_ratio: h,
      aspect: shellR ? shellR.width / Math.max(shellR.height, 1) : 0,
      instances: document.querySelectorAll('video-player').length,
      page_overflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
      player_overflow: shell ? Math.max(0, shell.scrollWidth - shell.clientWidth) : 0,
      small: w < 0.9 || h < 0.9 ? 1 : 0,
    };
  });
}

const VIEWPORTS = [
  { name: '1440', width: 1440, height: 900 },
  { name: '768', width: 768, height: 1024 },
  { name: '390', width: 390, height: 844 },
];

test.describe('full-bleed player contract', () => {
  for (const vp of VIEWPORTS) {
    test(`async SDK replacement @${vp.name}`, async ({ page }) => {
      const { css, script } = loadAssets();
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.setContent(buildPage(css, script, { replaceAsync: true }), {
        waitUntil: 'domcontentloaded',
      });
      await page.waitForTimeout(200);
      const early = await measure(page);
      expect(early.contract).toBe(CONTRACT);
      expect(early.instances).toBe(1);
      expect(early.width_fill_ratio).toBeGreaterThanOrEqual(0.98);
      expect(early.height_fill_ratio).toBeGreaterThanOrEqual(0.98);
      await page.waitForTimeout(500); // past async replacement
      const late = await measure(page);
      expect(late.instances).toBe(1);
      expect(late.small, JSON.stringify(late)).toBe(0);
      expect(late.width_fill_ratio, JSON.stringify(late)).toBeGreaterThanOrEqual(0.98);
      expect(late.height_fill_ratio, JSON.stringify(late)).toBeGreaterThanOrEqual(0.98);
      expect(late.aspect).toBeGreaterThan(1.6);
      expect(late.aspect).toBeLessThan(1.9);
      expect(late.page_overflow).toBe(0);
      expect(late.player_overflow).toBe(0);
    });
  }

  test('resize after replacement keeps fill', async ({ page }) => {
    const { css, script } = loadAssets();
    await page.setContent(buildPage(css, script, { replaceAsync: true }));
    await page.waitForTimeout(600);
    for (const size of [
      { width: 1440, height: 900 },
      { width: 390, height: 844 },
      { width: 1440, height: 900 },
    ]) {
      await page.setViewportSize(size);
      await page.waitForTimeout(400);
      const m = await measure(page);
      expect(m.width_fill_ratio, JSON.stringify({ size, m })).toBeGreaterThanOrEqual(0.98);
      expect(m.height_fill_ratio, JSON.stringify({ size, m })).toBeGreaterThanOrEqual(0.98);
      expect(m.small).toBe(0);
      expect(m.instances).toBe(1);
    }
  });
});
