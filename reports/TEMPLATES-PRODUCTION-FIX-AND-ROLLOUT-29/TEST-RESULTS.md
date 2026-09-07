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
