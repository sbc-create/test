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
