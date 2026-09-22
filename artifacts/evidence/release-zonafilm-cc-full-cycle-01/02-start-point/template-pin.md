# Какая версия шаблона Zona закреплена и почему

Дата снятия: 2026-09-22. Всё ниже — команды и их фактический вывод, а не пересказ.

## Вопрос

Шаблон Zona существует сейчас в двух видах. Нужно выбрать тот, который
**опубликован и исполняется**, а не тот, который просто новее.

| | назначенный релиз | подготовленный артефакт |
| --- | --- | --- |
| путь | `/srv/lords/.frontend/releases/zona-slider-2650fad6/lords-frontend.py` | `/srv/lords/.frontend/zona-01-frontend.py` |
| code sha256 | `7ccf094a1d7f2b5e648a38f51f6a63de9627576637d96f6c966fe1759ad8fa1e` | `bbd6467f7ee9012694020f2cb102e04e5a458bbc5b7c4759662b830987194ff5` |
| source commit | `5863d296264867f85138bd771f1b90a86ac9c599` | `6513e7e7f34baef809ec1149b06ddb47fc869ab9` |
| собран | 2026-09-21T16:29:37Z | 2026-09-21T17:37:22Z |
| назван в `template-manifest-zona-01.json` | как **rollback_target** | как **текущий** |

## Что связывает витрину с кодом

`/srv/lords/.frontend/lords-frontend.py` (138 строк) ничего не отдаёт сам. Он
находит витрину по порту в `lords-runtime-registry.json`, разрешает
`sites/<витрина>/current` и передаёт управление через `os.execv`.

```
$ ls -la /srv/lords/.frontend/sites/zona-01/
lrwxrwxrwx 1 claude claude 35 2026-09-21T16:34:40Z current -> ../../releases/zona-slider-2650fad6
```

Ссылка ведёт на `zona-slider-2650fad6`. Подготовленный `zona-01-frontend.py`
не назначен никому: на него не ссылается ни `current`, ни `ExecStart`.

```
$ grep ExecStart /etc/systemd/system/nova-zona-01.service
ExecStart=/usr/bin/python3 /srv/lords/.frontend/lords-frontend.py --port 9120
```

## Почему манифеста недостаточно

`/__template_version` отдаёт содержимое файла манифеста, а не свойство
исполняемого кода:

```
$ curl -s http://127.0.0.1:9120/__template_version
{… "build_id": "zona-slider-6513e7e7f34b", "code_file_sha256": "bbd6467f…" …}
```

То есть витрина **объявляет** сборку 17:37. Брать это на веру нельзя — манифест
пишется отдельно от выкладки релиза.

## Независимая проверка по выдаче

Скрипт слайдера героя появился только в новом артефакте, и он оставляет в
разметке атрибуты `data-zhero-*`, которых в назначенном релизе нет:

```
$ diff releases/zona-slider-2650fad6/lords-frontend.py zona-01-frontend.py | grep -c '^> .*data-zhero'
(ненулевое: весь блок ЗОНА_СКРИПТ_ГЕРОЯ присутствует только справа)

$ curl -s -H 'Host: zonafilm.space' http://127.0.0.1:9120/ | grep -o 'data-zhero-[a-z]*' | sort | uniq -c
(пусто)
```

Живая выдача **не содержит ни одного** `data-zhero-*`.

## Вывод

Исполняется `zona-slider-2650fad6` (`7ccf094a…`, commit `5863d296…`).
Он и закреплён для `zonafilm.cc`.

Сборка `6513e7e7` не опубликована: это незавершённая работа соседнего терминала
в `/home/claude/wt-zona-real-slider-01`, ожидающая рестарта. Подхватить её
значило бы сделать ровно то, что запрещено заданием.

## Побочная находка (не мой контур)

`zona-01` сейчас **неверно объявляет свою сборку**: `/__template_version`
называет `zona-slider-6513e7e7f34b`, а исполняет `7ccf094a…`. Эндпоинт читает
манифест, а не код, поэтому расхождение выкладки и манифеста им не ловится.

Оформлено как `TEMPLATE_ZONA_BLOCKER-01` с воспроизводимым тестом —
см. [`../../../../docs/release-orchestrator/TEMPLATE_ZONA_BLOCKERS.md`](../../../../docs/release-orchestrator/TEMPLATE_ZONA_BLOCKERS.md).
Ветка шаблона не трогается.
