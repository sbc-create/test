# Восстановленная хронология предыдущей работы по Animedia

Стадия: `ANIMEDIA-CURSOR-WORK-RECONCILIATION-01`
Режим: `RECOVER_VERIFY_FINISH_DO_NOT_RESTART`
Восстановлено: 2026-09-21, read-only по git, файловой системе и live HTTP.

## Кто на самом деле вёл работу

Ветки `cursor/*animedia*` в репозитории **нет**. Все семь существующих веток
`cursor/*` относятся к другим продуктам (lords, community-comments,
ratings-ingestion, release-orchestrator) и не трогают `animedia.icu` и
`animedia.space`. Каталог `.cursor/` в рабочем дереве Animedia существует, но
пуст — транскриптов терминалов (`.cursor/projects/**/terminals/*.txt`) нет и
восстановить их нечем.

Фактический носитель работы по Animedia — ветка
`claude/animedia-template-finalization-01`, committer `CORE integrator`,
рабочее дерево `/home/claude/wt-animedia-finalization-01`.
В отчётах ниже она и считается «предыдущей работой».

## Цепочка стадий

| # | Стадия | START_HEAD | FINAL_HEAD | Вердикт | Состояние |
| --- | --- | --- | --- | --- | --- |
| 1 | `ANIMEDIA-BLOCKWISE-2026-09-19` | `939df3d` | `8cce87e` | `PASS_READY_FOR_OWNER_VISUAL_REVIEW` | SUPERSEDED |
| 2 | `ANIMEDIA-REFERENCE-PARITY-02` | `25d3ad3` | `aeb4cbf` (+ `36a42fb`, `242a834` док/пины) | `NEEDS_REPAIR` | SUPERSEDED |
| 3 | `ANIMEDIA-BLOCKWISE-PARITY-03` | `242a834` | — (не закрыта) | — | **ACTIVE** |

Редакции не смешиваются: активен только контракт стадии 3.

### Стадия 1 — `ANIMEDIA-BLOCKWISE-2026-09-19`

12 блоков (shell/theme, top shelf, episode feed, home sections, title info,
ratings, player, catalog, search, collections, footer/schedule, responsive).
54/54 теста. Выкат: build `20260919T224052Z-ca169679-nova`, артефакт
`f89b9d82…`, rollback `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T224052Z`.
`BLOCK_11_FOOTER_SCHEDULE=PASS_VISUAL_BLOCKED_OWNER_DATA` — владельческие
контакты и правовые URL не переданы, поэтому не выдуманы.

### Стадия 2 — `ANIMEDIA-REFERENCE-PARITY-02`

Контракт `8138df34…`, референс `amd.online`. 93/93 теста, 2 стабильных local
прогона, 3 live. Выполнен один контролируемый выкат на оба домена:
build `20260920T102102Z-89666321-nova`, артефакт
`d2e9628f2a4b14c56ef28a6814b53f49cdb4017db1ab8ddebebb79aaad39e908`,
source commit `89666321093651d4bd5b06a00645fdf903124810`.

Вердикт `NEEDS_REPAIR`: `HARD_GATE_FAILURES=1`,
`HARD_GATE_REASON=AFTER_LIVE_SCREENSHOT_MATRIX_AND_ORACLE_SCORES_INCOMPLETE`.
Индексация сохранена закрытой (`NOINDEX_PRESERVED=1`), DNS не менялся,
push и merge не выполнялись. Owner visual review — `PENDING`.

Именно этот артефакт **и сейчас стоит на обоих доменах** (подтверждено live
2026-09-21, см. `LIVE_BASELINE.json`).

### Стадия 3 — `ANIMEDIA-BLOCKWISE-PARITY-03` (активная, незакрытая)

Заморожен неизменяемый контракт:

- spec `ANIMEDIA_BLOCK_SPEC_V1`
- `CONTRACT_SHA256 = 5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- `frozen_at_utc = 2026-09-20T11:17:59Z`, `start_head = 242a834`
- `contract_mutation_forbidden_after_digest = true`
- `self_reported_visual_score_allowed = false`, `template_only = true`
- reference baseline `84132b93…`, 9/9 захватов `amd.online`, 0 отказов доступа
- локальных кейсов 114, live-кейсов 84, 9/9 семейств маршрутов замаплены

Запрещённые мутации по контракту: core, search_ranker, route_semantics,
player_selection_policy, global_seo_indexability, ratings_formula,
http_status_policy, databases, event_ledgers, dns, other_domains, push, merge.

Разрешённые вердикты стадии: `PASS_READY_FOR_OWNER_VISUAL_REVIEW`,
`PRESENTATION_SHELL_PASS_WITH_GAPS`, `BLOCKED_CORE_DATA`, `NEEDS_REPAIR`,
`NEEDS_OWNER_VALUES`.

Флаги закрытия по умолчанию — все `NO`, и ни один не был переведён в `YES`.

## Owner approvals

| Decision ID | Область | Где записано |
| --- | --- | --- |
| `ANIMEDIA-B10-B16-20260920-01` | B08 default-episode = `FIRST_PLAYABLE_DETERMINISTIC`; B10 fallback `DETERMINISTIC_METADATA_RELATED_V1` | `04-backlog/DATA_GAPS.json` |

Отдельного owner approval на выкат артефакта, собранного из `03b3908`, **нет**.
Старое разрешение стадии 2 привязано к артефакту `d2e9628f…` и на новый
артефакт не переносится.

## Реальные пробелы данных (не выдумывать)

| Код | Поверхность | Честный fallback | Чего ждём |
| --- | --- | --- | --- |
| `CATALOG_FRESHNESS_DATA_GAP` | home/new «Новое в каталоге» | 0px либо честная пустота | ledger `catalog_added_at` |
| `TOP100_DATA_GAP` | home Top-100 | полка скрыта | `config/animedia-top100.json` |
| `WEEKLY_SNAPSHOT_DATA_GAP` | home «Популярное за неделю» | 0px | `config/animedia-weekly-popular.json` |
| `EPISODE_EVENT_DATA_GAP` | «Новые серии», `/schedule/` | честная пустота, дата каталога не выдаётся за дату выхода | провайдерский feed playable-событий |
| `RECOMMENDATIONS_DATA_GAP` | title/episode «Похожее аниме» | `DETERMINISTIC_METADATA_RELATED_V1` при ≥4, иначе 0px | `config/animedia-recommendations.json` |
| `OWNER_DATA_REQUIRED` | footer контакты/право | поля опускаются | владельческие email, Telegram, privacy, terms |

`TRUE_PROVIDER_PLAYABLE_EVENT_COUNT = 0`,
`TRUE_EPISODE_RELEASE_EVENT_COUNT = 0`,
`CATALOG_ADDED_EVENT_COUNT = 0`,
`catalog.items[].published_at` — семантика `AMBIGUOUS`, меткой «Добавлено» или
«Вышла серия» быть не может.

## Формат финального отчёта стадии 3

`03-blocks/BLOCK_B16.md` + `FINAL.md` по паспорту B16; требуются
`LIVE_STABLE_RUNS_ICU>=2`, `LIVE_STABLE_RUNS_SPACE>=2`,
`ROLLBACK_RESTORE_DRILL_PASS`, `indexability_before_after_must_match`.
Самооценка визуального качества запрещена контрактом.

## Остаточный backlog, унаследованный этой стадией

1. Незакрытые блоки B12–B16 стадии 3 (см. `BLOCK_MATRIX.json`).
2. `HARD_GATE_REASON` стадии 2 — after-live матрица скриншотов и оракулов.
3. Owner values для footer.
4. 102 локальных коммита не отправлены в `origin` (push запрещён без разрешения).
