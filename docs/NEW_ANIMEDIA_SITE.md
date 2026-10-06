# Новый сайт семейства Animedia: запуск без ручной установки обработчика

Документ для того, кто поднимает третий и следующие сайты Animedia. Отдельного
шаблона Animedia в пуле `factory cell templates` нет: шаблоном служит
репозиторий действующего сайта `sbc-create/site-animedia-space` (или
`site-animedia-icu`), его `docs/TEMPLATE_PORT.md` и `AGENTS.md`.

## Что сайт Animedia обязан иметь в репозитории

| Путь | Зачем |
| --- | --- |
| `src/anime_admission.py` | одно правило тематического допуска: аниме и дунхуа — admit, спорное — review, западная анимация — exclude |
| `src/animedia-frontend.py` | витрина; допуск применяется при загрузке снимка, `/healthz` несёт блок `updater` |
| `automation/<сайт>-update.py` | обработчик обновлений: допуск и карта сайта — обязательные шаги, замок данных, удостоверение кода |
| `deploy/<учётка>-update.service`, `.timer` | юнит и таймер обработчика; ExecStart и WorkingDirectory — **только** `/srv/<учётка>/current`; `SuccessExitStatus=0 1 75` |
| `checks/catalog_scope_rules.py`, `checks/updater_conformity.py` | правило допуска и путь обработчика; подключены в `checks/run.sh` |

## Порядок запуска

1. Репозиторий сайта — копией шаблона в `sbc-create/site-<домен>`; домен,
   site_id, учётка, порт, PUB ID — только из заказа владельца
   (`BLOCKED_INPUT` при пустом поле). Имена в `deploy/` заменить на учётку
   нового сайта; пути `/srv/<учётка>/current` и `/srv/<учётка>/data`.
2. `bash checks/run.sh` — зелёный. Ветка `claude/extract-*`, push, CI release
   зелёный.
3. Запись в `config/site-cells.json` фабрики с блоком
   ```json
   "runtime": {
     "account": "<учётка>", "unit": "nova-<учётка>.service", "port": <порт>,
     "data_dir": "/srv/<учётка>/data",
     "updater": {
       "service": "<учётка>-update.service",
       "timer": "<учётка>-update.timer",
       "credentials": ["<имя>:<путь секрета>"]
     }
   }
   ```
   Без `runtime.updater` исполнитель обработчик не ставит, и сайт будет жить
   на снимке, застывшем в момент выкладки.
4. Выпуск — штатной очередью (`factory cell submit … --cell-operation
   activate`). Исполнитель в `promote` сам ставит юнит витрины **и** юнит с
   таймером обработчика из `current/deploy/` выпуска, проверив их закрытым
   белым списком; предпроверка до прогрева отклоняет выпуск, после которого
   обработчик исполнял бы не выложенный код.
5. После выпуска:
   ```bash
   python3 -m factory cell updater-check --site <site_id>   # код 0 = согласован
   curl -s https://<домен>/healthz | python3 -c 'import json,sys;print(json.load(sys.stdin)["updater"])'
   ```
   Первый прогон обработчика (≤10 мин) обязан дать `result: "ok"`,
   `required_steps: {"admission": "ok", "sitemap": "ok"}` и
   `updater.release_commit` = коммит выпуска; `/sitemap.xml` — 200.

## Чего не делать

* Не ставить `deploy/*-update.service` руками (`sudo cp`). Так юнит
  animedia.icu с 27.09 неделю исполнял `/srv/animedia-icu/app` без шагов
  карты и допуска, а журнал говорил «проблем: 0».
* Не указывать в юнитах `app`, каталог конкретного выпуска или рабочую копию
  репозитория — только `/srv/<учётка>/current`.
* Не исключать записи из каталога списком названий: решает
  `anime_admission.py` по устойчивым ID и классификациям.
