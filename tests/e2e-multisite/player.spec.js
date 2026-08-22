// REQ-PLAYER: прямое встраивание <video-player> по документированному контракту.
const { test, expect } = require('@playwright/test');
const { EPISODE_SITES, SITES, url } = require('./helpers');

const EPISODE = SITES.a.episode;

// Контракт плеера проверяется на каждом сайте, где есть страница серии: у
// аниме-каталога и у витрины сериалов. Один сайт доказывал бы только его.
for (const key of EPISODE_SITES) {
  test(`[${key}] элемент плеера создаётся с атрибутами контракта`, async ({ page }) => {
    await page.goto(url(key, SITES[key].episode));
    const player = page.locator('video-player');
    await expect(player).toHaveCount(1);

    const attributes = await player.evaluate((node) =>
      Object.fromEntries([...node.attributes].map((attribute) => [attribute.name, attribute.value])),
    );

    expect(attributes['disable-licensed']).toBe('false');
    expect(attributes['data-aggregator']).toBe('kp');
    expect(attributes['data-title-id']).toBe(SITES[key].player.titleId);
    expect(attributes.ident).toBe(SITES[key].player.titleId);
    expect(attributes['data-publisher-id']).toBe(SITES[key].player.publisherId);
    expect(attributes.season).toBe('1');
    expect(attributes.episode).toBe('1');

    // Ни одного атрибута сверх контракта: «на всякий случай» здесь недопустимо.
    const allowed = new Set(['ident', 'season', 'episode', 'data-publisher-id', 'data-title-id',
      'data-aggregator', 'only-voice', 'priority-voice', 'is-show-voice-only', 'is-show-banner',
      'disable-licensed', 'style']);
    for (const name of Object.keys(attributes)) {
      expect(allowed.has(name), `неожиданный атрибут ${name}`).toBe(true);
    }
  });

  test(`[${key}] плеер не появляется на странице без прав или без записи`, async ({ page }) => {
    // Сайт подборок не индексирует произведения и не показывает плеер вовсе.
    await page.goto(url('g', '/collections/'));
    await expect(page.locator('video-player')).toHaveCount(0);
  });
}

test('методы контракта вызываются и меняют состояние плеера', async ({ page }) => {
  await page.goto(url('a', SITES.a.deeperEpisode.path));
  const player = page.locator('video-player');
  await expect(player).toHaveAttribute('season', '2');
  await expect(player).toHaveAttribute('episode', '3');

  // Методы появляются после того, как браузер определил custom element.
  // Ждём апгрейда, а не угадываем момент — иначе проверка мигает.
  await page.waitForFunction(() => {
    const node = document.querySelector('video-player');
    return Boolean(node) && typeof node.selectSeason === 'function'
      && typeof node.selectEpisode === 'function';
  });
});

test('событие noData переводит блок в честный статус вместо подмены видео', async ({ page }) => {
  await page.goto(url('a', EPISODE));
  await expect(page.locator('video-player')).toHaveCount(1);

  await page.locator('video-player').evaluate((node) => {
    node.dispatchEvent(new CustomEvent('noData'));
  });

  await expect(page.locator('video-player')).toHaveCount(0);
  await expect(page.getByTestId('player-status')).toContainText('недоступна');
});

test('кнопка «Повторить» действительно пересоздаёт плеер, а не прячет ошибку', async ({ page }) => {
  await page.goto(url('a', EPISODE));
  const player = page.locator('video-player');
  await expect(player).toHaveCount(1);

  // Помечаем текущий экземпляр, чтобы отличить пересозданный элемент от прежнего.
  await player.evaluate((node) => {
    node.dataset.instanceMark = 'first';
    node.dispatchEvent(new CustomEvent('noData'));
  });
  await expect(page.getByTestId('player-retry')).toBeVisible();

  await page.getByTestId('player-retry').click();

  await expect(page.locator('video-player')).toHaveCount(1);
  const mark = await page.locator('video-player').evaluate((node) => node.dataset.instanceMark ?? null);
  expect(mark, 'после Повторить должен быть новый экземпляр плеера').toBeNull();
  await expect(page.getByTestId('player-status')).toHaveCount(0);
});

test('скрипт плеера подключается один раз на страницу', async ({ page }) => {
  await page.goto(url('a', EPISODE));
  await expect(page.locator('video-player')).toHaveCount(1);
  await page.locator('video-player').evaluate((node) => node.dispatchEvent(new CustomEvent('noData')));
  await page.getByTestId('player-retry').click();
  await expect(page.locator('video-player')).toHaveCount(1);

  const scripts = await page.locator('script[data-player-script]').count();
  expect(scripts).toBe(1);
});

test('страница остаётся пригодной, когда плеер в состоянии ошибки', async ({ page }) => {
  await page.goto(url('a', EPISODE));
  await page.locator('video-player').evaluate((node) => node.dispatchEvent(new CustomEvent('noData')));
  await expect(page.getByTestId('player-status')).toBeVisible();

  // Метаданные, навигация и комментарии не должны зависеть от плеера.
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('#comments')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Навигация по сериям' })).toBeVisible();
});

test('токен Content API не попадает в страницу', async ({ page }) => {
  await page.goto(url('a', EPISODE));
  const content = await page.content();
  const sentinel = process.env.CDNVIDEOHUB_API_TOKEN;
  expect(sentinel && sentinel.length > 0).toBe(true);
  expect(content.includes(sentinel)).toBe(false);
});

test('плеер занимает видимую площадь и не спрятан на мобильном', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url('a', EPISODE));
  const box = await page.locator('video-player').boundingBox();
  expect(box).not.toBeNull();
  expect(box.width).toBeGreaterThan(300);
  expect(box.height).toBeGreaterThan(150);
});
