# TEMPLATE_TO_CORE-009 — список путей к Chromium отстал от среды, три шага падают ложно

> **Неизменяемый документ.** Правка запрещена; изменение состояния оформляется
> новым handoff с новым идентификатором.

| Поле | Значение |
|---|---|
| handoffId | `TEMPLATE_TO_CORE-009` |
| taskId | `TEMPLATES-RC-FREEZE-AND-POST-RELEASE-01` |
| fromLane | TEMPLATES |
| toLane | CORE / INFRA |
| type | environment_drift / false_negative_gate |
| status | open |
| severity | major — три шага полного прогона падают, причина не та, что в сообщении |
| repo | `sbc-create/test.git` (site-factory) |
| file | `factory/seo/render_check.py` |
| updatedAt | 2026-09-05 UTC |

---

## 1. Что происходит

`bash tests/run-all.sh` даёт три отказа:

```
deploy-pilot      FAIL exit=2   → BLOCKED_SEO
browser-audit     FAIL exit=1   → {'critical': 1}
e2e-playwright    FAIL exit=1   → 44 теста падают за 3–6 мс каждый
```

Свидетельство `seo-render.json` называет причину прямо:

```json
{"passed": false, "executed": false, "counts": {"status": "unavailable"},
 "findings": [{"check": "browser", "severity": "critical",
   "message": "Браузерная проверка не выполнялась: исполняемый Chromium не найден."}]}
```

`performance-budget` падает следом по той же причине: метрики не с чего снять.

## 2. Причина

`factory/seo/render_check.py` ищет Chromium по списку:

```python
CHROMIUM_CANDIDATES = (
    os.environ.get("FACTORY_CHROMIUM", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
)
```

Среда с тех пор сместилась дважды:

| | В списке | В среде |
|---|---|---|
| ревизия | `chromium-1194` | `chromium-1234` |
| каталог сборки | `chrome-linux` | `chrome-linux64` |

Обе части пути изменил апстрим Playwright, а не кто-то в проекте. Отсюда и
свойство отказа: он приходит не тогда, когда что-то сломали, а тогда, когда
среду обновили.

## 3. Проверка причины

С явно заданным путём тот же прогон проходит целиком:

```bash
FACTORY_CHROMIUM=/opt/pw-browsers/chromium-1234/chrome-linux64/chrome \
PATH="$PWD/.venv/bin:$PATH" python3 -m factory deploy --site pilot-local
```

```
status: DONE
  PASS seo-render          exit=0
  PASS performance-budget  exit=0
  … все восемь ворот PASS
```

Полный прогон с той же переменной: **20 PASS, 0 FAIL, 4 SKIPPED, exit 0**.

## 4. Почему это не исправлено полосой шаблонов

`factory/seo/` — слой SEO. Он в списке того, что полосе шаблонов менять
запрещено, и запрет здесь по существу: выбор способа находить браузер
определяет, какие ворота считаются выполненными, а какие пропущенными.

Отдельно стоит сказать, что **отказ правильный**. Проверка не притворилась
пройденной и не подставила ноль: `executed: false`, `status: unavailable`,
severity `critical`. Испортилось не поведение, а адрес.

## 5. Запрашиваемое действие

1. Перестать называть ревизию браузера в коде. Ревизию знает сам Playwright:
   `require('playwright-core').chromium.executablePath()` возвращает путь,
   который не устареет при следующем обновлении. Список фиксированных путей
   будет ломаться ровно так же при каждом апгрейде.
2. Решить, должен ли `run-all.sh` вызывать интерпретатор из `.venv`. Сегодня
   он вызывает системный `python3`, и без венва в `PATH` десять шагов из
   двадцати четырёх падают за секунду по отсутствию `pytest` и пакета
   `factory`. Отказ выглядит как провал проверок, а является провалом
   запуска — это два разных события, и различать их должен сам скрипт.

## 6. Приёмочная проверка

```bash
bash tests/run-all.sh          # без FACTORY_CHROMIUM и без правки PATH
                               # ожидается 20 PASS, 0 FAIL
```

## 7. Влияние на ворота полосы шаблонов

Никакого: все ворота Lords закрыты фактическими прогонами (см.
TEMPLATE_TO_CORE-008). Условие среды названо там же, чтобы прогон
воспроизводился, а не чтобы оправдать пропуск.
