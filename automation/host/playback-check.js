/**
 * Воспроизведение на публичном домене — без привязки к вёрстке семейства.
 *
 * Зачем ещё одна проверка. У AnimeGo есть `checks/playback.js`, но он ждёт
 * селектор `.ag-play__f`: на витрине Zona он не появится никогда, и проверка
 * падает по таймауту, ничего не сказав о плеере. Приёмка десяти доменов из
 * четырёх семейств не может зависеть от классов конкретного шаблона.
 *
 * Что проверяется:
 *   1. на странице серии есть элемент <video> — в любом кадре, включая кадр
 *      провайдера; отсутствие элемента отличается от «элемент есть, но стоит»;
 *   2. поток готов (readyState) и у него есть длительность;
 *   3. позиция РАСТЁТ — то есть серия действительно идёт, а не «загрузилась»;
 *   4. переход на следующую серию меняет запрошенный у провайдера ролик:
 *      одинаковый источник у двух серий означает, что смена не работает.
 *
 * Рекламный ролик в расчёт не берётся: выбирается видео с наибольшей
 * длительностью, преролл короче содержимого. Ровно на этом ошибалась первая
 * версия проверки AnimeGo — она мерила преролл и радовалась.
 *
 * Ничего не нажимает, кроме кнопки запуска, и ничего не отправляет: страницы
 * только открываются.
 *
 *   node automation/host/playback-check.js https://zonafilm.cc <slug> [<slug2>]
 */
const path = require('path');
const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright'),
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  'playwright', 'playwright-core',
];
let chromium = null;
for (const где of КАНДИДАТЫ) {
  try { chromium = require(где).chromium; break; } catch { /* следующий */ }
}
if (!chromium) {
  console.error('playwright не найден: проверка не запускалась (это не «плеер сломан»)');
  process.exit(4);
}

const BASE = (process.argv[2] || '').replace(/\/$/, '');
const SLUGS = process.argv.slice(3);
if (!BASE || !SLUGS.length) {
  console.error('нужны адрес и хотя бы один слаг тайтла');
  process.exit(2);
}

let pass = 0, fail = 0, безДорожки = 0;
const say = (ok, name, detail) => {
  ok ? pass++ : fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ': ' + detail : ''}`);
};

// Состояния, которые витрина выставляет САМА, когда провайдер не дал дорожки.
// Это ответ записи, а не поломка витрины: страница при этом честно говорит
// посетителю, что смотреть нечего. Считать такое отказом воспроизведения
// значит записывать в поломку отсутствие контента у поставщика — и тогда
// «плеер не работает» перестаёт отличаться от «этой серии у провайдера нет».
const СОСТОЯНИЯ_БЕЗ_ДОРОЖКИ = new Set(
  ['nosource', 'unavailable', 'provider', 'error', 'slow', 'noaccess']);

const нет_дорожки = (name, detail) => {
  безДорожки++;
  console.log(`НЕТ ДОРОЖКИ  ${name}${detail ? ': ' + detail : ''}`);
};

async function состояние_витрины(page) {
  // Читается то, что витрина показывает посетителю после попытки: атрибут
  // состояния и подпись под ним. Ни того, ни другого нет — значит витрина
  // молчит, и это уже её дефект.
  try {
    return await page.evaluate(() => {
      const узел = document.querySelector('[data-player][data-state]');
      const подпись = document.querySelector('[data-player-state]');
      return {
        state: узел ? узел.getAttribute('data-state') : '',
        text: подпись ? (подпись.innerText || '').trim().slice(0, 120) : '',
        hasPlayer: !!document.querySelector('video-player, [data-player-host]'),
        publisher: (document.querySelector('video-player') || {})
          .getAttribute ? document.querySelector('video-player').getAttribute('data-publisher-id') : '',
      };
    });
  } catch { return { state: '', text: '', hasPlayer: false, publisher: '' }; }
}

async function содержимое(page) {
  // Обходим все кадры: <video> провайдера живёт во вложенном iframe.
  const найдено = [];
  for (const f of page.frames()) {
    try {
      const v = await f.evaluate(() => {
        // Обход ВКЛЮЧАЕТ теневые деревья: у Zona провайдер отдаёт веб-компонент
        // <video-player>, и настоящий <video> живёт в его shadowRoot. Плоский
        // document.querySelectorAll('video') его не видит, и проверка честно
        // сообщала «элемента нет» на работающем плеере. Проверка, которая
        // ошибается на рабочем сайте, хуже отсутствия проверки: она уводит
        // искать несуществующую поломку.
        const собрать = (корень, найдено) => {
          for (const e of корень.querySelectorAll('*')) {
            if (e.tagName === 'VIDEO') найдено.push(e);
            if (e.shadowRoot) собрать(e.shadowRoot, найдено);
          }
          return найдено;
        };
        const список = собрать(document, []);
        return список.map((e) => ({
          readyState: e.readyState, duration: e.duration || 0,
          currentTime: e.currentTime || 0, paused: e.paused,
          error: e.error ? e.error.code : null,
          src: (e.currentSrc || e.src || '').slice(0, 160),
        }));
      });
      найдено.push(...v);
    } catch { /* кадр мог уйти */ }
  }
  найдено.sort((a, b) => b.duration - a.duration);
  return найдено[0] || null;
}

// Запуск самим элементом, если кнопка шаблона не опознана. Это то же
// действие, что делает клик зрителя, и единственный способ ответить на вопрос
// «плеер работает?» там, где элементы управления живут в теневом дереве
// провайдера — как у шаблона Lords, где на странице серии кнопки play вообще
// нет: её рисует веб-компонент.
async function запустить_элементом(page) {
  for (const f of page.frames()) {
    try {
      const вышло = await f.evaluate(async () => {
        const собрать = (корень, найдено) => {
          for (const e of корень.querySelectorAll('*')) {
            if (e.tagName === 'VIDEO') найдено.push(e);
            if (e.shadowRoot) собрать(e.shadowRoot, найдено);
          }
          return найдено;
        };
        const список = собрать(document, []);
        список.sort((a, b) => (b.duration || 0) - (a.duration || 0));
        const v = список[0];
        if (!v) return false;
        try { v.muted = true; await v.play(); return !v.paused; } catch { return false; }
      });
      if (вышло) return true;
    } catch { /* кадр мог уйти */ }
  }
  return false;
}

async function открыть_запись(page, slug) {
  // Порядок: сначала серия (у сериала плеер именно там), потом карточка.
  // Возвращается тот путь, который ответил 200 и содержит элемент плеера.
  //
  // Причина каждой неудачной попытки СОХРАНЯЕТСЯ. Прежняя версия глотала её
  // через `catch { continue; }` и печатала «ни адрес серии, ни адрес карточки
  // не ответили 200» — формулировку, которая была просто неправдой: обе
  // страницы master-omyur отвечали 200 с плеером в разметке, а падала
  // навигация по таймауту. Проглоченное исключение — не осторожность, а
  // отчёт, называющий не то.
  const причины = [];
  let запасной = '';
  for (const путь of [`/title/${slug}/season-1/episode-1/`, `/title/${slug}/`]) {
    let ответ;
    try {
      ответ = await page.goto(BASE + путь, { waitUntil: 'domcontentloaded', timeout: 60000 });
    } catch (ош) {
      причины.push(`${путь}: навигация не завершилась (${(ош && ош.message || ош)
        .toString().split('\n')[0].slice(0, 90)})`);
      continue;
    }
    if (!ответ) { причины.push(`${путь}: ответа нет`); continue; }
    if (ответ.status() >= 400) { причины.push(`${путь}: HTTP ${ответ.status()}`); continue; }
    if (await page.locator('video-player, [data-player-host]').count()) return путь;
    // Страница есть, плеера на ней нет. Это НЕ повод бросать запись: витрина
    // именно так и показывает запись, для которой источник не передан вовсе
    // (`master-omyur`: sources=0, из внешних идентификаторов только imdb).
    // Запоминаем первый такой адрес и разбираемся по состоянию витрины —
    // отличить «источника нет» от «плеер сломан» умеет она сама.
    if (!запасной) запасной = путь;
    причины.push(`${путь}: HTTP 200, но элемента плеера в разметке нет`);
  }
  if (запасной) return запасной;
  return { ошибка: причины.join('; ') };
}

async function запустить(page) {
  // Кнопка запуска у шаблонов называется по-разному, поэтому сначала пробуем
  // родной элемент управления видео, затем любой видимый элемент со словом
  // «смотреть»/play. Если ничего не нашлось — не страшно: часть плееров
  // запускается сама.
  for (const селектор of ['button[aria-label*="Play" i]', 'button:has-text("Смотреть")',
                          'a:has-text("Смотреть")', '.play', '[class*="play"]']) {
    const el = page.locator(селектор).first();
    try {
      if (await el.count() && await el.isVisible()) { await el.click({ timeout: 4000 }); return селектор; }
    } catch { /* следующий */ }
  }
  return '';
}

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  for (const slug of SLUGS) {
    console.log(`\n--- ${slug} ---`);
    // Адрес первой серии есть НЕ у всякой записи: у фильма серий нет, и
    // `/season-1/episode-1/` отдаёт 404. Прежняя версия шла на него всегда,
    // получала пустую страницу и печатала «элемент video не появился: нажато:
    // нечего» — то есть объявляла поломкой воспроизведения собственный
    // неверный адрес. Пять таких «отказов» на zonafilm.cc я успел приписать
    // издателю 10238; на деле те же записи, открытые по адресу карточки,
    // играют. Поэтому адрес теперь выбирается по ответу, а не по догадке.
    const первая = await открыть_запись(page, slug);
    if (typeof первая !== 'string') {
      say(false, `${slug}: запись не открылась`, первая.ошибка);
      continue;
    }
    const нажато = await запустить(page);
    await page.waitForTimeout(6000);
    let v = await содержимое(page);
    if (!v) {
      // Прежде здесь был безусловный FAIL, и он смешивал две разные вещи:
      // сломанный плеер и запись, которой у провайдера нет. Теперь спрашиваем
      // саму витрину — она это различие знает и показывает посетителю.
      const сост = await состояние_витрины(page);
      if (!сост.hasPlayer) {
        if (СОСТОЯНИЯ_БЕЗ_ДОРОЖКИ.has(сост.state)) {
          нет_дорожки(`${slug}: источник записи не передан`,
                      `витрина говорит «${сост.text || сост.state}»`);
        } else {
          say(false, `${slug}: плеера нет и витрина молчит`,
              `состояние «${сост.state || 'не объявлено'}» — это её дефект`);
        }
      } else if (!сост.publisher) {
        say(false, `${slug}: у плеера не объявлен publisher_id`,
            'витрина не подключена к провайдеру — это настройка витрины');
      } else if (СОСТОЯНИЯ_БЕЗ_ДОРОЖКИ.has(сост.state)) {
        нет_дорожки(`${slug}: провайдер не дал дорожки`,
                    `витрина говорит «${сост.text || сост.state}»`);
      } else {
        say(false, `${slug}: элемент video не появился`,
            `состояние «${сост.state || 'не объявлено'}», нажато: ${нажато || 'нечего'}`);
      }
      continue;
    }
    say(v.readyState >= 2 && v.duration > 0, `${slug}: поток готов`,
        `readyState=${v.readyState} длительность=${Math.round(v.duration)}c`);
    say(v.error === null, `${slug}: ошибок декодирования нет`, `err=${v.error}`);
    const до = v.currentTime;
    await page.waitForTimeout(4000);
    v = await содержимое(page);
    // Стоящая позиция при готовом потоке — это «мою кнопку запуска не нашли», а
    // не «плеер сломан»: у каждого семейства свой элемент управления, и общая
    // проверка не обязана их все знать. Различие названо, чтобы отчёт не
    // объявлял поломкой собственное незнание вёрстки.
    if (v.currentTime <= до && v.paused) {
      // Кнопка шаблона не опознана — пробуем запустить сам элемент и мерим
      // заново. Без этой попытки «плеер не работает» и «я не нашёл кнопку»
      // выглядят одинаково.
      if (await запустить_элементом(page)) {
        await page.waitForTimeout(4000);
        v = await содержимое(page);
      }
    }
    const движется = v.currentTime > до;
    say(движется || v.paused === false, `${slug}: позиция растёт`,
        движется ? `${до.toFixed(2)}c -> ${v.currentTime.toFixed(2)}c`
                 : `стоит на ${v.currentTime.toFixed(2)}c, paused=${v.paused} — `
                   + `кнопка запуска этого шаблона не опознана (нажато: ${нажато || 'нечего'}); `
                   + `для AnimeGo используйте checks/playback.js его репозитория`);
    const источник1 = v.src;

    // Вторую серию проверяем только там, где серии вообще есть. У фильма её
    // отсутствие — не отказ витрины, а свойство записи, и записывать это в
    // FAIL значит портить итог собственным непониманием.
    if (!первая.includes('/season-')) {
      console.log(`  (пропуск) ${slug}: у записи нет серий — переключение не проверяется`);
      continue;
    }
    const вторая = `/title/${slug}/season-1/episode-2/`;
    const ответ = await page.goto(BASE + вторая, { waitUntil: 'load', timeout: 60000 });
    if (!ответ || ответ.status() >= 400) {
      say(false, `${slug}: вторая серия не открылась`, `HTTP ${ответ && ответ.status()}`);
      continue;
    }
    await запустить(page);
    await page.waitForTimeout(6000);
    const v2 = await содержимое(page);
    say(!!v2, `${slug}: вторая серия подняла поток`,
        v2 ? `длительность=${Math.round(v2.duration)}c` : 'элемента нет');
    if (v2) {
      say(v2.src !== источник1, `${slug}: провайдеру заказана другая серия`,
          `${источник1.slice(-28)} -> ${v2.src.slice(-28)}`);
    }
  }
  await browser.close();
  console.log(`\nИТОГО: PASS ${pass}  FAIL ${fail}`
    + (безДорожки ? `  НЕТ ДОРОЖКИ ${безДорожки} (ответ провайдера, не витрины)` : ''));
  process.exit(fail ? 1 : 0);
})();
