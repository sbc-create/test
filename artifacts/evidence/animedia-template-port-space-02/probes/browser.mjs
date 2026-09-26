// Браузерная проверка перенесённого поведения: настоящие клики, настоящая
// раскладка, обе темы, компьютер и телефон.
import { chromium } from 'playwright';
const БАЗА = process.env.ANIMEDIA_PROBE_BASE || 'http://127.0.0.1:9310';
const ок = [], плохо = [];
const п = (имя, усл, подр = '') => (усл ? ок : плохо).push(имя + (подр ? ` — ${подр}` : ''));

const экраны = [
  { имя: 'компьютер', viewport: { width: 1440, height: 900 }, isMobile: false },
  { имя: 'телефон', viewport: { width: 390, height: 844 }, isMobile: true,
    hasTouch: true, deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' },
];
const темы = ['dark', 'light'];

const браузер = await chromium.launch();
let адресСерии = null;

for (const э of экраны) {
  for (const тема of темы) {
    const ctx = await браузер.newContext({ ...э, colorScheme: тема === 'dark' ? 'dark' : 'light' });
    await ctx.addInitScript(t => { try { localStorage.setItem('amd-theme', t); } catch (e) {} }, тема);
    const стр = await ctx.newPage();
    const метка = `${э.имя}/${тема}`;
    const консоль = [];
    стр.on('console', м => { if (м.type() === 'error') консоль.push(м.text()); });
    const битые = [];
    стр.on('response', async r => {
      if (r.request().resourceType() === 'image' && r.status() >= 400) битые.push(`${r.status()} ${r.url()}`);
    });

    // --- главная ---------------------------------------------------------
    await стр.goto(БАЗА + '/', { waitUntil: 'load' });
    const тема_факт = await стр.evaluate(() => document.documentElement.getAttribute('data-theme'));
    п(`${метка} тема применена`, тема_факт === тема, `в разметке ${тема_факт}`);
    const перелив = await стр.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    п(`${метка} главная без горизонтальной прокрутки`, перелив <= 1, `${перелив}px`);

    // подборки: обложки видны, подписи читаемы без наведения
    // Обложки превью ленивые и лежат ниже сгиба: это задокументированный
    // остаток (вес изображений прокси), а не дефект разметки. Поэтому блок
    // сначала долистывается, и только потом проверяется, что обложки пришли.
    await стр.evaluate(() => {
      const б = document.querySelector('.zhub');
      if (б) б.scrollIntoView({ block: 'center' });
    });
    await стр.waitForFunction(() => {
      const и = [...document.querySelectorAll('img.zhub__img')];
      return и.length > 0 && и.every(i => i.complete);
    }, null, { timeout: 30000 }).catch(() => {});
    const подборки = await стр.evaluate(() => {
      const карточки = [...document.querySelectorAll('article.zhub__c')];
      return карточки.map(к => {
        const img = [...к.querySelectorAll('img.zhub__img')];
        const подписи = [...к.querySelectorAll('.zhub__n')];
        return {
          ключ: к.dataset.collectionKey,
          обложек: img.length,
          загрузилось: img.filter(i => i.naturalWidth > 0).length,
          пропорции: [...new Set(img.map(i => (i.clientWidth / Math.max(1, i.clientHeight)).toFixed(2)))],
          подписи: подписи.map(s => ({
            текст: s.textContent.trim().slice(0, 30),
            видна: s.offsetHeight > 0 && getComputedStyle(s).visibility !== 'hidden'
                   && getComputedStyle(s).opacity !== '0',
          })),
          вложенных: [...к.querySelectorAll('a a')].length,
          ссылкаНазвания: к.querySelector('a.zhub__t')?.getAttribute('href') || '',
        };
      });
    });
    п(`${метка} карточки подборок есть`, подборки.length > 0, `${подборки.length}`);
    for (const к of подборки) {
      п(`${метка}/${к.ключ} обложки загрузились`,
        к.обложек > 0 && к.загрузилось === к.обложек, `${к.загрузилось}/${к.обложек}`);
      п(`${метка}/${к.ключ} пропорции одинаковые`, к.пропорции.length === 1, к.пропорции.join(','));
      п(`${метка}/${к.ключ} подписи видны без наведения`,
        к.подписи.length === к.обложек && к.подписи.every(s => s.видна && s.текст),
        JSON.stringify(к.подписи.filter(s => !s.видна || !s.текст)).slice(0, 120));
      п(`${метка}/${к.ключ} вложенных ссылок нет`, к.вложенных === 0);
      п(`${метка}/${к.ключ} название ведёт в подборку`,
        к.ссылкаНазвания.startsWith('/collection/'), к.ссылкаНазвания);
    }
    const колонок = await стр.evaluate(() => {
      const с = document.querySelector('.zhub');
      return с ? getComputedStyle(с).gridTemplateColumns.split(' ').length : 0;
    });
    п(`${метка} колонок не больше карточек`, колонок > 0 && колонок <= подборки.length,
      `${колонок} колонок на ${подборки.length} карточек`);

    // постеры первого экрана уже пришли к моменту load
    // Первый экран считается по ОБЕИМ осям: карточки карусели, уехавшие
    // вправо, вертикально в виду, но посетитель их не видит — и грузить их
    // сразу как раз не надо. Прежняя проверка мерила только вертикаль и
    // объявляла дефектом ровно то поведение, которое здесь и требуется.
    await стр.evaluate(() => window.scrollTo(0, 0));
    const первыйЭкран = await стр.evaluate(() => {
      const W = document.documentElement.clientWidth, H = window.innerHeight;
      const вВиду = i => {
        const r = i.getBoundingClientRect();
        return r.top < H && r.bottom > 0 && r.left < W && r.right > 0;
      };
      const видимые = [...document.querySelectorAll('img[data-poster]')].filter(вВиду);
      const герой = [...document.querySelectorAll('[data-hero="1"] img[data-poster]')]
        .filter(вВиду);
      return {
        всего: видимые.length,
        готово: видимые.filter(i => i.naturalWidth > 0).length,
        героя: герой.length,
        героЛенивых: герой.filter(i => i.loading === 'lazy').length,
        высокийПриоритет: [...document.querySelectorAll('img[fetchpriority="high"]')].length,
        ленивыеКлассы: [...new Set(видимые.filter(i => i.loading === 'lazy')
          .map(i => i.className))],
      };
    });
    // Исход, который видит посетитель: к `load` видимые постеры УЖЕ есть.
    п(`${метка} постеры первого экрана готовы к load`,
      первыйЭкран.всего === 0 || первыйЭкран.готово === первыйЭкран.всего,
      `${первыйЭкран.готово}/${первыйЭкран.всего}, ленивые классы: ` +
      первыйЭкран.ленивыеКлассы.join(','));
    // И блок первого экрана не ждёт прокрутки: бюджет просит именно он.
    п(`${метка} постеры ленты первого экрана не ленивые`,
      первыйЭкран.героя > 0 && первыйЭкран.героЛенивых === 0,
      `${первыйЭкран.героЛенивых} ленивых из ${первыйЭкран.героя}`);
    п(`${метка} высокий приоритет отдан ровно четырём`,
      первыйЭкран.высокийПриоритет === 4, `${первыйЭкран.высокийПриоритет}`);

    // --- каталог и фильтры -----------------------------------------------
    await стр.goto(БАЗА + '/catalog/', { waitUntil: 'load' });
    const перелив2 = await стр.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    п(`${метка} каталог без горизонтальной прокрутки`, перелив2 <= 1, `${перелив2}px`);
    if (э.имя === 'телефон') await стр.click('[data-afilt-open]');
    const панели = стр.locator('details.afilt__dd');
    const сколько = await панели.count();
    п(`${метка} панелей фильтров`, сколько >= 5, `${сколько}`);
    const открытых = async () => стр.evaluate(() =>
      [...document.querySelectorAll('details.afilt__dd')].filter(d => d.open).length);
    п(`${метка} при загрузке открытых панелей нет`, (await открытых()) === 0);
    await панели.nth(0).locator('summary').click();
    п(`${метка} панель открылась`, (await открытых()) === 1, `${await открытых()}`);
    п(`${метка} aria-expanded объявлен`,
      (await панели.nth(0).locator('summary').getAttribute('aria-expanded')) === 'true');
    await панели.nth(2).locator('summary').click();
    const после2 = await открытых();
    п(`${метка} вторая панель закрыла первую`, после2 === 1, `открыто ${после2}`);
    await панели.nth(2).locator('summary').click();
    п(`${метка} повторное нажатие закрывает свою`, (await открытых()) === 0);
    await панели.nth(1).locator('summary').click();
    await стр.mouse.click(5, 5);
    п(`${метка} клик снаружи закрывает`, (await открытых()) === 0);
    await панели.nth(1).locator('summary').click();
    await стр.keyboard.press('Escape');
    п(`${метка} Escape закрывает`, (await открытых()) === 0);
    const фокус = await стр.evaluate(() =>
      document.activeElement?.closest('details.afilt__dd')?.dataset.afiltDd || '');
    п(`${метка} Escape вернул фокус на кнопку`, фокус !== '', `фокус на ${фокус || 'неизвестно'}`);
    // панель не уезжает за экран
    await панели.nth(сколько - 1).locator('summary').click();
    const уехало = await стр.evaluate(() => {
      const o = [...document.querySelectorAll('details.afilt__dd')].find(d => d.open)
        ?.querySelector('.afilt__opts');
      if (!o) return null;
      const r = o.getBoundingClientRect();
      return { right: Math.round(r.right), left: Math.round(r.left),
               width: document.documentElement.clientWidth };
    });
    п(`${метка} панель у края не уезжает за экран`,
      уехало && уехало.right <= уехало.width + 1 && уехало.left >= -1,
      JSON.stringify(уехало));
    // клавиатура: панель открывается с клавиатуры
    await стр.keyboard.press('Escape');
    await панели.nth(0).locator('summary').focus();
    await стр.keyboard.press('Enter');
    п(`${метка} панель открывается с клавиатуры`, (await открытых()) === 1);
    // выбранное значение остаётся после закрытия панели
    await стр.goto(БАЗА + '/catalog/?year=2024', { waitUntil: 'load' });
    if (э.имя === 'телефон') await стр.click('[data-afilt-open]');
    const помечено = await стр.evaluate(() =>
      document.querySelectorAll('summary[data-afilt-chosen]').length);
    п(`${метка} применённый фильтр помечен`, помечено >= 1, `${помечено}`);
    await стр.keyboard.press('Escape');
    п(`${метка} фильтр остался применённым`, стр.url().includes('year=2024'), стр.url());

    // --- ТОП-100 ----------------------------------------------------------
    await стр.goto(БАЗА + '/top/', { waitUntil: 'load' });
    const топ = await стр.evaluate(() => {
      const к = [...document.querySelectorAll('a.zt[data-rank]')];
      return { мест: к.length, номера: к.map(a => +a.dataset.rank),
               разных: new Set(к.map(a => a.getAttribute('href'))).size,
               видимыхНомеров: к.filter(a => {
                 const b = a.querySelector('.zt__rank');
                 return b && b.offsetHeight > 0;
               }).length };
    });
    п(`${метка} ТОП: сто мест`, топ.мест === 100, `${топ.мест}`);
    п(`${метка} ТОП: нумерация 1..100`,
      топ.номера.every((n, i) => n === i + 1));
    п(`${метка} ТОП: сто разных произведений`, топ.разных === 100, `${топ.разных}`);
    п(`${метка} ТОП: номера видны`, топ.видимыхНомеров === 100, `${топ.видимыхНомеров}`);
    const переливТоп = await стр.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    п(`${метка} ТОП без горизонтальной прокрутки`, переливТоп <= 1, `${переливТоп}px`);

    // --- подборки: раздел -------------------------------------------------
    await стр.goto(БАЗА + '/collections/', { waitUntil: 'load' });
    const раздел = await стр.evaluate(() => ({
      карточек: document.querySelectorAll('article.zhub__c').length,
      текстовых: document.querySelectorAll('article[data-collection-preview="0"]').length,
      битыхImg: [...document.querySelectorAll('img.zhub__img')]
        .filter(i => i.complete && i.naturalWidth === 0).length,
      перелив: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }));
    п(`${метка} раздел подборок: карточки есть`, раздел.карточек > 0, `${раздел.карточек}`);
    п(`${метка} раздел подборок: текстовых плиток нет`, раздел.текстовых === 0);
    п(`${метка} раздел подборок: битых картинок нет`, раздел.битыхImg === 0, `${раздел.битыхImg}`);
    п(`${метка} раздел подборок без горизонтальной прокрутки`, раздел.перелив <= 1,
      `${раздел.перелив}px`);

    // --- произведение и серия --------------------------------------------
    if (!адресСерии) {
      await стр.goto(БАЗА + '/catalog/', { waitUntil: 'load' });
      const адреса = await стр.evaluate(() =>
        [...document.querySelectorAll('a.zt')].map(a => a.getAttribute('href')).slice(0, 40));
      for (const а of адреса) {
        await стр.goto(БАЗА + а, { waitUntil: 'load' });
        const e = await стр.evaluate(() =>
          document.querySelector('a[href*="/episode-"]')?.getAttribute('href') || '');
        if (e) { адресСерии = e; break; }
      }
    }
    п(`${метка} серия найдена`, !!адресСерии, адресСерии || 'нет');
    if (адресСерии) {
      await стр.goto(БАЗА + адресСерии, { waitUntil: 'load' });
      const серия = await стр.evaluate(() => {
        const ctx = document.querySelector('[data-episode-context="1"]');
        const плеер = document.querySelector('[data-b08="player"]');
        const оценка = document.querySelector('[data-episode-rating="title"]');
        const постер = ctx?.querySelector('img');
        const свернуто = ctx?.querySelector('details.aep-ctx__more');
        return {
          есть: !!ctx, плеерВыше: !!(плеер && ctx) &&
            (плеер.compareDocumentPosition(ctx) & Node.DOCUMENT_POSITION_FOLLOWING) > 0,
          виднаБезПрокрутки: ctx ? ctx.getBoundingClientRect().top < window.innerHeight * 3 : false,
          постерГотов: постер ? постер.naturalWidth > 0 : null,
          подписьОценки: оценка?.textContent.includes('Рейтинг произведения') || false,
          оценкаВидна: oценкаВидна(оценка),
          раскрытие: !!свернуто,
          факты: !!document.querySelector('[data-episode-facts="1"]'),
          переход: document.querySelectorAll('.zepnav a').length,
          перелив: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
        function oценкаВидна(э) { return !!э && э.offsetHeight > 0; }
      });
      п(`${метка} серия: карточка произведения есть`, серия.есть);
      п(`${метка} серия: плеер выше карточки`, серия.плеерВыше);
      п(`${метка} серия: постер карточки загрузился`,
        серия.постерГотов === null || серия.постерГотов === true, `${серия.постерГотов}`);
      п(`${метка} серия: оценка подписана и видна`, серия.подписьОценки && серия.оценкаВидна);
      п(`${метка} серия: факты каталога есть`, серия.факты);
      п(`${метка} серия: переход между сериями есть`, серия.переход > 0, `${серия.переход}`);
      п(`${метка} серия без горизонтальной прокрутки`, серия.перелив <= 1, `${серия.перелив}px`);
      if (серия.раскрытие) {
        await стр.click('details.aep-ctx__more > summary');
        const развернулось = await стр.evaluate(() => {
          const d = document.querySelector('details.aep-ctx__more');
          const p = d.querySelector('.aep-ctx__desc');
          return d.open && getComputedStyle(p).webkitLineClamp === 'none';
        });
        п(`${метка} серия: описание раскрывается`, развернулось);
      }
      // переход на следующую серию действительно работает
      const след = await стр.evaluate(() =>
        [...document.querySelectorAll('.zepnav a')].map(a => a.getAttribute('href'))[0] || '');
      if (след) {
        const ответ = await стр.goto(БАЗА + след, { waitUntil: 'load' });
        п(`${метка} переход между сериями открывается`,
          ответ.status() === 200 && await стр.evaluate(() =>
            !!document.querySelector('[data-b08="player"]')), `${ответ.status()}`);
      }
    }

    п(`${метка} ошибок в консоли нет`, консоль.length === 0, консоль.slice(0, 2).join(' | '));
    п(`${метка} битых изображений нет`, битые.length === 0, битые.slice(0, 2).join(' | '));
    await ctx.close();
  }
}
await браузер.close();
console.log(`\nОК: ${ок.length}   ПЛОХО: ${плохо.length}`);
for (const с of плохо) console.log('  ✗', с);
process.exit(плохо.length ? 1 : 0);
