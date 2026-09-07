// REQ-LORDS-REFLOW: критерии AA, которые axe не проверяет и проверить не может.
//
// Прогон axe закрыл 25–29 правил и ноль нарушений, но это не весь уровень AA.
// Два критерия проверяются только изменением условий просмотра, а не разбором
// дерева доступности:
//
//   * **1.4.10 Reflow (AA)** — содержимое читается без горизонтальной прокрутки
//     при ширине, эквивалентной 320 CSS-px, и при увеличении до 400 %;
//   * **1.4.12 Text Spacing (AA)** — текст переживает увеличенные интервалы
//     между строками, словами и буквами без потери содержимого.
//
// Заявлять соответствие AA, не проверив их, значит завышать вывод: axe о них
// молчит, и молчание легко принять за успех. Здесь они измеряются.
//
// Сюда же собраны проверки, которые не про доступность, но про ту же природу
// «увидит только браузер»: сплошной проход ширин, поведение при выключенной
// анимации и чистота консоли.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const ROUTES = [
  ['home', '/'],
  ['catalog', '/catalog/'],
  ['search', '/search/'],
  ['not-found', '/nonexistent-address/'],
];

// Сплошной проход, а не три контрольные точки. Излом раскладки живёт между
// ними: сетка ломается на 610 px, а на 390 и 768 всё в порядке.
const SWEEP = [320, 360, 390, 414, 480, 560, 640, 720, 768, 900, 1024, 1180, 1280, 1440, 1600, 1920];

const evidence = { captured_at_utc: null, sweep: [], reflow: [], textSpacing: [], zoom200: [], console: [] };

// Свидетельство собирается по разделам, а не перезаписью файла целиком.
// Первая версия писала весь объект, и результат зависел от того, какой блок
// завершился последним: сплошной проход ширин исчезал из файла, хотя был
// выполнен, и отчёт выглядел так, будто проверку не запускали.
//
// Раздел, в который этот прогон что-то положил, заменяется целиком — он
// принадлежит одному блоку тестов. Раздел, к которому прогон не притрагивался,
// остаётся прежним. Слияния строк нет намеренно: оно оставило бы записи
// прошлого прогона рядом с новыми и выдало бы устаревший замер за свежий.
const FILE = path.join(OUT, 'responsive.json');

function save() {
  let stored = {};
  try { stored = JSON.parse(fs.readFileSync(FILE, 'utf8')); } catch { /* первого файла ещё нет */ }
  const merged = { ...stored, captured_at_utc: new Date().toISOString() };
  for (const key of ['sweep', 'reflow', 'textSpacing', 'zoom200', 'console']) {
    if (evidence[key].length) { merged[key] = evidence[key]; }
    else if (!merged[key]) { merged[key] = []; }
  }
  fs.writeFileSync(FILE, `${JSON.stringify(merged, null, 2)}\n`);
}

/** Горизонтальная прокрутка документа и самый широкий виновник, если она есть. */
const overflow = () => {
  const doc = document.documentElement;
  const limit = doc.clientWidth;
  if (doc.scrollWidth <= limit + 1) { return { overflows: false, scrollWidth: doc.scrollWidth, limit }; }
  let worst = null;
  for (const el of document.querySelectorAll('body *')) {
    const rect = el.getBoundingClientRect();
    const right = rect.left + rect.width + window.scrollX;
    if (right > limit + 1 && (!worst || right > worst.right)) {
      worst = {
        right: Math.round(right),
        tag: el.tagName.toLowerCase(),
        cls: el.getAttribute('class') || '',
      };
    }
  }
  return { overflows: true, scrollWidth: doc.scrollWidth, limit, worst };
};

test.describe('1.4.10 Reflow и сплошной проход ширин', () => {
  for (const site of Object.keys(SITES)) {
    test(`${site}: ни одна ширина от 320 до 1920 не даёт горизонтальной прокрутки`, async ({ page }) => {
      const failures = [];
      for (const width of SWEEP) {
        await page.setViewportSize({ width, height: 900 });
        for (const [name, route] of ROUTES) {
          await page.goto(url(site, route));
          const result = await page.evaluate(overflow);
          evidence.sweep.push({ site, route: name, width, ...result });
          if (result.overflows) { failures.push(`${name}@${width}: ${JSON.stringify(result.worst)}`); }
        }
      }
      save();
      expect(failures, `горизонтальная прокрутка: ${failures.join('; ')}`).toEqual([]);
    });
  }

  test('увеличение до 400 % не ломает чтение (1.4.10)', async ({ page }) => {
    // Увеличение моделируется шириной окна, а не свойством `zoom`, и это не
    // упрощение, а единственная верная модель. Замерено на этом же стенде:
    //
    //   1280 px + style.zoom = 400%  ->  clientWidth 1280, (max-width:767px) = false
    //   ширина окна 320 px           ->  clientWidth  320, (max-width:767px) = true
    //
    // `zoom` увеличивает отрисовку, но оставляет CSS-viewport прежним, поэтому
    // медиазапросы продолжают отвечать по-настольному. Получается раскладка,
    // которой в браузере не бывает: настольная сетка, нарисованная вчетверо
    // крупнее внутри окна 1280 px. Первая версия этой проверки именно так и
    // «нашла» переполнение пагинации на 4257 px — дефекта не было, была
    // неверная модель.
    //
    // Настоящее увеличение до 400 % в окне 1280 px даёт 320 CSS-px, и критерий
    // 1.4.10 формулируется ровно через эту величину.
    const failures = [];
    const ZOOMED_WIDTH = Math.round(1280 / 4);
    for (const [name, route] of ROUTES) {
      await page.setViewportSize({ width: ZOOMED_WIDTH, height: 1024 });
      await page.goto(url('lords-01', route));
      const result = await page.evaluate(overflow);
      const mode = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        mobileMediaQuery: matchMedia('(max-width: 767px)').matches,
      }));
      evidence.reflow.push({
        site: 'lords-01', route: name, zoom: '400% (эквивалент 320 CSS-px)',
        ...result, ...mode,
      });
      if (result.overflows) { failures.push(`${name}: ${JSON.stringify(result.worst)}`); }
      expect(mode.mobileMediaQuery, `${name}: при 400 % не включилась мобильная раскладка`)
        .toBe(true);
    }
    save();
    expect(failures, `при 400 % появилась прокрутка: ${failures.join('; ')}`).toEqual([]);
  });
});

test.describe('1.4.12 Text Spacing', () => {
  test('увеличение текста до 200 % не съедает названия (1.4.4)', async ({ page }) => {
    // 1.4.4 отличается от 1.4.10: там масштабируется страница целиком и
    // спасает узкая раскладка, здесь растёт только шрифт при прежней ширине.
    // Ломается это иначе — не прокруткой, а обрезкой: содержимое, помещавшееся
    // в отведённые строки, перестаёт помещаться и пропадает. Критерий требует,
    // чтобы при увеличении до 200 % не терялись ни содержимое, ни возможность
    // им пользоваться, поэтому проверяется именно обрезка.
    await page.setViewportSize({ width: 1280, height: 900 });
    const failures = [];
    for (const site of Object.keys(SITES)) {
      for (const [name, route] of ROUTES) {
        await page.goto(url(site, route));
        await page.addStyleTag({ content: 'html { font-size: 200% !important }' });
        // Перерасчёт раскладки ждём кадром, а не надеждой: измерение сразу
        // после вставки стиля читает прежние размеры и не видит обрезки.
        await page.evaluate(
          () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
        );
        const result = await page.evaluate(() => {
          const clipped = [];
          for (const el of document.querySelectorAll('body *')) {
            // `visually-hidden` обрезан намеренно и по назначению: он прячет
            // текст от глаза, оставляя его экранному диктору. Это не потеря.
            if (el.classList.contains('visually-hidden')) { continue; }
            const cs = getComputedStyle(el);
            if (cs.overflow !== 'hidden' && cs.overflowY !== 'hidden') { continue; }
            if (!el.clientHeight || !el.textContent.trim()) { continue; }
            if (el.scrollHeight > el.clientHeight + 2) {
              clipped.push({
                cls: el.getAttribute('class') || el.tagName.toLowerCase(),
                need: el.scrollHeight, have: el.clientHeight,
                text: el.textContent.trim().slice(0, 60),
              });
            }
          }
          const doc = document.documentElement;
          return { clipped, overflowX: doc.scrollWidth > doc.clientWidth + 1 };
        });
        evidence.zoom200.push({ site, route: name, clipped: result.clipped.length,
                                overflowX: result.overflowX, examples: result.clipped.slice(0, 4) });
        for (const c of result.clipped) {
          failures.push(`${site}${route}: .${c.cls} обрезано ${c.have}/${c.need} px — «${c.text}»`);
        }
        if (result.overflowX) { failures.push(`${site}${route}: горизонтальная прокрутка при 200 %`); }
      }
    }
    save();
    expect(failures, `потеря содержимого при 200 %:\n  ${failures.join('\n  ')}`).toEqual([]);
  });

  test('увеличенные интервалы не режут содержимое', async ({ page }) => {
    // Значения взяты из формулировки критерия, а не выбраны на глаз:
    // межстрочный 1.5×кегль, между абзацами 2×кегль, межбуквенный 0.12×,
    // межсловный 0.16×.
    const failures = [];
    for (const [name, route] of ROUTES) {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(url('lords-01', route));
      const before = await page.evaluate(() => document.body.scrollHeight);
      await page.addStyleTag({
        content: `* { line-height: 1.5em !important; letter-spacing: 0.12em !important;
                      word-spacing: 0.16em !important; }
                  p { margin-bottom: 2em !important; }`,
      });
      const after = await page.evaluate(() => {
        const doc = document.documentElement;
        // Обрезанный текст ищется прямо: элемент, у которого содержимое выше
        // рамки и прокрутка внутри запрещена, теряет часть текста навсегда.
        const clipped = [...document.querySelectorAll('p, h1, h2, h3, a, span, li')]
          .filter((el) => {
            const style = getComputedStyle(el);
            if (style.overflow === 'visible' || style.overflow === '') { return false; }
            // Спрятанное до фокуса обрезано намеренно: приём `visually-hidden`
            // в том и состоит, чтобы держать элемент в рамке 1×1. Считать это
            // потерей текста — значит объявлять дефектом работающий приём.
            if (el.closest('.visually-hidden') || el.classList.contains('visually-hidden')) {
              return false;
            }
            return el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2;
          })
          .slice(0, 5)
          .map((el) => `${el.tagName.toLowerCase()}.${el.getAttribute('class') || ''}`);
        return {
          height: document.body.scrollHeight,
          horizontal: doc.scrollWidth > doc.clientWidth + 1,
          clipped,
        };
      });
      evidence.textSpacing.push({ route: name, heightBefore: before, ...after });
      if (after.horizontal) { failures.push(`${name}: горизонтальная прокрутка`); }
      if (after.clipped.length) { failures.push(`${name}: обрезано ${after.clipped.join(', ')}`); }
    }
    save();
    expect(failures, failures.join('; ')).toEqual([]);
  });
});

test.describe('консоль и сеть чисты', () => {
  for (const site of Object.keys(SITES)) {
    test(`${site}: ни ошибок консоли, ни неудавшихся запросов`, async ({ page }) => {
      const problems = [];
      // Переход на несуществующий адрес входит в набор маршрутов намеренно, и
      // сообщение об его 404 — не ошибка страницы, а ожидаемый ответ сервера.
      // Учитывать его значило бы объявить дефектом собственную проверку.
      let expecting404 = false;
      page.on('console', (message) => {
        if (message.type() !== 'error') { return; }
        const text = message.text();
        if (expecting404 && text.includes('404')) { return; }
        problems.push(`console: ${text.slice(0, 160)}`);
      });
      page.on('pageerror', (error) => problems.push(`pageerror: ${String(error).slice(0, 160)}`));
      page.on('requestfailed', (request) => {
        problems.push(`requestfailed: ${request.url()} ${request.failure()?.errorText || ''}`);
      });
      page.on('response', (response) => {
        if (response.status() >= 400 && !response.url().includes('nonexistent')) {
          problems.push(`http ${response.status()}: ${response.url()}`);
        }
      });
      await page.setViewportSize({ width: 1440, height: 900 });
      for (const [name, route] of ROUTES) {
        expecting404 = name === 'not-found';
        await page.goto(url(site, route));
        await page.waitForLoadState('load');
      }
      expecting404 = false;
      evidence.console.push({ site, problems });
      save();
      expect(problems, problems.join('\n')).toEqual([]);
    });
  }
});

test.describe('prefers-reduced-motion', () => {
  test('при выключенной анимации карусель остаётся управляемой', async ({ browser }) => {
    // Выключенная анимация не должна выключать функцию: полка обязана
    // прокручиваться, просто без плавности.
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url('lords-02', '/'));
    const rail = page.locator('.rail').first();
    if (await rail.count()) {
      const before = await rail.evaluate((el) => el.scrollLeft);
      await rail.evaluate((el) => { el.scrollLeft = 300; });
      const after = await rail.evaluate((el) => el.scrollLeft);
      expect(after, 'полка не прокручивается при reduced motion').toBeGreaterThan(before);
    }
    await context.close();
  });
});
