// Ядро приёмки по действующим адресам, отдельно от самого набора.
//
// Отдельно — чтобы его можно было проверить. Набор без адресов целиком
// пропускается, и в таком виде он непроверяем: объявить готовой оснастку,
// которая ни разу не работала, значит повторить ровно ту ошибку отчёта, от
// которой заведены эти правила.
//
// `harness.selftest.spec.js` проверяет всё, что здесь есть, на перехваченных
// ответах — без сети, без сервера и без единого запроса наружу.

const fs = require('node:fs');
const path = require('node:path');

const МУТИРУЮЩИЕ = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

// 401, 403 и 429 — защита провайдера или ограничение частоты. Это состояние
// доступа, а не дефект витрины, и приёмка обязана их различать.
const ОТКАЗ_ДОСТУПА = new Set([401, 403, 429]);

const ШИРИНЫ = [390, 768, 1440];

function loadConfig(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8')).products;
}

/** Чтение-слияние-запись: рабочие процессы пишут в один файл. */
function record(evidenceFile, product, key, value) {
  fs.mkdirSync(path.dirname(evidenceFile), { recursive: true });
  let all = {};
  try { all = JSON.parse(fs.readFileSync(evidenceFile, 'utf8')); } catch { all = {}; }
  all[product] = { ...(all[product] || {}), [key]: value };
  fs.writeFileSync(evidenceFile, JSON.stringify(all, null, 2) + '\n');
  return all;
}

/**
 * Обрывает изменяющие запросы и запоминает попытки.
 *
 * Обрыв на уровне браузера, а не обещание ничего не отправлять: страница
 * действующего сайта может отправить что угодно — форму, счётчик, служебный
 * вызов, — и доверять её содержимому приёмка не вправе. Гарантия должна быть
 * видимой и проверяемой, иначе это не гарантия.
 */
async function readOnly(page, attempts) {
  await page.route('**/*', (route) => {
    const request = route.request();
    if (МУТИРУЮЩИЕ.has(request.method())) {
      attempts.push({ method: request.method(), url: request.url() });
      return route.abort();
    }
    return route.continue();
  });
}

/** Ширина, на которую страница выходит за окно. Ноль и меньше — не выходит. */
async function overflowPx(page) {
  return page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

function classify(status) {
  if (ОТКАЗ_ДОСТУПА.has(status)) return 'BLOCKED_ACCESS';
  return status === 200 ? 'OK' : 'FAILED';
}

module.exports = { МУТИРУЮЩИЕ, ОТКАЗ_ДОСТУПА, ШИРИНЫ, classify, loadConfig,
                   overflowPx, readOnly, record };
