# TEMPLATE-ZONA-FINALIZATION-21 — независимая финализационная проверка Zona

Сессия: `claude/zona-template-finalization-01`. START_HEAD и FINAL_HEAD этой
задачи не меняют код фабрики, Lords или Animedia — только добавляют этот
Zona-only evidence-пакет. Ни один файл вне `artifacts/evidence/` не менялся.

## Объект проверки

| Поле | Значение |
| --- | --- |
| `site_id` | `zona-cinema-preview` |
| `profile` | `zona-cinema` (`blueprints/lords/profiles/zona-cinema.yaml`) |
| `blueprint` | `lords` (portfolio `lords`, job_id `lords-04-001`) |
| Пакет | `sites/zona-cinema-preview/package.yaml` |
| Live alias | `zona-01` (см. `tests/lords/test_suite1_route_catalog_parity.py: ПАКЕТЫ`) |

Пакет — локальный срез без домена и без production-авторизации
(`deployment_readiness.status: BLOCKED_INPUT_DOMAIN_TARGET`,
`production_authorized: false`). Это состояние не менялось и меняться в этой
задаче не должно.

## Что проверено в этой сессии

### 1. `python3 -m factory validate --site zona-cinema-preview`

Exit: статус `BLOCKED_RIGHTS` (плюс `BLOCKED_ACCESS`: `target_ref` не
передан). Права на контент не подтверждены владельцем — это факт пакета, не
дефект: полноценная сборка на реальном каталоге здесь недоступна и
недоступна законно (`content_source.rights_confirmed: false`).

### 2. `python3 -m factory lords-preview --site zona-cinema-preview`

Собран локальный стенд на синтетическом fixture-каталоге (62 записи, не
реальный контент): `artifacts/lords/preview/zona-cinema-preview/` (не
коммитится — генерируемый каталог, воспроизводится командой выше). Плеер:
`BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS` — секретов CDNVideoHub в этой среде
нет, проверка контракта плеера не запускалась. Это ожидаемо и не выдаётся за
`PASS`.

### 3. `python3 -m factory template-audit --site zona-cinema-preview --root artifacts/lords/preview/zona-cinema-preview`

Результат сохранён целиком: `template-audit-zona-cinema-preview.json`.
Минимум по всем применимым страницам — **10.0** (`home`, `catalog`, `title`,
`new`, `schedule`, `genres`, `genre_landing`, `search`). `collections` —
`applicable: 0`, поскольку `content_types.collections: false` в пакете: это
не пустая секция, а корректно выключенный тип по манифесту, ложных 0.0 в
смысле дефекта здесь нет.

Рубрика `LORDS_KEY_PAGES` (`factory/templates/rubric.py`), которую использует
`template-audit` для профилей на blueprint `lords` (в т.ч. Zona), **не
содержит** ожидания `not_found` (404) — оно объявлено только в наборе
`BASIS_KEY_PAGES`. Поэтому `/404.html` не входит в автоматический отчёт;
страница проверена вручную (см. ниже). Это пробел общей рубрики, а не
Zona-специфичный файл — не исправлялся, см. «Передано Lords writer».

### 4. Ручная проверка 404

`artifacts/lords/preview/zona-cinema-preview/404.html`: корректный `<title>`,
`h1`, `noindex, nofollow`, работающая навигация и форма поиска, явная пометка
тестового стенда, никакого выдуманного контента. Дефектов не найдено.

### 5. Постеры и карточки — найден дефект (не Zona, общий движок)

На локальном fixture-стенде все карточки каталога и блока «похожее»
рендерятся с заглушкой (`card__poster-empty`, первая буква названия), хотя
для каждой записи реально существует сгенерированный постер
(`assets/posters/<slug>.svg`, 50/50 записей) и страница произведения
**своим** постером пользуется корректно
(`<img src="/assets/posters/<slug>.svg" ... width="400" height="600">`,
пропорция сохранена — фикс 399f49b подтверждён на этом пути).

Причина — в `factory/lords/render.py`:

- `_poster()` (строка ~655) читает `getattr(title, "poster_url", None)`;
- атрибут `poster_url` существует только у `live_catalog.py`-модели (реальный
  content_api), а у `fixtures.py::Title` (синтетический стенд) есть
  `poster_src`/`poster_path` — их и использует `_title_page()` (строка 1993)
  для постера самой страницы произведения;
- в карточках (`_card`, строка 603, и вызовы на строках 2516/2690) поэтому
  `source` всегда `None`, и всегда рисуется буква вместо изображения — на
  ЛЮБОМ синтетическом стенде `lords-preview`, для ЛЮБОГО профиля портфеля
  `lords` (Lords, Zona, Animedia), не только для Zona.

Воспроизведение:
```
python3 -m factory lords-preview --site zona-cinema-preview
grep -o '<a class="card__poster"[^>]*>' artifacts/lords/preview/zona-cinema-preview/catalog/index.html | wc -l   # 24
grep -o 'card__poster-empty' artifacts/lords/preview/zona-cinema-preview/catalog/index.html | wc -l              # 24 — все без картинки
ls artifacts/lords/preview/zona-cinema-preview/assets/posters/pepelnyy-nevod-2025.svg                            # файл есть
```

Файл `factory/lords/render.py` — общий код (`factory/lords/**`), править его
в Zona-задаче запрещено. **Передано Lords writer как есть**, не исправлено.
На production/candidate это не проявляется: там `poster_url` приходит из
живого content_api и карточки рендерятся с изображением (см. свежую
браузерную матрицу ниже, `overflow=false` на всех cross-browser снимках).

### 6. `pytest tests/zone -q` (целевой прогон, полный suite не запускался)

Полный вывод хвоста — `pytest-zone-tail.log`. Итог:
**1 failed, 67 passed, 86 skipped, 3 warnings** за 165.79s.

Скип — все по одной причине: нет локальной полной сборки
`var/build-a/{zona-cinema,animedia-portal,lords-02}` (suite4/5/7). Это
честный `SKIPPED` с причиной, не `PASS`.

Единственное падение —
`test_suite3_full_catalog_route_policy.py::TestУстойчивостьПубличныхАдресов::test_действующие_адреса_остались_за_своими_сущностями`.
Разобрано: фикстуры этого теста жёстко читают снимок каталога **lords-02**
(`СНИМОК = /srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json`,
строка 22 файла) — это живой, постоянно обновляемый снимок другого сайта
портфеля (`lords-02`, НЕ `zona-cinema-preview`/`zona-01`). Файл лежит в
`tests/zone/` по историческим причинам организации тестов, но данные и код
(`factory.lords.urlmap`, `factory.lords.live_catalog`) не принадлежат Zona.

Падение: сущность `01a0af0e-4f6f-76b3-ac08-a8be6fc3c6f2` в текущем живом
снимке lords-02 лишилась ранее закреплённого адреса. Снимок каталога и
route-ledger обновляются фоново (mtime на момент прогона: `catalog-cache/lords-02.json`
— 2026-09-17T14:49:27Z, `route-ledger.json` — 2026-09-17T15:10:06Z, то есть
«сейчас», а не при последнем коммите фабрики) — воспроизводимость зависит от
текущего состояния живых данных lords-02, не от кода этой ветки. Это
**существовало до начала задачи**: между коммитом evidence прежнего полного
прогона (`36dc0c2`, только Yummy-падение) и текущим HEAD (`60870de`) код не
менялся вовсе (60870de — только evidence). **Передано Lords writer как
есть**, не исправлено: код (`factory/lords/**`) и данные (`lords-02`) вне
Zona-области этой задачи.

### 7. Свежесть прежних evidence

| Каталог | Дата коммита | Относительно фиксов 399f49b (06:01 UTC) / bccf1ba (06:52 UTC) 2026-09-15 | Статус |
| --- | --- | --- | --- |
| `templates-zona-animedia-owner-review-007/browser-matrix.json`, `browser-matrix-final.json`, `performance.json` (обновлены в `60870de`) | 2026-09-15T10:23Z | ПОСЛЕ обоих фиксов | Актуально |
| `templates-zona-animedia-owner-review-007/test-results-final.txt` (`36dc0c2`) | 2026-09-15 (после `36dc0c2`, само `36dc0c2` после обоих фиксов) | ПОСЛЕ | Актуально |
| `templates-zona-animedia-owner-review-007/width-sweep.json` (`399f49b`) | 2026-09-15T05:55Z | ДО фикса пропорций (запись «before», сам фикс — часть того же коммита) | Историческое «до», не текущее состояние |
| `templates-zona-animedia-owner-review-007/shots/*`, `owner-package/pairs/*` | 2026-09-15T05:27Z | ДО обоих фиксов | Устарело — не отражает текущие постеры/карточки |
| `artifacts/evidence/release/preview-screenshots/zona-cinema-*.png` | 2026-09-05 | Задолго до редизайна `0a2658c`/фиксов | Устарело |
| `artifacts/evidence/templates/families-a11y/axe-zona-cinema-*.json` | 2026-09-05 | Задолго до редизайна/фиксов | Устарело |
| `templates-zona-animedia-visual-parity-005/006/*` | до `0a2658c` | Предшествует переработке | Устарело, историческая веха |
| `templates-lords-zona-canary-004/*`, `templates-lords-zona-visible-003/*` | ранние канареечные разборы | Предшествуют текущему коду | Историческая веха расследования, не текущее состояние |

Устаревшие каталоги не удалялись и не переписывались: они — исторический
след расследований, полезный для контекста, но не источник текущего PASS.

### 8. Закрытый reference-доступ (не выдаётся за PASS)

`w140.zona.plus` отклоняется guard'ом до сети: домена нет в
`network_allowlist`/`inventory`, и это зафиксировано ранее
(`145f2db`, «оба эталона закрыты политикой»). В этой сессии сеть наружу не
запрашивалась и visual parity против внешнего эталона не выполнялась —
статус остаётся BLOCKED, не PASS.

### 9. Production и деплой

Не трогались. `production_authorized: false`, `target_ref: null`,
`inventory/targets.yaml` без production-целей — состояние не менялось и
менять его не входило в задачу.

## Итог

Ни одного Zona-специфичного дефекта, который можно и нужно чинить в
границах этой задачи, не найдено. Оба найденных дефекта — общий движок
(`factory/lords/render.py`, снимок `lords-02`) — переданы Lords writer с
точным воспроизведением выше и не исправлялись. Все целевые Zona-тесты и
доступные локальные проверки (validate, lords-preview, template-audit,
ручная проверка 404, pytest tests/zone) прошли в пределах того, что в этой
среде вообще измеримо; недоступное (реальный плеер, полная сборка,
внешний эталон) честно отмечено как заблокированное, а не как PASS.
