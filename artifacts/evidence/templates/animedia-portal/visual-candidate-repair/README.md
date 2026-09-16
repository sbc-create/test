# animedia-portal — ремонт визуального кандидата PR #76

Свидетельства этого каталога измерены в текущей сессии на локальном
loopback-стенде (`python3 -m factory lords-preview --site animedia-preview --serve`,
синтетический каталог `fixture/test`, штатный harness фабрики). Инструменты
измерения — `tests/tools/measure_reference.js` (уже в этой ветке) и, для
цвета и среды, `tests/tools/measure_reference_colors.js` /
`tests/tools/measure_reference_environment.js` — оба вошли только PR #80 и
использованы здесь **без изменений** (не перенесены в эту ветку и не
закоммичены сюда), строго для локального прогона против кандидата. Ни PR #80,
ни PR #81 (`contracts/visual-scoring/1.0.0`) этой сессией не менялись.

## Что здесь есть

| Файл | Что измерено |
| --- | --- |
| `geometry-{home,catalog,title,collection_hub,not_found}.json` | `outer_gutter`, `content_width`, `horizontal_overflow`, типографика — все 5 поверхностей × 390/768/1440 |
| `colors-home.json`, `colors-not_found.json` | `color_page_background`, `surface_header_background`, `color_text_primary` и другие цветовые токены — два независимых прохода каждый |
| `environment-manifest.json` | Среда замера в форме `schemas/visual-scoring-result.schema.json:environment_manifest` (PR #81) |
| `environment-raw-measurement.json` | Сырой вывод `measure_reference_environment.js` до нормализации |

Скриншоты и сырые снимки страниц сюда не попали — только числовые токены,
ровно как требует политика `inventory/reference-sources.yaml` для reference
pack и как эта сессия применяет её же к кандидату.

## Что подтверждено измерением

- **Геометрия (дефект 2).** `outer_gutter` на всех пяти поверхностях и трёх
  вьюпортах — 1px (было 60px@1440 / 16px@768 на измеренных поверхностях
  исходной оценки). Горизонтальной прокрутки нет ни на одной из 15 комбинаций.
  Единственное отступление: `geometry-not_found.json` показывает `gutter: 0`
  на всех трёх вьюпортах — это артефакт эвристики инструмента (он ищет
  вложенный блок уже вьюпорта для оценки внутреннего отступа; на странице
  `not_found` из-за минимальной разметки такого блока нет, и функция
  возвращает 0, а не измеренное значение). Прямая проверка
  `getComputedStyle('.container').paddingLeft` на этой же странице даёт
  `1px`, и разметка `<main id="content"><div class="container">` совпадает
  со всеми остальными поверхностями буквально.
- **Цвет (дефект 3).** `color_page_background`/`surface_header_background`
  = `#ffffff`, `color_text_primary` = `#161616` на обеих измеренных
  поверхностях — точное совпадение с измеренными значениями референса.
  Тёмная палитра (прежние `#0f1419`/`#161d24`/`#e8edf2`) сохранена как
  `tokens_alt` и доступна явным переключателем.
- **collection_hub (дефект 1).** `/collections/` отдаёт 200 и реальные
  данные фикстурного каталога (4 коллекции: `first-season`, `long-evenings`,
  `northern-set`, `short-form`), а не пустую заглушку — обе геометрия и
  render coverage подтверждены на всех трёх вьюпортах.

## Что НЕ покрыто этим ремонтом

Полный повтор scoring по контракту PR #81 (все компоненты — structure_order,
cards_media, typography, responsive — по всем 5×3 ячейкам, с полным
candidate_pack по схеме `visual-scoring-result.schema.json`) этой сессией не
выполнен: контракт прямо требует независимости проверяющего от автора
ремонта (`checker_identity != candidate_author_identity`), поэтому
сертификация `VISUAL_CERTIFIED` — задача отдельного checker-прогона, а не
этой правки. Здесь — измеренная, воспроизводимая база для этого прогона,
а не сам вердикт.

`environment-manifest.json.template_manifest_compatibility` наследует
`pending` из `docs/reference-packs/amd-online/TemplateManifest.yaml` (обе
стороны обязаны совпасть) — значение не проходит `$defs/declared_range`
схемы PR #81, которая `pending` запрещает. Это решение владельца эталонного
пакета (см. `ACCEPTANCE.md` эталона, пункт 4 — «не выполнен»), а не то, что
чинит ремонт кандидата: подставить правдоподобный диапазон вместо чужого
блокера значило бы закрыть его записью, а не решением.
