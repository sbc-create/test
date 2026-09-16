// Браузерная приёмка центра управления: роли, ширины, клавиатура.
//
// Проверяется не «кнопки не видно», а серверный отказ: скрытая кнопка защищает
// от случайного нажатия, а не от того, кто ввёл адрес руками.
const path = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium, firefox } = require(path);

const БАЗА = process.argv[2];
const ДВИЖОК = process.argv[3] || 'both';
const ПАРОЛЬ = process.env.STAND_PASSWORD || 'длинный-пароль-для-проверки-1';

let провалов = 0;
const проверить = (у, ч) => {
  if (!у) { провалов++; console.log(`  FAIL ${ч}`); } else console.log(`  PASS ${ч}`);
};

async function войти(ctx, email, база) {
  const p = await ctx.newPage();
  await p.goto(`${база}/admin`, { waitUntil: 'domcontentloaded' });
  await p.fill('input[name="email"]', email);
  await p.fill('input[name="password"]', ПАРОЛЬ);
  await p.locator('input[name="password"]').press('Enter');
  await p.waitForLoadState('domcontentloaded');
  return p;
}

async function прогон(движок, имя) {
  const b = await движок.launch({ args: ['--no-sandbox'] });
  console.log(`\n### движок ${имя}`);

  // --- супер-администратор ---
  const супер = await войти(await b.newContext(), 'super@test', БАЗА);
  await супер.goto(`${БАЗА}/admin/fleet`, { waitUntil: 'domcontentloaded' });
  const флот = await супер.content();
  проверить(флот.includes('Центр управления') || флот.includes('Флот'),
            'супер-администратор открывает флот');
  проверить(флот.includes('lords-01') && флот.includes('lords-02'),
            'во флоте видны обе витрины');
  проверить(флот.includes('не подключено') || флот.includes('не спрашивали'),
            'неизвестное подписано словами, а не пустой ячейкой');
  проверить(/источник|site-profile|release-manifest|observations/.test(флот),
            'у показателей виден источник');

  await супер.goto(`${БАЗА}/admin/templates`, { waitUntil: 'domcontentloaded' });
  проверить((await супер.content()).includes('Реестр шаблонов'), 'экран шаблонов открывается');
  await супер.goto(`${БАЗА}/admin/analytics`, { waitUntil: 'domcontentloaded' });
  const аналитика = await супер.content();
  проверить(аналитика.includes('Аналитика') && аналитика.includes('SEO'),
            'экран аналитики и SEO открывается');
  проверить(аналитика.includes('ИКС'), 'ИКС на экране, а не устаревший ТИЦ');

  // --- ширины и отсутствие горизонтальной прокрутки ---
  for (const [ш, в, подпись] of [[390, 780, '390px'], [768, 1024, '768px'],
                                 [1440, 900, '1440px']]) {
    const c = await b.newContext({ viewport: { width: ш, height: в } });
    const s = await войти(c, 'super@test', БАЗА);
    for (const адрес of ['/admin/fleet', '/admin/templates', '/admin/analytics']) {
      await s.goto(`${БАЗА}${адрес}`, { waitUntil: 'domcontentloaded' });
      const беда = await s.evaluate(() => {
        const ш2 = document.documentElement.clientWidth;
        for (const el of document.querySelectorAll('body *')) {
          const r = el.getBoundingClientRect();
          if (r.width > ш2 + 1 && !el.closest('.scroll-x')) return el.tagName + '.' + el.className;
        }
        return '';
      });
      проверить(беда === '', `${подпись} ${адрес}${беда ? ': ' + беда : ''}`);
    }
    await c.close();
  }

  // --- клавиатура ---
  await супер.goto(`${БАЗА}/admin/fleet`, { waitUntil: 'domcontentloaded' });
  await супер.keyboard.press('Tab');
  const первый = await супер.evaluate(() => document.activeElement
    && (document.activeElement.getAttribute('href') || document.activeElement.tagName));
  проверить(!!первый, 'первый Tab попадает на управляемый элемент');

  // --- местный администратор витрины ---
  const местный = await войти(await b.newContext(), 'admin-lords-01@test',
                              `${БАЗА}/s/lords-01`);
  const домашняя = await местный.content();
  проверить(домашняя.includes('Выйти'), 'местный администратор вошёл в свой контур');
  проверить(!домашняя.includes('/admin/fleet'), 'из контура витрины ссылки на флот нет');
  const ответ = await местный.goto(`${БАЗА}/admin/fleet`, { waitUntil: 'domcontentloaded' });
  проверить(ответ.status() === 403 || (await местный.content()).includes('password'),
            'флот по прямому адресу закрыт серверным отказом, а не скрытой кнопкой');

  // --- читатель ---
  const читатель = await войти(await b.newContext(), 'viewer-lords-01@test',
                               `${БАЗА}/s/lords-01`);
  await читатель.goto(`${БАЗА}/s/lords-01/admin/settings`, { waitUntil: 'domcontentloaded' });
  const у_читателя = await читатель.content();
  проверить(!у_читателя.includes('method="post" action="/s/lords-01/admin/settings"'),
            'у читателя нет отправляемых форм настроек');

  // --- без входа ---
  const гость = await (await b.newContext()).newPage();
  await гость.goto(`${БАЗА}/admin/fleet`, { waitUntil: 'domcontentloaded' });
  const у_гостя = await гость.content();
  проверить(у_гостя.includes('name="password"'), 'без входа предлагается вход, а не флот');
  проверить(!у_гостя.includes('lords-02'), 'без входа состав флота не виден');

  await b.close();
}

(async () => {
  if (!БАЗА) { console.log('нужен адрес'); process.exit(2); }
  if (ДВИЖОК === 'chromium' || ДВИЖОК === 'both') await прогон(chromium, 'chromium');
  if (ДВИЖОК === 'firefox' || ДВИЖОК === 'both') await прогон(firefox, 'firefox');
  console.log(`\nпровалов: ${провалов}`);
  process.exit(провалов === 0 ? 0 : 1);
})();
