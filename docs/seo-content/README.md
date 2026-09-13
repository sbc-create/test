# Контур качества SEO-контента

Путь новой или изменённой сущности до черновика:

```
событие → SEOFactPack → Writer → детерминированные проверки →
Blind Judge → ворота → SEOContentDraft → (тень) предложение
```

Контур ничего не публикует. Последняя точка — черновик в собственном
эфемерном хранилище. Одобрение, применение и публикация принадлежат Control
Plane, и прав на них у контура нет — не «мы ими не пользуемся», а их нет в
контракте.

## Как новый тайтл доходит до SEO

Не обходом витрины. SEO не ищет новинки, перебирая страницы: появление и
правка контента приходят **событием**. Поддержаны семь канонических событий:

```
title.created  title.updated
season.created season.updated
episode.created episode.updated
metadata.corrected
```

Из события собирается неизменяемый `SEOFactPack`. У пакета нет скалярных
полей — есть факты, и значение достаётся через `pack.value("/year")`. Если
факта нет, значения нет тоже. Именно поэтому «подставить значение по
умолчанию» технически не к чему: выдумывать пришлось бы факт с источником,
снимком и временем получения.

## Почему текст не может содержать выдумки

Три независимых рубежа.

1. **Вход.** Факт без `source_id`, `provider`, `retrieved_at`,
   `snapshot_hash` и `field_path` не создаётся — конструктор отказывает.
2. **Сборка.** Предложение строится из значения факта. Нет факта — нет
   предложения; текст становится короче, а не богаче.
3. **Выход.** Из готового текста извлекаются проверяемые утверждения и
   сверяются с фактами: `SUPPORTED` (со ссылкой на `fact_id`),
   `CONTRADICTED`, `UNSUPPORTED`, `NON_FACTUAL_STYLE`. Существенное
   недоказанное утверждение блокирует черновик наравне с опровергнутым:
   для читателя недоказанное и ложное неразличимы.

## Пять чисел серии

Номер внутри сезона, абсолютный, номер источника, число в адресе и
отображаемый — пять разных величин. Они совпадают часто и потому кажутся
одним числом; стоит каталогу досчитаться до 210, а списку оборваться на 100 —
и совпадение кончается.

Здесь ни одно число не выводится из другого арифметикой. Какое из них стоит
в адресе — **объявляет маршрут**; не объявлено — `URL_NUMBERING_SCHEME_UNDECLARED`
и отказ. Адрес обязан вести к той же сущности, иначе
`URL_RESOLVES_TO_OTHER_EPISODE`. Если перечень обрывается раньше номера —
`EPISODE_NOT_REACHABLE`: страница есть, пути к ней нет.

После разрешения личности отдельная проверка ищет отставший номер во всех
поверхностях сразу: заголовок, описание, H1, текст, хлебные крошки,
canonical, OpenGraph, JSON-LD.

## Редакционные заметки, а не поддельные отзывы

`resource_kind=seo.editorial_note`, `comment_mode=EDITORIAL_COMMENTARY`,
`author_type=EDITORIAL_AI`.

Разница с отзывом не в пометке, а в устройстве: у заметки нет полей автора,
оценки, времени, лайков и ответов — их не существует, и попытка прислать
отклоняется. Разметка `Review` и `AggregateRating` из модельного текста не
создаётся никогда: утверждать машине о существовании чужого мнения нельзя по
той же причине, по которой нельзя утверждать это человеку.

Заметок от нуля до трёх. Пустой массив — исправный исход. Заметка ради
наличия заметки — брак.

## Уникальность

Несколько независимых измерителей вместо одного «процента уникальности»:
точный хеш, нормализованный, по основам слов, цепочки от 12 слов,
char-5-граммы, MinHash, SimHash и маскирование имён — последнее ловит
главный способ подделки: взять чужой текст и поменять название.

Семантическая близость **не измеряется**: локальных embeddings нет, и порог
0,92 объявлен `NOT_EVALUATED`, а не пройденным.

Если у витрины нет собственного информационного угла, а каталог тот же, что
у соседей, — фиксируется doorway-риск и рекомендуется канонизация либо
`noindex`. Механический рерайт ценности не создаёт, и делать вид, что
создаёт, контур не будет.

## Файлы

| Путь | Что делает |
| --- | --- |
| `factory/seo_content/factpack.py` | неизменяемый пакет фактов, события |
| `factory/seo_content/draft.py` | черновик, ключ идемпотентности, границы роли модели |
| `factory/seo_content/editorial.py` | редакционные заметки и запрет поддельного UGC |
| `factory/seo_content/writer.py` | контракт Writer и три исполнения |
| `factory/seo_content/claims.py` | извлечение утверждений и сверка с фактами |
| `factory/seo_content/identity.py` | личность сущности и пять чисел серии |
| `factory/seo_content/dedup.py` | дубли, каннибализация, doorway-риск |
| `factory/seo_content/language.py` | русский язык и стиль |
| `factory/seo_content/structured_data.py` | JSON-LD и техническое соответствие |
| `factory/seo_content/judge.py` | Blind Judge |
| `factory/seo_content/gate.py` | ворота качества — единственное место решения |
| `factory/seo_content/store.py` | эфемерное хранилище черновиков |
| `factory/seo_content/pipeline.py` | сцепка событие → черновик |
| `factory/seo_content/budget.py` | бюджет и отказ платному вызову до эффекта |
| `factory/seo_content/injection.py` | содержимое полей как данные |

## Команды

```bash
# Пересобрать корпус случаев
python3 tests/seo_content/fixtures/build_fixtures.py

# Прогнать корпус через контур
python3 scripts/seo_content/run_corpus.py \
    --corpus tests/seo_content/fixtures/golden.json \
    --out artifacts/evidence/fleet-seo-004/golden-run.json

# Скрытый набор
python3 scripts/seo_content/run_corpus.py \
    --corpus tests/seo_content/fixtures/holdout.json \
    --out artifacts/evidence/fleet-seo-004/holdout-run.json

# Наблюдение за общим хранилищем (только чтение)
python3 scripts/seo_content/observe_shared_store.py \
    --out artifacts/evidence/fleet-seo-004/shared-store-after.json \
    --compare artifacts/evidence/fleet-seo-004/shared-store-before.json

# Выборка принятых и отклонённых
python3 scripts/seo_content/export_examples.py \
    --run artifacts/evidence/fleet-seo-004/golden-run.json \
    --out docs/seo-content/examples

# Проверки
python3 -m pytest tests/seo_content/ -q
```

## Смежные документы

* [Рубрика слепого судьи](blind-judge-rubric.md)
* [Бесплатные сервисы: что проверено и что нет](free-services.md)
* [Handoff: подключение живого Qwen](QWEN-SHADOW-ONBOARDING-HANDOFF.md)
* [Принятые черновики](examples/accepted.md) и
  [отклонённые с причинами](examples/rejected.md)
