"""Привилегированный исполнитель заявок: закрытый набор операций, журнал, замок.

Что он делает и чего не делает
------------------------------

Делает: берёт заявку из очереди, проверяет её по реестру и по GitHub, выполняет
одну из четырёх операций и записывает результат. Между «намерен» и «сделал»
всегда есть запись на диске — после гибели процесса или перезагрузки хоста
восстановление начинается со сверки журнала с фактом, а не с догадки.

Не делает: не выполняет путей, скриптов и команд из заявки. Их там нет как
понятия — схема заявки закрыта. Пути, юниты, порты и учётные записи берутся из
реестра, а артефакт собирается из названного коммита и сверяется по digest.

Почему замок с владельцем, а не с возрастом
-------------------------------------------

Старый замок направления лежал без pid, и решение «протух или нет» пришлось
принимать человеку. Возраст ничего не доказывает: долгая выкладка живёт часами,
а мёртвый процесс не становится живым от того, что замок свежий. Поэтому в
замке записан владелец — pid и время старта процесса — и живость проверяется,
а не предполагается. Совпадение одного pid недостаточно: номера переиспользуются,
и время старта отличает нового владельца от призрака.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import privileged, queue, registry, runtime


class ExecutorError(Exception):
    """Операция не выполнена. Витрина не тронута либо возвращена."""


def _сейчас() -> str:
    return datetime.now(timezone.utc).isoformat()


def _время_старта(pid: int) -> str:
    """Отметка старта процесса из /proc. Отличает живого владельца от тёзки."""
    try:
        поля = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        return поля[19]  # starttime в тиках с загрузки системы
    except (OSError, IndexError):
        return ""


@dataclass
class Замок:
    путь: Path
    владелец: dict[str, Any]

    def снять(self) -> None:
        with contextlib.suppress(OSError):
            self.путь.unlink()


def взять_замок(site_id: str, *, база: Path, операция: str) -> Замок:
    """Живая блокировка на сайт. Возраст не является разрешением на захват."""
    каталог = база / "locks"
    каталог.mkdir(parents=True, exist_ok=True)
    файл = каталог / f"{site_id}.json"
    мой = {"pid": os.getpid(), "starttime": _время_старта(os.getpid()),
           "site": site_id, "operation": операция, "at": _сейчас(),
           "host": os.uname().nodename}

    if файл.is_file():
        try:
            чужой = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ExecutorError(
                f"замок {файл} нечитаем. Испорченный замок хуже отсутствующего: "
                "он молча разрешает всё. Нужно решение человека") from None
        pid = чужой.get("pid")
        живой = False
        if isinstance(pid, int) and pid > 0:
            try:
                os.kill(pid, 0)
                живой = _время_старта(pid) == (чужой.get("starttime") or "")
            except OSError:
                живой = False
        if живой:
            raise ExecutorError(
                f"{site_id}: операцию {чужой.get('operation')} держит живой процесс "
                f"{pid} с {чужой.get('at')}. Ждём его, а не отнимаем")
        if not чужой.get("starttime"):
            raise ExecutorError(
                f"{site_id}: в замке {файл} нет отметки старта владельца. "
                "Снимать такой замок автоматически нельзя — возраст не "
                "доказывает смерть процесса")
        # Владелец мёртв и это доказано: pid не отвечает либо это другой процесс.
        файл.unlink()

    queue.записать_атомарно(файл, мой)
    return Замок(путь=файл, владелец=мой)


def проверить_заявку(заявка: queue.Заявка) -> dict[str, Any]:
    """Всё, что можно проверить до единой мутации."""
    try:
        cell = registry.resolve(заявка.site_id)
    except registry.RegistryError as exc:
        raise ExecutorError(
            f"{заявка.site_id}: сайта нет в реестре ячеек — исполнитель работает "
            "только с зарегистрированными сайтами") from exc
    remote = registry.require_own_repo(cell)

    # Имя репозитория из заявки — не источник доверия, а повод отказать при
    # расхождении: доверенным остаётся то, что записано в реестре.
    if заявка.repo and заявка.repo.split("/")[-1].removesuffix(".git") not in remote:
        raise ExecutorError(
            f"заявка называет репозиторий {заявка.repo}, а в реестре у "
            f"{заявка.site_id} записан {remote}")

    размещение = runtime.размещение(заявка.site_id)
    if размещение.previous_unit and размещение.unit == размещение.previous_unit:
        raise ExecutorError(
            f"{заявка.site_id}: реестр называет один и тот же юнит текущим и "
            "прежним; исполнять по такому описанию нельзя")
    return {"remote": remote, "runtime": размещение.as_dict()}


#: Имя файла учётных данных, которое юнит получает через LoadCredential.
ФАЙЛ_ТОКЕНА = "gh-token"


class ПроисхождениеНеПодтверждено(ExecutorError):
    """Спросить GitHub не удалось. Это отказ, а не примечание к успеху.

    Раньше здесь возвращалось `checked: false`, и выпуск шёл дальше. Проверка,
    которая отключается сама и никого не останавливает, хуже отсутствующей:
    результат выглядит одинаково и когда происхождение доказано, и когда его
    не спросили. Единственная связка, отделяющая выпуск от произвольного кода,
    не может быть необязательной.
    """


def _окружение_gh() -> dict[str, str]:
    """Учётные данные GitHub для root — из systemd, а не из чьего-то HOME.

    Исполнитель работает от root, у root нет входа в gh. Значение читается из
    каталога учётных данных юнита и никуда не пишется: ни в результат, ни в
    журнал, ни в отчёт.
    """
    окружение = dict(os.environ)
    каталог = окружение.get("CREDENTIALS_DIRECTORY")
    if каталог and not окружение.get("GH_TOKEN"):
        файл = Path(каталог) / ФАЙЛ_ТОКЕНА
        if файл.is_file():
            окружение["GH_TOKEN"] = файл.read_text(encoding="utf-8").strip()
    return окружение


#: Операции, которые ставят на сайт НОВЫЙ исполняемый код. Только им нужна
#: связка с прогоном CI. Доставка данных и откат её не требуют: доставка не
#: зовёт install_release вовсе, а откат возвращает выпуск, происхождение
#: которого доказывали при установке. Требовать прогон от доставки значило бы
#: остановить обновление каталога ради проверки, которой там нечего проверять.
ОПЕРАЦИИ_С_КОДОМ = ("activate",)


def проверить_ci(заявка: queue.Заявка, *, remote: str,
                 операция: str = "activate") -> dict[str, Any]:
    """Прогон CI обязан относиться именно к этому выпуску.

    Один хеш файла не доказывает происхождение: артефакт с тем же digest можно
    собрать где угодно. Доверие даёт связка целиком — РЕПОЗИТОРИЙ из реестра,
    РАЗРЕШЁННАЯ ветка, ТОЧНЫЙ коммит и УСПЕШНЫЙ прогон, — и проверяется она у
    GitHub, а не по словам заявки. Выпадение любого звена означает отказ.

    Репозиторий задаётся ключом `-R`, а не берётся из ответа: иначе прогон из
    чужого проекта с подходящим SHA прошёл бы проверку.
    """
    if операция not in ОПЕРАЦИИ_С_КОДОМ:
        return {"checked": False, "applicable": False,
                "reason": f"операция {операция} не ставит новый код"}
    if not заявка.ci_run:
        raise ПроисхождениеНеПодтверждено(
            f"{заявка.site_id}: заявка не называет прогон CI")
    проект = "/".join(remote.rstrip("/").split("/")[-2:]).removesuffix(".git")
    готово = subprocess.run(
        ["gh", "run", "view", заявка.ci_run, "-R", проект, "--json",
         "headSha,headBranch,conclusion,status,workflowName,databaseId"],
        capture_output=True, text=True, env=_окружение_gh())
    if готово.returncode != 0:
        raise ПроисхождениеНеПодтверждено(
            f"{заявка.site_id}: GitHub не ответил про прогон {заявка.ci_run} "
            f"в {проект}: {готово.stderr.strip()[:200]}")
    try:
        данные = json.loads(готово.stdout or "{}")
    except ValueError as exc:
        raise ПроисхождениеНеПодтверждено(
            f"{заявка.site_id}: ответ GitHub нечитаем: {exc}") from exc
    if not данные:
        raise ПроисхождениеНеПодтверждено(
            f"{заявка.site_id}: прогона {заявка.ci_run} в {проект} нет")
    if данные.get("status") != "completed":
        raise ExecutorError(
            f"прогон {заявка.ci_run} ещё не завершён ({данные.get('status')!r})")
    if данные.get("conclusion") != "success":
        raise ExecutorError(
            f"прогон {заявка.ci_run} завершился как {данные.get('conclusion')!r}; "
            "выкладывается только проверенный выпуск")
    if (данные.get("headSha") or "") != заявка.commit:
        raise ExecutorError(
            f"прогон {заявка.ci_run} относится к коммиту "
            f"{(данные.get('headSha') or '')[:12]}, а заявка — к {заявка.commit[:12]}. "
            "Зелёный CI на другом коммите ничего не доказывает об этом выпуске")
    ветка = данные.get("headBranch") or ""
    if not registry.ветка_разрешена(ветка):
        raise ExecutorError(
            f"прогон {заявка.ci_run} сделан на ветке {ветка!r}, а выпуск "
            f"разрешён только с {list(registry.ВЕТКИ_ВЫПУСКА)}. Зелёная ветка "
            "эксперимента — не разрешение выложить её на живой сайт")
    return {"checked": True, "repo": проект, "branch": ветка,
            "run": str(данные.get("databaseId") or заявка.ci_run),
            "workflow": данные.get("workflowName"),
            "conclusion": данные.get("conclusion")}


def происхождение_выпусков(*, база: Path | None = None) -> dict[str, Any]:
    """Какой выпуск исполняется у каждой витрины и кем он установлен.

    Исполнитель — не единственный, кто умеет ставить выпуск: в репозитории
    каждой витрины остались `deploy/activate.sh` и `deploy/rollback.sh`, и
    запуск их от root кладёт выпуск мимо очереди. Проверки происхождения
    (разрешённая ветка, точный коммит, успешный прогон) при этом не
    выполняются вовсе.

    Наблюдалось на lords-02: из четырёх выпусков в `releases/` результат
    исполнителя есть ровно у одного, а витрина исполняет тот, которого в
    результатах нет. Снаружи это неотличимо от штатного выпуска — сайт
    отвечает 200 и называет ожидаемый build-id, и следующий триггер честно
    говорит «нечего выкладывать».

    Отменить чужой путь отсюда нельзя — root есть root. Но молчание о нём
    хуже самого обхода: пока он невидим, отчёт «выложено исполнителем»
    описывает не то, что работает. Здесь он становится видимым.
    """
    корень = база or queue.БАЗА
    результаты = корень / "results"
    итог: list[dict[str, Any]] = []
    for site_id in sorted(registry.extracted_sites()):
        try:
            п = privileged.Площадка.из_реестра(site_id)
        except (privileged.PrivilegedRefused, registry.RegistryError) as exc:
            итог.append({"site_id": site_id, "state": "не размещён",
                         "reason": str(exc)[:120]})
            continue
        ссылка = п.current
        текущий = ссылка.resolve().name if ссылка.is_symlink() or ссылка.exists() else None
        # Различаются две вещи, которые легко спутать:
        #   тронутые  — исполнитель этот коммит РАЗВОРАЧИВАЛ, чем бы оно ни
        #               кончилось. Выпуск, поставленный в попытке, которая
        #               потом откатилась, остаётся в releases/ и обходом НЕ
        #               является. На первом же прогоне эта проверка назвала
        #               обходом zona-01/f0d1a9413e1a — ровно такой случай;
        #   успешные  — дошли до конца. Только они годятся в ответ на вопрос
        #               «исполняется ли то, что выпущено штатно».
        тронутые, успешные = set(), set()
        for файл in результаты.glob(f"{site_id}-*.json"):
            try:
                д = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            коммит = (д.get("commit") or "")[:12]
            if not коммит:
                continue
            тронутые.add(коммит)
            if д.get("status") == "ok":
                успешные.add(коммит)
        установлены = sorted(p.name for p in п.releases.iterdir()) if п.releases.is_dir() else []
        вне = [r for r in установлены if r not in тронутые]
        итог.append({
            "site_id": site_id, "current": текущий,
            "by_executor": bool(текущий and текущий in успешные),
            "releases_installed": len(установлены),
            "outside_queue": вне,
        })
    обход = [с for с in итог if с.get("outside_queue")]
    return {"sites": итог, "bypassed": [с["site_id"] for с in обход]}


def готовность_проверки() -> dict[str, Any]:
    """Может ли ИСПОЛНИТЕЛЬ спросить GitHub — не может ли это кто-то другой.

    Успешный `gh` у подающей стороны ничего не говорит о службе: у неё другой
    пользователь, другой HOME и учётные данные приходят от systemd. Поэтому
    вопрос задаётся тем же кодом и тем же окружением, каким пойдёт настоящая
    проверка, и по каждому разрешённому репозиторию отдельно — токен может
    открывать один проект и не открывать соседний.

    Ни одного значения токена наружу: возвращается только «да/нет» и причина.
    """
    окружение = _окружение_gh()
    итог: dict[str, Any] = {
        "credentials_directory": bool(os.environ.get("CREDENTIALS_DIRECTORY")),
        "token_available": bool(окружение.get("GH_TOKEN")),
        "sites": [],
    }
    for site_id in sorted(registry.extracted_sites()):
        try:
            cell = registry.resolve(site_id)
            remote = registry.require_own_repo(cell)
        except registry.RegistryError as exc:
            итог["sites"].append({"site_id": site_id, "ready": False,
                                  "reason": str(exc)[:200]})
            continue
        проект = "/".join(remote.rstrip("/").split("/")[-2:]).removesuffix(".git")
        готово = subprocess.run(
            ["gh", "run", "list", "-R", проект, "--limit", "1", "--json", "databaseId"],
            capture_output=True, text=True, env=окружение)
        if готово.returncode != 0:
            итог["sites"].append({"site_id": site_id, "repo": проект, "ready": False,
                                  "reason": готово.stderr.strip()[:200]})
        else:
            итог["sites"].append({"site_id": site_id, "repo": проект, "ready": True})
    итог["ready"] = bool(итог["sites"]) and all(с["ready"] for с in итог["sites"])
    итог["blocked"] = [с["site_id"] for с in итог["sites"] if not с["ready"]]
    return итог


def _засеять_хранилище(site_id: str, *, dry_run: bool) -> dict[str, Any]:
    """Первый выпуск витрины: положить каталог в ЕЁ хранилище.

    Витрина под монолитом читает общий каталог производителя; у выделенной
    ячейки хранилище своё, и при первом выпуске оно пустое. Кандидат в таком
    хранилище не поднимается вовсе — отказывается до первого запроса: «нет
    снимка каталога …: витрине нечего показывать». Проверено сборкой lords-01
    на пустом каталоге данных.

    Прежний сценарий активации делал это копированием из общего каталога; здесь
    то же самое, но проверенным путём снимка. Шаг выполняется ТОЛЬКО когда
    каталога нет: у витрины с наполненным хранилищем данные обновляются
    отдельной операцией, и трогать их выпуском кода нельзя.
    """
    from factory.cell import delivery

    п = privileged.Площадка.из_реестра(site_id)
    # Проверяется ВЕСЬ снимок, а не один каталог. Пятиминутный конвейер
    # доставляет в хранилище ячейки только каталог, как только витрина
    # объявлена управляемой; подробностей он не кладёт. По наличию каталога
    # витрина выглядела бы наполненной, а выложилась бы обеднённой: замерено на
    # сборке lords-01 — с каталогом и подробностями главная отдаёт 48 карточек
    # и 8 ссылок на серии, с одним каталогом 12 карточек и НОЛЬ ссылок на серии.
    # Для посетителя это пропавшие серии, а не «частичные данные».
    нехватка = [и for и in (ш.format(site=site_id) for ш in privileged.СНИМОК)
                if not (п.data / и).is_file()]
    if not нехватка:
        return {"seeded": False, "reason": "хранилище уже наполнено"}
    снимок = privileged.stage_snapshot(site_id, Path(delivery.ОБЩИЙ), dry_run=dry_run)
    повышение = privileged.promote_snapshot(site_id, dry_run=dry_run)
    return {"seeded": True, "missing": нехватка,
            "stage_snapshot": снимок, "promote_snapshot": повышение}


def активировать(заявка: queue.Заявка, *, файл: Path,
                 dry_run: bool = True) -> dict[str, Any]:
    """Выпуск без остановки работающего сайта и без кода репозитория от root.

    Порядок проверен на стенде с настоящими systemd и nginx:

      1. сборка ПОД УЧЁТНОЙ ЗАПИСЬЮ САЙТА — сборщик это код репозитория, и
         запускать его от root значило бы отдать root тому, кто может туда
         писать; root получает файл и сверяет digest;
      2. распаковка в отдельный выпуск — действующая версия продолжает
         исполнять свой;
      3. прогрев кандидата на отдельном порту, пока старая версия отвечает;
      4. кандидат обязан не просто ответить, а назвать ожидаемый выпуск;
      5. переключение трафика — замена одного файла upstream, nginx -t, reload;
      6. повышение: основная служба переводится на тот же выпуск и забирает
         трафик обратно, кандидат гасится.

    Любой отказ после шага 5 — откат маршрута с проверкой ответом.
    """
    cell = registry.resolve(заявка.site_id)
    try:
        repo = cell.repo_path
    except registry.RegistryError as exc:
        raise ExecutorError(f"{заявка.site_id}: {exc}") from exc
    if not (repo / "tools" / "build_release.py").is_file():
        # Отказ здесь, а не внутри сборки: понятно, что искали и где.
        raise ExecutorError(
            f"{заявка.site_id}: рабочей копии репозитория нет по пути {repo}. "
            f"Основание путей — {registry.корень_репозиториев()}")
    размещение = runtime.размещение(заявка.site_id)
    шаги: dict[str, Any] = {}

    # Площадка готовится ДО сборки. Сборщик запускается под учётной записью
    # САЙТА, а создаёт её именно `prepare`: при первом выпуске витрины учётной
    # записи ещё нет, и сборка падала на `getpwnam` раньше, чем что-либо
    # происходило. Проверено на lords-01: учётной записи lordfilm47-space не
    # существует, заявка уходила в бесконечный повтор по таймеру.
    шаги["prepare"] = privileged.prepare(заявка.site_id, dry_run=dry_run)
    шаги["seed_data"] = _засеять_хранилище(заявка.site_id, dry_run=dry_run)

    with tempfile.TemporaryDirectory() as tmp:
        артефакт, манифест = privileged.собрать_без_прав(
            repo, Path(tmp), размещение.account or "nobody")
        if манифест.get("source_commit") != заявка.commit:
            raise ExecutorError(
                f"собран коммит {манифест.get('source_commit', '')[:12]}, "
                f"а заявка о {заявка.commit[:12]}")
        if манифест.get("source_dirty"):
            # Совпадение digest здесь ничего не доказывает: и заявку, и дерево
            # правит одна и та же непривилегированная сторона. Выложить дерево
            # с несохранённой правкой значит выложить то, чего нет в коммите.
            raise ExecutorError(
                f"{заявка.site_id}: рабочая копия {repo} содержит несохранённые "
                f"изменения; выкладывается коммит, а не рабочий стол")
        if манифест.get("digest") != заявка.digest:
            raise ExecutorError(
                f"digest сборки {манифест.get('digest')} не совпал с заявленным "
                f"{заявка.digest}; выкладывается проверенный выпуск или никакой")
        build_id = манифест.get("live_build_id") or ""
        if файл.is_file():
            queue.отметить(файл, "artifact_verified", {"digest": заявка.digest})

        шаги["install_release"] = privileged.install_release(
            заявка.site_id, артефакт, заявка.digest,
            commit=заявка.commit, dry_run=dry_run)

    шаги["warm_up"] = privileged.warm_up(
        заявка.site_id, dry_run=dry_run, ожидаемый_build=build_id)
    прогрет = dry_run or (шаги["warm_up"].get("ready") or {}).get("ready")
    проверен = dry_run or (шаги["warm_up"].get("verify") or {}).get("ok")
    if not (прогрет and проверен):
        # Трафик не переключался: действующая версия и не переставала отвечать.
        шаги["rollback"] = privileged.rollback(заявка.site_id, dry_run=dry_run)
        return {"status": "candidate-failed", "stage": "failed", "steps": шаги,
                "build_id": build_id}
    if файл.is_file():
        queue.отметить(файл, "candidate_ready", {"build_id": build_id})

    порт_кандидата = privileged.Площадка.из_реестра(заявка.site_id).candidate_port
    шаги["switch_route"] = privileged.switch_route(
        заявка.site_id, порт_кандидата, dry_run=dry_run)
    if файл.is_file() and not dry_run:
        queue.отметить(файл, "switched")

    шаги["promote"] = privileged.promote(
        заявка.site_id, dry_run=dry_run, ожидаемый_build=build_id)
    повышено = dry_run or (шаги["promote"].get("verify") or {}).get("ok")
    if not повышено:
        шаги["rollback"] = privileged.rollback(заявка.site_id, dry_run=dry_run)
        return {"status": "rolled-back", "stage": "rolled_back", "steps": шаги,
                "build_id": build_id}

    шаги["verify"] = privileged.verify(заявка.site_id, ожидаемый_build=build_id)
    if not dry_run and not шаги["verify"].get("ok"):
        шаги["rollback"] = privileged.rollback(заявка.site_id, dry_run=False)
        return {"status": "rolled-back", "stage": "rolled_back", "steps": шаги,
                "build_id": build_id}
    return {"status": "dry-run" if dry_run else "activated",
            "stage": "validated" if dry_run else "live_verified",
            "steps": шаги, "digest": заявка.digest, "build_id": build_id}


def обновить_данные(заявка: queue.Заявка, *, файл: Path,
                    dry_run: bool = True) -> dict[str, Any]:
    """Обновление каталога тем же прогревом, что и выпуск кода.

    Работающий процесс отдаёт ПРЕЖНИЙ снимок, пока кандидат читает и
    индексирует новый. Раньше снимок подменялся под живым процессом, и на
    время перестроения запросы ждали секундами.

    Повтор того же снимка не делает ничего: «данные не изменились» — это
    законный исход, а не повод поднимать кандидата на четыре минуты.
    """
    from factory.cell import delivery

    размещение = runtime.размещение(заявка.site_id)
    шаги: dict[str, Any] = {}
    источник = Path(delivery.ОБЩИЙ)

    шаги["stage_snapshot"] = privileged.stage_snapshot(
        заявка.site_id, источник, dry_run=dry_run)
    if шаги["stage_snapshot"].get("unchanged"):
        return {"status": "unchanged", "stage": "live_verified", "steps": шаги}

    п = privileged.Площадка.из_реестра(заявка.site_id)
    шаги["warm_up"] = privileged.warm_up(
        заявка.site_id, dry_run=dry_run, данные=п.data_candidate)
    прогрет = dry_run or (шаги["warm_up"].get("ready") or {}).get("ready")
    if not прогрет:
        шаги["rollback"] = privileged.rollback(заявка.site_id, dry_run=dry_run)
        return {"status": "candidate-failed", "stage": "failed", "steps": шаги}
    if файл.is_file():
        queue.отметить(файл, "candidate_ready", {"data": True})

    шаги["switch_route"] = privileged.switch_route(
        заявка.site_id, п.candidate_port, dry_run=dry_run)
    шаги["promote_snapshot"] = privileged.promote_snapshot(
        заявка.site_id, dry_run=dry_run)
    шаги["promote"] = privileged.promote(
        заявка.site_id, dry_run=dry_run,
        ожидаемый_build=(размещение.as_dict().get("build_id") or ""))
    повышено = dry_run or (шаги["promote"].get("ready") or {}).get("ready")
    if not повышено:
        шаги["rollback"] = privileged.rollback(заявка.site_id, dry_run=dry_run)
        return {"status": "rolled-back", "stage": "rolled_back", "steps": шаги}

    шаги["verify"] = privileged.verify(заявка.site_id)
    if not dry_run and not шаги["verify"].get("ok"):
        шаги["rollback"] = privileged.rollback(заявка.site_id, dry_run=False)
        return {"status": "rolled-back", "stage": "rolled_back", "steps": шаги}
    return {"status": "dry-run" if dry_run else "delivered",
            "stage": "validated" if dry_run else "live_verified", "steps": шаги}


def выполнить(заявка: queue.Заявка, *, база: Path, dry_run: bool = True) -> dict[str, Any]:
    """Одна операция целиком, с журналом переходов."""
    файл = база / "requests" / f"{заявка.request_id}.json"
    результат: dict[str, Any] = {"request_id": заявка.request_id,
                                 "site_id": заявка.site_id,
                                 "operation": заявка.operation,
                                 "commit": заявка.commit,
                                 "dry_run": dry_run,
                                 "started_at": _сейчас()}
    замок = None
    try:
        проверено = проверить_заявку(заявка)
        if файл.is_file():
            queue.отметить(файл, "validated", {"remote": проверено["remote"]})
        результат["runtime"] = проверено["runtime"]

        результат["ci"] = проверить_ci(заявка, remote=проверено["remote"],
                                       операция=заявка.operation)

        замок = взять_замок(заявка.site_id, база=база, операция=заявка.operation)
        результат["lock"] = замок.владелец

        if заявка.operation == "activate":
            итог = активировать(заявка, файл=файл, dry_run=dry_run)
            результат["outcome"] = итог
            этап = итог["stage"]
        elif заявка.operation == "deliver":
            итог = обновить_данные(заявка, файл=файл, dry_run=dry_run)
            результат["outcome"] = итог
            этап = итог["stage"]
        else:
            raise ExecutorError(
                f"операция {заявка.operation} ещё не реализована исполнителем; "
                "объявлять её выполненной нельзя")

        if файл.is_file():
            queue.отметить(файл, этап, {"dry_run": dry_run})
        # Откат отрабатывает без исключения, но выпуска не было. Называть это
        # `ok` значит объявить применённым то, что откатили.
        применено = (итог.get("status") in queue.ПРИМЕНЁННЫЕ_ИСХОДЫ
                     if isinstance(итог, dict) else False)
        результат["status"] = "ok" if применено else "failed"
    except (ExecutorError, privileged.PrivilegedRefused,
            registry.RegistryError) as exc:
        результат["status"] = "rejected"
        результат["error"] = str(exc)
        if файл.is_file():
            queue.отметить(файл, "failed", {"error": str(exc)[:500]})
    except Exception as exc:   # noqa: BLE001 — см. ниже, это не «на всякий случай»
        # Заявка, на которой исполнитель падает непредвиденно, остаётся в
        # очереди без результата — и таймер повторяет её каждую минуту вечно.
        # Наблюдалось на lords-01: сборка под несуществующей учётной записью
        # давала KeyError, заявка переписывалась раз в минуту, результата не
        # появлялось, и снаружи это выглядело как «операция идёт».
        #
        # Широкий перехват здесь не прячет ошибку, а наоборот: без него она
        # видна только в журнале службы, а с ним — в результате, который читает
        # подающая сторона. Тип исключения называется явно.
        результат["status"] = "rejected"
        результат["error"] = f"непредвиденный отказ {type(exc).__name__}: {exc}"
        if файл.is_file():
            queue.отметить(файл, "failed", {"error": результат["error"][:500]})
    finally:
        if замок is not None:
            замок.снять()
        результат["finished_at"] = _сейчас()
    return результат


def обслужить_очередь(*, база: Path | None = None, dry_run: bool = True,
                      предел: int = 10) -> list[dict[str, Any]]:
    """Разобрать накопившиеся заявки. Порядок — по времени появления."""
    корень = база or queue.БАЗА
    очередь = корень / "requests"
    if not очередь.is_dir():
        return []
    итоги = []
    for файл in sorted(очередь.glob("*.json"), key=lambda p: p.stat().st_mtime)[:предел]:
        try:
            заявка = queue.разобрать(json.loads(файл.read_text(encoding="utf-8")))
        except (queue.RequestRejected, ValueError) as exc:
            итоги.append({"request_id": файл.stem, "status": "rejected",
                          "error": str(exc)})
            queue.записать_атомарно(корень / "results" / файл.name,
                                    итоги[-1])
            файл.unlink()
            continue
        итог = выполнить(заявка, база=корень, dry_run=dry_run)
        queue.записать_атомарно(корень / "results" / файл.name, итог)
        # Заявка уходит из очереди только после записи результата: обратный
        # порядок терял бы операцию при гибели процесса между двумя шагами.
        файл.unlink()
        итоги.append(итог)
    return итоги


def ждать(*, база: Path | None = None, интервал: float = 5.0,
          dry_run: bool = True, циклов: int = 0) -> None:
    """Цикл службы. `циклов=0` — до остановки."""
    сделано = 0
    while циклов == 0 or сделано < циклов:
        обслужить_очередь(база=база, dry_run=dry_run)
        сделано += 1
        if циклов and сделано >= циклов:
            break
        time.sleep(интервал)
