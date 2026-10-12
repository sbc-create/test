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
| garden-season A | claude/template-garden-season | wt-template-garden-season | — | 127.0.0.1:8853 (план) | — | building |
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
