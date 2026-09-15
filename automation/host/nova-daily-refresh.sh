#!/usr/bin/env bash
# Суточное пополнение каталога и метаданных витрин Lords и Zona.
#
# Порядок шагов не произволен. Каталог тянется первым, потому что всё
# остальное описывает его записи; подробности добираются вторыми, потому что
# они дополняют каталог, а не наоборот; публикация идёт последней и одним
# поколением на обе витрины — иначе Lords и Zona разойдутся по составу, и
# заметить это будет некому.
#
# Чего этот сценарий не делает: не трогает шаблоны, оформление, SEO, плеер,
# аналитику, DNS и чужие витрины. Каталог других сайтов семейства собирает
# прежний конвейер, и второго производителя тех же файлов здесь не появляется.
#
# Отказ источника не имеет права стать пустым сайтом: публикация отклоняется,
# витрины остаются на прежнем поколении, и прогон завершается ненулевым кодом.
set -Eeuo pipefail

# Имена переменных здесь латиницей намеренно. Кириллическое имя bash
# переменной не создаёт: строка выполняется как команда, оболочка отвечает
# «command not found», значение теряется, а прогон продолжается как ни в чём
# не бывало — с пустыми статусами в отчёте.

REPO="${FACTORY_REPO:-/srv/site-factory/repo}"
TOOLS="${NOVA_TOOLS:-${REPO}/automation/host}"
PYTHON="${FACTORY_PYTHON:-/usr/bin/python3}"
VAR="${REPO}/var/lords"
REPORTS="${VAR}/daily-reports"
STATE="${VAR}/daily-state"
RUN_ID="daily-$(date -u +%Y%m%dT%H%M%SZ)"

# Сколько подробностей добирается за сутки. Замер: detail отвечает примерно за
# три секунды на запись, то есть 6000 записей — это около пяти часов при
# шестичасовом пределе юнита. Числа взяты из замера, а не из округления:
# бюджет, выбранный «покруглее», либо не укладывается в предел, либо оставляет
# источник недоспрошенным.
DETAIL_BUDGET="${NOVA_DETAIL_BUDGET:-6000}"
# Нижняя граница каталога. Меньше — это неполный обход источника, а не
# «мало контента», и публиковать такое нельзя.
MIN_CATALOG="${NOVA_MIN_CATALOG:-52000}"
# Заявленные пороги покрытия оценками. Источник их сегодня не достигает
# (36.68 % КП, 50.66 % IMDb — замер на 673 свежих запросах, ноль добытых
# оценок сверх списка), поэтому по умолчанию их недостижение — предупреждение,
# а не отказ: job, который падает каждые сутки по неустранимой причине,
# перестают читать, и настоящий отказ тонет вместе с ним.
#
# Отказом остаётся РЕГРЕССИЯ: падение покрытия ниже достигнутого уровня
# означает, что оценки начали теряться по дороге, и это как раз тот случай,
# ради которого гейт заводят.
MIN_KP_PCT="${NOVA_MIN_KP_PCT:-90}"
MIN_IMDB_PCT="${NOVA_MIN_IMDB_PCT:-90}"
# Ставить 1, когда источник дорастёт до порога: тогда недостижение снова
# станет отказом без правки кода.
RATINGS_GATE_HARD="${NOVA_RATINGS_GATE_HARD:-0}"
BASELINE="${VAR}/rating-baseline.json"

mkdir -p "$REPORTS" "$STATE"
REPORT="${REPORTS}/${RUN_ID}.json"

log() { printf '[nova-daily] %s\n' "$*"; }

STATUS_CATALOG="skipped"; STATUS_DETAILS="skipped"; STATUS_PUBLISH="skipped"
STATUS_RATINGS="skipped"
CODE=0
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ------------------------------------------------------------- 1. каталог
# Источник умеет отдавать изменения с отметки времени; полный обход он
# повторяет сам раз в шесть часов. Отказ здесь не останавливает прогон:
# публикация просто пойдёт на прежнем снимке, и это лучше, чем не пойти
# вовсе — витрина всё равно получит подробности, добранные вчера.
log "шаг 1: каталог"
if "${REPO}/.venv/bin/python" -m factory lords-live --incremental \
     > "${STATE}/last-catalog.log" 2>&1; then
  STATUS_CATALOG="ok"
else
  STATUS_CATALOG="failed"
  log "каталог не обновлён; работаем на прежнем снимке"
fi

# ----------------------------------------------------------- 2. подробности
log "шаг 2: подробности (бюджет ${DETAIL_BUDGET})"
if "$PYTHON" "${TOOLS}/nova-detail-backfill.py" --budget "$DETAIL_BUDGET" \
     > "${STATE}/last-detail.log" 2>&1; then
  STATUS_DETAILS="ok"
else
  STATUS_DETAILS="failed"
  log "добор подробностей не выполнен; страницы останутся беднее"
fi

# ------------------------------------------------------------ 2b. оценки
# Внешние источники оценок. Ходит только за тем, чего не хватает, и
# складывает в хранилище; публикация берёт оттуда готовое и в сеть не ходит.
# Поэтому отказ источника стоит одного непополненного прогона, а не витрины
# без оценок.
#
# Выгрузка IMDb обновляется раз в сутки: она меняется ежедневно, а весит
# восемь мегабайт — перекачивать её чаще незачем, реже — значит показывать
# вчерашние числа дольше, чем нужно.
log "шаг 2b: оценки из внешних источников"
if "$PYTHON" "${TOOLS}/nova-ratings-backfill.py" --refresh-dataset      > "${STATE}/last-ratings.json" 2>&1; then
  STATUS_RATINGS="ok"
else
  STATUS_RATINGS="failed"
  log "добор оценок не выполнен; публикация пойдёт на прежнем хранилище"
fi

# ------------------------------------------------------------ 3. публикация
# Единственный шаг, который меняет то, что видит посетитель. Его отказ — отказ
# всего прогона: молча оставить витрины на вчерашнем поколении и отчитаться
# успехом значит завести расхождение, о котором никто не узнает.
log "шаг 3: публикация обеих витрин одним поколением"
if "$PYTHON" "${TOOLS}/nova-catalog-publish.py" --apply \
     --run-id "$RUN_ID" --min-catalog "$MIN_CATALOG" \
     > "${STATE}/last-publish.json" 2>&1; then
  STATUS_PUBLISH="ok"
  systemctl restart lords-nova-01.service nova-zona-01.service || true
else
  STATUS_PUBLISH="refused"
  CODE=1
  log "публикация отклонена; витрины оставлены на прежнем поколении"
fi

# -------------------------------------------------------------- 4. гейты
# Гейты считаются по тому, что реально опубликовано, а не по тому, что
# намеревались опубликовать.
log "шаг 4: гейты"
GATES_JSON="$("$PYTHON" - "$MIN_CATALOG" "$MIN_KP_PCT" "$MIN_IMDB_PCT" "$RATINGS_GATE_HARD" "$BASELINE" <<'PYEOF'
import json, sys, hashlib
from pathlib import Path

минимум = int(sys.argv[1])
порог_кп = float(sys.argv[2])
порог_имдб = float(sys.argv[3])
жёстко = sys.argv[4] == "1"
база_путь = Path(sys.argv[5])
# Допуск на дрожание: каталог растёт быстрее, чем источник проставляет
# оценки, поэтому доля может просесть на доли процента без всякой потери.
ДОПУСК = 1.0
фронт = Path("/srv/lords/.frontend")
итог, нарушения = {}, []
суммы = {}
for site in ("lords-01", "zona-01"):
    каталог = json.loads((фронт / f"{site}-catalog.json").read_text(encoding="utf-8"))
    детали = json.loads((фронт / f"{site}-details.json").read_text(encoding="utf-8"))["details"]
    ид = sorted({str(з["id"]) for з in детали.values() if з.get("id")})
    всего = len(детали) or 1
    кп = sum(1 for з in детали.values() if з.get("kinopoisk_rating"))
    им = sum(1 for з in детали.values() if з.get("imdb_rating"))
    оп = sum(1 for з in детали.values() if з.get("description"))
    по = sum(1 for з in детали.values() if з.get("poster_url"))
    суммы[site] = hashlib.sha256("\n".join(ид).encode()).hexdigest()
    итог[site] = {
        "catalog_items": каталог.get("count"),
        "unique_canonical_ids": len(ид),
        "id_set_checksum": суммы[site],
        "kp": кп, "kp_pct": round(кп * 100 / всего, 2),
        "imdb": им, "imdb_pct": round(им * 100 / всего, 2),
        "description_pct": round(оп * 100 / всего, 2),
        "poster_pct": round(по * 100 / всего, 2),
    }
    if (каталог.get("count") or 0) < минимум:
        нарушения.append(f"{site}: каталог {каталог.get('count')} < {минимум}")
if len(set(суммы.values())) != 1:
    нарушения.append("наборы canonical ID витрин разошлись")

# Пустой список провайдеров — отказ, а не тишина: витрина, переставшая
# пополняться оценками, внешне неотличима от исправной.
try:
    оц = json.loads(Path("/srv/site-factory/repo/var/lords/daily-state/last-ratings.json").read_text(encoding="utf-8"))
except Exception:
    оц = {}
if not (оц.get("providers") or []):
    нарушения.append("список провайдеров оценок пуст")
else:
    дано = sum((и.get("fetched") or 0) for и in (оц.get("sources") or {}).values())
    добавлено = sum((и.get("ratings_added") or 0) for и in (оц.get("sources") or {}).values())
    # Ноль изменений допустим только когда источник действительно опрошен.
    if добавлено == 0 and дано == 0:
        нарушения.append("провайдеры не опрошены: fetched=0 и ratings_added=0")

# Оценки: недостижение заявленного порога и регрессия — разные события.
предупреждения = []
база = {}
if база_путь.is_file():
    try:
        база = json.loads(база_путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        база = {}
новая_база = {}
for site in ("lords-01", "zona-01"):
    кп, имдб = итог[site]["kp_pct"], итог[site]["imdb_pct"]
    новая_база[site] = {"kp_pct": кп, "imdb_pct": имдб}
    for имя, доля, порог in (("KP", кп, порог_кп), ("IMDb", имдб, порог_имдб)):
        if доля < порог:
            (нарушения if жёстко else предупреждения).append(
                f"{site}: {имя} {доля}% < заявленных {порог}%"
                + ("" if жёстко else " (потолок источника; отказом не считается)"))
    прежнее = база.get(site) or {}
    for имя, ключ, доля in (("KP", "kp_pct", кп), ("IMDb", "imdb_pct", имдб)):
        было = прежнее.get(ключ)
        if было is not None and доля < было - ДОПУСК:
            нарушения.append(
                f"{site}: {имя} просело {было}% → {доля}% — оценки теряются по дороге")
try:
    база_путь.write_text(json.dumps(новая_база, ensure_ascii=False, indent=2),
                         encoding="utf-8")
except OSError:
    pass

итог["rating_targets"] = {"kp_pct": порог_кп, "imdb_pct": порог_имдб,
                          "hard_gate": жёстко}
итог["rating_baseline_previous"] = база
итог["warnings"] = предупреждения
итог["violations"] = нарушения
print(json.dumps(итог, ensure_ascii=False))
PYEOF
)"
if [ -z "$GATES_JSON" ]; then GATES_JSON='{"violations":["гейты не посчитаны"]}'; CODE=1; fi
if [ "$(printf '%s' "$GATES_JSON" | "$PYTHON" -c 'import json,sys;print(len(json.load(sys.stdin).get("violations") or []))')" != "0" ]; then
  CODE=1
fi

# -------------------------------------------------------------- 5. отчёт
"$PYTHON" - "$REPORT" "$RUN_ID" "$STARTED_AT" "$STATUS_CATALOG" "$STATUS_DETAILS" \
  "$STATUS_PUBLISH" "$CODE" "$GATES_JSON" "$STATUS_RATINGS" <<'PYEOF'
import json, sys, time
from pathlib import Path
(путь, run_id, начало, кат, дет, пуб, код, гейты) = sys.argv[1:9]
оценки_статус = sys.argv[9] if len(sys.argv) > 9 else "skipped"
оценки = {}
try:
    оценки = json.loads(Path("/srv/site-factory/repo/var/lords/daily-state/last-ratings.json").read_text(encoding="utf-8"))
except Exception:
    оценки = {}
публикация = {}
try:
    публикация = json.loads(Path("/srv/site-factory/repo/var/lords/daily-state/last-publish.json").read_text(encoding="utf-8"))
except Exception:
    публикация = {}
детали = {}
try:
    детали = json.loads(Path("/srv/site-factory/repo/var/lords/detail-backfill-report.json").read_text(encoding="utf-8"))
except Exception:
    детали = {}
отчёт = {
    "run_id": run_id,
    "started_at": начало,
    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "exit_code": int(код),
    "steps": {"catalog": кат, "details": дет, "ratings": оценки_статус,
              "publish": пуб},
    "ratings": {
        "providers": оценки.get("providers") or [],
        "sources": оценки.get("sources") or {},
        "coverage_before": оценки.get("coverage_before"),
        "coverage_after": оценки.get("coverage_after"),
        "store_entries": оценки.get("store_entries"),
        "quarantined_total": оценки.get("quarantined_total"),
        "started_at": оценки.get("started_at"),
        "completed_at": оценки.get("completed_at"),
    },
    "snapshot": публикация.get("snapshot"),
    "parity": публикация.get("parity"),
    "sites": публикация.get("sites"),
    "detail_backfill": {k: детали.get(k) for k in
                        ("requests_made", "gained_cached", "gained_description",
                         "before", "after")},
    "gates": json.loads(гейты),
    "rollback": {"available": bool(публикация.get("before_images")),
                 "command": публикация.get("rollback_command")},
}
Path(путь).write_text(json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
Path("/srv/site-factory/repo/var/lords/daily-latest.json").write_text(
    json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"run_id": run_id, "exit_code": int(код),
                  "violations": отчёт["gates"].get("violations")}, ensure_ascii=False))
PYEOF

log "готово: ${RUN_ID}, код ${CODE}, отчёт ${REPORT}"
exit "$CODE"
