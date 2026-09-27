// Настоящее воспроизведение и смена серии на свежем экземпляре.
// Настройка плеера — семейная (secret://cdnvideohub/lords/publisher-id),
// та же, которую получит новый сайт Lords. Значение нигде не печатается.
const { chromium } = require('playwright');
const БАЗА = 'http://127.0.0.1:9190';
const СЕРИАЛ = process.argv[2] || 'zabluzhdenie-2';
const ФИЛЬМ = process.argv[3] || 'vremya-siyat';
const итог = [];
const пров = (имя, ок, подр = '') => итог.push([имя, ок, подр]);

async function состояниеПлеера(page, путь, ждать = 25000) {
  const запросы = [];
  page.on('request', r => {
    const u = r.url();
    if (u.includes('cdnvideohub')) запросы.push(u);
  });
  await page.goto(БАЗА + путь, { waitUntil: 'domcontentloaded' });
  // Плеер провайдера — это <video-player> с ТЕНЕВЫМ корнем, внутри которого
  // живёт настоящий <iframe>. Искать его обычным селектором бесполезно:
  // querySelector сквозь shadow root не ходит.
  let появился = false;
  try {
    await page.waitForFunction(() => {
      const vp = document.querySelector('[data-player] video-player');
      return !!(vp && vp.shadowRoot && vp.shadowRoot.querySelector('iframe,video'));
    }, null, { timeout: ждать });
    появился = true;
  } catch (e) { /* остаётся false */ }
  // `active` выставляет КЛИЕНТ после подтверждения провайдером — это и есть
  // «плеер поднялся». Между появлением рамки и подтверждением проходит
  // секунда-другая, и мерить сразу значит мерить середину загрузки.
  try {
    await page.waitForFunction(
      () => document.querySelector('[data-player]')?.getAttribute('data-state') === 'active',
      null, { timeout: 20000 });
  } catch (e) { /* состояние останется тем, что есть */ }
  const свод = await page.evaluate(() => {
    const f = document.querySelector('[data-player]');
    const vp = f && f.querySelector('video-player');
    const внутри = vp && vp.shadowRoot ? vp.shadowRoot.querySelector('iframe,video') : null;
    const хост = f && f.querySelector('[data-src-candidates]');
    return {
      state: f ? f.getAttribute('data-state') : null,
      медиа: внутри ? внутри.tagName.toLowerCase() : null,
      src: внутри ? (внутри.getAttribute('src') || '').slice(0, 200) : null,
      кандидаты: хост ? (хост.getAttribute('data-src-candidates') || '').slice(0, 300) : '',
      // Серия передаётся плееру АТРИБУТАМИ, а не адресом рамки: адрес у всех
      // серий один и тот же, и сравнивать его бессмысленно.
      серия: vp ? `${vp.getAttribute('ident')}|s${vp.getAttribute('season')}` +
                  `e${vp.getAttribute('episode')}` : null,
      агрегатор: vp ? vp.getAttribute('data-aggregator') : null,
      титул: vp ? vp.getAttribute('data-title-id') : null,
      подпись: (document.querySelector('.pl__note') || {}).textContent || '',
    };
  });
  return { появился, запросы, ...свод };
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();

  // --- фильм: прямое воспроизведение ---------------------------------------
  const ф = await состояниеПлеера(page, `/title/${ФИЛЬМ}/`);
  пров('фильм: SDK провайдера запрошен', ф.запросы.length > 0,
       `запросов к провайдеру ${ф.запросы.length}`);
  пров('фильм: элемент воспроизведения появился', ф.появился,
       `state=${ф.state} медиа=${ф.медиа}`);
  пров('фильм: состояние не отказ', !['nosource','noaccess','error','provider'].includes(ф.state),
       String(ф.state));

  // --- сериал: смена серии --------------------------------------------------
  const э1 = await состояниеПлеера(page, `/title/${СЕРИАЛ}/season-1/episode-1/`);
  const э2 = await состояниеПлеера(page, `/title/${СЕРИАЛ}/season-1/episode-2/`);
  пров('серия 1: элемент воспроизведения появился', э1.появился,
       `state=${э1.state} медиа=${э1.медиа}`);
  пров('серия 2: элемент воспроизведения появился', э2.появился,
       `state=${э2.state} медиа=${э2.медиа}`);
  пров('смена серии меняет серию у плеера', э1.серия && э2.серия && э1.серия !== э2.серия,
       `1: ${э1.серия} | 2: ${э2.серия}`);
  пров('смена серии не меняет произведение',
       э1.титул && э1.титул === э2.титул && э1.агрегатор === э2.агрегатор,
       `${э1.агрегатор}/${э1.титул} против ${э2.агрегатор}/${э2.титул}`);
  пров('оба эпизода подняли плеер провайдера',
       э1.state === 'active' && э2.state === 'active', `${э1.state} / ${э2.state}`);

  // --- действия интерфейса не пересоздают плеер ------------------------------
  await page.goto(`${БАЗА}/title/${СЕРИАЛ}/season-1/episode-1/`, { waitUntil: 'domcontentloaded' });
  try {
    await page.waitForFunction(() => {
      const vp = document.querySelector('[data-player] video-player');
      return !!(vp && vp.shadowRoot && vp.shadowRoot.querySelector('iframe,video'));
    }, null, { timeout: 20000 });
  } catch (e) {}
  await page.evaluate(() => {
    window.__снято = 0;
    const f = document.querySelector('[data-player]');
    f.dataset.метка = 'исходный';
    new MutationObserver(ms => { for (const m of ms) for (const n of m.removedNodes)
      if (n.nodeType === 1 && (n.matches?.('video-player,iframe,video')
          || n.querySelector?.('video-player,iframe,video')))
        window.__снято++; }).observe(f, { childList: true, subtree: true });
  });
  const кнопка = await page.$('[data-theme-toggle]');
  if (кнопка) await кнопка.click();
  await page.waitForTimeout(1200);
  const цел = await page.evaluate(() => ({
    снято: window.__снято,
    метка: document.querySelector('[data-player]')?.dataset.метка,
    медиа: (() => { const vp = document.querySelector('[data-player] video-player');
                    return !!(vp && vp.shadowRoot && vp.shadowRoot.querySelector('iframe,video')); })(),
  }));
  пров('смена темы не пересоздаёт плеер',
       цел.снято === 0 && цел.метка === 'исходный' && цел.медиа,
       JSON.stringify(цел));

  await browser.close();
  console.log('проверка'.padEnd(48) + 'итог');
  console.log('-'.repeat(74));
  let плохо = 0;
  for (const [имя, ок, подр] of итог) {
    if (!ок) плохо++;
    console.log(имя.padEnd(48) + (ок ? 'PASS' : 'FAIL') + (подр ? '  ' + подр : ''));
  }
  console.log('-'.repeat(74));
  console.log(`всего ${итог.length}, провалов ${плохо}`);
  process.exit(плохо ? 1 : 0);
})();
