"""Генерация клиента событий из описания в :mod:`factory.analytics.events`.

Клиент один на все сайты и не копируется руками: и вариант для темы (обычный
JavaScript), и вариант для Next-блюпринта (TypeScript) собираются из одного
описания. Расхождение между целью в Метрике и событием на сайте становится
невозможным, а тест сверяет файлы в репозитории с результатом генерации.

Ключевое свойство сгенерированного кода: он **не грузит Метрику**, пока не
выполнены все условия — включён флаг, задан counter ID, окружение production и
hostname точно совпал с разрешённым. Не «загрузил и не отправляет», а не
загрузил вовсе: на staging тега Метрики в странице нет.
"""
from __future__ import annotations

import json

from factory.analytics.events import EVENTS, FORBIDDEN_PARAM_NAMES

GENERATED_BANNER = (
    "Сгенерировано `python3 -m factory analytics codegen` из factory/analytics/events.py.\n"
    " * Руками не редактируется: правка теряется при следующей генерации, а описание\n"
    " * событий и цели Метрики разойдутся. Меняй events.py и перегенерируй."
)


def _spec_json() -> str:
    spec = {
        event.id: {
            param.name: (
                {"kind": param.kind, "values": list(param.values)}
                if param.kind == "enum"
                else {"kind": param.kind, "maxLength": param.max_length}
                if param.kind == "id"
                else {"kind": param.kind}
            )
            for param in event.params
        }
        for event in EVENTS
    }
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True)


def _forbidden_json() -> str:
    return json.dumps(sorted(FORBIDDEN_PARAM_NAMES), ensure_ascii=False)


#: Общее тело проверки параметров. Один текст на оба языка: расхождение в
#: фильтре персональных данных между вариантами клиента недопустимо.
_SANITIZE_BODY = """\
  var out = {};
  var spec = EVENT_SPEC[eventId];
  if (!spec) { return null; }
  if (!params) { return out; }
  for (var key in params) {
    if (!Object.prototype.hasOwnProperty.call(params, key)) { continue; }
    var lower = String(key).toLowerCase();
    // Запрещённое имя отбрасывается до сверки со списком разрешённых:
    // список разрешённых когда-нибудь расширят по ошибке, этот — нет.
    if (FORBIDDEN.indexOf(lower) !== -1) { continue; }
    var rule = spec[key];
    if (!rule) { continue; }
    var value = params[key];
    if (rule.kind === 'enum') {
      if (rule.values.indexOf(String(value)) === -1) { continue; }
      out[key] = String(value);
    } else if (rule.kind === 'int') {
      var num = parseInt(value, 10);
      if (!isFinite(num)) { continue; }
      out[key] = num;
    } else if (rule.kind === 'bool') {
      out[key] = value === true || value === 'true';
    } else if (rule.kind === 'id') {
      var id = String(value);
      // Идентификатор — это слаг или число. Всё, что похоже на текст, адрес
      // или произвольную строку, идентификатором не является и не отправляется.
      if (!/^[A-Za-z0-9_-]+$/.test(id) || id.length > rule.maxLength) { continue; }
      out[key] = id;
    }
  }
  return out;"""

_DECIDE_BODY = """\
  if (!config) { return { active: false, reason: 'нет конфигурации' }; }
  if (config.enabled === false) { return { active: false, reason: 'ANALYTICS_ENABLED=false' }; }
  if (!config.counterId) { return { active: false, reason: 'counter ID не задан' }; }
  if (config.environment !== 'production') {
    return { active: false, reason: 'окружение ' + config.environment + ', не production' };
  }
  if (!config.allowedHosts || config.allowedHosts.length === 0) {
    return { active: false, reason: 'список разрешённых hostname пуст' };
  }
  if (config.allowedHosts.indexOf(hostname) === -1) {
    return { active: false, reason: 'hostname ' + hostname + ' не совпал с разрешённым' };
  }
  return { active: true, reason: 'разрешено' };"""

#: То же поведение для TypeScript в строгом режиме. Два текста вместо одного —
#: осознанная цена: подстановкой `var`→`let` получается код, который никто не
#: компилировал. Совпадение поведения обоих вариантов проверяет тест.
_SANITIZE_BODY_TS = """\
  const out: Record<string, string | number | boolean> = {};
  const spec = EVENT_SPEC[eventId];
  if (!spec) { return null; }
  if (!params) { return out; }
  for (const key of Object.keys(params)) {
    const lower = key.toLowerCase();
    // Запрещённое имя отбрасывается до сверки со списком разрешённых:
    // список разрешённых когда-нибудь расширят по ошибке, этот — нет.
    if (FORBIDDEN.indexOf(lower) !== -1) { continue; }
    const rule = spec[key];
    if (!rule) { continue; }
    const value = params[key];
    if (rule.kind === 'enum') {
      if (rule.values.indexOf(String(value)) === -1) { continue; }
      out[key] = String(value);
    } else if (rule.kind === 'int') {
      const num = parseInt(String(value), 10);
      if (!isFinite(num)) { continue; }
      out[key] = num;
    } else if (rule.kind === 'bool') {
      out[key] = value === true || value === 'true';
    } else if (rule.kind === 'id') {
      const id = String(value);
      // Идентификатор — это слаг или число. Всё, что похоже на текст, адрес
      // или произвольную строку, идентификатором не является и не отправляется.
      if (!/^[A-Za-z0-9_-]+$/.test(id) || id.length > rule.maxLength) { continue; }
      out[key] = id;
    }
  }
  return out;"""

#: Параметры инициализации тега. Вебвизор выключен явно, а не «по умолчанию»:
#: значение по умолчанию когда-нибудь поменяют, а эта строка — обещание.
_INIT_OPTIONS = "{ clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: false }"

#: Загрузчик тега — дословно из официальной документации Метрики.
_LOADER = """\
  (function (m, e, t, r, i, k, a) {
    m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
    m[i].l = 1 * new Date();
    k = e.createElement(t); a = e.getElementsByTagName(t)[0];
    k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
  })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym');"""


def render_js() -> str:
    """Клиент для темы: обычный JavaScript, подключается как внешний файл.

    Инлайнового кода нет намеренно: CSP не должна выбирать между работающей
    аналитикой и работающим плеером.
    """
    return f"""/* {GENERATED_BANNER} */
(function () {{
  'use strict';

  var EVENT_SPEC = {_spec_json()};

  var FORBIDDEN = {_forbidden_json()};

  function sanitize(eventId, params) {{
{_SANITIZE_BODY}
  }}

  function decide(config, hostname) {{
{_DECIDE_BODY}
  }}

  function readConfig() {{
    var el = document.currentScript || document.querySelector('script[data-analytics-provider]');
    if (!el) {{ return null; }}
    var hosts = (el.getAttribute('data-allowed-hosts') || '').split(',')
      .map(function (h) {{ return h.trim().toLowerCase(); }})
      .filter(Boolean);
    return {{
      counterId: parseInt(el.getAttribute('data-counter-id') || '', 10) || 0,
      allowedHosts: hosts,
      environment: el.getAttribute('data-environment') || 'staging',
      enabled: el.getAttribute('data-analytics-enabled') !== 'false'
    }};
  }}

  var config = readConfig();
  var verdict = decide(config, (window.location.hostname || '').toLowerCase());

  // Публичный интерфейс существует всегда: страницы вызывают track() без
  // проверок, и в выключенном состоянии он обязан молча ничего не делать.
  window.siteAnalytics = {{
    active: verdict.active,
    reason: verdict.reason,
    track: function (eventId, params) {{
      if (!verdict.active) {{ return false; }}
      var clean = sanitize(eventId, params);
      if (clean === null) {{ return false; }}
      window.ym(config.counterId, 'reachGoal', eventId, clean);
      return true;
    }}
  }};

  if (!verdict.active) {{
    // Тег не загружается вовсе: на staging в странице нет ни одного запроса
    // к Метрике, а не «загрузились и не отправляем».
    return;
  }}

{_LOADER}

  window.ym(config.counterId, 'init', {_INIT_OPTIONS});
}})();
"""


def _ts_param_type(param) -> str:
    if param.kind == "enum":
        return " | ".join(f"'{v}'" for v in param.values)
    if param.kind == "int":
        return "number"
    if param.kind == "bool":
        return "boolean"
    return "string"


def render_ts() -> str:
    """Типизированный клиент для Next-блюпринта.

    Типы — не украшение: имя события и набор его параметров проверяются
    компилятором, поэтому «отправили в Метрику текст комментария» не проходит
    сборку, а не только фильтр во время выполнения.
    """
    lines: list[str] = [f"/* {GENERATED_BANNER} */", ""]
    lines.append("export type AnalyticsEventId =")
    for index, event in enumerate(EVENTS):
        tail = ";" if index == len(EVENTS) - 1 else ""
        lines.append(f"  | '{event.id}'{tail}")
    lines.append("")

    lines.append("export interface AnalyticsEventParams {")
    for event in EVENTS:
        if not event.params:
            lines.append(f"  '{event.id}': Record<string, never>;")
            continue
        lines.append(f"  '{event.id}': {{")
        for param in event.params:
            lines.append(f"    /** {param.description} */")
            lines.append(f"    {param.name}?: {_ts_param_type(param)};")
        lines.append("  };")
    lines.append("}")
    lines.append("")

    lines.append("export interface AnalyticsConfig {")
    lines.append("  counterId: number;")
    lines.append("  allowedHosts: string[];")
    lines.append("  environment: string;")
    lines.append("  enabled: boolean;")
    lines.append("}")
    lines.append("")
    lines.append("export interface AnalyticsVerdict {")
    lines.append("  active: boolean;")
    lines.append("  reason: string;")
    lines.append("}")
    lines.append("")
    lines.append(f"const EVENT_SPEC: Record<string, Record<string, any>> = {_spec_json()};")
    lines.append("")
    lines.append(f"const FORBIDDEN: string[] = {_forbidden_json()};")
    lines.append("")
    lines.append("export function sanitize(eventId: string, params?: Record<string, unknown>)")
    lines.append("    : Record<string, string | number | boolean> | null {")
    lines.append(_SANITIZE_BODY_TS)
    lines.append("}")
    lines.append("")
    lines.append("/** Решение принимается до загрузки тега: выключено — значит не загружаем. */")
    lines.append("export function decide(config: AnalyticsConfig | null, hostname: string): AnalyticsVerdict {")
    lines.append(_DECIDE_BODY)
    lines.append("}")
    lines.append("")
    lines.append("declare global {")
    lines.append("  interface Window { ym?: (...args: unknown[]) => void }")
    lines.append("}")
    lines.append("")
    lines.append("let verdict: AnalyticsVerdict = { active: false, reason: 'не инициализирован' };")
    lines.append("let counterId = 0;")
    lines.append("")
    lines.append("/** Загружает тег Метрики, но только когда выполнены все условия. */")
    lines.append("export function initAnalytics(config: AnalyticsConfig | null, hostname: string): AnalyticsVerdict {")
    lines.append("  verdict = decide(config, hostname.toLowerCase());")
    lines.append("  if (!verdict.active || !config) { return verdict; }")
    lines.append("  counterId = config.counterId;")
    lines.append(_LOADER)
    lines.append(f"  window.ym!(counterId, 'init', {_INIT_OPTIONS});")
    lines.append("  return verdict;")
    lines.append("}")
    lines.append("")
    lines.append("/** Отправка события. Типы не дают ни назвать чужое событие, ни передать лишнее. */")
    lines.append("export function track<E extends AnalyticsEventId>(")
    lines.append("  eventId: E,")
    lines.append("  params?: AnalyticsEventParams[E],")
    lines.append("): boolean {")
    lines.append("  if (!verdict.active || typeof window === 'undefined' || !window.ym) { return false; }")
    lines.append("  const clean = sanitize(eventId, params as Record<string, unknown> | undefined);")
    lines.append("  if (clean === null) { return false; }")
    lines.append("  window.ym(counterId, 'reachGoal', eventId, clean);")
    lines.append("  return true;")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


#: Куда кладутся сгенерированные файлы. Оба пути — часть контракта: тест сверяет
#: содержимое файлов с результатом генерации и краснеет на ручной правке.
JS_TARGET = "themes/basis-video/assets/analytics.js"
TS_TARGET = "blueprints/payload-next-multisite/app/src/lib/analytics.ts"


def write_all(root=None) -> list[str]:
    from pathlib import Path

    from factory.paths import PATHS

    base = Path(root) if root else PATHS.root
    written = []
    for target, content in ((JS_TARGET, render_js()), (TS_TARGET, render_ts())):
        path = base / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(target)
    return written
