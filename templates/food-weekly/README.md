# food-weekly — «Меню на неделю», вариант C `own-week`

Вариант C: своя неделя из каталога (или план как основа) → список покупок на 1–8 чел. Порт 8873, ключи `fwc.*`.
Вариант A — ветка `claude/template-food-weekly`, B — `claude/template-food-weekly-b`.

Третий сайт сети (PRACTICAL-NETWORK-NIGHT-CONTINUE-02). Ветка `claude/template-food-weekly`,
worktree `/home/claude/wt-template-food-weekly`, база `origin/main` `a7f7cb6`. Весь сайт — `templates/food-weekly/`.

Планировщик: недельная сетка 7 × (завтрак, обед, ужин), страница дня, список покупок,
который считается из реальных рецептов соседнего сайта «Будни на кухне», замена блюда
без регистрации и без JS. Рецепты не копируются: план ссылается на материал по
`content_id` из ленты `recipe-catalog/1` (`/api/catalog.v1.json` сайта food-daily).

| страница | адрес |
| --- | --- |
| главная | `/` |
| каталог меню | `/menyu/` |
| неделя | `/menyu/<план>/`, замены — `?s=` / `?zamena=` (noindex, без canonical) |
| день | `/menyu/<план>/den-<1..7>/` |
| список покупок | `/menyu/<план>/pokupki/` |
| инструкция | `/kak-planirovat/` |
| подборки | `/podborki/`, `/podborki/<id>/` (≥3 блюд) |

```bash
bash templates/food-weekly/bin/food-weekly start | stop | status | restart   # только этот preview, 127.0.0.1:8873
bash templates/food-weekly/bin/food-weekly catalog    # обновить снимок каталога food-daily (preview должен работать)
bash templates/food-weekly/bin/food-weekly test
bash templates/food-weekly/bin/food-weekly build --commit HEAD
cd templates/food-weekly && python3 -m weekplan.qa --shots <dir> --out <json>   # браузер + axe (templates/food-weekly/qa)
```

Связь с каталогом: `config/network.yaml` — адреса сайтов сети по режимам; production-адресов
нет (домены не выбраны), поэтому ссылки в preview ведут в закрытый preview food-daily
(`integration_status: preview_adapter`). При недоступности соседа меню работает от снимка
`data/catalog/food-daily.json`.

Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
