// Проверка самой оснастки приёмки — без сети, сервера и запросов наружу.
//
// Набор приёмки без адресов пропускается целиком, и в таком виде он ничего о
// себе не доказывает. Объявить готовой оснастку, которая ни разу не работала,
// значит утверждать проверку, которая не запускалась.
//
// Поэтому здесь ответы перехватываются и подставляются: браузер настоящий,
// страница настоящая, наружу не уходит ни один запрос.

const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const h = require('./harness');

const БАЗА = 'https://приёмка.invalid/';

/** Подставляет страницу вместо ответа сети. `.invalid` не существует по RFC 2606. */
async function serve(page, body, status = 200) {
  await page.route(`${БАЗА}**`, (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    return route.fulfill({ status, contentType: 'text/html; charset=utf-8', body });
  });
}

test.describe('оснастка приёмки', () => {
  test('изменяющий запрос обрывается, а не отправляется', async ({ page }) => {
    const attempts = [];
    await h.readOnly(page, attempts);
    await serve(page, `<!doctype html><meta charset="utf-8"><title>т</title>
      <body><form id="f" method="post" action="/отправить"><button>ок</button></form>
      <script>
        // Страница действующего сайта вправе отправить что угодно; приёмка
        // обязана этого не допустить независимо от её содержимого.
        fetch('/счётчик', {method: 'POST', body: 'x'}).catch(() => {});
      </script></body>`);
    await page.goto(БАЗА, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    expect(attempts.length, 'попытка изменения замечена').toBeGreaterThan(0);
    expect(attempts.every((a) => h.МУТИРУЮЩИЕ.has(a.method))).toBe(true);
  });

  test('чтение не обрывается', async ({ page }) => {
    const attempts = [];
    await h.readOnly(page, attempts);
    await serve(page, '<!doctype html><meta charset="utf-8"><title>т</title><body>текст');
    const response = await page.goto(БАЗА, { waitUntil: 'domcontentloaded' });
    expect(response.status()).toBe(200);
    expect(attempts).toEqual([]);
  });

  test('отказ доступа отличается от дефекта витрины', async () => {
    expect(h.classify(403)).toBe('BLOCKED_ACCESS');
    expect(h.classify(429)).toBe('BLOCKED_ACCESS');
    expect(h.classify(401)).toBe('BLOCKED_ACCESS');
    expect(h.classify(500)).toBe('FAILED');
    expect(h.classify(404)).toBe('FAILED');
    expect(h.classify(200)).toBe('OK');
  });

  test('выход за окно измеряется, а не предполагается', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await serve(page, `<!doctype html><meta charset="utf-8"><title>т</title>
      <body style="margin:0"><div style="width:900px;height:10px"></div>`);
    await page.goto(БАЗА, { waitUntil: 'domcontentloaded' });
    expect(await h.overflowPx(page), 'широкий блок обязан быть замечен').toBeGreaterThan(0);
  });

  test('вписавшаяся страница выхода за окно не даёт', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await serve(page, `<!doctype html><meta charset="utf-8"><title>т</title>
      <body style="margin:0"><div style="width:100%;height:10px"></div>`);
    await page.goto(БАЗА, { waitUntil: 'domcontentloaded' });
    expect(await h.overflowPx(page)).toBeLessThanOrEqual(0);
  });

  test('запись свидетельств сливает, а не затирает чужое', async () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'приёмка-')), 'evidence.json');
    h.record(file, 'zona-cinema', '/@390', { status: 200 });
    h.record(file, 'zona-cinema', '/catalog/@390', { status: 200 });
    const all = h.record(file, 'animedia-portal', '/@768', { status: 200 });
    expect(Object.keys(all).sort()).toEqual(['animedia-portal', 'zona-cinema']);
    expect(Object.keys(all['zona-cinema']).sort()).toEqual(['/@390', '/catalog/@390']);
  });

  test('адреса продуктов читаются из настроек и не выдумываются', () => {
    const config = h.loadConfig(path.join(__dirname, '..', '..', 'config',
                                          'live-acceptance.json'));
    expect(Object.keys(config).sort())
      .toEqual(['animedia-portal', 'basis-video', 'yummy', 'zona-cinema']);
    for (const [name, entry] of Object.entries(config)) {
      expect(entry.base_url === null || entry.base_url.startsWith('https://'),
             `${name}: адрес либо не передан, либо является настоящим https-адресом`).toBe(true);
    }
  });
});
