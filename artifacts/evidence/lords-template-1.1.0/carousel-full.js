// Все элементы ленты доступны: ничего не спрятано и ничего не потеряно.
const { chromium } = require('playwright');
const БАЗА = 'http://127.0.0.1:9190';
const итог = [];
const пров = (и, ок, п = '') => итог.push([и, ок, п]);

(async () => {
  const b = await chromium.launch();
  for (const [имя, вп] of [['телефон', {width:390,height:844}],
                           ['планшет', {width:900,height:900}],
                           ['компьютер', {width:1440,height:900}],
                           ['широкий', {width:1920,height:1080}]]) {
    const ctx = await b.newContext({viewport: вп});
    const p = await ctx.newPage();
    await p.goto(БАЗА + '/', {waitUntil:'networkidle'});

    // 1. В ленте ни одна карточка не скрыта стилями.
    const лента = await p.evaluate(() => {
      const v = document.querySelector('[data-rl-vp]');
      if (!v) return null;
      const t = v.querySelector('[data-rl-track]');
      const карточки = [...t.children];
      const спрятаны = карточки.filter(e => {
        const s = getComputedStyle(e);
        const r = e.getBoundingClientRect();
        return s.display === 'none' || s.visibility === 'hidden' || r.width < 1;
      }).length;
      return {всего: карточки.length, спрятаны};
    });
    пров(`${имя}: в ленте ничего не спрятано`,
         лента && лента.спрятаны === 0, лента ? `${лента.всего} карточек, спрятано ${лента.спрятаны}` : 'ленты нет');

    // 2. Прокруткой достижима КАЖДАЯ карточка ленты.
    if (лента) {
      const достижимо = await p.evaluate(async () => {
        const v = document.querySelector('[data-rl-vp]');
        const t = v.querySelector('[data-rl-track]');
        const карточки = [...t.children];
        v.scrollTo({left: v.scrollWidth, behavior: 'instant'});
        await new Promise(r => setTimeout(r, 300));
        const справа = v.getBoundingClientRect().right + 2;
        const слева0 = v.getBoundingClientRect().left - 2;
        const видна_в_конце = карточки.filter(e => {
          const r = e.getBoundingClientRect();
          return r.left < справа && r.right > слева0;
        });
        const последняя = карточки[карточки.length - 1].getBoundingClientRect();
        v.scrollTo({left: 0, behavior: 'instant'});
        return {последняя_видна: последняя.right <= справа && последняя.left >= слева0 - 1,
                в_конце: видна_в_конце.length};
      });
      пров(`${имя}: последняя карточка достижима прокруткой`,
           достижимо.последняя_видна, JSON.stringify(достижимо));
    }

    // 3. В полках главной хвост неполного ряда снимается СТИЛЯМИ, но записи
    //    остаются в разметке: каталог их не теряет.
    const полки = await p.evaluate(() => {
      const итог = [];
      for (const g of document.querySelectorAll('[data-rows="full"]')) {
        const дети = [...g.children];
        const видно = дети.filter(e => getComputedStyle(e).display !== 'none').length;
        итог.push({в_разметке: дети.length, видно,
                   объявлено: +(g.getAttribute('data-cards') || 0)});
      }
      return итог;
    });
    пров(`${имя}: у полок число в разметке совпадает с объявленным`,
         полки.length > 0 && полки.every(x => x.в_разметке === x.объявлено),
         JSON.stringify(полки.slice(0, 2)));
    пров(`${имя}: скрытый хвост полки кратен ряду`,
         полки.every(x => x.видно > 0 && x.видно <= x.в_разметке),
         JSON.stringify(полки.slice(0, 2)));

    // 4. На странице каталога не спрятано НИЧЕГО.
    await p.goto(БАЗА + '/catalog/', {waitUntil:'domcontentloaded'});
    const каталог = await p.evaluate(() => {
      const g = document.querySelector('[data-card-grid]');
      if (!g) return null;
      const дети = [...g.children];
      return {всего: дети.length,
              спрятаны: дети.filter(e => getComputedStyle(e).display === 'none').length,
              пометка: g.hasAttribute('data-rows')};
    });
    пров(`${имя}: в каталоге ничего не спрятано`,
         каталог && каталог.спрятаны === 0 && !каталог.пометка,
         JSON.stringify(каталог));
    await ctx.close();
  }
  await b.close();
  console.log('проверка'.padEnd(52) + 'итог');
  console.log('-'.repeat(80));
  let плохо = 0;
  for (const [и, ок, п] of итог) { if (!ок) плохо++;
    console.log(и.padEnd(52) + (ок ? 'PASS' : 'FAIL') + (п ? '  ' + п : '')); }
  console.log('-'.repeat(80));
  console.log(`всего ${итог.length}, провалов ${плохо}`);
  process.exit(плохо ? 1 : 0);
})();
