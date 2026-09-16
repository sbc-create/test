// Потребление контракта `site-admin/1.0.0` слоем шаблонов.
//
// Движок админки и сам контракт принадлежат Core и сюда не копируются. Здесь
// проверяется ровно то, что принадлежит шаблонам: что отданное админкой
// доходит до страницы, что витрины не видят настроек друг друга и что
// незаполненное поле не подменяется выдуманным значением.
//
// Почему это не мелочь. Имена полей живут в компонентах строками. Переименуй
// поле в админке — и витрина покажет пустоту вместо текста, молча: ни ошибки
// сборки, ни падения, только исчезнувший абзац. Проверка обязана заметить это
// раньше зрителя.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const STAND = path.join(__dirname, '..', '..', 'blueprints', 'payload-next-multisite',
  'app', 'var', 'family-stand');
const OUT = path.join(__dirname, '..', '..', 'artifacts', 'evidence', 'templates');
fs.mkdirSync(OUT, { recursive: true });

const index = JSON.parse(fs.readFileSync(path.join(STAND, 'index.json'), 'utf8'));
const FAMILIES = index.families;
const TENANTS = index.tenants;

const url = (family, suffix) =>
  `file://${path.join(STAND, suffix ? `${family}-${suffix}.html` : `${family}.html`)}`;

const collected = { captured_at_utc: null, consumption: [], isolation: [] };

function save() {
  const file = path.join(OUT, 'admin-contract.json');
  let previous = { consumption: [], isolation: [] };
  try {
    previous = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch { /* первый работник */ }
  fs.writeFileSync(file, `${JSON.stringify({
    captured_at_utc: new Date().toISOString(),
    contract: 'site-admin/1.0.0',
    consumed_settings: index.consumedSettings,
    consumption: [...(previous.consumption || []), ...collected.consumption],
    isolation: [...(previous.isolation || []), ...collected.isolation],
  }, null, 2)}\n`);
}

test.describe('отданное админкой доходит до страницы', () => {
  for (const family of FAMILIES) {
    for (const key of Object.keys(TENANTS)) {
      const tenant = TENANTS[key];
      test(`${family}/${tenant.suffix}: настройки и навигация витрины видны`, async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(url(family, tenant.suffix), { waitUntil: 'load' });
        const body = await page.evaluate(() => document.body.innerText);
        const navTexts = await page.locator('.site-header a').allInnerTexts();

        collected.consumption.push({
          family, tenant: tenant.suffix,
          navigation: navTexts.map((t) => t.trim()).filter(Boolean),
          rightsNoticeVisible: body.includes(tenant.rightsNotice),
        });
        save();

        expect(body, `${family}/${tenant.suffix}: примечание о правах не выведено`)
          .toContain(tenant.rightsNotice);
        for (const item of tenant.nav) {
          expect(navTexts.join(' | '),
            `${family}/${tenant.suffix}: пункт «${item}» не выведен`).toContain(item);
        }
      });
    }
  }
});

test.describe('витрины не видят друг друга', () => {
  for (const family of FAMILIES) {
    test(`${family}: настройки соседней витрины на страницу не попадают`, async ({ page }) => {
      const seen = {};
      for (const key of Object.keys(TENANTS)) {
        await page.goto(url(family, TENANTS[key].suffix), { waitUntil: 'load' });
        seen[key] = await page.evaluate(() => ({
          // Навигация сравнивается по своей области, а не по всему тексту
          // страницы: заголовок раздела и хлебные крошки стенда содержат слово
          // «Каталог» всегда, и сравнение по документу целиком объявляло
          // утечкой обычную шапку страницы.
          nav: [...document.querySelectorAll('.site-header a')].map((a) => a.textContent.trim()),
          text: document.body.innerText,
        }));
      }
      const leaks = [];
      for (const [key, page_] of Object.entries(seen)) {
        for (const [other, data] of Object.entries(TENANTS)) {
          if (other === key) continue;
          if (page_.text.includes(data.rightsNotice)) {
            leaks.push(`${key} показывает права витрины ${other}`);
          }
          for (const item of data.nav) {
            // Пункт соседа считается утечкой, только если его нет у самой
            // витрины: совпадающее название — не утечка, а совпадение.
            if (!TENANTS[key].nav.includes(item) && page_.nav.includes(item)) {
              leaks.push(`${key} показывает пункт «${item}» витрины ${other}`);
            }
          }
        }
      }
      collected.isolation.push({ family, leaks });
      save();
      expect(leaks, `${family}: утечка между витринами`).toEqual([]);
    });
  }
});

test.describe('незаполненная настройка не подменяется выдумкой', () => {
  for (const family of FAMILIES) {
    test(`${family}: без настроек витрина не сочиняет текст`, async ({ page }) => {
      // Страница без суффикса собрана с `settings: null` — так выглядит витрина,
      // у которой оператор ещё ничего не заполнил.
      await page.goto(url(family, null), { waitUntil: 'load' });
      const body = await page.evaluate(() => document.body.innerText);
      for (const key of Object.keys(TENANTS)) {
        expect(body, `${family}: показан текст витрины ${key} при пустых настройках`)
          .not.toContain(TENANTS[key].rightsNotice);
      }
      // Страница обязана остаться пригодной: пустая настройка — не повод
      // отдавать пустую страницу.
      expect(await page.locator('.card').count(),
        `${family}: без настроек пропало содержимое`).toBeGreaterThan(0);
    });
  }
});
