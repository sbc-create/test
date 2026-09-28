# Граф зависимостей и что в нём не так

Построено разбором AST по `factory/`. Полный граф порождается командой
`python3 tools/inventory.py .` и ложится в
`artifacts/site-engine/dependency-graph.json`. В репозиторий он не
коммитится: каталог `artifacts/` под `.gitignore`, и производный файл там
устаревал бы молча. Воспроизводится одной командой.

## Зависимости между областями

```
__main__      -> cli
cli           -> analytics, input_request, locks, lords, paths, report, secret_hub, seo, state, targets, errors
lords         -> analytics, build, errors, paths, recs, seo
build         -> errors, lords, paths, render
recs          -> lords, paths
validation    -> analytics, lords, paths
pipeline      -> analytics, errors, locks, paths, report, retry, seo, state, targets
verify        -> paths, redaction, seo
render        -> analytics, errors, paths
analytics     -> errors, paths, redaction, retry
secret_hub    -> errors, paths, redaction
targets       -> errors, locks, paths, redaction
topvisor      -> errors, redaction, retry
seo           -> paths
```

`paths`, `errors`, `redaction`, `retry`, `locks`, `state` ни от кого не зависят
— это фактическое ядро, и оно уже нейтрально.

## Найденные нарушения

Ничего не удалено и не переписано. Каждая запись классифицирована.

### 1. Взаимные зависимости

| Пара | Точные рёбра | Классификация |
| --- | --- | --- |
| `build` ↔ `lords` | `factory.build → factory.lords`, `factory.lords.preview → factory.build` | **заменить контрактом**: `build` должен знать интерфейс рендерера, а не витрину |
| `lords` ↔ `recs` | `factory.lords.recommend → factory.recs{,.model,.ranker}`, `factory.recs.cli → factory.lords` | **обернуть адаптером**: `recs` — универсальный ранжировщик, обратное ребро идёт только из его CLI |

На уровне модулей (а не областей) настоящий импортный цикл один:
`factory.analytics ↔ factory.analytics.yandex` — пакет и его подмодуль,
`__init__` реэкспортирует. Безвреден, оставить.

### 2. SEO внутри модуля сайта

`factory.lords.gate → factory.seo`, `factory.seo.model`;
`factory.lords.plan → factory.seo.uniqueness`.

Классификация: **заменить контрактом** (`seo-bridge`). SEO не должен быть
зависимостью витрины; витрине нужен результат проверки, а не сам модуль.

### 3. Ядро знает тип сайта

`factory.validation → factory.lords`, `factory.build → factory.lords`,
`factory.cli → factory.lords`.

Классификация: `cli` — **оставить** (командной строке положено знать команды);
`validation` и `build` — **заменить контрактом** через реестр рендереров.

### 4. Единой точки входа к поставщику нет

`cdnvideohub` упоминается в семи модулях `lords` плюс `verify` и
`analytics.events`. Классификация: **обернуть адаптером** — `provider-adapters`.

### 5. Кэш смешан с выборкой

`factory/lords/content_live.py` одновременно ходит к поставщику, решает
свежесть кэша и пишет файлы. На стороне Yummy то же смешение было в
`catalog-query.ts` и частично разделено в родительской задаче.
Классификация: **заменить контрактом** (`cache-invalidation` + `CacheProvider`).

### 6. Дублирование Lords и Yummy

Полки, рейтинги, расписание и события реализованы дважды — на Python для Lords
и на TypeScript для Yummy. Классификация: **оставить пока**, свести к общему
контракту нормализованной модели; переписывать рабочие витрины в рамках 02A
запрещено.

## Чего в графе нет

Прямых обращений UI к runtime-файлам на стороне Python нет: витрины Lords
статические, файлы читает сборщик. На стороне Yummy такое обращение есть и
описано отдельно — страница читает снимок наблюдателя. Это осознанное
исключение: снимок и есть публичный интерфейс наблюдателя, и он вынесен за
`readWatcherSnapshot`, а не разбросан по компонентам.
