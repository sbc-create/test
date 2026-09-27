/**
 * Фактическая отправка просмотра в Метрику — настоящим браузером.
 *
 * Зачем не разметка. Наличие `ym(id,"init")` в HTML доказывает, что код на
 * странице есть, и ничего не говорит о том, ушёл ли запрос: скрипт счётчика
 * может не загрузиться (блокировка, CSP, обрыв), инициализация может упасть на
 * предыдущей ошибке JS, идентификатор может оказаться чужим. Поэтому здесь
 * перехватываются исходящие запросы и проверяется тот, который Метрика
 * отправляет при просмотре: GET на mc.yandex.ru/watch/<id>.
 *
 * Что считается доказательством отправки:
 *   1. запрос на mc.yandex.ru/watch/<ожидаемый id> состоялся;
 *   2. в его параметрах адрес страницы совпадает с открытой;
 *   3. ответ получен (статус 200/302) — то есть запрос не был оборван;
 *   4. запросов ровно один на просмотр: два означали бы двойной учёт.
 *
 * Чего проверка НЕ доказывает: что данные видны в кабинете. Между успешной
 * отправкой и появлением визита в отчёте стоит обработка на стороне Яндекса,
 * и увидеть её результат можно только чтением статистики по OAuth.
 *
 * Аргументы:
 *   --urls <json>   [{url, counter, name}]
 *   --out <json>    куда записать отчёт
 *   --timeout мс    сколько ждать запроса счётчика (по умолчанию 15000)
 */
const fs = require('fs');
const path = require('path');

const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  '/home/claude/node_modules/playwright-core',
];
let chromium = null;
for (const к of КАНДИДАТЫ) {
  try { chromium = require(к).chromium; break; } catch (e) { /* следующий */ }
}
if (!chromium) { console.error('playwright-core не найден'); process.exit(2); }

function arg(имя, по) { const i = process.argv.indexOf(имя); return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : по; }

const МАРКЕР = /^https?:\/\/mc\.yandex\.(?:ru|com)\/watch\/(\d+)/;

async function проверить(браузер, цель, таймаут) {
  const контекст = await браузер.newContext({
    viewport: { width: 1440, height: 900 },
    // Заголовок Do-Not-Track не ставим: он менял бы поведение счётчика, и
    // измерялась бы не та конфигурация, которую видит посетитель.
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36',
  });
  const страница = await контекст.newPage();
  const запросы = [];
  const ошибкиJS = [];

  страница.on('request', (req) => {
    const м = МАРКЕР.exec(req.url());
    if (!м) return;
    // Перенаправление — это ТОТ ЖЕ запрос, а не второй. Метрика отвечает на
    // /watch/<id> кодом 302 и ведёт на свой же адрес синхронизации, поэтому
    // событие request приходит дважды на одну отправку. Первая версия
    // проверки считала их двумя и объявила двойной учёт на всех 25 страницах
    // четырёх разных семейств — одинаковость картины и была подсказкой, что
    // ошибка в измерении, а не на сайтах.
    запросы.push({
      id: м[1],
      url: req.url(),
      метод: req.method(),
      статус: null,
      продолжение: req.redirectedFrom() !== null,
    });
  });
  страница.on('response', async (res) => {
    const м = МАРКЕР.exec(res.url());
    if (!м) return;
    const запись = запросы.find((з) => з.url === res.url() && з.статус === null);
    if (запись) запись.статус = res.status();
  });
  страница.on('pageerror', (e) => ошибкиJS.push(String(e).slice(0, 200)));

  let навигация = null;
  try {
    const ответ = await страница.goto(цель.url, { waitUntil: 'load', timeout: таймаут });
    навигация = ответ ? ответ.status() : null;
  } catch (e) {
    await контекст.close();
    return { ...цель, ошибка: `навигация: ${String(e).slice(0, 160)}` };
  }

  // Ждём именно запрос счётчика, а не фиксированную паузу: счётчик уходит
  // асинхронно после загрузки, и пауза «на всякий случай» либо коротка, либо
  // тратит время на каждой странице.
  try {
    await страница.waitForRequest((req) => МАРКЕР.test(req.url()), { timeout: таймаут });
  } catch (e) { /* ниже это станет «отправки нет» */ }
  await страница.waitForTimeout(1200);

  const build = навигация !== null
    ? await страница.evaluate(() => {
        const м = document.querySelector('meta[name="site-factory-build-id"]');
        return м ? м.content : null;
      }).catch(() => null)
    : null;

  await контекст.close();

  const свои = запросы.filter((з) => з.id === String(цель.counter) && !з.продолжение);
  const продолжения = запросы.filter((з) => з.id === String(цель.counter) && з.продолжение);
  const чужие = запросы.filter((з) => з.id !== String(цель.counter));
  const адресВПараметрах = свои.some((з) => {
    try {
      const u = new URL(з.url);
      const где = u.searchParams.get('ut') === null ? (u.searchParams.get('rn'), null) : null;
      const ref = u.searchParams.get('ur') || u.searchParams.get('u') || '';
      return ref.includes(new URL(цель.url).hostname) || u.search.includes(encodeURIComponent(new URL(цель.url).pathname));
    } catch (e) { return false; }
  });

  return {
    ...цель,
    навигация,
    build_id: build,
    отправок: свои.length,
    перенаправлений: продолжения.length,
    статусы: свои.map((з) => з.статус),
    статусы_продолжений: продолжения.map((з) => з.статус),
    чужих_счётчиков: чужие.map((з) => з.id),
    адрес_в_параметрах: адресВПараметрах,
    ошибки_js: ошибкиJS,
    // Однократность просмотра доказывается разметкой (одна инициализация на
    // страницу, metrika-audit.py). Сеть доказывает другое: что отправка
    // ДОШЛА. Обращений к /watch/ на странице с настроенными целями больше
    // одного — это события целей, и объявлять их двойным учётом неверно.
    вердикт: свои.length === 0 ? 'ОТПРАВКИ НЕТ'
      : чужие.length ? 'ЕСТЬ ЧУЖОЙ СЧЁТЧИК'
      : свои.some((з) => з.статус === null) ? 'ЗАПРОС БЕЗ ОТВЕТА'
      : свои.some((з) => з.статус >= 400) ? `ОТВЕТ ${свои.map((з) => з.статус).join(',')}`
      : 'отправлено',
  };
}

(async () => {
  const цели = JSON.parse(arg('--urls', '[]'));
  const таймаут = Number(arg('--timeout', '15000'));
  if (!цели.length) { console.error('нужен --urls'); process.exit(2); }
  const браузер = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const итог = [];
  for (const цель of цели) {
    const строка = await проверить(браузер, цель, таймаут);
    итог.push(строка);
    const имя = (цель.name || цель.url).slice(0, 44);
    console.log(
      `${имя.padEnd(46)} счётчик ${String(цель.counter).padEnd(10)} ` +
      `обращений ${строка.отправок ?? '-'} (+${строка.перенаправлений ?? 0} перенаправлений) ` +
      `статусы ${JSON.stringify(строка.статусы ?? [])} ` +
      `${строка.вердикт || строка.ошибка}`,
    );
  }
  await браузер.close();
  const куда = arg('--out', '');
  if (куда) fs.writeFileSync(куда, JSON.stringify({ checks: итог }, null, 2));
  const плохо = итог.filter((с) => с.вердикт !== 'отправлено');
  console.log(`\nстраниц с подтверждённой отправкой: ${итог.length - плохо.length} из ${итог.length}`);
  process.exit(плохо.length ? 1 : 0);
})();
