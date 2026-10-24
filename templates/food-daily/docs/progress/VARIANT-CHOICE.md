# Выбор основных вариантов (решение владельца, 13.10.2026)

Владелец принял рекомендации из `RECOMMENDATIONS.md`. Основные варианты развиваются дальше,
остальные сохраняются для сравнения (ветки и PR не закрываются, в main ничего не сливается).

| сайт | основной | ветка | PR |
| --- | --- | --- | --- |
| food-daily | C party-list | claude/template-food-daily-c | #124 |
| food-baking | B oven-bench | claude/template-food-baking-b | #112 |
| food-weekly | C own-week | claude/template-food-weekly-c | #121 |
| food-appliances | B step-console | claude/template-food-appliances-b | #114 |
| home-practical | C home-audit | claude/template-home-practical-c | #115 |
| garden-season | C my-plot | claude/template-garden-season-c | #116 |
| plants-home | C my-collection | claude/template-plants-home-c | #117 |
| games-story | C atlas | claude/template-games-story-c | #118 |
| games-rpg | C index-compare | claude/template-games-rpg-c | #119 |
| games-survival | C inventory-first | claude/template-games-survival-c | #120 |

Правила переноса: функции из альтернатив переносятся точечно (не слиянием веток целиком),
каждая — с проверкой совместимости и приёмкой на актуальном коммите основного варианта.
Ход работ — `PROGRESS-PRIMARY.md`. Домены: отсутствуют, production/DNS/индексация не подключаются.

CI: исправление lint shared core уже есть в открытом PR #71 — см. `ci/CI-RED.md`.
