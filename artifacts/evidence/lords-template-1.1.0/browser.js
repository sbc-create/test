// Браузерная приёмка нового экземпляра: темы, лента, плеер.
const { chromium } = require('playwright');
const БАЗА = 'http://127.0.0.1:9190';
const итог = [];
const пров = (имя, ок, подр = '') => { итог.push([имя, ок, подр]); };

(async () => {
  const browser = await chromium.launch();

  for (const [имя_вп, вп] of [['телефон', {width: 390, height: 844}],
                              ['компьютер', {width: 1440, height: 900}]]) {
    for (const тема of ['light', 'dark']) {
      const ctx = await browser.newContext({viewport: вп, colorScheme: тема});
      const page = await ctx.newPage();
      await page.goto(БАЗА + '/', {waitUntil: 'networkidle'});
      const метка = `${имя_вп}/${тема}`;

      // --- нет горизонтальной прокрутки страницы ---
      const переполнение = await page.evaluate(() =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth);
      пров(`${метка}: нет горизонтальной прокрутки`, переполнение <= 1, `${переполнение}px`);

      // --- активная тема применена ---
      const фон = await page.evaluate(() =>
        getComputedStyle(document.body).backgroundColor);
      пров(`${метка}: фон задан`, фон && фон !== 'rgba(0, 0, 0, 0)', фон);

      // --- контраст подписи карточки на фактическом фоне ---
      const контраст = await page.evaluate(() => {
        function яркость(c) {
          const [r,g,b] = c.match(/\d+/g).slice(0,3).map(Number).map(v => {
            v /= 255; return v <= 0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4);
          });
          return 0.2126*r + 0.7152*g + 0.0722*b;
        }
        function фонПредка(el) {
          let n = el;
          while (n) {
            const bg = getComputedStyle(n).backgroundColor;
            if (bg && !/rgba\(0, 0, 0, 0\)|transparent/.test(bg)) return bg;
            n = n.parentElement;
          }
          return 'rgb(255,255,255)';
        }
        const плохо = [];
        for (const el of document.querySelectorAll('.c__t, .zt__t, .cm__tx, .sec-rail__h h2 a, .hub__n')) {
          const c = getComputedStyle(el).color, b = фонПредка(el);
          const l1 = яркость(c), l2 = яркость(b);
          const к = (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
          if (к < 4.5) плохо.push(`${el.className} ${c} на ${b} = ${к.toFixed(2)}`);
        }
        return плохо;
      });
      пров(`${метка}: подписи читаются (≥4.5:1)`, контраст.length === 0,
           контраст.slice(0,2).join('; '));

      // --- переключатель темы ---
      const кнопка = await page.$('[data-theme-toggle]');
      пров(`${метка}: переключатель есть`, !!кнопка);
      if (кнопка) {
        const до = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        await кнопка.click();
        await page.waitForTimeout(150);
        const после = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        пров(`${метка}: тема переключилась`, до !== после, `${до} → ${после}`);
        const выбор = await page.evaluate(() => localStorage.getItem('lords-theme'));
        пров(`${метка}: выбор сохранён`, выбор === 'dark' || выбор === 'light', String(выбор));
        // выбор переживает переход на другую страницу
        await page.goto(БАЗА + '/catalog/', {waitUntil: 'domcontentloaded'});
        const после2 = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        пров(`${метка}: выбор пережил переход`, после2 === после, `${после} → ${после2}`);
      }
      await ctx.close();
    }
  }

  // --- лента: шаг, края, клавиатура, изменение ширины -----------------------
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}});
  const page = await ctx.newPage();
  await page.goto(БАЗА + '/', {waitUntil: 'networkidle'});

  const измерить = () => page.evaluate(() => {
    const v = document.querySelector('[data-rl-vp]');
    const t = v.querySelector('[data-rl-track]');
    const к = t.firstElementChild;
    const з = parseFloat(getComputedStyle(t).columnGap) || 0;
    const ш = к.getBoundingClientRect().width + з;
    return {left: v.scrollLeft, max: v.scrollWidth - v.clientWidth,
            шагКарточки: ш, видно: Math.max(1, Math.floor((v.clientWidth + з) / ш)),
            карточек: t.children.length, окно: v.clientWidth};
  });
  const м0 = await измерить();
  пров('лента: карточки есть', м0.карточек > 0, String(м0.карточек));
  пров('лента: прокручивается', м0.max > 0, `max=${Math.round(м0.max)}`);
  пров('лента: начало — левая кнопка погашена',
       await page.evaluate(() => document.querySelector('[data-rl="prev"]').disabled));

  // Стрелки показываются при наведении на ленту: это правило ядра для
  // широких экранов, а не дефект. Наводимся, как это делает посетитель.
  await page.hover('.zrl');
  await page.click('[data-rl="next"]');
  await page.waitForTimeout(700);
  const м1 = await измерить();
  const ожидаемый = м0.шагКарточки * м0.видно;
  const отклонение = Math.abs((м1.left - м0.left) - ожидаемый);
  пров('лента: шаг равен ширине видимых карточек', отклонение <= 2,
       `сдвиг ${Math.round(м1.left - м0.left)} при ожидаемом ${Math.round(ожидаемый)}`);
  пров('лента: страницы не налезают', отклонение <= 2);

  // --- доходит до последнего положения без пропусков -----------------------
  let шагов = 1, предыдущий = м1.left;
  for (let i = 0; i < 20; i++) {
    const before = (await измерить()).left;
    // Кнопка гаснет на краю — это и есть искомое состояние, а не помеха.
    if (await page.evaluate(() => document.querySelector('[data-rl="next"]').disabled)) break;
    await page.hover('.zrl');
    await page.click('[data-rl="next"]');
    await page.waitForTimeout(600);
    const m = await измерить();
    if (m.left <= before + 1) break;
    шагов++;
    предыдущий = m.left;
  }
  const мк = await измерить();
  пров('лента: доходит до конца', Math.abs(мк.left - мк.max) <= 2,
       `${Math.round(мк.left)} из ${Math.round(мк.max)}`);
  пров('лента: правая кнопка погашена в конце',
       await page.evaluate(() => document.querySelector('[data-rl="next"]').disabled));
  const страниц = Math.ceil(мк.карточек / м0.видно);
  пров('лента: число страниц совпало с расчётом', шагов + 1 === страниц || шагов + 1 === страниц - 0,
       `шагов ${шагов}+1, расчёт ${страниц} (видно ${м0.видно}, карточек ${мк.карточек})`);

  // --- клавиатура ----------------------------------------------------------
  await page.evaluate(() => {
    const v = document.querySelector('[data-rl-vp]');
    v.scrollTo({left: 0, behavior: 'instant'});
    v.focus();
  });
  await page.waitForTimeout(400);
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1200);
  const мкл = await измерить();
  пров('лента: стрелка вправо листает', мкл.left > 1, String(Math.round(мкл.left)));
  await page.keyboard.press('End');
  await page.waitForTimeout(1500);
  пров('лента: End доводит до конца',
       Math.abs((await измерить()).left - мк.max) <= 2);
  await page.keyboard.press('Home');
  await page.waitForTimeout(1500);
  пров('лента: Home возвращает в начало', (await измерить()).left <= 1);

  // --- изменение ширины окна ------------------------------------------------
  await page.setViewportSize({width: 900, height: 900});
  // Ширина карточки задана в vw: после смены размера окна раскладке нужно
  // успеть пересчитаться, иначе измеряется прежняя геометрия.
  await page.waitForTimeout(800);
  await page.evaluate(() => document.querySelector('[data-rl-vp]')
    .scrollTo({left: 0, behavior: 'instant'}));
  await page.waitForTimeout(300);
  const муз = await измерить();
  пров('лента: на узком экране шаг пересчитан', муз.видно < м0.видно,
       `${м0.видно} → ${муз.видно}`);
  // На 900 px стрелки скрыты правилом ядра (они появляются от 1024 px), и
  // листание там — свайп и клавиатура. Проверяем тем способом, который на
  // этой ширине действительно доступен.
  await page.evaluate(() => document.querySelector('[data-rl-vp]').focus());
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1200);
  const муз2 = await измерить();
  пров('лента: шаг на узком равен видимым',
       Math.abs((муз2.left - муз.left) - муз.шагКарточки * муз.видно) <= 2,
       `${Math.round(муз2.left - муз.left)} при ${Math.round(муз.шагКарточки * муз.видно)}`);

  // --- телефон: следующая карточка видна частично ---------------------------
  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(800);
  const мт = await измерить();
  const дробная = мт.окно / мт.шагКарточки;
  пров('телефон: следующая карточка видна частично',
       Math.abs(дробная - Math.round(дробная)) > 0.1,
       `видно ${дробная.toFixed(2)} карточки`);

  await ctx.close();

  // --- плеер не пересоздаётся действиями интерфейса -------------------------
  const ctx2 = await browser.newContext({viewport: {width: 1440, height: 900}});
  const p2 = await ctx2.newPage();
  await p2.goto(БАЗА + '/title/serial-001/', {waitUntil: 'networkidle'});
  await p2.evaluate(() => {
    const el = document.querySelector('[data-player]');
    el.dataset.меткаПроверки = 'исходный';
    window.__пересозданий = 0;
    new MutationObserver(ms => { for (const m of ms)
      for (const n of m.removedNodes)
        if (n.nodeType === 1 && (n.matches?.('[data-player]') || n.querySelector?.('[data-player]')))
          window.__пересозданий++;
    }).observe(document.body, {childList: true, subtree: true});
  });
  await p2.hover('.rt__s');                                  // наведение на звёзды
  await p2.click('.rt__s');                                  // выбор оценки
  await p2.click('[data-theme-toggle]');                     // переключение темы
  await p2.fill('#cm-text', 'Проверочный текст комментария');
  await p2.waitForTimeout(400);
  const цел = await p2.evaluate(() => ({
    пересозданий: window.__пересозданий,
    метка: document.querySelector('[data-player]')?.dataset.меткаПроверки || 'нет',
  }));
  пров('плеер не пересоздан действиями интерфейса',
       цел.пересозданий === 0 && цел.метка === 'исходный', JSON.stringify(цел));
  const голосов = await p2.evaluate(() =>
    document.querySelector('[data-rating-out]')?.textContent || '');
  пров('выбранная оценка показана словами', /\d/.test(голосов), голосов);
  const отправлено = await p2.evaluate(() => !!document.querySelector('[data-rating="done"]'));
  пров('выбор звезды не отправил голос', !отправлено);
  await ctx2.close();

  await browser.close();

  console.log('проверка'.padEnd(54) + 'итог');
  console.log('-'.repeat(72));
  let плохо = 0;
  for (const [имя, ок, подр] of итог) {
    if (!ок) плохо++;
    console.log(имя.padEnd(54) + (ок ? 'PASS' : 'FAIL') + (подр ? '  ' + подр : ''));
  }
  console.log('-'.repeat(72));
  console.log(`всего ${итог.length}, провалов ${плохо}`);
  process.exit(плохо ? 1 : 0);
})();
