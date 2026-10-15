# Режим индексации партии K2 — измерение 2026-10-15

Вопрос: допущены ли восемь витрин партии (`lords-10`…`lords-17`) к индексации,
и нужен ли для согласованного открытия НОВЫЙ выпуск. Поводом стал вердикт
инструмента, утверждавший второе.

## Что сообщал инструмент до правки

```
$ python3 -m factory.qwen indexing --site lords-10      # exit 0
"status": "MECHANISM_UNSUPPORTED", "release_gap": "reader_missing",
"reason": "в выложенном релизе  нет src/indexing_mode.py",
"next_action": "остановиться: открытие невозможно до НОВОГО выпуска…"
```

Это вывод о ДРУГОЙ машине. Витрины партии выкладываются на `k2-zomro-01`
(`deploy_target.ref` в реестре ячеек), а читатель режима, корень выпуска и
слой nginx инструмент искал по локальным путям `/srv/<учётная запись>/…`
управляющего узла, где этих каталогов нет и быть не должно. Поле
`published_release` по той же причине было пустым — отсюда двойной пробел в
тексте причины.

## Измерение на узле витрин

`bash scratchpad/д20-режим-на-узле.sh` (ansible → `k2-zomro-01`, exit 0),
полный вывод — ниже. Одинаково у всех восьми:

| Признак | Значение |
| --- | --- |
| читатель `src/indexing_mode.py` в выложенном релизе | есть, 8237 байт |
| подключён файлом выпуска | `src/lords-frontend.py` |
| заголовок самого приложения | `X-Robots-Tag: noindex, nofollow` |
| переключаемый слой nginx | `add_header X-Robots-Tag $cell_robots_lords_1X always;` |
| `robots.txt` | `User-agent: *` / `Disallow: /` |
| `sitemap.xml` | 404 (так задумано: карту рантайм отдаёт только в режиме OPEN) |

```
lords-10|lordfilm.group|reader=8237|wired=…/src/lords-frontend.py|app_xrobots=X-Robots-Tag: noindex, nofollow|nginx=add_header X-Robots-Tag $cell_robots_lords_10 always;|robots=User-agent: */Disallow: //|sitemap=404
lords-11|lordfilm.spb.ru|reader=8237|…|lords-12|lordfilm.msk.ru|reader=8237|…
lords-13|lordserial.su|reader=8237|…|lords-14|lordserial.group|reader=8237|…
lords-15|lordserial.spb.ru|reader=8237|…|lords-16|lordserial.msk.ru|reader=8237|…
lords-17|lordserial.net.ru|reader=8237|…
```

## Вывод

Режим восьми витрин — **CLOSED, и это согласованное состояние**, а не пробел
выпуска. Механизм режима в выложенном релизе ЕСТЬ и работает: закрытие
объявляет сам рантайм, а слой nginx управляется переменной ячейки. Нового
выпуска для открытия не требуется — открытие выполняется действующей
процедурой проекта на узле витрины:

```
python3 -m factory cell submit --cell-operation indexing-nginx --mode open --site <site_id>
```

Открытие по этому измерению НЕ выполняется: оно остаётся за предусмотренным
проектом сроком и решением владельца (задание прямо требует сохранять CLOSED).

Отдельно: доступность посетителям и допуск к индексации — разные вещи. Витрины
отвечают 200 на своём узле и будут доступны посетителям сразу после перевода
DNS; допуск к индексации при этом остаётся закрытым до отдельной операции.

## Чем эту закрытость доказывать НЕЛЬЗЯ

Реестром аналитики. Измерено 20:10 (MOD-41): поле `seo_indexing_enabled`
равно `false` у **всех** записей и в копии службы, и в ветке — ни одной
«открытой», — при том что `animedia.icu` отдаёт `x-robots-tag: index, follow`
и открытый `robots.txt`. Поле отвечает «закрыто» независимо от
действительности, и проверка по нему «подтвердила» бы требование владельца,
не измерив ничего. Это тот же класс, что исправленный утром в самом
инструменте: ответ, который не зависит от предмета.

Поэтому закрытость партии K2 здесь доказана **измерением на узле витрин**
(раздел выше): состояние читается у самой витрины на её узле, а не из
реестра и не из локальных путей управляющего узла. Если понадобится
перепроверить после выпуска — тем же способом; сверка поля реестра с живой
витриной делается `automation/local/analytics-registry-vs-live.py`, и для
восьми витрин она пока неприменима: публичные имена ведут на прежний узел
(HTTP 421), то есть снаружи мерить нечего до перевода DNS.

## Правка инструмента

`factory/qwen/registry.py` — запись сайта несёт `deploy_target` и
`release_measurable_here`; пустой `published_release` у витрины другого узла
сопровождается примечанием «измеряется ТАМ».

`factory/qwen/indexing.py` — `чужой_узел()`: отсутствие читателя на этом узле
у витрины другого узла даёт `MECHANISM_UNPROVEN` с полем `proof` (точная
команда на узле витрины), а не `MECHANISM_UNSUPPORTED/reader_missing`;
предпроверка операции блокирует по верной причине; блок `nginx_layer` называет
машину, на которой прочитан.

```
$ python3 -m factory.qwen indexing --site lords-10      # exit 0, после правки
"deploy_target": "k2-zomro-01", "status": "MECHANISM_UNPROVEN",
"public_mode": "CLOSED",
"proof": "не получено: наличие и подключение src/indexing_mode.py … измеряется
          на узле витрины — на k2-zomro-01: ls -l /srv/lordfilm-group/current/src/indexing_mode.py"
```

```
$ python3 -m pytest tests/unit/test_indexing_remote_target.py -q
6 passed in 3.22s
# на неисправленном коде (git checkout обоих файлов): 6 failed
$ python3 -m pytest tests/unit/test_indexing_core_registry.py \
    tests/unit/test_indexing_live_snapshot.py \
    tests/unit/test_indexing_operation_behaviour.py \
    tests/unit/test_qwen_indexing_operation.py \
    tests/unit/test_nginx_indexing_layer.py tests/unit/test_qwen_site_management.py \
    tests/unit/test_qwen_mcp_bridge.py tests/unit/test_cell_registry.py -q
273 passed in 155.91s
```

Это третий случай одного класса в этом модуле: сперва зашитый `current` у
витрин прямой установки, затем реестр ядра не того узла, теперь — верный путь
на неверной машине. Вывод по локальному пути о витрине другого узла впредь
невозможен: решение одно, названо и покрыто проверками.
