# Результаты тестов

## Фабрика (`sbc-create/test`, ветка `claude/templates-production-fix-29`)

```
5156 passed, 9 failed, 6 skipped, 2 xfailed   (13 мин 05 с)
```

**Все девять провалов воспроизводятся на точке ветвления `f87b2ff` — ни один
не вызван правками этапа.** Сверено запуском тех же файлов в отдельном рабочем
дереве на `f87b2ff`:

| файл | на `f87b2ff` | на ветке этапа |
|---|---|---|
| `test_owner_status_document.py` | 6 провалов, 13 проходов | 6 провалов, 13 проходов |
| `test_lords_canary.py::TestDubiousOwnershipReproduced`, `test_lords_search_index.py`, `test_lords_theme_switch.py` | 3 провала, 28 проходов | 3 провала, 28 проходов |

Числа совпадают полностью. Правки этапа трогают слой отдачи постеров и
отчётность, а перечисленные проверки относятся к документу состояния
продуктов, канареечному сценарию Lords, порогу скорости указателя поиска и
переключателю темы.

### Новое в наборе

* `tests/unit/test_poster_origin_is_resolved_per_request.py` — 15 проверок.
  На конфигурации ДО исправления набор падает (6 failed, 9 errors), после —
  15 passed. То есть проверка ловит именно тот дефект, ради которого написана.
* `tests/unit/test_lords_search_multiword_typo.py` — 6 проходов и один
  `xfail(strict=True)`, удерживающий видимым предел поиска по опечатке.

## Приложение Yummy (`sbc-create/yummyani`, ветка `claude/yummy-update-time-29`)

```
763 passed, 0 failed   (97 файлов)
tsc --noEmit: 33 сообщения — столько же, сколько до правок, и те же самые
eslint, prettier: чисто
```

Новое: 4 проверки в `tests/unit/updates-from-events.test.ts` и 5 в
`tests/unit/announcements-sparse-state.test.ts`.

Отдельно: фикстура `syntheticTitleDetail` наследовала `updated_at` от
`syntheticTitleItem` и потому была щедрее боевого поставщика — на ней дефект
времени не воспроизводился. В файле проверок деталь теперь строится без
`updated_at`, как отвечает боевой API.

## После цикла 9 (8 сентября 2026)

### Фабрика

```
5171 passed, 9 failed, 6 skipped, 1 xfailed   (14 мин 21 с)
```

Набор провалов **посимвольно тот же**, что и до правки поиска — сверено
построчным сравнением списков `FAILED`:

```
tests/unit/test_lords_canary.py::TestDubiousOwnershipReproduced::…
tests/unit/test_lords_search_index.py::test_живой_каталог_…
tests/unit/test_lords_theme_switch.py::test_без_второй_палитры_…
tests/unit/test_owner_status_document.py::…  (шесть)
```

Все девять ранее воспроизведены на точке ветвления `f87b2ff`. Проходов стало
на 15 больше — это новые проверки token-aware поиска за вычетом снятого файла
с постоянным `xfail`. Самих `xfailed` осталось 1 вместо 2: предел
многословного поиска закрыт, и пометка снята вместе с файлом.

### Приложение Yummy

```
808 passed, 0 failed   (102 файла)
tsc --noEmit: 33 сообщения — столько же, сколько до правок
eslint, prettier на изменённых файлах: чисто
```

Новое: 21 проверка `fuzzy-match.test.ts`, 4 — `search-typo-fallback.test.ts`,
5 — `provider-time-provenance.test.ts`, 10 — `estimated-air-date.test.ts`.
