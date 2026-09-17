/*
 * Измерение порядка секций и однозначного выбора основной сетки контента.
 *
 * Отдельный инструмент рядом с measure_reference.js и measure_reference_colors.js,
 * а не правка первого: тем уже сняты зафиксированные пакеты, и менять его
 * состав задним числом значило бы поменять смысл чужих дайджестов.
 *
 * Два измерения:
 *
 * structure_order — устойчивые семантические роли видимых секций верхнего
 * уровня, а не случайные CSS-классы: ARIA `role`, семантический тег
 * (header/nav/footer/aside/main/form) или признак по составу потомков
 * (заголовок/плеер/сетка ссылок с картинками/форма). Родовой блок без этих
 * признаков получает `section`. Скрытые узлы исключены (display:none,
 * visibility:hidden, нулевой размер, aria-hidden="true", смещение за экран на
 * -1000px и дальше) — этим же и снимается дубль мобильной и десктопной
 * навигации: на конкретной ширине через media query виден только один
 * вариант, и только он попадает в список.
 *
 * Контейнер секций ищется структурно, а не по тегу `<main>`: у amd.online
 * `<main>` — это только левая колонка вёрстки (`class="cols__left"`), и её
 * единственный видимый потомок — один блок, а не список секций. Вместо
 * фиксированного тега алгоритм спускается от `<body>` вниз по «сквозным
 * обёрткам»: пока у текущего узла ровно один видимый потомок — спуск
 * продолжается; если потомков несколько и один занимает >70% суммарного
 * числа DOM-узлов среди них (число потомков, а не высота: у закрытых
 * оверлеев вроде мобильного меню высота бокса может быть не нулевой при
 * пустом содержимом), спуск идёт в него. Останавливается на первом узле,
 * где такого явного доминирования нет, — это и есть список секций. Признак
 * структурный (размер поддерева), а не имя класса: код нигде не сравнивает
 * className.
 *
 * primaryGrid — вместо первого найденного grid-контейнера (порядок обхода
 * DOM не гарантирует «главный») выбирается контейнер с наибольшей видимой
 * площадью среди всех display:grid, исключая узлы внутри header/nav/footer/
 * aside — эти сетки принадлежат навигации и второстепенным блокам, а не
 * основной ленте контента. Среди кандидатов с >=4 потомками ранжирование
 * идёт только по ним: двухколоночная обёртка макета (2 потомка) может по
 * чистой площади bounding box перевесить рядом стоящую сетку из полутора
 * десятков карточек — так было поймано на catalog@390 при разработке этого
 * инструмента. Кандидатов и их геометрия сохраняются целиком (включая
 * второго по рангу), чтобы выбор был проверяем, а не однострочным
 * утверждением.
 *
 * cardsFound — то же правило, что в measure_reference.js (img >=60x60 внутри
 * <a>), нужен здесь только чтобы независимо подтвердить отсутствие карточек
 * на тех поверхностях, где measure_reference.js его уже показал: два разных
 * инструмента, одно наблюдение.
 *
 * Использование:
 *   node tests/tools/measure_reference_structure.js <url> <outDir> <виджеты> <surface>
 */
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const url = process.argv[2];
const outDir = process.argv[3];
const viewports = process.argv[4].split(',').map(Number);
const surface = process.argv[5];
const executablePath = process.env.FACTORY_CHROMIUM || undefined;

const PASSES = 2;

const measureInPage = () => {
  const round = (value) => Math.round(value * 100) / 100;

  function isVisible(node) {
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    if (rect.left < -1000 || rect.top < -1000) return false;
    const style = getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    if (parseFloat(style.opacity) === 0) return false;
    if (node.getAttribute('aria-hidden') === 'true') return false;
    return true;
  }

  const EXCLUDE_TAGS = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'LINK', 'META']);
  const LANDMARK_TAGS = new Set(['header', 'nav', 'footer', 'aside', 'main', 'form']);

  function classifyRole(node) {
    const tag = node.tagName.toLowerCase();
    const role = (node.getAttribute('role') || '').trim().toLowerCase();
    if (role) return `role_${role}`;
    if (LANDMARK_TAGS.has(tag)) return tag;
    if (node.querySelector('video-player, video, iframe[src*="player" i]')) return 'player_section';
    const links = node.querySelectorAll(':scope a, a');
    const images = node.querySelectorAll(':scope img, a img');
    if (images.length >= 4 && links.length >= 4) return 'grid_section';
    if (node.querySelector('h1, h2, h3')) return 'heading_section';
    if (node.querySelector('form, input, textarea')) return 'form_section';
    if (links.length >= 4) return 'link_list_section';
    return 'section';
  }

  function visibleChildren(node) {
    return [...node.children].filter((c) => !EXCLUDE_TAGS.has(c.tagName)).filter(isVisible);
  }

  function findSectionsContainer() {
    let node = document.body;
    let steps = 0;
    for (let depth = 0; depth < 16; depth += 1) {
      const kids = visibleChildren(node);
      if (kids.length === 0) break;
      if (kids.length === 1) { node = kids[0]; steps += 1; continue; }
      const sizes = kids.map((k) => k.querySelectorAll('*').length);
      const total = sizes.reduce((a, b) => a + b, 0);
      const maxIndex = sizes.indexOf(Math.max(...sizes));
      if (total > 0 && sizes[maxIndex] / total > 0.7) {
        node = kids[maxIndex];
        steps += 1;
        continue;
      }
      break;
    }
    return { node, steps };
  }

  const { node: container, steps: unwrapDepth } = findSectionsContainer();
  const sectionNodes = visibleChildren(container);
  const roles = sectionNodes.map((node) => classifyRole(node));

  // Одинаковые роли нумеруются по счёту появления, чтобы повтор оставался
  // видимым в последовательности, а не схлопывался при простом сравнении.
  const seen = {};
  const order = roles.map((role) => {
    seen[role] = (seen[role] || 0) + 1;
    return seen[role] > 1 ? `${role}_${seen[role]}` : role;
  });

  const EXCLUDE_ANCESTOR_SELECTOR = 'header, nav, footer, aside';
  const gridCandidates = [...document.querySelectorAll('*')]
    .filter((node) => getComputedStyle(node).display === 'grid')
    .filter((node) => !node.closest(EXCLUDE_ANCESTOR_SELECTOR))
    .filter((node) => node.children.length >= 2)
    .filter(isVisible)
    .map((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return {
        area: round(rect.width * rect.height),
        width: round(rect.width),
        columns: style.gridTemplateColumns.split(' ').filter(Boolean).length,
        gap: round(parseFloat(style.columnGap || style.gap) || 0),
        children: node.children.length,
        visibleChildren: visibleChildren(node).length,
        inMain: !!node.closest('main'),
      };
    })
    .sort((a, b) => b.area - a.area);

  // Площадь одна не отличает сетку карточек от двухколоночной обёртки
  // макета: на каталоге amd.online такая обёртка (2 потомка) занимает
  // площадь больше, чем сетка из 13 карточек рядом с ней. «Основной
  // контентной» считается сетка с >=4 потомками (порог согласован с card
  // grid_section в classifyRole — там тот же порог для сетки ссылок-картинок);
  // если ни одна не набирает 4 потомков, откатываемся к списку без фильтра.
  const contentGrids = gridCandidates.filter((g) => g.children >= 4);
  const rankedGrids = contentGrids.length ? contentGrids : gridCandidates;

  const cardImages = [...document.querySelectorAll('a img')]
    .map((img) => img.getBoundingClientRect())
    .filter((rect) => rect.width >= 60 && rect.height >= 60);

  return {
    order,
    sectionCount: order.length,
    containerTag: container.tagName.toLowerCase(),
    containerUnwrapDepth: unwrapDepth,
    gridCandidateCount: gridCandidates.length,
    primaryGrid: rankedGrids.length ? rankedGrids[0] : null,
    runnerUpGrid: rankedGrids.length > 1 ? rankedGrids[1] : null,
    cardsFound: cardImages.length,
  };
};

(async () => {
  const result = { url, surface, measured_at: new Date().toISOString(), viewports: {}, errors: [] };
  let browser;
  try {
    browser = await chromium.launch(executablePath ? { executablePath } : {});
  } catch (error) {
    result.errors.push({ stage: 'launch', message: String(error).slice(0, 400) });
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'structure.json'), JSON.stringify(result, null, 2));
    process.exit(3);
  }
  fs.mkdirSync(outDir, { recursive: true });

  for (const width of viewports) {
    const height = width < 500 ? 844 : 1000;
    try {
      const passes = [];
      for (let index = 0; index < PASSES; index += 1) {
        const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
        const page = await context.newPage();
        const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(1500);
        const measured = await page.evaluate(measureInPage);
        measured.httpStatus = response ? response.status() : null;
        if (index === 0) {
          await page.screenshot({ path: path.join(outDir, `structure-${width}.png`), fullPage: false });
        }
        passes.push(measured);
        await context.close();
      }

      const [a, b] = passes;
      const shot = path.join(outDir, `structure-${width}.png`);
      const digest = fs.existsSync(shot)
        ? crypto.createHash('sha256').update(fs.readFileSync(shot)).digest('hex')
        : null;

      // Сравнение сетки — только по полям, которые участвуют в оценке
      // (columns/gap/inMain). Площадь и ширина кандидата естественно дрожат
      // между двумя загрузками живой страницы (ленивый контент чуть меняет
      // высоту) и не являются частью измеряемого значения.
      const gridKey = (g) => (g ? JSON.stringify([g.columns, g.gap, g.inMain]) : null);

      result.viewports[width] = {
        pass_a: a,
        pass_b: b,
        order_stable: JSON.stringify(a.order) === JSON.stringify(b.order),
        grid_stable: gridKey(a.primaryGrid) === gridKey(b.primaryGrid),
        cards_stable: a.cardsFound === b.cardsFound,
        screenshot: { file: path.basename(shot), sha256: digest },
      };
    } catch (error) {
      result.errors.push({ stage: `viewport-${width}`, message: String(error).slice(0, 400) });
    }
  }

  await browser.close();
  fs.writeFileSync(path.join(outDir, 'structure.json'), JSON.stringify(result, null, 2));
  const measured = Object.keys(result.viewports).length;
  console.log(JSON.stringify({ surface, measured, errors: result.errors.length }));
  process.exit(measured > 0 ? 0 : 4);
})();
