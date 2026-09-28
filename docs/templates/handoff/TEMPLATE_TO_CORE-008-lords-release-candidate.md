# TEMPLATE_TO_CORE-008 — кандидат шаблона Lords готов к решению о canary

> **Неизменяемый документ.** Правка запрещена; изменение состояния оформляется
> новым handoff с новым идентификатором.

| Поле | Значение |
|---|---|
| handoffId | `TEMPLATE_TO_CORE-008` |
| taskId | `TEMPLATES-RC-FREEZE-AND-POST-RELEASE-01` |
| fromLane | TEMPLATES |
| toLane | CORE (Архитектор) |
| type | release_candidate |
| status | open |
| severity | normal — решения требует, блокировки не создаёт |
| repo | `sbc-create/test.git` (site-factory) |
| branch | `claude/templates-lords-yummy-refpacks-01` |
| baseSha | `76552b9a7372c5ad15cfc7d8b1052a10024722a3` |
| headSha | `2f87236a6e27b68fd1deed523390e5e3cc559d99` |
| templateDigest | `52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc` |
| engineContract | `>=1.2.0 <1.3.0` (наблюдаемая 1.2.0) |
| updatedAt | 2026-09-05 UTC |

---

## 1. Что предлагается

Шаблон четырёх витрин Lords в состоянии, где каждые ворота полосы закрыты
фактическим прогоном. Предлагается **решение о canary на одной витрине** —
не сама выкладка.

Отпечаток считается по девятнадцати файлам, определяющим шаблон, и
воспроизводится одной командой:

```bash
python3 -c "from factory.templates import digest; print(digest.compute()['template_digest'])"
# 52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc
```

Совпадение отпечатка — единственный способ убедиться, что выкладывается
именно то, что проверялось. Расхождение означает, что проверять надо заново.

## 2. Ворота и их фактический объём

| Ворота | Итог | Объём |
|---|---|---|
| `axe_wcag22aa` | PASS | 72 прогона, 0 нарушений, WCAG 2.0/2.1/2.2 A+AA |
| `a11y_manual` | PASS | клавиатура, порядок фокуса, размеры целей, 16 px в полях |
| `visual_baseline` | PASS | 24 строки замеров, допуск 1 px |
| `performance` | PASS | 16 замеров, худший CLS 0, худший LCP 196 мс |
| `budgets_and_inp` | PASS | 8 страниц, 8 проверок кадра плеера |
| `responsive` | PASS | 256 замеров 320–1920, 4 reflow, 4 text-spacing |
| `crossbrowser` | PASS | 16 проверок на Firefox и WebKit |
| `template_audit` | PASS | минимум 10.0 из 10 на каждой из четырёх витрин при пороге 8.0 |

Полный прогон фабрики с чистого состояния — `bash tests/run-all.sh`:
**20 PASS, 0 FAIL, 4 SKIPPED, exit 0**. Браузерные наборы Lords сверх него:

```
npx playwright test --config=playwright.lords.config.js        → 221 passed
npx playwright test --config=playwright.lords-cross.config.js  →  16 passed
npx playwright test --config=playwright.templates.config.js    →  40 passed
```

Условие среды, без которого прогон не повторится, — §6.

## 3. Что в кандидат не входит

- тема оформления (THEME-01) — отдельная post-release ветка;
- каркас подборок (COLLECTIONS-01/02) — там же;
- всё, что относится к Yummy;
- пакеты референсов Zona и Animedia — черновики.

Исключения не оговорка, а свойство: чем меньше в кандидате того, что не
проверялось вместе с ним, тем меньше поверхность отката.

## 4. Чего кандидат **не** утверждает

- Он не утверждает, что production готов. `production_authorized: false` во
  всех четырёх пакетах `sites/lords-0*`, три домена стоят с
  `launched: false`, у четвёртого пакета домена нет вовсе.
- Он не утверждает измеренной производительности продукта. LCP снят на
  локальном стенде без сети: это нижняя граница, а не полевая величина.
- Он не заменяет решения о лицензии DLE и о правах на контент.

## 5. Что делает Архитектор

1. Выбирает витрину с наименьшим риском.
2. Подтверждает `production_authorized` в её пакете.
3. Запускает выкладку штатной командой фабрики.

Выкладка, переключение ссылок, DNS, работающие контейнеры и откат production
принадлежат Архитектору. Полоса шаблонов подготовила кандидата и **не
выкатывала ничего**: `PRODUCTION_CHANGED = no`.

## 6. Условие среды, без которого прогон не повторяется

`tests/run-all.sh` вызывает системный `python3`; зависимости фабрики стоят в
`.venv`. Без венва в `PATH` десять шагов падают за секунду не по существу, а
потому что нет `pytest` и нет пакета `factory`. Воспроизводимая команда:

```bash
FACTORY_CHROMIUM=/opt/pw-browsers/chromium-1234/chrome-linux64/chrome \
PATH="$PWD/.venv/bin:$PATH" bash tests/run-all.sh
```

Про `FACTORY_CHROMIUM` — отдельный handoff TEMPLATE_TO_CORE-009: список путей
к Chromium в проверке отрисовки отстал от среды. Для кросс-браузерного набора
нужен `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`.

## 7. Откат

| Способ | Что делать |
|---|---|
| предпочтительный | вернуть предыдущий подтверждённый template artifact по отпечатку |
| запасной | `git revert` конкретных template-коммитов ветки |
| запрещено | `reset --hard` |

**Обязательный шаг после отката.** Вернуть заморозку базы знаний:

```bash
python3 -m factory knowledge freeze --version 2026-08-30-lords-full-catalog
```

Запись D128 входит в замороженную базу. Без перезаморозки падают тесты
заморозки, production-ворот и авторизации — то есть откат шаблона без этого
шага ломает не шаблон, а ворота, которые его охраняют.

## 8. Машиночитаемое описание

`artifacts/evidence/templates/lords-release-candidate.json` — собирается
`scripts/lords_release_candidate.py` из фактов: отпечаток считает
`factory/templates/digest.py`, ревизии берутся из git, состояние ворот — из
файлов свидетельств. Поле, которое нечем заполнить, остаётся пустым со
статусом, а не заполняется правдоподобным значением.
