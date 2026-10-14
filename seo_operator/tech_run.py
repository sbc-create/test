"""Фоновое техническое SEO: выбор задачи и проверка ПО СЛЕДАМ, а не по самоотчёту.

Образец — фоновый редактор (seo_operator.editor_run), перенесённый на технику
(разбор Архитектора, docs/verification/autocontinue-technical-seo-20261012.md):

* очередь — `config/seo-tech-queue.json` (определения задач, только чтение);
  состояние — `var/seo-tech/` (единственное, что прогон пишет вне рабочих копий);
* прогон ГОТОВИТ ветку в отдельной git-рабочей копии (`git worktree`) репозитория
  витрины и НЕ делает push и выпуск: это свойство юнита (InaccessiblePaths на
  учётные данные git), а здесь — ещё и проверяемый след;
* вердикт `verify()`: ветка есть, в ней есть коммит поверх базы, регрессионная
  проверка задачи ПАДАЕТ на базе и ПРОХОДИТ на ветке (D203), полный
  `checks/run.sh` ветки проходит, у ветки нет удалённого двойника;
* повторы ограничены (`MAX_ATTEMPTS`), зависший захват (старше `STALE_S` без
  итога) освобождается, а не держит задачу вечно.

Статусы задачи различаются строго: queued → prepared (ветка есть) → verified
(вердикт по следам) → released / live_verified (только сессией или человеком,
после просмотра: выпуск фоновому прогону не принадлежит).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
# Переопределения окружением — для приёмки и тестов на отдельном состоянии, чтобы
# проверка механизма не тратила попытки настоящих задач.
QUEUE = Path(os.environ.get("SEO_TECH_QUEUE") or REPO / "config" / "seo-tech-queue.json")
STATE = Path(os.environ.get("SEO_TECH_STATE") or REPO / "var" / "seo-tech")
#: Задачи, поставленные пополнением очереди (tech_backlog): лежат в состоянии, а не в
#: отслеживаемом config/ — служба не правит файлы git; сессия переносит их в очередь.
AUTO_QUEUE_NAME = "auto-tasks.json"
MAX_ATTEMPTS = 3
STALE_S = 2 * 3600
#: Исходы прогона, которые НЕ считаются неудачной попыткой.
НЕ_НЕУДАЧА = {"VERIFIED", "NO_TASK", "SUPERSEDED"}
ГОТОВО = {"verified", "released", "live_verified", "done"}


#: Восемь новых доменов Lords вне продвижения — тот же перечень, что
#: editor_run.ВНЕ_ПРОДВИЖЕНИЯ (равенство держит тест). Здесь литерал, а не
#: импорт: приёмка механизма (automation/local/seo-tech-mechanism-audit.py)
#: грузит этот файл из временного дерева без пакета seo_operator, и любой импорт
#: соседнего модуля там падает. После слияния — реестр ячеек
#: (promotion.excluded, область periodic_seo_edits).
ВНЕ_ПРОДВИЖЕНИЯ = ("lordfilm.group", "lordfilm.spb.ru", "lordfilm.msk.ru", "lordserial.su",
                   "lordserial.group", "lordserial.spb.ru", "lordserial.msk.ru",
                   "lordserial.net.ru")


#: Где на машине лежат каталоги данных витрин (имя — имя репозитория).
КОРНИ_ДАННЫХ = (Path("/srv"),)


def снимок_стенда(репо: Path, куда: Path) -> dict[str, str]:
    """Урезанный снимок для витрин с checks/mini_stand.py (Lords) — окружение проверок.

    Полный снимок Lords (63 тыс. записей) на живом хосте стенд не поднимает:
    память (ночные OOM 12–13.10), а юнит прогона ограничен MemoryMax=2G. Каждая
    двадцатая запись — тем же `mini_stand.урезать`, что и у проверок витрины
    (замер 13.10: пик 615 МиБ, 4 с). Без mini_stand.py или без данных — {}:
    проверки тогда честно скажут «НЕ ИЗМЕРЕНО», и вердикт не выйдет VERIFIED.
    """
    модуль = репо / "checks" / "mini_stand.py"
    источник = next((к for корень in КОРНИ_ДАННЫХ
                     for к in (корень / репо.name / "data", корень / f"site-{репо.name}" / "data")
                     if any(к.glob("*-catalog.json"))), None)
    if источник is None:
        return {}
    if not модуль.is_file():
        # Витрины без урезанного стенда (AnimeGo, Animedia, Zona): проверки читают снимок ячейки
        # сами и копируют его. В рабочей копии прогона имя каталога другое, и путь
        # /srv/<имя репозитория>/data проверка не находила — «НЕ ИЗМЕРЕНО» и на базе, и на ветке
        # (T093 14.10). Снимок только читается.
        return {"SITE_DATA_DIR": str(источник), "SITEMAP_CHECK_DATA": str(источник)}
    if not any(куда.glob("*-catalog.json")):
        import importlib.util
        try:
            спец = importlib.util.spec_from_file_location(f"mini_stand_{репо.name}", модуль)
            мини = importlib.util.module_from_spec(спец)
            спец.loader.exec_module(мини)
            куда.mkdir(parents=True, exist_ok=True)
            мини.урезать(источник, куда)
        except Exception:  # noqa: BLE001 — сбой снимка не роняет захват: проверки скажут «не измерено»
            shutil.rmtree(куда, ignore_errors=True)
            return {}
    return {"SITE_DATA_DIR": str(куда), "SITEMAP_CHECK_DATA": str(куда)}


class ВнеПродвижения(ValueError):
    """Задача касается домена, исключённого владельцем из продвижения."""


def вне_продвижения(задача: dict) -> str | None:
    """Исключённый домен, которого касается задача, или None.

    Восемь новых доменов Lords — только техническая подготовка ячеек
    (Архитектор); периодические SEO-правки очереди их не трогают. Очередь
    пишется руками, поэтому сверка идёт по доменам в `site` и по имени
    репозитория в `repo` (`lordfilm-group` для `lordfilm.group`).
    """
    домены = set(re.findall(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", str(задача.get("site", "")).lower()))
    репо = Path(str(задача.get("repo", ""))).name.lower()
    for д in ВНЕ_ПРОДВИЖЕНИЯ:
        if д in домены or репо == д.replace(".", "-"):
            return д
    return None


def _сейчас() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _git(репо: Path, *арг: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(репо), *арг], capture_output=True, text=True, timeout=300)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(арг)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def load_queue(путь: Path = QUEUE, state: Path | None = None) -> list[dict[str, Any]]:
    """Очередь: config/seo-tech-queue.json плюс задачи пополнения из состояния.

    Задача пополнения с id, уже занятым в config, отбрасывается: решение сессии
    в config главнее автоматического.
    """
    данные = json.loads(путь.read_text(encoding="utf-8"))
    задачи = данные["tasks"]
    ид = [з["id"] for з in задачи]
    if len(ид) != len(set(ид)):
        raise ValueError("в очереди повторяются id задач")
    авто = (state or STATE) / AUTO_QUEUE_NAME
    if авто.is_file():
        try:
            добавка = json.loads(авто.read_text(encoding="utf-8")).get("tasks") or []
        except (OSError, ValueError):
            добавка = []
        известные = set(ид)
        for з in добавка:
            if isinstance(з, dict) and з.get("id") and з["id"] not in известные:
                задачи.append({**з, "source": з.get("source") or "auto"})
                известные.add(з["id"])
    return задачи


def _runs(state: Path) -> list[dict[str, Any]]:
    f = state / "runs.jsonl"
    if not f.exists():
        return []
    return [json.loads(с) for с in f.read_text(encoding="utf-8").splitlines() if с.strip()]


def _claims(state: Path) -> list[dict[str, Any]]:
    f = state / "claims.jsonl"
    if not f.exists():
        return []
    return [json.loads(с) for с in f.read_text(encoding="utf-8").splitlines() if с.strip()]


class ЗанятоДругимПрогоном(RuntimeError):
    """Задачу уже держит живой захват другого прогона."""


def _замок(state: Path, task_id: str) -> Path:
    return state / "claims" / f"{task_id}.claim"


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _старт_процесса(pid: int) -> str:
    """Время старта процесса (поле 22 /proc/<pid>/stat) — отличает переиспользованный pid."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return ""
    return stat.rsplit(")", 1)[-1].split()[19] if ")" in stat else ""


def владелец_замка() -> dict[str, str]:
    """Чей это захват: процесс обёртки (SEO_TECH_OWNER_PID) или родитель команды."""
    pid = int(os.environ.get("SEO_TECH_OWNER_PID") or os.getppid())
    return {"pid": str(pid), "start": _старт_процесса(pid), "boot": _boot_id()}


def _поля_замка(текст: str) -> dict[str, str]:
    return dict(ч.split("=", 1) for ч in текст.split() if "=" in ч)


def _замок_свеж(замок: Path, now: dt.datetime) -> bool:
    """Живой ли захват.

    С 14.10 замок несёт pid, время старта и boot_id владельца: захват свеж, пока
    жив ИМЕННО этот процесс в ЭТОЙ загрузке. Остановка службы, OOM, перезагрузка
    освобождают задачу сразу, а не через STALE_S. Старый формат (без pid) — по
    возрасту, как прежде.
    """
    try:
        текст = замок.read_text(encoding="utf-8")
        возраст = now.timestamp() - замок.stat().st_mtime
    except FileNotFoundError:
        return False
    if возраст >= STALE_S:
        return False  # предел сверху: даже живой, но зависший владелец не держит задачу вечно
    поля = _поля_замка(текст)
    if поля.get("pid"):
        if поля.get("boot") and поля["boot"] != _boot_id():
            return False
        старт = _старт_процесса(int(поля["pid"]))
        return bool(старт) and старт == поля.get("start", старт)
    return True


def task_state(state: Path = STATE, now: dt.datetime | None = None) -> dict[str, dict[str, Any]]:
    """Сводка по задачам из следов: последний вердикт, число неудач, живой захват.

    «Занято» — ТОЛЬКО файл-замок claims/<id>.claim (один источник правды);
    claims.jsonl — журнал захватов, на занятость не влияет.
    """
    now = now or _сейчас()
    итог: dict[str, dict[str, Any]] = {}
    for р in _runs(state):
        з = итог.setdefault(р["task_id"], {"failures": 0})
        з["last"] = р
        вердикт = р.get("verdict")
        if вердикт == "VERIFIED":
            з["status"] = "verified"
        elif вердикт == "SUPERSEDED":
            # Подготовленная ветка устарела (база ушла вперёд, выпуск не fast-forward):
            # задача снова готовится — с чистым счётом попыток.
            з.pop("status", None)
            з["failures"] = 0
        elif вердикт not in НЕ_НЕУДАЧА:
            з["failures"] += 1
    for замок in sorted((state / "claims").glob("*.claim")) if (state / "claims").is_dir() else []:
        if _замок_свеж(замок, now):
            итог.setdefault(замок.stem, {"failures": 0})["open_claim"] = замок.read_text(encoding="utf-8").strip()
    return итог


#: Доли по направлениям (владелец 2026-10-13): 50 % — аниме, 50 % — действующие
#: Lordfilm/Lordserial. Zona и сетевые задачи в доли не входят и идут после.
ДОЛИ_ПО_УМОЛЧАНИЮ = {"anime": 0.5, "lords": 0.5, "window_h": 24}


def load_allocation(путь: Path = QUEUE) -> dict[str, Any]:
    try:
        raw = json.loads(путь.read_text(encoding="utf-8")).get("allocation") or {}
    except (OSError, ValueError):
        raw = {}
    return {**ДОЛИ_ПО_УМОЛЧАНИЮ, **{к: в for к, в in raw.items() if к != "note"}}


def захваты_по_направлениям(задачи: list[dict], state: Path, now: dt.datetime,
                            hours: int = 24) -> dict[str, int]:
    """Сколько захватов за окно пришлось на каждое направление (выделенный ресурс)."""
    направление = {з["id"]: з.get("direction") for з in задачи}
    счёт = {"anime": 0, "lords": 0}
    начало = now - dt.timedelta(hours=hours)
    for к in _claims(state):
        try:
            когда = dt.datetime.fromisoformat(str(к.get("at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        н = направление.get(к.get("task_id"))
        if когда >= начало and н in счёт:
            счёт[н] += 1
    return счёт


def candidates(задачи: list[dict], state: Path = STATE, now: dt.datetime | None = None,
               доли: dict | None = None) -> list[dict]:
    """Задачи queued без вердикта, без живого замка и с запасом попыток.

    Порядок — по долям направлений: первыми задачи направления, сильнее
    отставшего от своей доли за окно (при равенстве — Lords), затем другого,
    затем вне долей (Zona, сеть); внутри группы — порядок очереди. Без этого
    первой всегда шла бы верхняя задача файла, и направление, чьи задачи
    записаны выше, забирало бы весь ресурс.
    """
    now = now or _сейчас()
    сводка = task_state(state, now)
    итог = []
    for з in задачи:
        if з.get("status") != "queued":
            continue
        с = сводка.get(з["id"], {})
        if с.get("status") in ГОТОВО or с.get("failures", 0) >= MAX_ATTEMPTS or с.get("open_claim"):
            continue
        if вне_продвижения(з):
            continue
        итог.append(з)
    доли = доли or load_allocation()
    счёт = захваты_по_направлениям(задачи, state, now, int(доли.get("window_h", 24)))
    всего = sum(счёт.values())
    первое = min(счёт, key=lambda н: (счёт[н] - float(доли.get(н, 0.5)) * всего, н != "lords"))
    ранг = {первое: 0, ("anime" if первое == "lords" else "lords"): 1}
    return sorted(итог, key=lambda з: ранг.get(з.get("direction"), 2))


def next_task(задачи: list[dict], state: Path = STATE, now: dt.datetime | None = None) -> dict | None:
    """Первая доступная задача (без захвата; атомарный захват делает claim)."""
    к = candidates(задачи, state, now)
    return к[0] if к else None


#: Файлы рабочей копии витрины, которых нет в git, но без которых витрина не
#: стартует: `config/player.json` (в .gitignore, у части ячеек — root 0600).
#: Рабочая копия прогона и копии вердикта получают на них ССЫЛКУ из основной
#: копии репозитория — содержимое не читается и никуда не копируется. Без этого
#: стендовые проверки Animedia (sitemap_live, section_description) падали в
#: копиях вердикта на «витрина не поднялась» и на коде базы, и на ветке:
#: T083 14.10 — вердикт INCOMPLETE дважды при исправной правке.
НЕОТСЛЕЖИВАЕМЫЕ_ДЛЯ_ЗАПУСКА = ("config/player.json",)


def связать_неотслеживаемые(репо: Path, копия: Path) -> list[str]:
    """Ссылки на неотслеживаемые файлы запуска; возвращает связанные пути."""
    связано = []
    for относ in НЕОТСЛЕЖИВАЕМЫЕ_ДЛЯ_ЗАПУСКА:
        источник, цель = репо / относ, копия / относ
        # Нечитаемый источник (root 0600) не связывается: ссылка превратила бы
        # «файла нет» (его штатно обходит checks/stand_root.py) в PermissionError.
        if (источник.is_file() and os.access(источник, os.R_OK)
                and not цель.exists() and not цель.is_symlink()):
            if относ == "config/player.json" and not _плеер_совпадает(источник, копия):
                # Устаревший player.json (14.10: publisher_id сменён Архитектором, файл клона
                # прежний) уронил бы стенд «publisher_id …, а сайт объявляет …». Ссылки нет —
                # в копию кладётся фикстура из ПУБЛИЧНОГО publisher_id_expected (так же делает
                # checks/stand_root.py). Без неё стенды Lords (mini_stand) не поднимались вовсе:
                # T092 14.10 — INCOMPLETE, «стенд не поднялся» и на базе, и на ветке.
                if _фикстура_плеера(копия):
                    связано.append(относ + " (фикстура)")
                continue
            цель.parent.mkdir(parents=True, exist_ok=True)
            цель.symlink_to(источник)
            связано.append(относ)
    return связано


def _фикстура_плеера(копия: Path) -> bool:
    """config/player.json копии из publisher_id_expected (значение публичное: витрина отдаёт его атрибутом)."""
    try:
        ожидаемый = str(json.loads((копия / "config" / "site.json").read_text(encoding="utf-8"))
                        .get("publisher_id_expected") or "").strip()
    except (OSError, ValueError):
        return False
    if not ожидаемый:
        return False
    цель = копия / "config" / "player.json"
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(json.dumps({"publisher_id": ожидаемый, "source_mode": "provider-id",
                                "provenance": "фикстура проверки: publisher_id_expected из config/site.json"},
                               ensure_ascii=False), encoding="utf-8")
    return True


def _плеер_совпадает(плеер: Path, копия: Path) -> bool:
    """publisher_id файла плеера равен publisher_id_expected сайта (значения не печатаются)."""
    try:
        ожидаемый = str(json.loads((копия / "config" / "site.json").read_text(encoding="utf-8"))
                        .get("publisher_id_expected") or "").strip()
    except (OSError, ValueError):
        return True  # сверять не с чем — прежнее поведение (ссылка)
    if not ожидаемый:
        return True
    try:
        фактический = str(json.loads(плеер.read_text(encoding="utf-8")).get("publisher_id") or "").strip()
    except (OSError, ValueError):
        return False
    return ожидаемый == фактический


def claim(задача: dict, run_id: str, state: Path = STATE, now: dt.datetime | None = None) -> dict[str, Any]:
    """АТОМАРНЫЙ захват (O_EXCL на файл-замок задачи) + отдельная рабочая копия на новой ветке.

    Из двух одновременных прогонов файл создаст ровно один; второй получает
    ЗанятоДругимПрогоном и берёт следующую задачу. Просроченный замок (mtime
    старше STALE_S) снимается и захватывается заново — один раз.
    """
    now = now or _сейчас()
    if д := вне_продвижения(задача):
        raise ВнеПродвижения(f"{задача['id']}: {д} исключён из продвижения — только техническая подготовка ячейки")
    if any(к["run_id"] == run_id for к in _claims(state)):
        # Один run_id — один захват: verify() и release_worktree() ищут захват
        # по run_id, и второй захват под тем же именем увёл бы вердикт.
        raise ValueError(f"run_id {run_id} уже использован захватом")
    замок = _замок(state, задача["id"])
    замок.parent.mkdir(parents=True, exist_ok=True)
    for попытка in (1, 2):
        try:
            дескр = os.open(замок, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if попытка == 1 and not _замок_свеж(замок, now):
                закрыть_брошенный(замок, state, now)
                continue
            raise ЗанятоДругимПрогоном(задача["id"]) from None
    владелец = владелец_замка()
    with os.fdopen(дескр, "w", encoding="utf-8") as fh:
        fh.write(f"{run_id} {now.strftime('%Y-%m-%dT%H:%M:%SZ')} "
                 f"pid={владелец['pid']} start={владелец['start']} boot={владелец['boot']}\n")
    try:
        репо = REPO / задача["repo"]
        база = _git(репо, "rev-parse", "HEAD")
        ветка = f"claude/seo-tech-{задача['id'].lower()}-{run_id.lower()}"
        копия = state / "wt" / run_id
        копия.parent.mkdir(parents=True, exist_ok=True)
        _git(репо, "worktree", "add", "-q", "-b", ветка, str(копия), база)
        связать_неотслеживаемые(репо, копия)
    except Exception:
        замок.unlink(missing_ok=True)
        raise
    запись = {"run_id": run_id, "task_id": задача["id"], "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "repo": задача["repo"], "base_sha": база, "branch": ветка, "worktree": str(копия)}
    стенд = снимок_стенда(репо, state / "mini" / run_id)
    if стенд:
        запись["stand_data"] = стенд["SITE_DATA_DIR"]
    with open(state / "claims.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")
    (state / "next.json").write_text(json.dumps({**запись, "task": задача}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    return запись


def закрыть_брошенный(замок: Path, state: Path, now: dt.datetime) -> str | None:
    """Снять неживой замок; если его прогон не оставил итога — записать INTERRUPTED.

    Прерванная попытка (тайм-аут, остановка службы, OOM, перезагрузка) засчитывается
    в MAX_ATTEMPTS: задача, которая каждый раз роняет исполнитель, не крутится вечно.
    """
    try:
        текст = замок.read_text(encoding="utf-8").split()
    except FileNotFoundError:
        return None
    run_id = текст[0] if текст else ""
    task_id = замок.stem
    if run_id and run_id not in {р.get("run_id") for р in _runs(state)}:
        record({"run_id": run_id, "task_id": task_id, "verdict": "INTERRUPTED", "steps": {},
                "notes": ["прогон прерван до вердикта: владелец замка не жив "
                          "(тайм-аут, остановка службы, OOM или перезагрузка)"]},
               {"trigger": "recovery", "finished_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, state)
    замок.unlink(missing_ok=True)
    return run_id or None


def закрыть_брошенные(state: Path = STATE, now: dt.datetime | None = None) -> list[str]:
    """Все неживые замки задач — до выбора задачи (вызывается в начале каждого прогона)."""
    now = now or _сейчас()
    папка = state / "claims"
    закрыто = []
    for замок in sorted(папка.glob("*.claim")) if папка.is_dir() else []:
        if not _замок_свеж(замок, now):
            if закрыть_брошенный(замок, state, now):
                закрыто.append(замок.stem)
    return закрыто


def claim_next(задачи: list[dict], run_id: str, state: Path = STATE) -> dict[str, Any] | None:
    """Взять первую задачу, которую удалось захватить атомарно.

    Занятые пропускаются. Ошибка захвата одной задачи (нет репозитория, git отказал)
    записывается ей как неудачная попытка CLAIM_FAILED и не останавливает очередь.
    """
    for з in candidates(задачи, state):
        try:
            return claim(з, run_id, state)
        except ЗанятоДругимПрогоном:
            continue
        except ВнеПродвижения:
            continue
        except Exception as ош:  # noqa: BLE001 — одна задача не держит остальные
            record({"run_id": f"{run_id}-{з['id'].lower()}-claim", "task_id": з["id"],
                    "verdict": "CLAIM_FAILED", "steps": {},
                    "notes": [f"захват не удался: {type(ош).__name__}: {str(ош)[:300]}"]},
                   {"trigger": "claim", "finished_at": _сейчас().strftime("%Y-%m-%dT%H:%M:%SZ")}, state)
            continue
    return None


def prune_worktrees(state: Path = STATE, now: dt.datetime | None = None) -> list[str]:
    """Убрать брошенные рабочие копии — В НАЧАЛЕ каждого прогона, до захвата.

    Копия брошена, если её прогон закрыт (есть в runs.jsonl) или замок её задачи
    отсутствует, просрочен либо принадлежит другому прогону. Замок, принадлежащий
    брошенной копии и просроченный, снимается. Ветка остаётся (её смотрит человек).
    Восстановление после прерывания — свойство следующего прогона, а не человека.
    """
    now = now or _сейчас()
    убрано: list[str] = []
    закрыть_брошенные(state, now)
    корень = state / "wt"
    if not корень.is_dir():
        return убрано
    закрытые = {р["run_id"] for р in _runs(state)}
    захваты = {к["run_id"]: к for к in _claims(state)}
    репозитории: set[Path] = set()
    for копия in sorted(корень.iterdir()):
        run_id = копия.name.split("-verify-")[0]
        к = захваты.get(run_id)
        замок = _замок(state, к["task_id"]) if к else None
        владелец = замок.read_text(encoding="utf-8").split()[0] if замок and замок.exists() else ""
        живой = замок is not None and _замок_свеж(замок, now) and владелец == run_id
        if run_id in закрытые or not живой:
            репо = REPO / к["repo"] if к else None
            if репо:
                _git(репо, "worktree", "remove", "--force", str(копия), check=False)
                репозитории.add(репо)
            if копия.exists():
                shutil.rmtree(копия, ignore_errors=True)
            if замок and владелец == run_id and not живой:
                замок.unlink(missing_ok=True)
            убрано.append(копия.name)
    # Прогон, умерший между worktree add и записью журнала, оставляет копию без
    # записи в claims.jsonl: её репозиторий неизвестен. Поэтому prune — по всем
    # репозиториям очереди, а не только по найденным.
    try:
        for з in load_queue():
            if з.get("repo") and "*" not in з["repo"] and "<" not in з["repo"]:
                репозитории.add(REPO / з["repo"])
    except (OSError, ValueError, KeyError):
        pass
    for репо in репозитории:
        убрать_свои_ссылки(репо, state)
    return убрано


def убрать_свои_ссылки(репо: Path, state: Path) -> list[str]:
    """Снять служебные записи git ТОЛЬКО своих рабочих копий (state/wt/…), каталога которых нет.

    Глобальный `git worktree prune` здесь нельзя (14.10): служба живёт с PrivateTmp, и
    рабочие копии сессий в /tmp для неё «отсутствуют» — prune снимал их записи, рабочие
    копии сессий теряли связь с репозиторием. Чужие записи не трогаются вовсе.
    """
    служебные = репо / ".git" / "worktrees"
    if not служебные.is_dir():
        return []
    свои = str((state / "wt").resolve())
    снято = []
    for запись in sorted(служебные.iterdir()):
        try:
            цель = Path((запись / "gitdir").read_text(encoding="utf-8").strip()).parent
        except OSError:
            continue
        if str(цель).startswith(свои + os.sep) and not цель.exists():
            shutil.rmtree(запись, ignore_errors=True)
            снято.append(запись.name)
    return снято


def _прогнать(каталог: Path, команда: list[str], предел: int,
              среда: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(команда, cwd=каталог, capture_output=True, text=True, timeout=предел,
                           env=среда)
        return r.returncode, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return 124, f"предел {предел} с исчерпан"


def verify(run_id: str, state: Path = STATE, run_all: bool = True) -> dict[str, Any]:
    """Вердикт по следам. Каждый шаг — отдельный признак; VERIFIED только при всех."""
    захват = next((к for к in _claims(state) if к["run_id"] == run_id), None)
    if захват is None:
        return {"run_id": run_id, "verdict": "NO_TASK", "steps": {}, "notes": ["захвата с таким run_id нет"]}
    задачи = {з["id"]: з for з in load_queue()}
    задача = задачи.get(захват["task_id"], {})
    репо = REPO / захват["repo"]
    шаги: dict[str, bool] = {}
    заметки: list[str] = []

    голова = _git(репо, "rev-parse", "--verify", "-q", захват["branch"], check=False)
    шаги["branch_exists"] = bool(голова)
    # Коммит поверх базы: голова не равна базе, и база — её предок.
    шаги["has_commit"] = bool(голова) and голова != захват["base_sha"] and subprocess.run(
        ["git", "-C", str(репо), "merge-base", "--is-ancestor", захват["base_sha"], голова],
        capture_output=True).returncode == 0
    удалённые = _git(репо, "for-each-ref", "--format=%(refname)", f"refs/remotes/*/{захват['branch']}",
                     check=False)
    вверх = _git(репо, "config", "--get", f"branch.{захват['branch']}.remote", check=False)
    шаги["not_pushed"] = not удалённые and not вверх
    проверка = задача.get("check")
    шаги["check_declared"] = bool(проверка)

    if шаги["has_commit"] and проверка:
        # -z: без экранирования не-ASCII путей (иначе кириллическое имя проверки
        # не нашлось бы в ветке — замечание Архитектора 12.10).
        файлы = _git(репо, "ls-tree", "-r", "-z", "--name-only", голова)
        шаги["check_in_branch"] = проверка in файлы.split("\0")
        if шаги["check_in_branch"]:
            база_wt = state / "wt" / f"{run_id}-verify-base"
            голова_wt = state / "wt" / f"{run_id}-verify-head"
            for wt, sha in ((база_wt, захват["base_sha"]), (голова_wt, голова)):
                if wt.exists():
                    _git(репо, "worktree", "remove", "--force", str(wt), check=False)
                _git(репо, "worktree", "add", "-q", "--detach", str(wt), sha)
                связать_неотслеживаемые(репо, wt)
            стенд = снимок_стенда(репо, state / "mini" / run_id)
            среда = {**os.environ, **стенд} if стенд else None
            try:
                # Проверка ветки — на коде базы: обязана упасть (D203).
                (база_wt / проверка).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(голова_wt / проверка, база_wt / проверка)
                rc_база, вывод_база = _прогнать(база_wt, ["python3", проверка], 600, среда)
                rc_голова, вывод_голова = _прогнать(голова_wt, ["python3", проверка], 600, среда)
                # Коды проверок: 1 — дефект на месте, 2 — проверка не смогла
                # выполниться. Необработанное исключение Python тоже даёт 1,
                # поэтому трассировка в выводе — признак непригодности, а не дефекта.
                непригодна = any(rc not in (0, 1) or "Traceback (most recent call last)" in out
                                 for rc, out in ((rc_база, вывод_база), (rc_голова, вывод_голова)))
                шаги["check_usable"] = not непригодна
                if непригодна:
                    заметки.append(f"проверка непригодна: база rc={rc_база} {вывод_база[-200:]!r}; "
                                   f"ветка rc={rc_голова} {вывод_голова[-200:]!r}")
                шаги["check_fails_on_base"] = rc_база == 1 and not непригодна
                шаги["check_passes_on_branch"] = rc_голова == 0
                if not шаги["check_fails_on_base"]:
                    заметки.append("проверка проходит и на базе — она не различает (D203)")
                if not шаги["check_passes_on_branch"]:
                    заметки.append(f"проверка на ветке: {вывод_голова[-300:]}")
                if run_all:
                    rc_все, вывод_все = _прогнать(голова_wt, ["bash", "checks/run.sh"], 1800, среда)
                    шаги["run_all_passes"] = rc_все == 0
                    if rc_все:
                        заметки.append(f"checks/run.sh: {вывод_все[-400:]}")
            finally:
                for wt in (база_wt, голова_wt):
                    _git(репо, "worktree", "remove", "--force", str(wt), check=False)
                shutil.rmtree(state / "mini" / run_id, ignore_errors=True)

    нужно = ["branch_exists", "has_commit", "not_pushed", "check_declared", "check_in_branch",
             "check_usable", "check_fails_on_base", "check_passes_on_branch"] + (["run_all_passes"] if run_all else [])
    полный = all(шаги.get(к) for к in нужно)
    return {"run_id": run_id, "task_id": захват["task_id"], "branch": захват["branch"],
            "head": голова or None, "base_sha": захват["base_sha"],
            "verdict": "VERIFIED" if полный else "INCOMPLETE", "steps": шаги, "notes": заметки}


#: Штатные инструменты витрины, которые приводят служебные файлы в соответствие с кодом.
#: Шаг механический и детерминированный, поэтому выполняется обёрткой после модели, а не
#: заданием модели (14.10: T101 три раза без перештамповки манифеста — INCOMPLETE).
ИНСТРУМЕНТЫ_ДОВОДКИ = ("tools/stamp_manifest.py", "tools/update_pins.py")


def довести(run_id: str, state: Path = STATE) -> dict[str, Any]:
    """После модели: штамп манифеста и замок штатными инструментами, отдельным коммитом.

    Только если модель сделала коммит поверх базы; инструменты отсутствуют — ничего.
    Вердикт после этого проверяет ветку как обычно (manifest_and_entrypoint, verify_pins).
    """
    захват = next((к for к in _claims(state) if к["run_id"] == run_id), None)
    if захват is None:
        return {"run_id": run_id, "done": False, "reason": "захвата нет"}
    копия = Path(захват["worktree"])
    if not копия.is_dir():
        return {"run_id": run_id, "done": False, "reason": "рабочей копии нет"}
    голова = _git(копия, "rev-parse", "HEAD", check=False)
    if not голова or голова == захват["base_sha"]:
        return {"run_id": run_id, "done": False, "reason": "коммита поверх базы нет — доводить нечего"}
    выполнено = []
    for инструмент in ИНСТРУМЕНТЫ_ДОВОДКИ:
        if (копия / инструмент).is_file():
            r = subprocess.run(["python3", инструмент], cwd=копия, capture_output=True, text=True, timeout=300)
            выполнено.append({"tool": инструмент, "rc": r.returncode})
            if r.returncode:
                return {"run_id": run_id, "done": False, "tools": выполнено,
                        "reason": f"{инструмент}: {(r.stdout + r.stderr).strip()[-200:]}"}
    if not выполнено:
        return {"run_id": run_id, "done": False, "reason": "инструментов доводки в репозитории нет"}
    пути = [п for п in ("config/template-manifest.json", "pins.lock.json") if (копия / п).exists()]
    закоммичено = False
    if пути and _git(копия, "status", "--porcelain", "--", *пути, check=False):
        _git(копия, "add", "--", *пути, check=False)
        r = subprocess.run(["git", "-C", str(копия), "-c", "user.name=seo-tech-run",
                            "-c", "user.email=seo-tech-run@localhost", "commit", "-q", "-m",
                            "штамп манифеста и замок — штатные инструменты витрины (доводка seo-tech-run)"],
                           capture_output=True, text=True, timeout=120)
        закоммичено = r.returncode == 0
        if not закоммичено:
            return {"run_id": run_id, "done": False, "tools": выполнено,
                    "reason": f"коммит доводки не удался: {(r.stdout + r.stderr).strip()[-200:]}"}
    return {"run_id": run_id, "done": True, "tools": выполнено, "committed": закоммичено}


def record(результат: dict[str, Any], extra: dict[str, Any], state: Path = STATE) -> dict[str, Any]:
    запись = {**результат, **extra}
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "runs.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")
    return запись


def release_worktree(run_id: str, state: Path = STATE) -> None:
    """Рабочая копия прогона убирается; ВЕТКА остаётся для просмотра человеком."""
    захват = next((к for к in _claims(state) if к["run_id"] == run_id), None)
    if захват:
        _git(REPO / захват["repo"], "worktree", "remove", "--force", захват["worktree"], check=False)
        замок = _замок(state, захват["task_id"])
        if замок.exists() and замок.read_text(encoding="utf-8").split()[:1] == [run_id]:
            замок.unlink(missing_ok=True)
