"""Очередь заявок на выпуск: что именно принимает привилегированный исполнитель.

Зачем очередь, а не команда
---------------------------

Активация требует root. Соблазнительное решение — разрешить владельцу один раз
выполнить «любой скрипт по такому-то пути от root». Оно не работает как
граница: кто может писать в этот путь, тот выполняет код от root, а писать в
рабочий каталог может кто угодно из сессии.

Поэтому между непривилегированной стороной и root стоит файл заявки со строгой
схемой. Заявка не может назвать путь, службу, команду или репозиторий. В ней
только идентификаторы, которые исполнитель проверяет по реестру и по GitHub:

* `site_id`   — обязан быть в реестре ячеек и иметь собственный репозиторий;
* `commit`    — 40 шестнадцатеричных знаков, обязан существовать в этом репозитории;
* `digest`    — ожидаемый отпечаток артефакта; исполнитель собирает артефакт сам
                и сверяет, поэтому подложить байты нечем;
* `ci_run`    — прогон, на котором digest получен; проверяется отдельно.

Всё остальное — пути, юниты, порты, учётные записи — исполнитель берёт из
реестра, а не из заявки. Это и есть граница.

Повтор
------

У заявки есть `request_id`. Повторная подача того же идентификатора не заводит
вторую операцию: возвращается состояние первой. Так выглядит обрыв сети со
стороны подающего — он не знает, дошла ли заявка, и обязан иметь право
повторить без последствий.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

#: Каталог очереди. Пишет непривилегированная сторона, читает root-исполнитель.
#: Тот же приём, что у прижившегося lords-deploy-broker: граница проходит по
#: схеме заявки, а не по правам на каталог.
БАЗА = Path(os.environ.get("SITE_CELL_QUEUE", "/var/lib/site-cells"))
ЗАЯВКИ = БАЗА / "requests"
РЕЗУЛЬТАТЫ = БАЗА / "results"
СОСТОЯНИЕ = БАЗА / "state"

ХЕКС40 = re.compile(r"^[0-9a-f]{40}$")
ДАЙДЖЕСТ = re.compile(r"^sha256:[0-9a-f]{64}$")
ИДЕНТ = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
ЗАПРОС_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")

#: Что исполнителю разрешено делать. Список закрытый: «выполнить произвольную
#: операцию» отсутствует как понятие, а не запрещено проверкой.
ОПЕРАЦИИ = ("activate", "update", "deliver", "rollback")

#: Этапы операции. Расширение уже существующей схемы онбординга, не вторая.
ЭТАПЫ = ("received", "validated", "artifact_verified", "candidate_ready",
         "switched", "live_verified", "failed", "rolled_back")


class RequestRejected(Exception):
    """Заявка отвергнута до единой мутации."""


@dataclass
class Заявка:
    request_id: str
    operation: str
    site_id: str
    commit: str
    digest: str
    ci_run: str = ""
    repo: str = ""
    submitted_at: str = ""
    submitted_by: str = ""
    note: str = ""
    stages: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _проверить(значение: str, правило: re.Pattern, поле: str) -> str:
    очищенное = (значение or "").strip()
    if not правило.match(очищенное):
        raise RequestRejected(
            f"{поле}={значение!r} не проходит форму {правило.pattern}. "
            "Форма проверяется до всего остального: значение уходит в аргументы "
            "внешних программ, и единственный надёжный способ не спорить с "
            "оболочкой — не пропускать ничего, что могло бы ей что-то значить")
    return очищенное


def разобрать(сырое: dict[str, Any]) -> Заявка:
    """Проверить форму заявки. Ни одного обращения к диску и сети."""
    if not isinstance(сырое, dict):
        raise RequestRejected("заявка обязана быть объектом JSON")
    лишние = set(сырое) - set(Заявка.__dataclass_fields__)
    if лишние:
        raise RequestRejected(
            f"в заявке неизвестные поля: {sorted(лишние)}. Заявка со свободными "
            "полями перестаёт быть договором: завтра в ней окажется путь")
    операция = (сырое.get("operation") or "").strip()
    if операция not in ОПЕРАЦИИ:
        raise RequestRejected(f"operation={операция!r}; разрешены {list(ОПЕРАЦИИ)}")
    заявка = Заявка(
        request_id=_проверить(сырое.get("request_id", ""), ЗАПРОС_ID, "request_id"),
        operation=операция,
        site_id=_проверить(сырое.get("site_id", ""), ИДЕНТ, "site_id"),
        commit=_проверить(сырое.get("commit", ""), ХЕКС40, "commit"),
        digest=_проверить(сырое.get("digest", ""), ДАЙДЖЕСТ, "digest"),
        ci_run=str(сырое.get("ci_run") or "").strip(),
        repo=str(сырое.get("repo") or "").strip(),
        submitted_at=str(сырое.get("submitted_at") or ""),
        submitted_by=str(сырое.get("submitted_by") or ""),
        note=str(сырое.get("note") or "")[:500],
        stages=list(сырое.get("stages") or []),
    )
    if заявка.ci_run and not заявка.ci_run.isdigit():
        raise RequestRejected(f"ci_run={заявка.ci_run!r} должен быть числом прогона")
    return заявка


def новый_идентификатор(site_id: str, commit: str, *, operation: str = "activate",
                        snapshot: str = "") -> str:
    """Устойчивый идентификатор заявки.

    Выводится из того, ЧТО выкладывается, поэтому повтор той же работы даёт тот
    же идентификатор и не заводит вторую операцию.

    Операция входит в идентификатор обязательно. Без неё обновление данных на
    том же коммите сталкивалось с уже выполненным выпуском кода: заявка
    возвращала `already-finished`, и снимок молча не доезжал.

    Для обновления данных к идентификатору добавляется отпечаток снимка: тот же
    коммит с НОВЫМ снимком — это новая работа, а тот же снимок — повтор,
    который обязан ничего не менять.
    """
    хвост = (snapshot or commit)[:12]
    краткая = {"activate": "code", "update": "code", "deliver": "data",
               "rollback": "back"}.get(operation, operation[:4])
    return f"{site_id}-{краткая}-{хвост}"[:64].lower()


def записать_атомарно(путь: Path, данные: dict[str, Any], *,
                      режим: int = 0o640) -> None:
    """Атомарная запись с явным режимом И группой каталога назначения.

    Двух вещей не хватало по очереди, и каждая поодиночке ломала обратную связь.

    Режим: NamedTemporaryFile создаёт файл 0600, и результат операции оказывался
    нечитаемым для того, кто её подал. Снаружи это молчание — заявка исчезла,
    ответа нет, причину узнать нечем.

    Группа: каталог результатов принадлежит `root:<подающий>`, но новый файл
    получает ПЕРВИЧНУЮ группу процесса, то есть root. Исполнитель работает от
    root, и файл выходил `rw-r----- root:root` — режим правильный, а группа
    такая, что читать его всё равно некому. Поэтому группа берётся у каталога
    назначения явно, а не через надежду на setgid: setgid ставится установщиком
    и может не стоять на каталоге, созданном раньше или руками.

    Смена группы возможна только root. Обычный процесс пишет свои файлы себе и
    в подмене группы не нуждается — отказ здесь не ошибка.
    """
    путь.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=путь.parent, delete=False,
                                     encoding="utf-8") as врем:
        json.dump(данные, врем, ensure_ascii=False, indent=2)
        врем.write("\n")
        временный = Path(врем.name)
    os.chmod(временный, режим)
    try:
        гид = путь.parent.stat().st_gid
        if гид != временный.stat().st_gid:
            os.chown(временный, -1, гид)
    except OSError:
        pass
    os.replace(временный, путь)


def подать(заявка: Заявка, *, база: Path | None = None) -> dict[str, Any]:
    """Положить заявку в очередь. Повтор возвращает состояние первой."""
    корень = база or БАЗА
    очередь = корень / "requests"
    результаты = корень / "results"
    файл = очередь / f"{заявка.request_id}.json"
    готовый = результаты / f"{заявка.request_id}.json"

    if готовый.is_file():
        try:
            итог = json.loads(готовый.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            итог = {"status": "нечитаем"}
        # Повторять нельзя только УСПЕШНУЮ операцию: она уже применена, и второй
        # прогон стал бы повторной выкладкой. Неудачная — наоборот, обязана быть
        # повторяемой: причина отказа устраняется, и заявка подаётся снова. Иначе
        # один сбой запирал бы выпуск этого коммита навсегда.
        if итог.get("status") == "ok":
            return {"status": "already-finished", "request_id": заявка.request_id,
                    "result": итог}
        предыдущий = итог.get("status")
        готовый.unlink(missing_ok=True)
        заявка.stages = [{"stage": "received", "at": заявка.submitted_at,
                          "retry_after": предыдущий}]
        записать_атомарно(файл, заявка.as_dict())
        return {"status": "requeued-after-failure", "request_id": заявка.request_id,
                "previous_status": предыдущий, "path": str(файл)}
    if файл.is_file():
        существующая = json.loads(файл.read_text(encoding="utf-8"))
        if (существующая.get("commit") != заявка.commit
                or существующая.get("operation") != заявка.operation):
            raise RequestRejected(
                f"заявка {заявка.request_id} уже есть и описывает другой выпуск "
                f"({существующая.get('commit', '')[:12]} / {существующая.get('operation')}). "
                "Молча заменить её значило бы потерять идущую операцию")
        return {"status": "already-queued", "request_id": заявка.request_id,
                "request": существующая}

    заявка.stages = [{"stage": "received", "at": заявка.submitted_at}]
    записать_атомарно(файл, заявка.as_dict())
    return {"status": "queued", "request_id": заявка.request_id,
            "path": str(файл), "request": заявка.as_dict()}


def состояние(request_id: str, *, база: Path | None = None) -> dict[str, Any]:
    корень = база or БАЗА
    готовый = корень / "results" / f"{request_id}.json"
    если_в_очереди = корень / "requests" / f"{request_id}.json"
    if готовый.is_file():
        return {"status": "finished", **json.loads(готовый.read_text(encoding="utf-8"))}
    if если_в_очереди.is_file():
        return {"status": "queued", **json.loads(если_в_очереди.read_text(encoding="utf-8"))}
    return {"status": "unknown", "request_id": request_id}


def отметить(заявка_путь: Path, этап: str, детали: dict[str, Any] | None = None) -> None:
    """Записать переход. Журнал живёт вне процесса.

    Восстановление после гибели процесса или перезагрузки хоста возможно только
    если намерение записано до действия, а результат — после. Shell-trap этого
    не даёт: его не будет ни при SIGKILL, ни при перезагрузке.
    """
    if этап not in ЭТАПЫ:
        raise RequestRejected(f"неизвестный этап {этап!r}")
    данные = json.loads(заявка_путь.read_text(encoding="utf-8"))
    данные.setdefault("stages", []).append(
        {"stage": этап, "at": _сейчас(), **(детали or {})})
    записать_атомарно(заявка_путь, данные)


def _сейчас() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def собрать(site_id: str, commit: str, digest: str, *, operation: str = "activate",
            ci_run: str = "", repo: str = "", note: str = "",
            snapshot: str = "") -> Заявка:
    """Заявка из результата проверенной сборки, а не из рук человека."""
    return разобрать({
        "request_id": новый_идентификатор(site_id, commit, operation=operation,
                                          snapshot=snapshot),
        "operation": operation, "site_id": site_id, "commit": commit,
        "digest": digest, "ci_run": ci_run, "repo": repo,
        "submitted_at": _сейчас(),
        "submitted_by": os.environ.get("GITHUB_WORKFLOW") or "manual",
        "note": note,
    })


def случайный_идентификатор() -> str:
    """Для репетиций: заведомо не совпадёт с боевым."""
    return f"rehearsal-{uuid.uuid4().hex[:12]}"
