// Размеры интерактивных целей по WCAG 2.2 — общая реализация критерия.
//
// Модуль появился, когда вторая проверка (шаблоны направлений) начала мерить
// цели заново и объявила нарушением 110 элементов, которые критерию
// удовлетворяют: наивный порог «каждая цель ≥ N px» не знает про исключения.
// Две копии критерия расходятся молча, поэтому копия здесь одна.
//
// Критерий 2.5.8 (AA, 24 px) не требует размера от каждой цели. Он даёт
// исключения, и три из них существенны для витрины:
//
//   * **интервал** — маленькая цель проходит, если вокруг неё есть место:
//     окружность диаметром 24 px с центром в цели не пересекает такую же
//     окружность соседней цели;
//   * **эквивалент** — то же действие доступно другой целью достаточного
//     размера (постер и заголовок карточки ведут по одному адресу);
//   * **строчная** — цель внутри предложения размер держать не обязана,
//     иначе ссылка в абзаце разрывала бы строку.
//
// Считать по одному размеру, игнорируя исключения, значит объявлять
// нарушением работающую вёрстку и чинить её под ошибку измерения.

const AA_MIN = 24; // WCAG 2.2 SC 2.5.8, уровень AA
const AAA_MIN = 44; // WCAG 2.2 SC 2.5.5, уровень AAA — требование задания
const INPUT_MIN_FONT = 16; // ниже этого мобильный браузер зумит страницу при фокусе

/** Снимает размеры целей в браузере. Замыканий не имеет: функция целиком
 *  уезжает в page.evaluate и выполняется на стороне страницы. */
const measureTargets = () => {
  const MIN = 24;
  const selector = 'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';
  const visible = [...document.querySelectorAll(selector)].filter((el) => {
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') { return false; }
    const rect = el.getBoundingClientRect();
    // Ссылка перехода к содержимому спрятана до фокуса и целью указателя не
    // является: измерять её как цель — измерять то, чего пальцем не касаются.
    if (rect.width <= 1 || rect.height <= 1) { return false; }
    return true;
  });

  const boxes = visible.map((el) => {
    const r = el.getBoundingClientRect();
    return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height };
  });

  return visible.map((el, index) => {
    const rect = el.getBoundingClientRect();
    const me = boxes[index];
    // Интервал: расстояние до ближайшего центра другой цели. Если оно не
    // меньше 24 px, окружности не пересекаются и исключение применимо.
    let nearest = Infinity;
    boxes.forEach((other, j) => {
      if (j === index) { return; }
      const distance = Math.hypot(me.cx - other.cx, me.cy - other.cy);
      if (distance < nearest) { nearest = distance; }
    });
    // Исключение «эквивалент»: если то же действие доступно другой целью
    // достаточного размера, маленькая цель критерию не противоречит. На
    // карточке это буквальный случай — постер и заголовок ведут по одному
    // адресу, и постер крупный. Требовать 44 px от подписи под постером
    // значило бы растить карточку ради цели, дубль которой уже большой.
    const href = el.getAttribute('href');
    let equivalent = null;
    if (href) {
      visible.forEach((other, j) => {
        if (j === index || other.getAttribute('href') !== href) { return; }
        const r = boxes[j];
        if (r.w >= 44 && r.h >= 44) { equivalent = Math.round(Math.min(r.w, r.h)); }
      });
    }
    return {
      tag: el.tagName.toLowerCase(),
      cls: el.getAttribute('class') || '',
      text: (el.textContent || '').trim().slice(0, 40),
      width: Math.round(rect.width * 100) / 100,
      height: Math.round(rect.height * 100) / 100,
      nearestTargetPx: Number.isFinite(nearest) ? Math.round(nearest * 100) / 100 : null,
      spacingExempt: Number.isFinite(nearest) ? nearest >= MIN : true,
      equivalentTargetPx: equivalent,
      inline: !!el.closest('p, li.inline, .lede, footer p'),
    };
  });
};

/** Цели, нарушающие 2.5.8 (AA): без исключения по строке и по интервалу. */
const failingAA = (targets) => targets.filter(
  (t) => !t.inline && !t.spacingExempt && (t.width < AA_MIN || t.height < AA_MIN));

/** Цели, нарушающие усиленный порог 2.5.5: без исключения по строке и по
 *  эквивалентной цели. Интервал здесь не спасает — критерий AAA его не даёт. */
const failingAAA = (targets) => targets.filter(
  (t) => !t.inline && !t.equivalentTargetPx && (t.width < AAA_MIN || t.height < AAA_MIN));

module.exports = { AA_MIN, AAA_MIN, INPUT_MIN_FONT, measureTargets, failingAA, failingAAA };
