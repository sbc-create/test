// REQ-LORDS-BUDGETS: вес, отзывчивость и кликабельность кадра плеера.
//
// Три разные вещи собраны здесь по одному признаку: каждую видно только в
// работающем браузере и ни одну не видно в разметке.
//
//   * **Бюджеты** — сколько страница весит и сколько запросов делает. Критерий
//     скорости в рубрике считает вес документа, но не вес того, что документ
//     за собой тянет.
//   * **INP** — задержка между действием зрителя и откликом. LCP говорит, когда
//     страница появилась; INP — слушается ли она после этого.
//   * **Кадр плеера** — виден, зарезервирован и по нему действительно попадают
//     указателем. Видимый, но перекрытый кадр — обычный способ сломать
//     просмотр, и внешне он неотличим от исправного.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });
const FILE = path.join(OUT, 'budgets.json');

// Бюджеты названы вместе с основанием. Это стенд на 62 записях, поэтому пороги
// поставлены с запасом к текущему замеру, но не «по текущему замеру»: сторож,
// подогнанный вплотную, срабатывает на шуме, а сторож без запаса не ловит
// ничего. Порог INP взят из Core Web Vitals и от размера стенда не зависит.
const BUDGET = {
  documentKb: 120,
  scriptKb: 60,
  styleKb: 60,
  imageKb: 400,
  requests: 60,
  domNodes: 3000,
  inpMs: 200,
};

const collected = { captured_at_utc: null, pages: [], inp: [], player: [] };

function save() {
  let stored = {};
  try { stored = JSON.parse(fs.readFileSync(FILE, 'utf8')); } catch { /* первого файла нет */ }
  const merged = { ...stored, captured_at_utc: new Date().toISOString(), budget: BUDGET };
  for (const key of ['pages', 'inp', 'player']) {
    if (collected[key].length) { merged[key] = collected[key]; }
    else if (!merged[key]) { merged[key] = []; }
  }
  fs.writeFileSync(FILE, `${JSON.stringify(merged, null, 2)}\n`);
}

test.describe('бюджеты веса и запросов', () => {
  for (const site of Object.keys(SITES)) {
    test(`${site}: главная и каталог укладываются в бюджет`, async ({ page }) => {
      const failures = [];
      for (const [name, route] of [['home', '/'], ['catalog', '/catalog/']]) {
        const seen = [];
        // Считается то, что реально пришло по сети, а не то, что объявлено в
        // разметке: препроцессор, шрифт и фоновая картинка в CSS в разметке не
        // видны, а вес добавляют.
        const onResponse = async (response) => {
          try {
            const body = await response.body();
            seen.push({
              url: response.url(),
              type: response.request().resourceType(),
              bytes: body.length,
            });
          } catch { /* тело недоступно — редирект или прерванный запрос */ }
        };
        page.on('response', onResponse);
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(url(site, route), { waitUntil: 'load' });
        await page.waitForLoadState('networkidle').catch(() => {});
        page.off('response', onResponse);

        const domNodes = await page.evaluate(() => document.getElementsByTagName('*').length);
        const kb = (types) => Math.round(
          seen.filter((r) => types.includes(r.type)).reduce((sum, r) => sum + r.bytes, 0) / 1024);
        const measured = {
          site,
          page: name,
          url: page.url(),
          requests: seen.length,
          documentKb: kb(['document']),
          scriptKb: kb(['script']),
          styleKb: kb(['stylesheet']),
          imageKb: kb(['image']),
          domNodes,
        };
        collected.pages.push(measured);

        for (const key of ['documentKb', 'scriptKb', 'styleKb', 'imageKb', 'requests', 'domNodes']) {
          if (measured[key] > BUDGET[key]) {
            failures.push(`${name}.${key}=${measured[key]} > ${BUDGET[key]}`);
          }
        }
      }
      save();
      expect(failures, failures.join('; ')).toEqual([]);
    });
  }
});

test.describe('INP: страница слушается после появления', () => {
  test('отклик на действия зрителя укладывается в 200 мс', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url('lords-01', '/catalog/'), { waitUntil: 'load' });

    // Наблюдатель ставится до действий: событие, случившееся раньше подписки,
    // в измерение не попадёт, и результат окажется занижен.
    await page.evaluate(() => {
      window.__interactions = [];
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.interactionId) {
            window.__interactions.push({ name: entry.name, duration: Math.round(entry.duration) });
          }
        }
      }).observe({ type: 'event', buffered: true, durationThreshold: 0 });
    });

    const value = await page.locator('#f-genre option').nth(1).getAttribute('value');
    await page.selectOption('#f-genre', value);
    await page.locator('.facets__reset').click();
    await page.locator('#f-sort').selectOption({ index: 1 });
    const toggle = page.locator('.nav-toggle');
    if (await toggle.isVisible()) { await toggle.click(); }
    await page.waitForTimeout(300);

    const interactions = await page.evaluate(() => window.__interactions.slice());

    // Наблюдатель обязан доказать, что он вообще срабатывает. Порог отчётности
    // Event Timing — 16 мс, и значения ниже спецификация до наблюдателя не
    // доводит: `durationThreshold: 0` молча поднимается до 16. Поэтому пустой
    // список означает не «наблюдатель сломан», а «ни одно взаимодействие не
    // достигло 16 мс» — то есть лучший исход. Отличить одно от другого можно
    // только заведомо медленным взаимодействием.
    // Кнопка ставится заведомо медленной, а нажимается настоящим вводом.
    // Программный `element.click()` здесь не годится: Event Timing считает
    // только доверенный ввод, и синтетическое нажатие не получает
    // `interactionId` вовсе. Первая версия самопроверки кликала из страницы и
    // потому «доказывала», что наблюдатель сломан, — сломана была проверка.
    await page.evaluate(() => {
      const button = document.createElement('button');
      button.id = 'inp-selfcheck';
      button.textContent = 'проверка наблюдателя';
      button.style.cssText = 'position:fixed;top:8px;left:8px;z-index:99999;';
      button.addEventListener('click', () => {
        const until = performance.now() + 120;
        while (performance.now() < until) { /* заведомо долгий обработчик */ }
      });
      document.body.append(button);
    });
    await page.locator('#inp-selfcheck').click();
    await page.waitForTimeout(300);
    const selfCheck = await page.evaluate(() => {
      const slow = window.__interactions.filter((i) => i.duration >= 100);
      document.getElementById('inp-selfcheck')?.remove();
      return { observed: slow.length > 0, worst: slow.reduce((m, i) => Math.max(m, i.duration), 0) };
    });
    expect(selfCheck.observed,
      'наблюдатель Event Timing не зафиксировал даже 120-миллисекундный обработчик')
      .toBe(true);

    // INP — не среднее, а практически худшее взаимодействие: зритель запоминает
    // задержку, а не её отсутствие в остальных случаях. Подсаженная проверка из
    // счёта исключается: она измеряет наблюдателя, а не страницу.
    const real = interactions;
    const worst = real.reduce((max, i) => Math.max(max, i.duration), 0);
    collected.inp.push({
      site: 'lords-01',
      route: '/catalog/',
      interactions: real.length,
      worstMs: worst,
      reporting_threshold_ms: 16,
      note: real.length
        ? 'зафиксированы взаимодействия выше порога отчётности'
        : 'ни одно взаимодействие не достигло порога 16 мс — INP ниже него',
      observer_selfcheck_ms: selfCheck.worst,
    });
    save();
    expect(worst, `худшее взаимодействие ${worst} мс`).toBeLessThanOrEqual(BUDGET.inpMs);
  });
});

test.describe('кадр плеера доступен указателю', () => {
  for (const site of Object.keys(SITES)) {
    for (const width of [390, 1440]) {
      test(`${site}@${width}: кадр виден, зарезервирован и кликабелен`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(url(site, '/movies/'));
        await page.locator('.card__title').first().click();

        const frame = page.locator('.player__frame');
        await expect(frame).toBeVisible();
        // Кадр подводится под видимую область до попадания. `elementFromPoint`
        // работает в координатах окна и возвращает null для точки за его
        // пределами: у высокого кадра центр оказывается ниже сгиба, и проверка
        // сообщала бы «перехвачен неизвестно чем» там, где перехвата нет.
        await frame.scrollIntoViewIfNeeded();
        const box = await frame.boundingBox();
        const ratio = box.width / box.height;

        // Кто на самом деле лежит в центре кадра. Перекрывающий слой — самый
        // частый способ сделать плеер видимым и неработающим, и увидеть его
        // можно только попаданием, а не разметкой.
        const hit = await page.evaluate(() => {
          const el = document.querySelector('.player__frame');
          const rect = el.getBoundingClientRect();
          // Берётся центр видимой части кадра, а не центр самого кадра: они
          // расходятся, как только кадр выше окна.
          const visibleTop = Math.max(rect.top, 0);
          const visibleBottom = Math.min(rect.bottom, window.innerHeight);
          const x = Math.round(rect.left + rect.width / 2);
          const y = Math.round((visibleTop + visibleBottom) / 2);
          const top = document.elementFromPoint(x, y);
          return {
            probePoint: { x, y },
            insideFrame: !!top && (el === top || el.contains(top)),
            topTag: top ? top.tagName.toLowerCase() : null,
            topClass: top ? (top.getAttribute('class') || '') : null,
            zIndex: getComputedStyle(el).zIndex,
          };
        });

        collected.player.push({
          site, viewport: width, url: page.url(),
          width: Math.round(box.width), height: Math.round(box.height),
          ratio: Math.round(ratio * 1000) / 1000, ...hit,
        });
        save();

        expect(ratio, `пропорция ${ratio.toFixed(3)} вместо 16/9`).toBeGreaterThan(1.5);
        expect(ratio, `пропорция ${ratio.toFixed(3)} вместо 16/9`).toBeLessThan(2.0);
        expect(hit.insideFrame,
          `центр кадра перехватывает ${hit.topTag}.${hit.topClass}`).toBe(true);
      });
    }
  }
});
