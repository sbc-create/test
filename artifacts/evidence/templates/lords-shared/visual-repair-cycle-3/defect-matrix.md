# Матрица причин потери баллов — visual-repair-cycle-3

Источники: `artifacts/evidence/templates/lords-shared/visual-repair-cycle-2/README.md`
(унаследовано, перепроверено на текущем дереве), `artifacts/evidence/templates/
animedia-portal/finalization-01/CORE-HANDOFF-nav-order.md` (`git show
b023bd50cced8d281cb3814a75bf72b429afee0b`), собственные замеры этого цикла
(`scoring-cells-390-768-1440.json`, `scoring-summary.json`).

Категории: **A** — общий дефект Lords/Core (эта ветка вправе чинить). **B** —
дефект профиля Animedia. **C** — дефект профиля Zona. **D** — честно
отсутствующий/заблокированный reference evidence. **E** — ошибка измерителя
или контракта (не Lords/Core, read-only для этой ветки).

| surface | viewport | component | expected (эталон) | measured (кандидат, до) | measured (кандидат, после) | категория | владелец |
|---|---|---|---|---|---|---|---|
| catalog/collection_hub/title/not_found | 768/1440 | geometry (header_height) | ~99/61px | 152.25/110.25px → **исправлено циклом-2**, теперь 61/61px | 61/61px (не тронуто этим циклом) | A (уже закрыто cycle-2) | Lords/Core — закрыто |
| все 5 | все 3 | structure_order (block_order, required_block_\*_present) | отсутствует у эталона (0 токенов этого имени в PR#80 pack) | 0.0 (компонент без эталонного токена) | 0.0 (не изменилось — не входит в словарь) | **E** | contracts/visual-scoring (PR #81) и/или docs/reference-packs/amd-online (инструмент замера эталона) |
| catalog/not_found | все 3 | cards_media | NOT_APPLICABLE (контракт 1.0.2+ явно исключает) | 0.0 (excluded, не в счёте) | без изменений | не дефект — контрактное решение | — |
| collection_hub | все 3 | cards_media | 2 эталонных токена ожидаются | 0.0, tokens_missing=2 (кандидат не публикует эти 2 токена на /collections/) | без изменений (не в scope этого цикла) | **D/E** — инструмент замера кандидата не снимает cards_media на collection_hub | tests/tools/measure_candidate_tokens.js (не тронут этой веткой) |
| home/title | все 3 | cards_media | измеримо | 7.3–85.8 (частично, не 0) | без изменений | вне scope: подробный разбор не входит в CORE-HANDOFF | Lords/Core, отдельная задача |
| все 5 (кроме home) | все 3 | header_sticky (в составе geometry) | `false` (эталон) | `true` на всех 15 ячейках (`.site-header{position:sticky}`, theme.py:473) | без изменений — не тронуто | **B** (профильное решение Animedia) | `blueprints/lords/profiles/animedia-portal.yaml` (владелец профиля) либо запрос владельцу `factory/lords/**` на профильный флаг `layout.header_sticky` |
| home/catalog/title | все 3 | typography (type_h3_font_size, type_h3_font_weight) | 14px / 500 | `.92rem`(≈14.7px)/600 (`factory/lords/theme.py:674`) | без изменений — не тронуто | **B** (общий design-токен шаблона, тюнинг под один эталон запрещён) | владелец дизайн-системы Lords/Core или профильный override, не эта ветка |
| — | — | **навигация шапки** (`.site-nav`, вне словаря токенов visual-scoring) | `navigation.primary`: Аниме, Сериалы, Фильмы, Мультфильмы (`sites/animedia-preview/package.yaml`) | Фильмы, Сериалы, Мультфильмы, …, Аниме (фиксированный порядок blueprint.yaml, игнорирует пакет) | **Аниме, Сериалы, Фильмы, Мультфильмы** (следует navigation.primary) | **A — исправлено этим циклом** | Lords/Core — закрыто |
| `/catalog/` | — | **фасет «Тип»** (вне словаря токенов visual-scoring) | тот же порядок, что в шапке того же пакета | Фильм, Сериал, Мультфильм, Аниме (глобальный CONTENT_TYPES, тот же дефект, что и в шапке) | **Аниме, Сериал, Фильм, Мультфильм** | **A — исправлено этим циклом** | Lords/Core — закрыто |

## Итог по категориям этого цикла

- **A (общий дефект, исправлено сейчас)**: 1 дефект — навигация шапки и
  фасет «Тип» игнорировали обязательное поле пакета `navigation.primary`;
  один и тот же корень для обоих проявлений (см. README.md, «Что исправлено»).
- **A (общий дефект, закрыто cycle-2, не трогалось сейчас)**: перенос
  `.header-search` на вторую строку шапки — подтверждено неизменным.
- **B (профиль Animedia, не эта ветка)**: `header_sticky`,
  `type_h3_font_size`/`type_h3_font_weight` — подтверждены неизменными,
  перенесены как остаточные блокеры.
- **D/E (не Lords/Core, read-only контракт/инструмент)**: `structure_order`
  константно 0.0 из-за отсутствия соответствующих имён токенов в эталонном
  паке; `cards_media` на `collection_hub` — измерительный инструмент не
  публикует токены для этой поверхности.
