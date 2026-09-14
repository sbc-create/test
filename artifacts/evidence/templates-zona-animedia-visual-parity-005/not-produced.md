# Свидетельства, которые НЕ созданы, и почему

Задание перечисляет обязательный состав evidence. Ниже — то, чего в пакете нет.
Пустые или формально заполненные файлы не создавались намеренно: файл с нулями
на месте непроведённого измерения читается как проведённое измерение.

| файл | почему отсутствует |
| --- | --- |
| `archetype-matrix.json` | архетип сопоставляется с архетипом оригинала; оригиналы недоступны — сопоставлять не с чем. Перечень ячеек со статусом `BLOCKED_REFERENCE` вынесен в `reference-url-matrix.json` |
| `component-inventory-reference.json` | требует обхода DOM оригинала |
| `computed-styles.json` (референсная половина) | требует вычисленных стилей оригинала |
| `geometry-results.json` | геометрическое отклонение считается ОТ якорей оригинала |
| `visual-results.json` | SSIM, DeltaE00 и heatmap считаются от скриншота оригинала |
| `component-inventory-candidate.json` | снимать инвентарь кандидата до появления самого кандидата бессмысленно: изменений шаблонов в этой задаче нет |
| `functional-results.json` | сценарии приёмки (карусели, фильтры, сезоны, плеер) определяются поведением оригинала |
| `accessibility-results.json` | не запускалось: приёмка кандидата не начиналась |
| `browser-matrix.json` | Firefox и WebKit не запускались: прогонять кандидата, которого нет, незачем |
| `zona-results.json`, `animedia-results.json` | итоговые вердикты кандидатов; кандидатов нет |
| `screenshots/reference/` | пусто: оригиналы не открывались ни разу |
| `screenshots/after/`, `overlay/`, `diff/` | пусто: нового кандидата нет, накладывать и вычитать нечего |

Созданы и содержат настоящие измерения:
`live-baseline.json`, `link-audit.json`, `responsive-results.json`,
`data-vs-template-defects.json`, `reference-manifest.json`,
`reference-url-matrix.json`, `screenshots/before/` (9 снимков).
