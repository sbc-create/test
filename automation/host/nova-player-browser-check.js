/**
 * Браузерная проверка плеера: инициализация, консоль, сеть, вёрстка.
 *
 * Наличие блока «Просмотр» за работу не считается. Требуется, чтобы кастомный
 * элемент провайдера действительно поднялся (customElements его знает и внутри
 * появилось содержимое), чтобы в консоли не было ошибок плеера и провайдера,
 * чтобы сетевые запросы к провайдеру не падали, и чтобы элемент не вылезал за
 * свой контейнер ни на десктопе, ни на телефоне.
 *
 * Аргументы: --urls <file.json> [--out <file.json>]
 */
const path = require('path');
const fs = require('fs');
// playwright-core установлен не в репозитории, а в домашнем каталоге учётной
// записи. Путь ищется, а не угадывается: иначе проверка молча не запускается.
const КАНДИДАТЫ = [
  path.join('/srv/site-factory/repo', 'node_modules', 'playwright-core'),
  '/home/claude/node_modules/playwright-core',
];
let chromium = null;
for (const к of КАНДИДАТЫ) {
  try { chromium = require(к).chromium; break; } catch (e) { /* следующий */ }
}
if (!chromium) { console.error('playwright-core не найден:', КАНДИДАТЫ.join(', ')); process.exit(2); }

function arg(name, fb = null) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fb;
}

const ВИДЫ = [
  { имя: 'desktop', viewport: { width: 1366, height: 900 }, isMobile: false },
  { имя: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    deviceScaleFactor: 3, hasTouch: true },
];

// Шум, не относящийся к плееру: реклама и счётчики к предмету проверки не относятся.
const ПОСТОРОННЕЕ = /googlesyndication|adsbygoogle|mc\.yandex|metrika|telecid|doubleclick|autonews\.blog|justtalks|kinotrap/i;
const ПРОВАЙДЕР = /cdnvideohub/i;

// SDK прогревает соединение запросом к голому origin и обрывает его, как только
// TCP+TLS установлены. В журнале это выглядит как ERR_ABORTED, хотя тот же URL
// секундой раньше ответил 200, а все последующие вызовы API проходят. Считать
// это отказом плеера — значит завалить проверку на здоровом поведении провайдера.
const ПРОГРЕВ = /^https:\/\/plapi\.cdnvideohub\.com\/?$/;

// Признаки того, что провайдер реально отдал контент, а не только поднял рамку.
const ПЛЕЙЛИСТ = /\/player\/sv\/playlist/;
const РАМКА = /\/s2\/[^/]+\/frame\/?$/;
const ВИДЕО = /\/player\/sv\/video\//;

(async () => {
  const urls = JSON.parse(fs.readFileSync(arg('--urls'), 'utf8'));
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const итог = [];

  for (const вид of ВИДЫ) {
    const ctx = await browser.newContext({
      viewport: вид.viewport, isMobile: вид.isMobile || false,
      userAgent: вид.userAgent, deviceScaleFactor: вид.deviceScaleFactor,
      hasTouch: вид.hasTouch || false,
    });
    for (const u of urls) {
      const page = await ctx.newPage();
      const консоль = [];
      const сеть = [];
      page.on('console', (m) => {
        if (m.type() === 'error' && !ПОСТОРОННЕЕ.test(m.text())) консоль.push(m.text().slice(0, 300));
      });
      const успехи = [];
      page.on('requestfailed', (r) => {
        if (ПОСТОРОННЕЕ.test(r.url()) || ПРОГРЕВ.test(r.url())) return;
        сеть.push(`FAILED ${r.url().slice(0, 160)} ${(r.failure() || {}).errorText || ''}`);
      });
      page.on('response', (r) => {
        const u = r.url();
        if (r.status() === 200 && ПРОВАЙДЕР.test(u)) успехи.push(u);
        if (r.status() >= 400 && !ПОСТОРОННЕЕ.test(u)) сеть.push(`HTTP ${r.status()} ${u.slice(0, 160)}`);
      });

      const строка = { url: u, viewport: вид.имя };
      try {
        await page.goto(u, { waitUntil: 'domcontentloaded', timeout: 60000 });
        // Плеер поднимается скриптом провайдера: ждём именно его готовности,
        // а не произвольной паузы.
        await page.waitForSelector('video-player', { timeout: 30000 });
        // Ответ плейлиста нередко приходит раньше, чем на него успевают подписаться,
        // поэтому ждём не событие, а накопленный слушателем список: он заведён до
        // перехода и гонки с ним нет.
        const ждать = async (пред, мс) => {
          const предел = Date.now() + мс;
          while (Date.now() < предел) {
            if (пред()) return true;
            await page.waitForTimeout(500);
          }
          return false;
        };
        await ждать(() => успехи.some((u) => ПЛЕЙЛИСТ.test(u)), 45000);
        await ждать(() => успехи.some((u) => РАМКА.test(u)), 30000);
        await page.waitForFunction(
          () => {
            const el = document.querySelector('video-player');
            if (!el || !window.customElements || !customElements.get('video-player')) return false;
            const внутри = (el.shadowRoot && el.shadowRoot.childElementCount > 0) || el.childElementCount > 0;
            return внутри;
          }, { timeout: 45000 });

        const данные = await page.evaluate(() => {
          const el = document.querySelector('video-player');
          const рамка = el.closest('[data-player]') || el.parentElement;
          const a = el.getBoundingClientRect();
          const b = рамка.getBoundingClientRect();
          const корень = el.shadowRoot || el;
          return {
            upgraded: !!customElements.get('video-player'),
            children: (el.shadowRoot ? el.shadowRoot.childElementCount : el.childElementCount),
            hasMedia: !!корень.querySelector('video, iframe, canvas'),
            elW: Math.round(a.width), elH: Math.round(a.height),
            boxW: Math.round(b.width),
            docW: Math.round(document.documentElement.clientWidth),
            scrollW: Math.round(document.documentElement.scrollWidth),
            state: (document.querySelector('[data-player]') || {}).getAttribute
              ? document.querySelector('[data-player]').getAttribute('data-state') : null,
          };
        });
        Object.assign(строка, данные);
        // Предмет проверки — плеер, а не вся страница. Эти два переполнения разные:
        // на 1lordserials1.online страница шире вьюпорта на 6 px из-за `div.backdrop`
        // в шапке, и это видно одинаково на карточке с плеером и на карточке без
        // него. Записывать чужую вёрстку в отказ плеера неверно, а править её здесь
        // нельзя: это выход за player-контур.
        строка.player_overflow = данные.elW > данные.boxW + 2;
        строка.page_overflow_px = Math.max(0, данные.scrollW - данные.docW);
        строка.overflow = строка.player_overflow;
        строка.console_errors = консоль;
        строка.network_errors = сеть;
        строка.provider_errors = сеть.filter((x) => ПРОВАЙДЕР.test(x));
        строка.playlist_200 = успехи.some((u) => ПЛЕЙЛИСТ.test(u));
        строка.frame_200 = успехи.some((u) => РАМКА.test(u));
        строка.video_200 = успехи.some((u) => ВИДЕО.test(u));
        строка.result =
          данные.upgraded && данные.children > 0 && данные.hasMedia &&
          строка.playlist_200 && строка.frame_200 &&
          !строка.player_overflow && консоль.length === 0 && строка.provider_errors.length === 0
            ? 'PLAYER_INIT_OK' : 'PLAYER_INIT_PROBLEM';
      } catch (e) {
        строка.result = 'PLAYER_INIT_PROBLEM';
        строка.error = String(e).slice(0, 300);
        строка.console_errors = консоль;
        строка.network_errors = сеть;
      }
      итог.push(строка);
      console.log(`${строка.result}  ${вид.имя.padEnd(7)} ${u}  el=${строка.elW}x${строка.elH} box=${строка.boxW} media=${строка.hasMedia} console=${(строка.console_errors || []).length} net=${(строка.network_errors || []).length} playlist=${строка.playlist_200} frame=${строка.frame_200} fits=${!строка.player_overflow} pageovf=${строка.page_overflow_px}px`);
      if ((строка.console_errors || []).length) console.log('     console:', строка.console_errors.slice(0, 3));
      if ((строка.network_errors || []).length) console.log('     network:', строка.network_errors.slice(0, 3));
      if (строка.error) console.log('     error:', строка.error);
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
  if (arg('--out')) fs.writeFileSync(arg('--out'), JSON.stringify(итог, null, 1));
  const ок = итог.filter((r) => r.result === 'PLAYER_INIT_OK').length;
  console.log(`\nPLAYER_INIT_OK=${ок}/${итог.length}`);
  process.exit(ок === итог.length ? 0 : 1);
})();
