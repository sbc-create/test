/**
 * Структурная полнота витрины по перечню задания.
 *
 * Проверяется наличие и состояние элементов, а не их красота. Отсутствие
 * элемента — факт; отсутствие данных под элементом — другой факт, и он
 * обязан выражаться корректным пустым состоянием, а не выдуманным значением.
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');

const БАЗА = process.argv[2];
const ВЫХОД = process.argv[3] || 'var/structural-audit.json';

const ПРОВЕРКИ = {
  'верхняя карусель': (d) => d.querySelectorAll('.rail').length,
  'карточки': (d) => d.querySelectorAll('.card').length,
  'постеры': (d) => d.querySelectorAll('.card__poster').length,
  'заглушка постера': (d) => d.querySelectorAll('.card__poster-empty').length,
  'название на карточке': (d) => d.querySelectorAll('.card__title').length,
  'метаданные карточки': (d) => d.querySelectorAll('.card__meta').length,
  'оценка на карточке': (d) => d.querySelectorAll('.card__rating, .rail__rating').length,
  'сетка каталога': (d) => d.querySelectorAll('.grid, .cards, .catalog__grid').length,
  'фасеты': (d) => d.querySelectorAll('.facet, .facet__list, fieldset').length,
  'пагинация': (d) => d.querySelectorAll('.pagination, nav[aria-label*="страниц" i]').length,
  'шапка': (d) => d.querySelectorAll('header').length,
  'подвал': (d) => d.querySelectorAll('footer, .site-footer').length,
  'навигация': (d) => d.querySelectorAll('nav').length,
  'форма поиска': (d) => d.querySelectorAll('form[role="search"], .header-search').length,
  'кнопка меню': (d) => d.querySelectorAll('.nav-toggle').length,
  'ориентиры main': (d) => d.querySelectorAll('main, [role="main"]').length,
  'h1': (d) => d.querySelectorAll('h1').length,
  'живая область': (d) => d.querySelectorAll('[aria-live], [role="status"], [role="alert"]').length,
};

(async () => {
  const b = await chromium.launch();
  const итог = {};
  const адреса = JSON.parse(process.argv[4] || '{}');
  for (const [имя, путь] of Object.entries(адреса)) {
    for (const w of [390, 1440]) {
      const ctx = await b.newContext({ viewport: { width: w, height: 900 } });
      const p = await ctx.newPage();
      const ошибки = [];
      p.on('console', (m) => m.type() === 'error' && ошибки.push(m.text().slice(0, 120)));
      const ответ = await p.goto(БАЗА + путь, { waitUntil: 'networkidle' });
      const д = await p.evaluate((список) => {
        const out = {};
        for (const [к, тело] of Object.entries(список)) {
          // eslint-disable-next-line no-new-func
          out[к] = new Function('d', 'return (' + тело + ')(d)')(document);
        }
        // Доступные имена интерактивных элементов.
        const безымянные = [...document.querySelectorAll('a, button')]
          .filter((el) => {
            const текст = (el.innerText || '').trim();
            return !текст && !el.getAttribute('aria-label')
              && !el.getAttribute('title') && el.getAttribute('aria-hidden') !== 'true';
          }).length;
        out['интерактивные без имени'] = безымянные;
        out['битые изображения'] = [...document.querySelectorAll('img')]
          .filter((i) => i.complete && i.naturalWidth === 0).length;
        return out;
      }, Object.fromEntries(Object.entries(ПРОВЕРКИ).map(([к, f]) => [к, f.toString()])));
      д['http'] = ответ ? ответ.status() : null;
      д['ошибки консоли'] = ошибки.length;
      итог[`${имя}@${w}`] = д;
      await ctx.close();
    }
  }
  await b.close();
  fs.writeFileSync(ВЫХОД, JSON.stringify(итог, null, 1));
  console.log(JSON.stringify(итог, null, 1));
})();
