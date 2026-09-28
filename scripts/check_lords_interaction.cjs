/** Доступность и взаимодействие: клавиатура, фокус, меню, поиск, карусель. */
const { chromium } = require('@playwright/test');
(async () => {
  const b = await chromium.launch();
  const итог = {};
  for (const w of [390, 1440]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 } });
    const p = await ctx.newPage();
    const ошибки = [];
    p.on('console', (m) => m.type() === 'error' && ошибки.push(m.text()));
    await p.goto(process.argv[2] + '/', { waitUntil: 'networkidle' });

    // Табуляция: первые 12 остановок обязаны быть видимыми и иметь фокус-стиль.
    const остановки = [];
    for (let i = 0; i < 12; i += 1) {
      await p.keyboard.press('Tab');
      остановки.push(await p.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return { тег: el.tagName.toLowerCase(), класс: String(el.className).slice(0, 24),
                 виден: r.width > 0 && r.height > 0,
                 вОкне: r.top >= -1 && r.left >= -1,
                 контур: s.outlineStyle !== 'none' || s.boxShadow !== 'none' };
      }));
    }
    const живые = остановки.filter(Boolean);
    итог[`tab@${w}`] = {
      остановок: живые.length,
      невидимых: живые.filter((о) => !о.виден).length,
      безКонтура: живые.filter((о) => !о.контур).length,
    };

    // Поиск: форма отправляется и ведёт на страницу поиска.
    const поиск = await p.$('.header-search input');
    if (поиск) {
      await поиск.fill('тест');
      await Promise.all([p.waitForLoadState('networkidle'), поиск.press('Enter')]);
      итог[`поиск@${w}`] = { адрес: new URL(p.url()).pathname, статус: 'перешли' };
      await p.goBack({ waitUntil: 'networkidle' });
    }

    // Меню на узкой ширине открывается с клавиатуры.
    if (w < 900) {
      const кнопка = await p.$('.nav-toggle');
      if (кнопка) {
        await кнопка.focus();
        await кнопка.press('Enter');
        итог[`меню@${w}`] = await p.evaluate(() => {
          const nav = document.querySelector('.site-nav');
          const s = getComputedStyle(nav);
          const r = nav.getBoundingClientRect();
          return { открыто: s.display !== 'none', высота: Math.round(r.height),
                   доступно: nav.querySelectorAll('a').length };
        });
      }
    }

    // Карусель прокручивается.
    итог[`карусель@${w}`] = await p.evaluate(() => {
      const rail = document.querySelector('.rail');
      if (!rail) return { есть: false };
      const до = rail.scrollLeft;
      rail.scrollLeft = 200;
      const после = rail.scrollLeft;
      rail.scrollLeft = до;
      return { есть: true, прокрутилась: после > до, ширина: rail.scrollWidth };
    });
    итог[`ошибки@${w}`] = ошибки.length;
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(итог, null, 1));
})();
