# Команды проверки и фактические результаты — visual-repair-cycle-3

Все команды выполнены в `/home/claude/wt-canon-76` на ветке
`claude/fleet-tpl-baseline-001`. Пути к контракту/pack — вне tracked tree
(`/tmp/.../scratchpad`, не коммитится).

## Preflight

```
$ pwd                                                → /home/claude/wt-canon-76
$ git branch --show-current                          → claude/fleet-tpl-baseline-001
$ git rev-parse HEAD                                  → 35c038398ea4bab4990ee8ba00e12ab09bd49e8d
$ git status --porcelain                              → (пусто)
$ git fetch origin --prune                            → exit 0
$ git rev-parse origin/claude/fleet-tpl-baseline-001   → 35c038398ea4bab4990ee8ba00e12ab09bd49e8d
```
Совпадает с EXPECTED_START_HEAD — продолжение разрешено.

## Регресс-тест (падает до правки, проходит после)

```
$ python3 -m pytest tests/unit/test_lords_navigation_priority.py -v
# до правки factory/lords/render.py:
2 failed, 3 passed in 1.89s
  FAILED test_header_nav_follows_navigation_primary_order
  FAILED test_catalog_type_facet_follows_navigation_primary_order
# после правки:
5 passed in 1.93s
```

## Полный набор тестов Lords (после правки)

```
$ python3 -m pytest tests/unit/ -k "lords" -q
7 failed, 1499 passed, 5 skipped, 4117 deselected in 291.26s
```

Семь провалов проверены на pristine START_HEAD через `git stash`
(`git stash push -u -m "wip: nav-order fix cycle-3" -- factory/lords/render.py
tests/unit/test_lords_navigation_priority.py`, затем `git stash pop` — дерево
вернулось к прежнему diff, HEAD не менялся):

```
$ python3 -m pytest tests/unit/test_lords_canary.py::TestProvenanceVerify::test_нетронутая_оснастка_проходит \
    tests/unit/test_lords_canary.py::TestProvenanceVerify::test_изменённый_файл_оснастки_ломает_сверку \
    tests/unit/test_lords_canary.py::TestDubiousOwnershipReproduced::test_сверка_происхождения_переживает_чужого_владельца \
    tests/unit/test_lords_canary.py::TestDubiousOwnershipReproduced::test_сценарий_проходит_предполётные_проверки_при_чужом_владельце \
    tests/unit/test_lords_data_source_label.py::TestЗакреплённыйОтпечатокСовпадаетСДеревом::test_константа_сценария_равна_посчитанному_отпечатку \
    tests/unit/test_lords_search_index.py::test_живой_каталог_подсказка_при_наборе_укладывается_в_250_мс \
    tests/unit/test_secret_hub_panel_server.py::TestPortfolioIsolation::test_saving_yami_does_not_touch_lords -q
# на pristine 35c0383 (до этого цикла):
6 failed, 1 passed in 19.19s
```

6 из 7 уже падают на чистом START_HEAD (окружение: отсутствует `.venv/bin/python`
для canary/fingerprint-тестов, отсутствует модуль webauthn для
secret_hub_panel_server — обе причины не связаны с этим циклом и не с
`factory/lords/**`). Седьмой (`test_живой_каталог...250_мс`) — таймингочувствительный
перф-тест; в изоляции после правки:

```
$ python3 -m pytest tests/unit/test_lords_search_index.py::test_живой_каталог_подсказка_при_наборе_укладывается_в_250_мс -q
1 passed in 17.31s
```
Падение в общем прогоне — нагрузка параллельного запуска 4000+ тестов, не
регрессия этого цикла.

## Смежные наборы (nav/content/visual-coverage) — все зелёные после правки

```
$ python3 -m pytest tests/unit/test_product_content_types_match_purpose.py \
    tests/unit/test_candidate_visual_coverage.py \
    tests/unit/test_lords_navigation_priority.py -q
22 passed in 4.04s
```

## Schema validation

```
$ python3 scripts/validate_schemas.py
OK: 20 schema(s) compile: analytics-registry, content-backlog, data-source-registry,
debt-accepted, editorial-calendar, editorial-sources, experiment-registry,
fleet-registry, job-result, keyword-plan, live-acceptance, page-metadata,
portfolio-registry, reference-pack, secret-hub, seo-audit, site-matrix,
site-package, template-baseline-manifest, template-manifest
```
(schemas не менялись этим циклом — проверка подтверждает отсутствие порчи.)

## Template contract

```
$ python3 -m factory template-check
шаблоны приняты
```

## git diff --check

```
$ git diff --check
(пусто — чисто)
```

## Живая проверка нового поведения (lords-preview)

```
$ python3 -m factory lords-preview --site animedia-preview --serve --port 8853 &
$ curl -s http://127.0.0.1:8853/ | grep -oE '<nav class="site-nav".*?</nav>'
# → …Главная, Каталог, Аниме, Сериалы, Фильмы, Мультфильмы, Подборки, Новое,
#     Расписание, Жанры, Годы, Страны, Поиск

$ curl -s http://127.0.0.1:8853/catalog/ | grep -o 'Тип</legend><ul class="facet__list">.*'
# → …Аниме, Сериал, Фильм, Мультфильм
```

## Замер токенов после правки и сверка с cycle-2 (0 расхождений)

```
$ CANDIDATE_COMMIT=worktree-postfix-uncommitted node tests/tools/measure_candidate_tokens.js \
    http://127.0.0.1:8853 <scratchpad>/measure-after-fix
{"surfaces":5,"tokens":639,"ok":true}

$ python3 - <<'PY'
# сравнение (surface, viewport, name) -> value между cycle-2 candidate-tokens.json
# и свежим замером после правки
# old count 639 new count 639 / missing_in_new 0 / missing_in_old 0 / value diffs: 0
PY
```

## Пересчёт visual-scoring (contract 1.0.3, read-only, вне tracked tree)

```
$ python3 <scratchpad>/visual_scoring/run_compare.py \
    artifacts/evidence/templates/lords-shared/visual-repair-cycle-2/candidate-tokens.json \
    "BEFORE" \
    artifacts/evidence/templates/lords-shared/visual-repair-cycle-2/environment-manifest.json
overall_score=33.186630083599, evidence_completeness=91.27789046653145,
certification_status=BLOCKED_INDEPENDENCE_VIOLATION

$ python3 <scratchpad>/visual_scoring/run_compare.py \
    <scratchpad>/measure-after-fix/candidate-tokens.json \
    "AFTER" \
    artifacts/evidence/templates/lords-shared/visual-repair-cycle-2/environment-manifest.json
overall_score=33.186630083599, evidence_completeness=91.27789046653145,
certification_status=BLOCKED_INDEPENDENCE_VIOLATION
```
Оба прогона идентичны побитово — объяснение в `scoring-summary.json.score_delta_explained`.
