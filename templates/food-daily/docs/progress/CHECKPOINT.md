# Checkpoint — PRACTICAL-NETWORK-NIGHT-CONTINUE-02

Старт: 12.10.2026. Обновляется при каждой смене этапа.

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
