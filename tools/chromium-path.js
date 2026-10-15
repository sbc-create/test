// Где взять Chromium для браузерных проверок — одно место на все запуски.
//
// Номер сборки был вписан числом в семь файлов (`chromium-1194`). На машине с
// другой сборкой это означало не «проверка упала», а «проверка не выполнялась»:
// playwright отказывался стартовать, e2e падал целиком, а `seo-render` отдавал
// honest-статус `unavailable` — и он читался как свойство среды, а не как
// устаревшая константа.
//
// Порядок: явный FACTORY_CHROMIUM, затем прежние закреплённые пути (чтобы
// ничего не сломать там, где они ещё верны), затем поиск по шаблону от НОВОЙ
// сборки к старой.
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

const ЗАКРЕПЛЁННЫЕ = [
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  '/opt/pw-browsers/chromium/chrome-linux/chrome',
];
const КОРНИ = ['/opt/pw-browsers', path.join(os.homedir(), '.cache', 'ms-playwright')];
const ХВОСТЫ = ['chrome-linux/chrome', 'chrome-linux64/chrome'];

function номерСборки(имя) {
  const хвост = имя.slice(имя.lastIndexOf('-') + 1);
  const число = Number.parseInt(хвост, 10);
  return Number.isNaN(число) ? -1 : число;
}

function поШаблону() {
  const найдено = [];
  for (const корень of КОРНИ) {
    let записи;
    try {
      записи = fs.readdirSync(корень);
    } catch (e) {
      continue;
    }
    записи
      .filter((имя) => имя.startsWith('chromium-'))
      // Сортировка по ЧИСЛУ: строковая ставит `chromium-980` выше
      // `chromium-1243`, и поиск «от новой сборки к старой» молча выбрал бы
      // старую. Пока у сборок одинаковое число цифр, разницы не видно.
      .sort((а, б) => номерСборки(б) - номерСборки(а))
      .forEach((имя) => {
        for (const хвост of ХВОСТЫ) {
          const кандидат = path.join(корень, имя, хвост);
          if (fs.existsSync(кандидат)) найдено.push(кандидат);
        }
      });
  }
  return найдено;
}

function chromiumPath() {
  if (process.env.FACTORY_CHROMIUM && fs.existsSync(process.env.FACTORY_CHROMIUM)) {
    return process.env.FACTORY_CHROMIUM;
  }
  for (const кандидат of ЗАКРЕПЛЁННЫЕ) {
    if (fs.existsSync(кандидат)) return кандидат;
  }
  const найдено = поШаблону();
  if (найдено.length) return найдено[0];
  // Ничего не нашли — возвращаем прежнее значение по умолчанию, чтобы
  // сообщение об ошибке называло ожидаемый путь, а не пустую строку.
  return process.env.FACTORY_CHROMIUM || ЗАКРЕПЛЁННЫЕ[0];
}

module.exports = { chromiumPath };
