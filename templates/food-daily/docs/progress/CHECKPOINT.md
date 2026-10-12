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
