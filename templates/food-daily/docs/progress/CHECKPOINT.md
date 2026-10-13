# Checkpoint — PRACTICAL-NETWORK-NIGHT-CONTINUE-02

Старт: 12.10.2026. Обновляется при каждой смене этапа.

**Этап 1 закрыт: food-daily — `59972fa`, READY_FOR_REVIEW_WITH_BLOCKERS. Далее — food-baking (новая ветка от origin/main).**

## Состояние на старте (проверено)

| что | значение |
| --- | --- |
| хост | claude-control-01 |
| worktree / ветка | /home/claude/wt-template-food-daily / claude/template-food-daily |
| HEAD | 4d53f9d (= origin/claude/template-food-daily) |
| origin/main | a7f7cb6 (не менялся) |
| PR | #95 draft |
| preview | 127.0.0.1:8847, pid 339624, 22 рецепта |
| ветка `qwen/content-food-daily-night-001` | **нет на origin** (`git ls-remote --heads origin 'qwen/*'` — пусто) |
| следы QWEN-NIGHT-RECIPES-100X5-001 / FD-CONTENT-001 на сервере | не найдены (grep по /home/claude, /srv/site-factory, /opt — 100 с, совпадений нет) |

Вывод: ночной прогон Qwen не подтверждён; партия FD-CONTENT-001 повторно не запускается (прямое указание задания).

## Подтверждённые дефекты food-daily (по влиянию на читателя)

1. Все карточки и все рецепты раздела показывают одну и ту же иллюстрацию — выглядит как одно блюдо.
2. На странице рецепта нет ссылок на теги; индексных страниц `/produkty/`, `/sposob/` нет (404).
3. Нет типа страницы «статья/совет».
4. Нет печатной версии рецепта.
5. axe-core не запускался (висячая ссылка node_modules).
6. Коллекции и разделы без ItemList-разметки.
7. Карантин двух рецептов не оформлен как вопрос редактору.

## Следующие действия

1. Исправить 1–4, 6, 7 в шаблоне food-daily, тесты.
2. Своя установка axe-core в `templates/food-daily/qa/` + прогон + ручной проход клавиатурой.
3. Commit, приёмка, обновление PR #95 → переход к food-baking.

## Прогресс сети (обновлено 12.10.2026)

| сайт | ветка / worktree | проверенный код | preview | PR | статус |
| --- | --- | --- | --- | --- | --- |
| food-daily | claude/template-food-daily / wt-template-food-daily | 59972fa (+ лента каталога 5ac8115) | 127.0.0.1:8847 | #95 | READY_FOR_REVIEW_WITH_BLOCKERS |
| food-baking | claude/template-food-baking / wt-template-food-baking | cd39fdc | 127.0.0.1:8848 | #96 | READY_FOR_REVIEW_WITH_BLOCKERS |
| food-weekly | claude/template-food-weekly / wt-template-food-weekly | 8b1e34d | 127.0.0.1:8849 | #97 | READY_FOR_REVIEW_WITH_BLOCKERS |
| food-appliances | claude/template-food-appliances / wt-template-food-appliances | 0dc5e4d | 127.0.0.1:8850 | #98 | READY_FOR_REVIEW_WITH_BLOCKERS |
| остальные 6 | — | — | — | — | planned |

Ревизия после ~30 задач: лучше — три работающих сайта с собственными дизайнами и axe 0;
сломалось — ничего, но guard не даёт сессии возвращаться в старые worktree после EnterWorktree
(решение: работать через `cd` из исходной сессии); проверить перед продолжением — ruff format
перед каждым коммитом, CI-гейт красный из-за общего линта (handoff).

Ревизия после food-appliances: лучше — табло прибора со ссылками на шаги, валидатор режимов
(выдуманный режим или число отклоняется), axe 0 после исправления контраста; сломалось — ничего;
проверить — гриль без полных фактов (раздел 404), мелочи мобильной шапки и крошек (REPORT.md).

Продолжение: home-practical — новая ветка `claude/template-home-practical` и worktree от origin/main,
сначала аудит 3 референсов (хосты только из задания; если их нет — BLOCKED_INPUT, без подстановки).

---

# Ночь 12–13.10.2026 (старт 2026-10-12T20:00Z = 23:00 MSK)

Хост claude-control-01, пользователь claude, origin `sbc-create/test`, main `a7f7cb6` (не менялся).
Варианты: идентификатор `variant_id` по образцу фабрики (мета `site-factory-variant-id`); A — исходная ветка
`claude/template-<site>`, B — `claude/template-<site>-b`, свой worktree и порт.

| сайт / вариант | ветка | worktree | проверенный код | preview | PR | статус |
| --- | --- | --- | --- | --- | --- | --- |
| food-daily A | claude/template-food-daily | wt-template-food-daily | 4c263da | 127.0.0.1:8847 | #95 | READY_FOR_REVIEW_WITH_BLOCKERS |
| food-baking A | claude/template-food-baking | wt-template-food-baking | 0b95dcb | 127.0.0.1:8848 | #96 | READY_FOR_REVIEW_WITH_BLOCKERS |
| food-weekly A | claude/template-food-weekly | wt-template-food-weekly | da65202 | 127.0.0.1:8849 | #97 | READY_FOR_REVIEW_WITH_BLOCKERS |
| food-appliances A | claude/template-food-appliances | wt-template-food-appliances | 8953b3a | 127.0.0.1:8850 | #98 | READY_FOR_REVIEW_WITH_BLOCKERS |
| home-practical A (rooms-cards) | claude/template-home-practical | wt-template-home-practical | 06d708c | 127.0.0.1:8851 | #99 | READY_FOR_REVIEW_WITH_BLOCKERS |
| home-practical B (problem-checklists) | claude/template-home-practical-b | wt-template-home-practical-b | 819b934 | 127.0.0.1:8852 | #100 (база — ветка A) | READY_FOR_REVIEW_WITH_BLOCKERS |
| garden-season A (month-calendar) | claude/template-garden-season | wt-template-garden-season | 31fec6c | 127.0.0.1:8853 | #101 | READY_FOR_REVIEW_WITH_BLOCKERS |
| garden-season B (region-timeline) | claude/template-garden-season-b | wt-template-garden-season-b | 65f5054 | 127.0.0.1:8854 | #102 (база — A) | READY_FOR_REVIEW_WITH_BLOCKERS |
| plants-home A (plant-catalog) | claude/template-plants-home | wt-template-plants-home | f034b3f | 127.0.0.1:8855 | #103 | READY_FOR_REVIEW_WITH_BLOCKERS |
| plants-home B (pick-and-diagnose) | claude/template-plants-home-b | wt-template-plants-home-b | 694e764 | 127.0.0.1:8856 | #104 (база — A) | READY_FOR_REVIEW_WITH_BLOCKERS |
| games-story A (chapter-guides) | claude/template-games-story | wt-template-games-story | 1b5e5ae | 127.0.0.1:8857 | #105 | READY_FOR_REVIEW_WITH_BLOCKERS |
| games-story B (progress-tracker) | claude/template-games-story-b | wt-template-games-story-b | 423ba88 | 127.0.0.1:8858 | #106 (база — A) | READY_FOR_REVIEW_WITH_BLOCKERS |
| games-rpg A (codex-sections) | claude/template-games-rpg | wt-template-games-rpg | 125d884 | 127.0.0.1:8859 | #107 | READY_FOR_REVIEW_WITH_BLOCKERS |
| games-rpg B (party-planner) | claude/template-games-rpg-b | wt-template-games-rpg-b | — | 127.0.0.1:8860 (план) | — | building |
| games-rpg, games-survival | claude/template-games-rpg, -survival | созданы, источники проверены (bg3.wiki, minecraft.wiki — 200) | — | 8859/8861 (план) | — | planned |
| garden-season … games-survival | — | — | — | — | — | planned |

Сделано за первые 50 минут: сверка 4 сайтов на 320/390/768/1440 (найдены и исправлены скролл на 320 px в
food-baking, обрезанные подсказки, зоны нажатия <24 px во всех четырёх, падающий тест изоляции в отчётном
commit food-baking); home-practical A от аудита до PR.

Следующие 3 действия: (1) B: ветка `-b` от 19fb887, worktree, порт 8852, навигация «от проблемы», компактный
каталог, последовательные чек-листы; (2) B: QA, карта действий, PR; (3) garden-season A: аудит профильных
садовых/ботанических источников.

Возобновление: `cd /home/claude/wt-template-home-practical/templates/home-practical && bin/home-practical status`;
ветки и PR — таблица выше; проверка ширин — `python3 qa/viewports.py <порт>` в каждом шаблоне.

Обновление: home-practical B готов (34 действия PASS, axe 0, ширины 0). Следующие 3 действия: (1) garden-season A —
аудит садовых/ботанических/университетских источников, выбор проверяемых фактов с регионом; (2) модель «культура ×
сезон × регион», календарь работ; (3) QA и PR. Возобновление: `cd /home/claude/wt-template-garden-season`.

Обновление 21:20Z: garden-season A готов (#101; 29 действий PASS, axe 0, ширины 0; сроков для России в источниках нет — не
придуманы). Следующие 3 действия: (1) garden B «от региона» — ветка `-b` от 18e1723, порт 8854; (2) QA и PR B;
(3) plants-home A — аудит каталогов растений с условиями ухода. Возобновление: `cd /home/claude/wt-template-garden-season-b`.

Обновление 21:38Z: garden B (#102) и plants A (#103) готовы. MBG Plant Finder закрыт robots.txt — заменён NC State Extension.
Следующие 3 действия: (1) plants B — подбор по условиям и диагностика; (2) games-story A — реестр игр и проверка источников/видео;
(3) games-rpg A. Возобновление: `cd /home/claude/wt-template-plants-home-b`.

Обновление 21:58Z: plants B (#104) и games-story A (#105). Игровые вики wiki.gg/Fandom/StrategyWiki/Zelda Wiki — 403
(не обходились); Celeste Wiki, bg3.wiki, minecraft.wiki, terraria.wiki.gg — 200. Реестр games-ownership/1.
Следующие 3 действия: (1) games-story B; (2) games-rpg A (bg3.wiki, патч); (3) games-survival A (minecraft.wiki, крафт).

Обновление 22:19Z: games-story B (#106), games-rpg A (#107). Следующие 3 действия: (1) games-rpg B — планировщик отряда;
(2) games-survival A — minecraft.wiki, крафт с проверяемыми связями; (3) games-survival B.

Обновление 22:39Z: games-rpg B (#108), games-survival A (#109; 22 действия PASS, axe 0, 28 URL × 4 ширины — 0; рецепты кирки и
постройки не выпущены — нет надёжных фактов). Следующие 3 действия: (1) games-survival B «планировщик крафта» — ветка `-b` от db40378,
порт 8862, разбор до базовых ресурсов по количествам слотов источника; (2) QA и PR B; (3) B-варианты food-daily/baking/weekly/appliances.
Возобновление: `cd /home/claude/wt-template-games-survival-b`.

Обновление 22:48Z: games-survival B (#110; 27 действий PASS, axe 0, 32 URL × 4 ширины — 0; планировщик по слотам сетки).
В A исправлен ремонт щита как рецепт (897ebaa, доказательства 845322b). Очередь игровых сайтов закрыта (A и B у всех трёх).
Следующие 3 действия: (1) food-daily B — ветка `claude/template-food-daily-b` от текущего A, свой порт/CSS/JS/хранилище;
(2) food-baking B; (3) food-weekly B и food-appliances B. Возобновление: `cd /home/claude/wt-template-food-daily-b`.

Обновление 23:00Z: food-daily B (#111; fridge-first, порт 8863; 31 действие PASS, axe 0, 57 URL × 4 ширины — 0).
Следующие 3 действия: (1) food-baking B — ветка `-b`, порт 8864; (2) food-weekly B — порт 8865; (3) food-appliances B — порт 8866.
Возобновление: `cd /home/claude/wt-template-food-baking-b`.

Обновление 23:08Z: food-baking B (#112; oven-bench, 8864; 33 действия PASS, axe 0, 29 URL × 4 — 0). В A исправлена обрезанная
подсказка поиска (b758e94, ширины 27 URL — 0). Следующие 3 действия: (1) food-weekly B — порт 8865; (2) food-appliances B — 8866;
(3) итоговый утренний отчёт. Возобновление: `cd /home/claude/wt-template-food-weekly-b`.

Обновление 23:14Z: food-weekly B (#113; agenda-trips, 8865; 26 действий PASS, axe 0, 36 URL × 4 — 0). В A исправлены сокращения
дней (656d2cc, тест). Следующие 3 действия: (1) food-appliances B — порт 8866; (2) итоговый отчёт; (3) при остатке времени — UX A/B.
Возобновление: `cd /home/claude/wt-template-food-appliances-b`.

Обновление 23:19Z: food-appliances B (#114; step-console, 8866; 30 действий PASS, axe 0, 27 URL × 4 — 0). Очередь B-вариантов закрыта:
у всех 10 сайтов есть A и B. Следующие 3 действия: (1) независимая проверка честности отчётов и UX (отдельные агенты-ревьюеры);
(2) исправления по найденному; (3) итоговый утренний отчёт.

Обновление 23:32Z: метатеги варианта добавлены в 4 food-сайта A (de85a8b, 79bf0b8, 1c18349, 7575262). Закрыты пробелы ТЗ:
games-survival «Постройки» (A e5e1a10/b9a814d, B 9e5892b/978d803; 4 GET minecraft.wiki), games-rpg «Предметы» (A 14d7192/0e68f8a,
B 94e6dfb/1c61c07; 4 GET bg3.wiki, без цены; ложное срабатывание запрета «руб» на «рубящего» исправлено с тестом).
Агенты-ревьюеры запрещены хуком (default-deny для Agent) — проверка сделана вручную. Следующее: комментарии в PR, утренний отчёт.

Обновление 23:42Z: home-practical C (#115; home-audit, 8867; 44 действия PASS, axe 0, 48 URL × 4 — 0; найден и исправлен дефект
переноса отметок). Следующие 3 действия: (1) garden-season C — порт 8868; (2) plants-home C — 8869; (3) утренний отчёт.

Обновление 23:55Z: garden-season C (#116; my-plot, 8868; 37 действий PASS, axe 0, 59 URL × 4 — 0), plants-home C (#117; my-collection,
8869; 34 действия PASS, axe 0, 40 URL × 4 — 0). Следующие 3 действия: (1) games-story C — 8870; (2) при остатке времени — C ещё
для одного сайта; (3) утренний отчёт.

Обновление 00:02Z: games-story C (#118; atlas, 8870; 31 действие PASS, axe 0, 29 URL × 4 — 0; найдены белые на белом заголовки,
которые не поймал axe). Следующие 3 действия: (1) C для games-rpg — 8871; (2) C для games-survival — 8872; (3) утренний отчёт.

Обновление 00:07Z: games-rpg C (#119; index-compare, 8871; 27 действий PASS, axe 0, 32 URL × 4 — 0). Следующие 3 действия:
(1) games-survival C «что могу сделать из того, что есть» — 8872, от B (slot_items); (2) утренний отчёт; (3) финальная сверка превью.

Обновление 00:12Z: games-survival C (#120; inventory-first, 8872; 36 действий PASS, axe 0, 37 URL × 4 — 0). Третьи варианты есть у
home, garden, plants, games-story, games-rpg, games-survival. Следующие: (1) C для food-сайтов — по очереди, если хватит времени;
(2) утренний отчёт (за ~40 минут до конца окна).

Обновление 00:17Z: food-weekly C (#121; own-week, 8873; 31 действие PASS, axe 0, 38 URL × 4 — 0). Третьи варианты: 7 сайтов.
Следующие: (1) C для food-baking / food-appliances / food-daily — по времени; (2) утренний отчёт.

Обновление 00:23Z: food-appliances C (#122; device-queue, 8874; 28 действий PASS, axe 0, 30 URL × 4 — 0). Третьи варианты: 8 сайтов.
Осталось: food-daily C и food-baking C (по времени), утренний отчёт.

Обновление 00:29Z: food-baking C (#123; bake-batch, 8875; 32 действия PASS, axe 0, 30 URL × 4 — 0). Третьи варианты: 9 сайтов из 10.
Осталось: food-daily C, утренний отчёт.
