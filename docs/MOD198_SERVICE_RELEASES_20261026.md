# MOD-198: службы из рабочих копий — поэтапный перенос

Ответственный за координацию и результат: Архитектор (эта линия), поручение
владельца 26.10.2026. Общей остановки 18 служб нет и не планируется: перенос
идёт по одной, с проверкой результата и возвратом к прежнему выпуску.

## 1. Что измерено до всякого переноса

Инструмент `automation/local/service-dependency-map.py`, опись —
`artifacts/evidence/service-dependency-map-20261026.json`.

**18 служб из пяти рабочих копий**, точка входа разобрана у ВСЕХ. Четыре вида
точек входа, и каждый сначала разбирался неверно: многострочный `ExecStart`
(терялось `-m пакет.модуль`), интерпретатор вместо сценария, инлайн
`python -c 'from … import main'`, обёртка вне дерева с `export PYTHONPATH=`
на рабочую копию. Пятый случай — точка входа `.sh`: без разбора оболочки
служба выглядела как «файлов кода: 1».

**От незакоммиченного зависят РОВНО ДВЕ службы**, три файла:
`seo-content-operator` (`scripts/seo_content_operator_stage2_daily.py`,
`seo_engine/content_operator/ongoing_intake.py`) и
`seo-content-operator-report` (`seo_engine/content_operator/daily_ops_report.py`),
обе в `wt-seo-index-audit-20260930`. Это ответ на «необходимые незакоммиченные
изменения»: их три файла, а не 44 и не 583, и переносить их придётся как
названное отклонение от коммита, а не молча.

| служба | файлов кода | вне коммита | дерево |
| --- | --- | --- | --- |
| seo-content-operator | 33 | **2** | wt-seo-index-audit-20260930 |
| site-cell-executor | 28 | 0 | wt-portable-site-cell-01 |
| editor-run | 25 | 0 | wt-portable-site-cell-01 |
| seo-tech-publish | 25 | 0 | wt-portable-site-cell-01 |
| analytics-cabinet | 24 | 0 | wt-portable-site-cell-01 |
| seo-tech-run | 24 | 0 | wt-portable-site-cell-01 |
| seo-regular-hourly / daily / weekly / check | 23 каждая | 0 | wt-portable-site-cell-01 |
| seo-content-operator-report | 20 | **1** | wt-seo-index-audit-20260930 |
| community-ratings-gateway | 17 | 0 | wt-ratings-ingestion-01 |
| seo-engine-topvisor-inventory | 13 | 0 | wt-seo-operator-v2-01 |
| site-factory-mcp | 12 | 0 | wt-portable-site-cell-01 |
| seo-daily-cycle | 10 | 0 | wt-seo007 |
| community-ratings-monitor | 7 | 0 | wt-ratings-ingestion-01 |
| **seo-report-viewer** | **11** | 0 | wt-seo-index-audit-20260930 |
| yummy-sitemap-warm | 1 | 0 | wt-portable-site-cell-01 |

## 2. Механизм выпуска: существующий, обобщённый

`automation/local/install-service-release.py` — образец взят у
`k2-install-delivery.py` (копия, а не ссылка; опись `INSTALL.json` с коммитом
источника и суммой каждого файла; отдельная сверка) и дополнен тем, что
требует поручение:

* выпуски лежат рядом, `current` — ссылка, `.previous` — прежний выпуск:
  **откат это переключение ссылки**, а не повторная сборка;
* файлы вне коммита переносятся и ПЕРЕЧИСЛЯЮТСЯ в описи отдельным полем;
* состав замыкается транзитивно, включая пакетные `__init__.py` и их
  собственные импорты;
* **интерпретатор записан как зависимость** — он не файловая зависимость, и
  без него перенос половинчатый.

Путь выпусков: `/srv/site-factory/services/<служба>/releases/<метка>-<коммит>`,
корень принадлежит `claude` — установка root НЕ требует.

## 3. Первая служба: seo-report-viewer

Выбрана по измерению, а не по удобству: 11 файлов, ноль незакоммиченных, ноль
сторонних пакетов (все импорты — стандартная библиотека), запускается сама
(не таймером), читает отчёты только на чтение, слушает `127.0.0.1:8231` за
SSH-туннелем. Её отказ ничего не теряет и виден сразу.

**Три находки, каждая поймана пробой, а не чтением:**

1. состав был неполон — установленная копия упала с
   `ModuleNotFoundError: seo_engine.content_operator.methodology`, потому что
   пакетный `__init__.py` сам импортирует модуль. Замыкание исправлено;
2. после этого — `AttributeError: module 'enum' has no attribute 'StrEnum'`:
   службе нужен **Python ≥ 3.11**, а системный здесь 3.10.12. Её юнит зовёт
   python из `.venv` рабочей копии, а тот ведёт на интерпретатор uv в домашнем
   каталоге (3.11.16);
3. значит выпуску нужен СВОЙ venv: создан
   `/srv/site-factory/services/seo-report-viewer.service/venv` (3.11.16, без
   сторонних пакетов — они не нужны).

**Проверка выпуска до правки юнита:** запущен ровно так, как его запустит юнит
(`venv/bin/python -m seo_engine.content_operator.report_server --root
/var/lib/seo-content-operator/reports/runs --bind 127.0.0.1 --port 8299`,
рабочий каталог `current`) — ответил **HTTP 200, 18 837 байт**. Сверка выпуска:
`--verify` → файлов 11, расхождений 0, коммит источника `fd6d00a78905`.

## 4. Операторская врезка: переключить юнит на выпуск

Привилегированная часть ровно одна — правка юнита, `daemon-reload` и
перезапуск. Делается drop-in файлом, а не правкой самого юнита: откат это
удаление одного файла, и исходный юнит остаётся нетронутым.

```bash
# ВСЁ НИЖЕ — от root на УПРАВЛЯЮЩЕМ узле 45.131.182.225.
set -eu

# --- ДО: зафиксировать состояние, чтобы было с чем сравнить --------------
systemctl is-active seo-report-viewer.service
systemctl show -p WorkingDirectory -p ExecStart seo-report-viewer.service
curl -sS -o /dev/null -w 'до переключения: HTTP %{http_code}\n' \
  --max-time 10 http://127.0.0.1:8231/
# ожидается: active, WorkingDirectory=/home/claude/wt-seo-index-audit-20260930,
#            ExecStart с .venv этой же копии, HTTP 200

# --- ПЕРЕКЛЮЧЕНИЕ: drop-in, исходный юнит не правится --------------------
install -d -m 0755 /etc/systemd/system/seo-report-viewer.service.d
cat > /etc/systemd/system/seo-report-viewer.service.d/release.conf <<'CONF'
# MOD-198: служба переведена с рабочей копии сессии на зафиксированный выпуск.
# Пустой ExecStart= обязателен: он сбрасывает прежний список команд.
[Service]
WorkingDirectory=/srv/site-factory/services/seo-report-viewer.service/current
ExecStart=
ExecStart=/srv/site-factory/services/seo-report-viewer.service/venv/bin/python \
  -m seo_engine.content_operator.report_server \
  --root /var/lib/seo-content-operator/reports/runs \
  --bind 127.0.0.1 --port 8231
CONF
systemctl daemon-reload
systemctl restart seo-report-viewer.service

# --- ПОСЛЕ: те же три проверки плюс сверка выпуска -----------------------
sleep 3
systemctl is-active seo-report-viewer.service
systemctl show -p WorkingDirectory -p ExecStart seo-report-viewer.service
curl -sS -o /dev/null -w 'после переключения: HTTP %{http_code}\n' \
  --max-time 10 http://127.0.0.1:8231/
sudo -u claude python3 \
  /home/claude/wt-nova-publish-memory-02/automation/local/install-service-release.py \
  --service seo-report-viewer.service --verify
# ожидается: active; WorkingDirectory и ExecStart указывают в /srv/site-factory;
#            HTTP 200; «файлов 11, расхождений 0»

# --- ОТКАТ (если любая из проверок «после» не сошлась) -------------------
rm -f /etc/systemd/system/seo-report-viewer.service.d/release.conf
rmdir /etc/systemd/system/seo-report-viewer.service.d
systemctl daemon-reload
systemctl restart seo-report-viewer.service
curl -sS -o /dev/null -w 'после откату: HTTP %{http_code}\n' \
  --max-time 10 http://127.0.0.1:8231/
# служба возвращается на прежнюю рабочую копию; выпуск в /srv остаётся лежать
```

**Следующий штатный запуск.** У этой службы нет таймера: она работает
постоянно, и «следующий запуск» — это `Restart=on-failure` плюс перезагрузка
узла. Проверяется тем же `curl` и `systemctl is-active` после перезапуска;
отдельно — что `current` указывает на выпуск, а не на копию.

## 5. Порядок дальнейших групп (общей остановки нет)

1. **seo-report-viewer** — сделано до операторского шага (эта страница).
2. **Группа «никаких незакоммиченных, свой узкий состав»**:
   `yummy-sitemap-warm` (1 файл), `community-ratings-monitor` (7),
   `seo-daily-cycle` (10), `seo-engine-topvisor-inventory` (13). Каждая
   переносится отдельным выпуском, проверяется своим следующим срабатыванием
   таймера, и только после этого берётся следующая.
3. **Группа редактора и регулярных прогонов** (`editor-run`, `seo-tech-run`,
   `seo-tech-publish`, четыре `seo-regular-*`, `analytics-cabinet`,
   `site-cell-executor`, `site-factory-mcp`) — все из одной копии
   `wt-portable-site-cell-01`, 12–28 файлов, у них общий состав: переносятся
   ОДНИМ выпуском на копию, но переключаются по одной службе.
4. **Две службы с незакоммиченными файлами** (`seo-content-operator`,
   `seo-content-operator-report`) — последними и только после того, как линия
   `wt-seo-index-audit-20260930` решит судьбу этих трёх файлов: закоммитить
   или признать отклонением выпуска. Решение не моё.

## 6. Чего я НЕ делал

Не останавливал ни одной службы, не правил ни одного юнита, не коммитил
чужие незакоммиченные файлы и не сбрасывал ни одного дерева. Выпуск первой
службы разложен рядом и ничего не переключает до операторского шага.

## 7. Номера MOD: сверка линий и общий источник учёта

Поручение владельца. Сверено 26.10 сравнением файлов, а не на память.

| что | измерено |
| --- | --- |
| моя ветвь | 197 записей, максимум **MOD-198**, один пропуск — 126 |
| линия SEO (её HEAD) | 26 записей, максимум **MOD-026** |
| общих номеров | 26, и у ВСЕХ 26 заголовки совпадают дословно |
| расхождений по содержанию | **ноль** |
| номеров, которых нет у меня | ноль |
| `main` | файла `config/seo-module-defects.json в main НЕТ ВОВСЕ |

**Вывод: расхождения номеров нет, есть расхождение полноты.** Файл линии SEO —
префикс моего: она просто не брала записи с 027 по 198. Двух разных MOD-198 не
существует, и MOD-191 (вывод домена, заведённый ею) у меня есть с тем же
заголовком.

**Пропуск 126 намеренный:** номер снят 21.10 как дубль MOD-55 и MOD-71 (то же
измерено 16 и 17.10). Переиспользовать его нельзя — он уже назван в отчётах,
поэтому он числится снятым, а не свободным.

**Чего не хватает и что с этим делать.** Общего источника учёта нет: файла нет
в `main`, и каждая ветвь растит свою копию. Пока это так, правило одно и
проверяемое: следующий номер берётся от САМОЙ ПОЛНОЙ копии, а не от своей.
Проверка `tests/unit/test_mod_registry_single_source.py` ловит ровно оба
опасных случая — один номер с разными заголовками в двух линиях и ситуацию,
когда чужая копия полнее моей. Полное решение — слить реестр в `main`; это
часть слияния ветви и решение владельца, а не отдельная операция.

## 8. Поправка 26.10: перенос «только кода» ломает половину служб

Линия SEO (`wt-portable-site-cell-01-dc`) указала на целый класс зависимостей,
которого мой измеритель не видел вовсе. Проверил сам по юнитам и сценариям —
подтвердилось полностью, измеритель дополнен. Это та же ошибка, что весь
сегодняшний день: проверка смотрела не туда, где факт.

### Что именно не видел разбор импортов

| вид | пример (измерено) | куда при переносе |
| --- | --- | --- |
| **правила каталога запуска** | `editor-run.sh` и `seo-tech-run.sh` запускают АГЕНТА (`/home/claude/.local/bin/claude`), а он подчиняется `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks`, `.claude/rules`, `.claude/skills`, `.claude/agents` каталога запуска | **в выпуск**: без них агент либо встанет на запретах, либо, что хуже, пойдёт без них |
| **задание и редакционные правила** | `docs/editor/EDITOR_RUN_PROMPT.md` (читается через `sed`), `docs/editor/EDITORIAL_RULES.md` | в выпуск |
| **сценарии, вызываемые МОДЕЛЬЮ** | `automation/local/{bridge_call,source_fetch,comment-audit,comment-visible-check}.py` — их зовёт модель по заданию, а не `.sh` | в выпуск; найдены только после разбора самого ДОКУМЕНТА задания |
| **путевые поля юнита** | `analytics-cabinet`: `ConditionPathExists=…/config/analytics.json` (без файла юнит молча не стартует), `ReadWritePaths=…/var …/artifacts`, `ExecStartPre` создаёт `var/analytics`, `LoadCredential=yandex_oauth` | переключаются ОДНОВРЕМЕННО с `WorkingDirectory` |
| **состояние** | `var/editor-runs/{ledger.jsonl,next.json,run.lock,gate.jsonl,run-*}`, `var/analytics/`, `var/audit/operator.jsonl` | **НЕ в выпуск** |
| **бинарь вне дерева** | `/home/claude/.local/bin/claude`, `/usr/local/bin/community-ratings-gateway` | остаётся где есть |

Измерено после доработки: **агентных служб 2**, служб с путями состояния в
коде **8**, служб с путевыми полями юнита **13**.

### Следствие для замысла: состояние живёт ОТДЕЛЬНО от выпуска

Если `var/` попадёт внутрь выпуска, то откат переключением ссылки откатит и
состояние — редактор потеряет `ledger.jsonl` и `next.json`. Поэтому:

* выпуск содержит код, правила, задания и конфигурацию — и ничего из `var/`;
* состояние живёт в ПОСТОЯННОМ каталоге службы рядом с выпусками
  (`/srv/site-factory/services/<служба>/state`), и `current` на него не влияет;
* при переключении состояние **переносится один раз** (а не копируется каждый
  выпуск), и `ReadWritePaths` юнита указывает на него;
* отчёты и проверки линии SEO читают `var/` по пути рабочей копии — значит их
  перевод обязан идти ОДНОВРЕМЕННО с переключением службы, иначе отчёты будут
  показывать застывшие данные. Это названо их линией и принято.

### Окно, согласованное с линией SEO

Редактор, `analytics-cabinet`, `seo-tech-run/publish` — **вне 04:30–06:30Z**
(в 05:00 работает `analytics-cabinet`), окно **10:00–14:00Z**; отчёты идут в
07:00, 15:00 и 19:00Z. Редактор переключается только при свободном
`var/editor-runs/run.lock`. Порядок «редактор и аналитика последними в своей
группе» подтверждён.

### Что изменилось в составе групп

Линия `wt-seo-index-audit-20260930` закоммитила три файла (`ff8d678`), и теперь
**ни одна из 18 служб не зависит от незакоммиченного**. Группа «последними,
после решения о файлах» больше не нужна: обе её службы переходят в обычный
порядок. В том же дереве остаются 39 удалённых файлов — все снимки приёмки
`reports/*/evidence/*.png`; на состав служб они не влияют (в замыкания входят
только `.py`), но это отдельная находка, см. §9.

## 9. Две находки, вытащенные сверкой (не моей работой)

1. **Работа, которой не было в репозитории.** Линия аудита доложила владельцу
   «две правки с 13 проверками зафиксированы», а в репозитории лежала одна с
   четырьмя: код `daily_ops_report.py` и `ongoing_intake.py` не был
   закоммичен, два тестовых файла вовсе не отслеживались. Нашлось только
   потому, что моя сверка зависимостей назвала три файла «вне коммита».
   Исправлено их коммитом `ff8d678`. Класс записан как MOD-199.
2. **39 удалённых снимков приёмки** в дереве аудита. Проверил: **моя уборка
   их не удаляла** — в описи `artifacts/evidence/screenshot-census-two-worktrees-20261023.csv`
   597 строк и НИ ОДНОГО упоминания этого дерева, ни одно из 39 имён в ней не
   встречается. Файлы есть в истории git, то есть восстановимы. Диск сейчас:
   204 ГиБ всего, 191 занято, **13 свободно (94 %)**. Кто удалил — из моей
   линии не видно; это вопрос к владельцу, а не повод угадывать.

## Вторая группа переноса: измерение, два выпуска и готовые команды (26.10 11:4xZ)

### 1. Группу выбирает вердикт, а не число файлов

Прежняя намеченная четвёрка (`yummy-sitemap-warm`, `community-ratings-monitor`,
`seo-daily-cycle`, `seo-engine-topvisor-inventory`) была выбрана по числу
файлов, и это неверная мерка. `yummy-sitemap-warm` — один файл, но путь к
файлу паузы собирался от самого сценария, и после переноса приостановленный
прогрев возобновился бы сам, то есть пауза приёмки B016 чужой линии тихо
перестала бы действовать. Линия Yummy сделала путь параметром
(`YUMMY_WARM_PAUSE_FILE`, коммит 78d995a), и служба перешла в «можно при
условии».

Итог по 18 службам (`automation/local/service-dependency-map.py`,
доказательство `artifacts/evidence/service-dependency-map-20261026.json`):

| вердикт | служб | кто |
| --- | --- | --- |
| можно без условий | 4 | community-ratings-monitor, seo-report-viewer, site-cell-executor, seo-engine-topvisor-inventory |
| можно при условии | 11 | пять служб на `seo_operator/cli.py`, `analytics-cabinet`, `seo-daily-cycle`, `seo-content-operator-report`, `seo-tech-publish`, `editor-run`, `seo-tech-run`, `yummy-sitemap-warm` — у каждой условие названо переменной юнита |
| нельзя без правки | 3 | `community-ratings-gateway` (обёртка root прибивает копию), `seo-content-operator` и `site-factory-mcp` (зовут `git -C` по своему корню) |

**Эта таблица за час сменилась дважды, и обе причины названы, потому что
«12 нельзя» и «3 нельзя» — разный вывод для оператора.**

Первая смена — чужая работа: линия SEO вынесла корни состояния и реестров в
параметры (`8bf52ba`, затем `4574dd3`), и девять служб перешли из «нельзя» в
«можно при условии». Вторая — мои собственные ложные отказы, найденные при
проверке той правки: сканировалась только точка входа, а переопределение
уехало на модуль глубже; схема и фикстура считались живыми реестрами; текст
справки `--record` считался доступом к состоянию; вложенный путь под
параметризованным корнем считался отдельным.

Заодно нашёлся ложный ПРОПУСК в другую сторону: `community-ratings-gateway`
числился «можно без условий», пока я не прочитал его обёртку
`/usr/local/bin/community-ratings-gateway` — она принадлежит root и делает
`export PYTHONPATH` на рабочую копию, а `export` в обёртке перекрывает
`Environment` юнита. И второй: `seo-daily-cycle` грузит
`automation/host/seo_qwen_review.py` по пути от своего каталога, и 15 файлов
состава его не включали.

**Важное про `yummy-sitemap-warm`.** Путь паузы читает служба
(`YUMMY_WARM_PAUSE_FILE`), а ПИШЕТ его приёмка `yummy-b016-release.py` из
переменной `YB_WARM_PAUSE`. Имена разные. При переключении обе переменные
обязаны указывать на один файл, иначе приёмка поставит паузу туда, куда
служба не смотрит.

### 2. Что фактически установлено и проверено

| служба | выпуск | файлов | сверка | проверка делом |
| --- | --- | --- | --- | --- |
| seo-report-viewer | 20261026T102613Z-fd6d00a78905 | 11 | 0 расхождений, 0 недостающих | HTTP 200, 18 837 байт |
| community-ratings-monitor | 20261026T113854Z-ec29b2c7fa04 | 10 | 0 / 0 | импорт из выпуска, `REPORT_DIR` остался абсолютным |
| seo-engine-topvisor-inventory | 20261026T114139Z-5f26ed4fbd52 | 149 | 0 / 0 | `--mode status` отработал: 17 проектов, `source LIVE_READ_ONLY`, `stale false` |
| community-ratings-gateway | 20261026T120638Z-ec29b2c7fa04 | 20 | 0 / 0 | выпуск готов, но переключение бессмысленно до правки обёртки (root) |
| site-cell-executor | 20261026T120650Z-c1a901a6f0a8 | 145 | 0 / 0 | выпуск готов; переключение — после группы помельче |
| seo-content-operator | 20261026T124548Z-9621a7a3f6ef | 36 | 0 / 0 | свой venv (Python 3.11.16); из выпуска `_code_version()` даёт `9621a7a3f6ef` из `SEO_RELEASE_COMMIT`, без переменной — `unknown` (отрицательный контроль) |

### 2-бис. Готовый блок оператора: суточная служба отчёта (нужен root)

Служба системная. Линия, которая её ведёт (`wt-seo-index-audit-20260930`),
готовность подтвердила и прямо сказала, что переключение живой суточной службы
одобрить не может — это решение владельца. Условие переключения одно и
проверено делом: коммит берётся из переменной, а не из `git`.

```bash
# ДО
systemctl show -p WorkingDirectory -p ExecStart -p Environment seo-content-operator.service
systemctl list-timers seo-content-operator.timer --all
python3 /home/claude/wt-nova-publish-memory-02/automation/local/install-service-release.py \
  --service seo-content-operator.service --verify     # ждём: файлов 36, расхождений 0, недостающих 0

# ПЕРЕКЛЮЧЕНИЕ (drop-in; каталог выпуска и его venv)
sudo mkdir -p /etc/systemd/system/seo-content-operator.service.d
sudo tee /etc/systemd/system/seo-content-operator.service.d/release.conf >/dev/null <<'CONF'
[Service]
WorkingDirectory=/srv/site-factory/services/seo-content-operator.service/current
Environment=PYTHONPATH=/srv/site-factory/services/seo-content-operator.service/current
Environment=SEO_RELEASE_COMMIT=9621a7a3f6ef
ExecStart=
ExecStart=/srv/site-factory/services/seo-content-operator.service/venv/bin/python scripts/seo_content_operator_stage2_daily.py
CONF
sudo systemctl daemon-reload

# ПОСЛЕ: отчёт обязан назвать КОММИТ ВЫПУСКА, а не «unknown»
systemctl show -p WorkingDirectory -p ExecStart seo-content-operator.service
sudo systemctl start seo-content-operator.service
journalctl -u seo-content-operator.service -n 40 --no-pager | grep -i "commit\|version\|9621a7a"
systemctl list-timers seo-content-operator.timer --all

# ОТКАТ
sudo rm /etc/systemd/system/seo-content-operator.service.d/release.conf
sudo systemctl daemon-reload
python3 /home/claude/wt-nova-publish-memory-02/automation/local/install-service-release.py \
  --service seo-content-operator.service --rollback
```

**Почему `SEO_RELEASE_COMMIT` обязателен, а не желателен.** Проверено обоими
исходами: с переменной `_code_version()` из выпуска даёт `9621a7a3f6ef`, без
неё — `unknown`, потому что каталог выпуска не репозиторий. Без переменной
служба работать будет, но отчёт перестанет различать версии кода, по которому
построен.

Оба новых выпуска сперва были НЕПОЛНЫ и при этом давали «расхождений 0»:
разбор импортов не видел `from factory.community import metrics_store` и
относительных импортов. Поймал это запуск, а не сверка; теперь сверка
проверяет самодостаточность выпуска (оракул — дерево-источник).

`seo-engine-topvisor-inventory` получил свой venv
(`/srv/site-factory/services/seo-engine-topvisor-inventory.service/venv`,
Python 3.11.16, uv): без него перенос половинчатый — код из выпуска,
интерпретатор из рабочей копии.

### 3. Готовый блок оператора: пользовательская служба (без root)

Сервер — узел фабрики, пользователь `claude`. Drop-in лежит в репозитории:
`automation/host/mod198/seo-engine-topvisor-inventory.service.d-release.conf`.

```bash
# ДО: откуда служба работает сейчас и когда следующий штатный запуск
systemctl --user show -p WorkingDirectory -p ExecStart seo-engine-topvisor-inventory.service
systemctl --user list-timers seo-engine-topvisor-inventory.timer --all
python3 /home/claude/wt-nova-publish-memory-02/automation/local/install-service-release.py \
  --service seo-engine-topvisor-inventory.service --verify   # ждём: расхождений 0, недостающих 0

# ПЕРЕКЛЮЧЕНИЕ
mkdir -p /home/claude/.config/systemd/user/seo-engine-topvisor-inventory.service.d
cp /home/claude/wt-nova-publish-memory-02/automation/host/mod198/seo-engine-topvisor-inventory.service.d-release.conf \
   /home/claude/.config/systemd/user/seo-engine-topvisor-inventory.service.d/release.conf
systemctl --user daemon-reload

# ПОСЛЕ: путь, пробный запуск, результат и следующий запуск
systemctl --user show -p WorkingDirectory -p ExecStart seo-engine-topvisor-inventory.service
systemctl --user start seo-engine-topvisor-inventory.service
systemctl --user status seo-engine-topvisor-inventory.service --no-pager | head -20
journalctl --user -u seo-engine-topvisor-inventory.service -n 30 --no-pager
ls -l /home/claude/.local/share/seo-engine/topvisor-inventory/   # состояние на месте, не в выпуске
systemctl --user list-timers seo-engine-topvisor-inventory.timer --all  # следующий — 04:20 UTC

# ОТКАТ (любой из двух уровней)
rm /home/claude/.config/systemd/user/seo-engine-topvisor-inventory.service.d/release.conf
systemctl --user daemon-reload          # 1) вернуться к запуску из рабочей копии
python3 /home/claude/wt-nova-publish-memory-02/automation/local/install-service-release.py \
  --service seo-engine-topvisor-inventory.service --rollback   # 2) вернуть прежний выпуск
```

### 4. Готовый блок оператора: системная служба (нужен root)

Служба `community-ratings-monitor` системная и работает как `User=lords`,
таймер — каждые 15 минут (`OnUnitActiveSec=15min`), поэтому результат виден
быстро. Выпуск читаем всем, секреты остаются в `/etc/site-factory/secrets`.

```bash
# ДО
systemctl show -p WorkingDirectory -p ExecStart -p User community-ratings-monitor.service
systemctl list-timers community-ratings-monitor.timer --all
ls -t /srv/site-factory/repo/var/ratings/monitor | head -3   # последний отчёт ДО переключения

# ПЕРЕКЛЮЧЕНИЕ
sudo mkdir -p /etc/systemd/system/community-ratings-monitor.service.d
sudo cp /home/claude/wt-nova-publish-memory-02/automation/host/mod198/community-ratings-monitor.service.d-release.conf \
        /etc/systemd/system/community-ratings-monitor.service.d/release.conf
sudo systemctl daemon-reload

# ПОСЛЕ
systemctl show -p WorkingDirectory -p ExecStart community-ratings-monitor.service
sudo systemctl start community-ratings-monitor.service
systemctl status community-ratings-monitor.service --no-pager | head -20
ls -t /srv/site-factory/repo/var/ratings/monitor | head -3   # появился НОВЫЙ отчёт
systemctl list-timers community-ratings-monitor.timer --all  # следующий запуск через ≤15 минут

# ОТКАТ
sudo rm /etc/systemd/system/community-ratings-monitor.service.d/release.conf
sudo systemctl daemon-reload
```

### 5. Чего я намеренно не делал

* **Общей остановки 18 служб нет** и не будет: переключение идёт по одной, с
  проверкой результата и следующего запуска.
* **Drop-in не положен в живой systemd.** Файлы лежат в репозитории; копирование
  и `daemon-reload` — шаг оператора. Положить файл молча значит сменить
  определение действующей службы без ведома того, кто её ведёт.
* **Пароль базы не читался.** `seo-engine-topvisor-inventory` в режиме status с
  postgres-URL падает на пароле из `EnvironmentFile`; с настоящим sqlite-URL
  юнита он работает. `.env` не открывался.
* **Службы чужих линий не переключались** и ничего в их деревьях не менялось.

## 6. Первые штатные запуски после правки корней (26.10 12:2x–12:5x UTC)

Линия `wt-portable-site-cell-01` сообщила о трёх запусках, и я сверил их
СЛЕДАМИ в её дереве, а не по сообщению:

| служба | след | время | исход |
| --- | --- | --- | --- |
| seo-tech-run | `var/seo-tech/backlog.log` | запись 12:24:27Z | `{"skipped": "прошлый проход моложе --if-older"}` — штатный пропуск |
| editor-run (шлюз) | `var/editor-runs/gate.jsonl` | 12:50:01Z | `gate_rc 0`, `state resources` — штатный отказ по памяти |
| seo-regular-hourly | `var/seo-regular/runs/hourly-2026-10-26T12/run.json` | 12:50:23–12:50:25Z | `state DONE` |

Код запусков: `38ddfb8` (корни в обёртках) и `9a9344f` (убрана мёртвая ветка
`:-$REPO`, на которую я указал: `SEO_STATE_ROOT` уже экспортирован выше).

**Что это доказывает и чего не доказывает.** Доказывает: правка корней не
сломала штатный ход — три службы отработали по таймеру, записали свои следы в
прежние места, состояние осталось в рабочей копии. НЕ доказывает, что запуск
МОДЕЛИ редактора работает: шлюз отказал по памяти, то есть сама модель после
правки ещё не запускалась ни разу. Это ждёт освобождения памяти узла, а не
правки.

Для вердикта переноса это важно так: `editor-run` и `seo-tech-run` числятся
«можно при условии» (юнит задаёт `SEO_STATE_ROOT`, соответственно
`SEO_TECH_STATE`), и условие теперь подтверждено не чтением кода, а штатными
запусками.

## 7. Условие, которое видно только при сравнении служб: поля юнита

Класс нашла линия `wt-portable-site-cell-01`, и он межслужебный: писатель и
читатель одного файла начинают считать путь от разных корней, после чего файл
остаётся на месте, обе службы работают, а связь между ними исчезает молча.
Одна служба такого не показывает по устройству.

Измерено 26.10 по всем 18 службам: общих файлов состояния **23** — согласованы
11, расходятся **3**, не измерено 9. Все три расхождения одного вида, и ни одно
не в коде:

| файл | кто расходится | следствие при переносе |
| --- | --- | --- |
| `var/analytics` | `analytics-cabinet` называет путь в `ExecStartPre`, остальные берут из `SEO_STATE_ROOT` | предварительный шаг запишет не туда, читатели не увидят |
| `var/seo-regular` | у `seo-regular-*` путь в `ReadWritePaths`, код берёт из `SEO_STATE_ROOT` | **песочница запретит запись** — служба упадёт на записи |
| `var/seo-tech` | то же | то же |

**Следствие для переключения.** У `seo-regular-*` условие переноса не одно, а
два: `Environment=SEO_STATE_ROOT=…` И `ReadWritePaths=` с тем же каталогом.
Второе забыть легче, а отказ будет позже и в другом месте — на первой записи.
`ReadWritePaths` в этом смысле честнее `--out`: он не промолчит.
