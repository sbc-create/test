# Baseline и цикл 0 — воспроизведение handoff 061

Снято 2026-09-09, начало 16:57 UTC, хост claude-control-01.

## Baseline

| поле | значение |
|---|---|
| BASE_SHA | `974a8bb65c766c3244b9f41cd4437bebdd3e5362` |
| база — ветка | `claude/core-content-kind-contract-33` |
| база — дата | 2026-09-09 14:27:38 +0000 |
| новая ветка | `claude/core-unified-identity-provenance-35` |
| рабочее дерево | `/home/claude/wt-core-ident-35` (создано от полного SHA, без reset) |
| репозиторий CORE | `sbc-create/test.git` |
| SEO consumer SHA | `ca2b6ca96a50e644b287c92380a9f0fa70723a38` |
| репозиторий SEO | `sbc-create/seo-engine-platform.git` (ОТДЕЛЬНЫЙ) |
| SEO worktree | `/home/claude/wt-seo-kind-34` — на точном SHA, только чтение |
| TEMPLATES SHA | `d633b1947f87fe87720d7ad19e740e63def26a09` |
| диск | 112 ГБ свободно |
| активные pytest | 2 процесса чужого потока — полный набор CORE с ними не конкурирует |
| lock | `RELEASE-BLOCK-b0d0362` — область «production deploy of control-api», работу в ветке не блокирует |

### Замечание о расположении координации

`coordination/v1` в репозитории CORE **нет**. Каталог общий и лежит вне
репозиториев: `/srv/site-factory/coordination/v1`. Записано, чтобы следующий
не искал его в дереве.

## Расхождения с текстом задания

Проверено фактами, а не принято на веру.

1. **Тесты SEO: 3335, но не там, где сказано.** Верхний ключ `suite` в
   `status/seo.json` содержит `3214` — это итерация 33. Число `3335` лежит в
   `suite34`. Оба присутствуют; читать надо `suite34`.

2. **Канонического product score не существует.** Задание требует взять его из
   `status/seo.json`. Там `fourScores` = `{SEO_READINESS_SCORE: null,
   SEO_OUTCOME_SCORE: null, OPERATOR_EFFECTIVENESS_SCORE: null,
   DATA_CONFIDENCE_SCORE: 70.0}` и прямая оговорка: «четыре оценки не
   складываются в одну; свойства overall_score нет». `scorecard.overallStatus`
   = `UNKNOWN`, `canClaimEight` = `false`. Предлагать «дельту score» не от
   чего: базы нет. Это не отказ считать, это отсутствие измеряемой величины.

3. **Таксономия названа по-разному.** В задании `core-catalog/type:r2`, в коде
   `route_snapshot.KIND_TAXONOMY = "core-catalog/type:2"`. Различие в одном
   знаке; какое значение принимает потребитель — проверяется на его SHA.

## Цикл 0 — что на самом деле означают «71 запись»

Handoff 061 просит либо снимок маршрутов для yummyani, либо «вид произведения
в `seo-route-binding`, младшим повышением», и обосновывает это тем, что
контракт связи вида **не передаёт**:

> «Они связываются `seo-route-binding/1.0.0`, а он вида произведения не
> передаёт — те же поля, что и раньше: `slug`, `providerTitleId`, `canonical`,
> `updatedAt`.»

**Это неверно относительно контракта, как он реализован на BASE_SHA.**

`factory/site_engine/seo_binding.py`, `RouteBinding.as_dict()`, строки 356–358:

```
"contentKind":            self.content_kind.value,
"contentKindState":       self.content_kind_state.value,
"contentKindProvenance":  self.content_kind_provenance,
```

Вид вычисляется тем же авторитетным механизмом, что и у Lords:
`factory/site_engine/adapters/yummy_seo_binding.py:bind_route` вызывает
`decide(provider_type=entry["type"], tags=entry["tags"], entity_id=...)` и
`kind_state_of(...)`. Ни угадывания по названию, ни по URL там нет.

Фактическое распределение в выгрузках связи (наблюдение 2026-09-06):

| витрина | записей | BOUND | KIND_UNRESOLVED | ROUTE_COLLISION |
|---|---:|---:|---:|---:|
| yummyani-site | 7 303 | 7 225 | 77 | 1 |
| yummyani-org | 7 291 | 7 213 | 77 | 1 |
| yummyani-biz | 7 291 | 7 213 | 77 | 1 |

То есть вид у yummyani разрешён у подавляющего большинства записей и
**передаётся контрактом**.

### Настоящая причина

Причина не в контракте CORE, а в форме приёма у потребителя.

`seo_engine/binding/route_resolution.py` (SEO, SHA `ca2b6ca9`), ветка
«витрина со связью маршрутов прежнего контракта», строки 243–246:

```
stable_work_id=идентификатор, contract="seo-route-binding/1.0.0",
content_kind="", content_kind_state="MISSING",
reason="связь установлена контрактом маршрутов витрины; вид произведения
        этим контрактом не передаётся"
```

Вид там **зашит пустым**, и причина объявлена строкой. Смотреть в запись не
на что: параметр объявлен как `bindings: dict[str, dict[str, str]] | None` —
это отображение «слаг → идентификатор». Вид отсутствует не в контракте, а в
той проекции контракта, которую потребитель загружает.

Ветка снимка, строки 223–224, читает вид штатно:

```
content_kind=str(запись.get("contentKind") or ""),
content_kind_state=str(запись.get("contentKindState") or ""),
```

### Следствие для выбора решения

Из двух вариантов handoff 061 правильным оказывается **первый** — снимок
маршрутов для yummyani, — и по причине более сильной, чем «два механизма
однажды разойдутся»:

* вариант 2 (повысить `seo-route-binding`) не решает задачу: контракт уже
  несёт вид, а потребитель его в этой ветке не читает. Повышение версии
  ничего не изменит без правки потребителя;
* вариант 1 переводит yummyani в ветку, которая вид **уже читает**. Правка
  SEO не требуется вовсе.

Это соответствует правилу «не исправляй SEO ради прохождения тестов CORE».

## Данные, которые уже есть и второго источника не требуют

* маршруты yummyani — таблица самой витрины `PublicTitleRoute`, выгрузка
  `automation/host/yummy-route-export.py`; это объявление витрины, а не
  догадка о правиле адресации;
* каталог — `/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-0N.json`;
  происхождение выгрузки прямо ссылается на него: `PublicTitleRoute+lords-01.json`;
  все 7 303 идентификатора витрины в нём нашлись;
* функция адреса — `yummy_seo_binding.route_of`, объявленная функция витрины;
* построитель снимка — `route_snapshot.build(entries, *, site_id, route_of, …)`
  уже **обобщён**: он принимает `site_id` и функцию адреса и ничего
  Lords-специфичного не содержит.

Недостающего звена в данных нет. Отсутствует только вызов построителя для
профилей yummyani.
