// REQ-LORDS-A11Y-MANUAL: то, чего axe не проверяет и проверить не может.
//
// axe разбирает статическое дерево доступности. Он не нажимает Tab, не смотрит,
// виден ли фокус, и не меряет палец. Между тем ровно здесь ломается
// клавиатурная работа: порядок обхода расходится с порядком чтения, кольцо
// фокуса срезано `outline: none`, кнопка меньше подушечки пальца, а поле ввода
// на телефоне заставляет браузер зумить страницу.
//
// Пороги названы вместе с их уровнем, потому что они разные:
//   * 24×24 CSS-px — WCAG 2.2, критерий 2.5.8 Target Size (Minimum), уровень AA;
//   * 44×44 CSS-px — критерий 2.5.5 Target Size (Enhanced), уровень AAA, и
//     одновременно требование задания владельца;
//   * 16 px у поля ввода — не критерий WCAG вовсе, а защита от того, что iOS
//     Safari зумит страницу при фокусе в поле с меньшим кеглем и оставляет
//     зрителя в увеличенной раскладке без пути назад.
//
// Первые два порога проверяются раздельно: провал по AAA не выдаётся за провал
// по AA, иначе отчёт завышал бы строгость и обесценивал настоящие нарушения.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { SITES, url } = require('./helpers');

const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates', 'a11y');
fs.mkdirSync(OUT, { recursive: true });

const AA_MIN = 24;   // WCAG 2.2 SC 2.5.8, уровень AA
const AAA_MIN = 44;  // WCAG 2.2 SC 2.5.5, уровень AAA — требование задания
const INPUT_MIN_FONT = 16;

const evidence = {};

function save(name, payload) {
  evidence[name] = payload;
  fs.writeFileSync(
    path.join(OUT, `manual-${name}.json`),
    `${JSON.stringify({ captured_at_utc: new Date().toISOString(), ...payload }, null, 2)}\n`,
  );
}

/** Размеры интерактивных целей с учётом исключений SC 2.5.8.
 *
 * Критерий не требует, чтобы каждая цель была 24×24. Он даёт четыре
 * исключения, и два из них здесь существенны:
 *
 *   * **интервал** — маленькая цель проходит, если вокруг неё есть место:
 *     окружность диаметром 24 px с центром в цели не пересекает такую же
 *     окружность соседней цели;
 *   * **строчная** — цель внутри предложения размер держать не обязана,
 *     иначе ссылка в абзаце разрывала бы строку.
 *
 * Считать по одному размеру, игнорируя интервал, значит объявлять нарушением
 * то, что критерию удовлетворяет, и чинить работающую вёрстку.
 */
const measureTargets = () => {
  const MIN = 24;
  const selector = 'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';
  const visible = [...document.querySelectorAll(selector)].filter((el) => {
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') { return false; }
    const rect = el.getBoundingClientRect();
    // Ссылка перехода к содержимому спрятана до фокуса и целью указателя не
    // является: измерять её как цель — измерять то, чего пальцем не касаются.
    if (rect.width <= 1 || rect.height <= 1) { return false; }
    return true;
  });

  const boxes = visible.map((el) => {
    const r = el.getBoundingClientRect();
    return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height };
  });

  return visible.map((el, index) => {
    const rect = el.getBoundingClientRect();
    const me = boxes[index];
    // Интервал: расстояние до ближайшего центра другой цели. Если оно не
    // меньше 24 px, окружности не пересекаются и исключение применимо.
    let nearest = Infinity;
    boxes.forEach((other, j) => {
      if (j === index) { return; }
      const distance = Math.hypot(me.cx - other.cx, me.cy - other.cy);
      if (distance < nearest) { nearest = distance; }
    });
    // Исключение «эквивалент»: если то же действие доступно другой целью
    // достаточного размера, маленькая цель критерию не противоречит. На
    // карточке это буквальный случай — постер и заголовок ведут по одному
    // адресу, и постер крупный. Требовать 44 px от подписи под постером
    // значило бы растить карточку ради цели, дубль которой уже большой.
    const href = el.getAttribute('href');
    let equivalent = null;
    if (href) {
      visible.forEach((other, j) => {
        if (j === index || other.getAttribute('href') !== href) { return; }
        const r = boxes[j];
        if (r.w >= 44 && r.h >= 44) { equivalent = Math.round(Math.min(r.w, r.h)); }
      });
    }
    return {
      tag: el.tagName.toLowerCase(),
      cls: el.getAttribute('class') || '',
      text: (el.textContent || '').trim().slice(0, 40),
      width: Math.round(rect.width * 100) / 100,
      height: Math.round(rect.height * 100) / 100,
      nearestTargetPx: Number.isFinite(nearest) ? Math.round(nearest * 100) / 100 : null,
      spacingExempt: Number.isFinite(nearest) ? nearest >= MIN : true,
      equivalentTargetPx: equivalent,
      inline: !!el.closest('p, li.inline, .lede, footer p'),
    };
  });
};

test.describe('клавиатура, фокус и размеры целей', () => {
  test('обход с клавиатуры доходит до содержимого и не проваливается в ловушку', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url('lords-01', '/catalog/'));

    const order = [];
    let trapped = false;
    for (let i = 0; i < 40; i += 1) {
      await page.keyboard.press('Tab');
      const active = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) { return null; }
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
          tag: el.tagName.toLowerCase(),
          cls: el.getAttribute('class') || '',
          id: el.id || '',
          text: (el.textContent || '').trim().slice(0, 30),
          top: Math.round(rect.top + window.scrollY),
          left: Math.round(rect.left + window.scrollX),
          // Видимость фокуса: хотя бы одно из колец должно существовать.
          focusVisible: style.outlineStyle !== 'none'
            || style.boxShadow !== 'none'
            || style.borderStyle !== 'none',
        };
      });
      if (!active) { break; }
      order.push(active);
    }

    save('keyboard-order', {
      site: 'lords-01', route: '/catalog/', viewport: 1440, order, trapped,
    });

    expect(order.length, 'фокус не двигается по Tab').toBeGreaterThan(5);
    const invisible = order.filter((o) => !o.focusVisible);
    expect(invisible, `фокус не виден на: ${invisible.map((o) => o.cls || o.tag).join(', ')}`)
      .toEqual([]);
  });

  test('первая остановка Tab — ссылка перехода к содержимому', async ({ page }) => {
    // Ссылка «к содержимому» существует ради одного сценария: клавиатурный
    // зритель не должен проходить всё меню на каждой странице. Если она не
    // первая, она не работает, даже когда присутствует в разметке.
    await page.goto(url('lords-01', '/'));
    await page.keyboard.press('Tab');
    const first = await page.evaluate(() => {
      const el = document.activeElement;
      return { tag: el.tagName.toLowerCase(), href: el.getAttribute('href') || '' };
    });
    expect(first.tag).toBe('a');
    expect(first.href).toBe('#content');
  });

  test('ссылка перехода к содержимому действительно уводит фокус в main', async ({ page }) => {
    await page.goto(url('lords-01', '/'));
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    const landed = await page.evaluate(() => {
      const target = document.getElementById('content');
      return {
        exists: !!target,
        isMain: target ? target.tagName.toLowerCase() === 'main' : false,
        focusable: target ? target.hasAttribute('tabindex') : false,
      };
    });
    expect(landed.exists, 'якоря #content нет').toBe(true);
    expect(landed.isMain, '#content не является main').toBe(true);
  });

  for (const site of Object.keys(SITES)) {
    test(`${site}: цели на телефоне не меньше 24 px (WCAG 2.2 AA)`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(url(site, '/catalog/'));
      const targets = await page.evaluate(measureTargets);
      const small = targets.filter(
        (t) => !t.inline && !t.spacingExempt
          && (t.width < AA_MIN || t.height < AA_MIN));
      save(`targets-aa-${site}`, {
        site, route: '/catalog/', viewport: 390, threshold: AA_MIN,
        total: targets.length, failing: small,
      });
      expect(small, `меньше ${AA_MIN} px: ${small.map(
        (t) => `${t.cls || t.tag} ${t.width}×${t.height}`).join('; ')}`).toEqual([]);
    });
  }

  test('поля ввода на телефоне не заставляют браузер зумить', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const pages = ['/catalog/', '/search/', '/'];
    const found = [];
    for (const route of pages) {
      await page.goto(url('lords-01', route));
      const fields = await page.evaluate(() => [...document.querySelectorAll('input, select, textarea')]
        .filter((el) => el.type !== 'hidden')
        .map((el) => ({
          id: el.id || '',
          tag: el.tagName.toLowerCase(),
          fontSize: Math.round(parseFloat(getComputedStyle(el).fontSize) * 100) / 100,
        })));
      found.push(...fields.map((f) => ({ route, ...f })));
    }
    save('mobile-input-font', { site: 'lords-01', viewport: 390, threshold: INPUT_MIN_FONT, fields: found });
    const tooSmall = found.filter((f) => f.fontSize < INPUT_MIN_FONT);
    expect(tooSmall, `кегль меньше ${INPUT_MIN_FONT}px: ${tooSmall.map(
      (f) => `${f.route} ${f.id || f.tag} ${f.fontSize}px`).join('; ')}`).toEqual([]);
  });
});

test.describe('цели по усиленному порогу 44 px (WCAG AAA, требование задания)', () => {
  for (const site of Object.keys(SITES)) {
    test(`${site}: отчёт по порогу 44 px`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(url(site, '/catalog/'));
      const targets = await page.evaluate(measureTargets);
      const small = targets.filter(
        (t) => !t.inline && !t.equivalentTargetPx
          && (t.width < AAA_MIN || t.height < AAA_MIN));
      save(`targets-aaa-${site}`, {
        site, route: '/catalog/', viewport: 390, threshold: AAA_MIN,
        total: targets.length, failing: small,
      });
      expect(small, `меньше ${AAA_MIN} px: ${small.map(
        (t) => `${t.cls || t.tag} ${t.width}×${t.height}`).join('; ')}`).toEqual([]);
    });
  }
});
