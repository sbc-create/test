"""Применение credentials к инфраструктуре направления.

Секреты не возвращаются вызывающей стороне — они применяются. Здесь живут две
реализации доставки, выбираемые полем ``kind`` из реестра:

``file_mount``
    Root-owned файлы, которые Docker монтирует read-only. Так уже устроен стенд
    Yami: ``/srv/sites/yummyani-staging/runtime/cdnvideohub`` монтируется в
    ``/run/cdnvideohub``, а entrypoint читает файлы уже внутри процесса.
    Значение не появляется ни в ``compose environment``, ни в ``docker inspect``.

``systemd_credential``
    Root-owned файлы плюс drop-in с ``LoadCredential``. systemd читает файл от
    имени PID 1 и кладёт копию в tmpfs, доступную только этому процессу; в
    окружении, ``systemctl show`` и журнале значения нет.

Порядок применения одинаков для обеих и продиктован требованием отката:

1. снять предыдущее состояние (бэкап файлов) — до единой мутации;
2. проверить права и цель; недоступная цель — отказ, а не «применим как выйдет»;
3. записать значения атомарно (временный файл рядом + ``os.replace``);
4. проверить, что записанное действительно на месте и с нужными правами;
5. только теперь — перезапуск, и только тех unit'ов, которые принадлежат этому
   направлению.

Ошибка на любом шаге возвращает предыдущее состояние файлов. Работающий сайт не
останавливается ради применения: перезапуск идёт после успешной записи, а для
Yami его вообще нет — контейнер читает файл при старте, и решение о рестарте
принимает оператор.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.errors import BlockedTarget
from factory.secret_hub import SECRET_FIELDS
from factory.secret_hub.crypto import Secret
from factory.secret_hub.registry import Consumer, Portfolio

#: Куда складываются копии прежних файлов потребителя перед перезаписью.
BACKUP_ROOT = Path("/var/lib/site-factory-secret-hub/consumer-backups")

#: Шаблон drop-in'а. Значение секрета сюда не попадает: только путь к файлу,
#: который прочитает systemd от имени PID 1.
DROPIN_TEMPLATE = """# Сгенерировано Secret Hub. Правки будут перезаписаны.
#
# Значения секретов здесь отсутствуют: systemd читает root-owned файлы сам и
# кладёт копии в tmpfs процесса ($CREDENTIALS_DIRECTORY). В окружении unit'а,
# в `systemctl show` и в журнале значений нет.
#
# Передаются ИМЕНА credentials, а не пути к ним. Специфер %d («каталог
# credentials») появился в systemd 250, а Ubuntu 22.04 везёт 249: там строка
# не разворачивается и остаётся literal-ом «%d/...», после чего потребитель
# падает на «файл не найден». Переменную CREDENTIALS_DIRECTORY systemd
# выставляет сам с той же версии, что и сам LoadCredential, поэтому путь
# собирает потребитель:
#
#     "$CREDENTIALS_DIRECTORY/$CDNVIDEOHUB_API_TOKEN_CREDENTIAL"
#
[Service]
LoadCredential={api_credential}:{api_path}
LoadCredential={publisher_credential}:{publisher_path}
Environment=CDNVIDEOHUB_API_TOKEN_CREDENTIAL={api_credential}
Environment=CDNVIDEOHUB_PUBLISHER_ID_CREDENTIAL={publisher_credential}
"""


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class ConsumerResult:
    consumer_id: str
    status: str
    detail: str = ""
    restarted: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "consumer": self.consumer_id,
            "status": self.status,
            "detail": self.detail,
            "restarted": list(self.restarted),
        }


@dataclass
class ApplyReport:
    portfolio: str
    version: int | None
    results: list[ConsumerResult] = field(default_factory=list)
    rolled_back: bool = False
    #: Почему откат не удался, если не удался. Молчаливо неудавшийся откат —
    #: худший из возможных исходов: направление остаётся в состоянии, которое
    #: никто не описывал, и отчёт об этом обязан говорить прямо.
    rollback_problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(r.status == "applied" for r in self.results)

    @property
    def reason(self) -> str:
        """Почему направление не применилось — словами, без секретов.

        Раньше причина оставалась в `consumers[].detail`, а наружу уходил
        отчёт без единого поля `reason`. Панель показывала «неизвестная
        причина» при том, что причина была известна и записана рядом.
        """
        if self.ok:
            return ""
        failed = [r for r in self.results if r.status != "applied"]
        if not failed:
            return "ни один потребитель не был обработан"
        parts = []
        for result in failed:
            label = {"blocked": "цель недоступна",
                     "failed": "запись не удалась"}.get(result.status, result.status)
            detail = result.detail.strip()
            parts.append(f"{result.consumer_id}: {label}" + (f" — {detail}" if detail else ""))
        return "; ".join(parts)

    def as_dict(self) -> dict:
        return {
            "portfolio": self.portfolio,
            "version": self.version,
            "ok": self.ok,
            "reason": self.reason,
            "rolled_back": self.rolled_back,
            "rollback_problems": list(self.rollback_problems),
            "consumers": [r.as_dict() for r in self.results],
        }


class Rollback:
    """Снимок файлов потребителя и способ вернуть их на место.

    Снимается до первой мутации. Хранит и «файла не было» — иначе откат после
    первой в жизни установки оставил бы после себя файл, которого раньше не
    существовало.
    """

    def __init__(self, backup_dir: Path) -> None:
        self.backup_dir = backup_dir
        self._entries: list[tuple[Path, Path | None, int | None]] = []

    def capture(self, path: Path) -> None:
        if not path.exists():
            self._entries.append((path, None, None))
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.backup_dir, 0o700)
        copy = self.backup_dir / path.name
        shutil.copy2(path, copy)
        os.chmod(copy, 0o600)
        self._entries.append((path, copy, stat.S_IMODE(path.stat().st_mode)))

    def restore(self) -> None:
        """Возвращает прежние файлы поверх нынешних.

        Через временный файл и ``os.replace``, а не ``shutil.copy2`` поверх
        цели: файлы секретов лежат с правами 0400, и copy2 открывает цель на
        запись — то есть падает с ``PermissionError`` ровно на тех файлах, ради
        которых откат и существует. Переименование — операция над каталогом, и
        права самого файла ей не мешают.
        """
        for path, copy, mode in reversed(self._entries):
            if copy is None:
                path.unlink(missing_ok=True)
                continue
            tmp = path.with_name(f".{path.name}.restore")
            tmp.unlink(missing_ok=True)
            shutil.copy2(copy, tmp)
            os.chmod(tmp, mode if mode is not None else 0o600)
            os.replace(tmp, path)

    @property
    def entries(self) -> tuple[Path, ...]:
        return tuple(p for p, _, _ in self._entries)


def _write_atomically(path: Path, value: str, mode: int) -> None:
    """Запись через временный файл рядом и ``os.replace``.

    Права ставятся на временный файл до наполнения: иначе между созданием и
    ``chmod`` существует окно, в котором секрет читается миром. ``os.replace``
    внутри одной файловой системы атомарен, поэтому потребитель видит либо
    прежнее содержимое, либо новое — но не половину.
    """
    tmp = path.with_name(f".{path.name}.tmp")
    if tmp.exists():
        tmp.unlink()
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    try:
        # Перевод строки не добавляется: потребители Yami читают файл через
        # `tr -d '\r\n'`, но systemd отдаёт credential байт в байт, и лишний
        # символ стал бы частью токена.
        os.write(fd, value.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    # Каталог тоже синхронизируется: без этого переименование может не пережить
    # внезапную перезагрузку, и потребитель останется без файла вовсе.
    dir_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _ensure_directory(consumer: Consumer) -> None:
    directory = consumer.directory
    directory.mkdir(parents=True, exist_ok=True, mode=consumer.directory_mode)
    os.chmod(directory, consumer.directory_mode)
    if os.geteuid() == 0:
        shutil.chown(directory, user=consumer.owner, group=consumer.group)


def _probe(path: Path) -> tuple[str, os.stat_result | None]:
    """Состояние пути: ``present`` / ``absent`` / ``unmeasured``.

    ``Path.exists()`` здесь не годится: он пропускает наружу ``PermissionError``
    (``EACCES`` не входит в список игнорируемых ошибок), и обычный `status`,
    запущенный не-root'ом, падал на каталоге ``/etc/site-factory/secrets``,
    закрытом ровно так, как и задумано. Закрытый каталог — это работающая
    защита, а не авария: честный ответ «не измерено», а не трассировка и не
    ложное «файла нет».
    """
    try:
        return "present", path.stat()
    except FileNotFoundError:
        return "absent", None
    except NotADirectoryError:
        # На месте одного из предков лежит файл. Путь не существует и не может
        # существовать — это «нет», а не «не измерено». Python по той же
        # причине считает ENOTDIR и ENOENT одинаково в `Path.exists()`.
        return "absent", None
    except PermissionError:
        return "unmeasured", None
    except OSError:
        return "unmeasured", None


def _creatable(directory: Path) -> str | None:
    """Можно ли создать каталог. Возвращает причину отказа или ``None``.

    Проверяется не существование родителя, а возможность его создать:
    ``_ensure_directory`` делает ``mkdir(parents=True)`` и построит всю
    недостающую цепочку. Прежняя проверка требовала, чтобы непосредственный
    родитель уже существовал, — она была строже действия, которое охраняла, и
    на этом встали все три потребителя Lords. Их каталоги
    ``/etc/site-factory/secrets/lords/lords-0N`` не создаёт никто: установщик
    делает только ``/etc/site-factory/secrets``. Yami работал лишь потому, что
    его родительский каталог существует по другой причине.

    Настоящее препятствие — не отсутствие каталога, а файл на месте одного из
    предков: тогда ``mkdir`` не пройдёт никогда.
    """
    for ancestor in [directory, *directory.parents]:
        state, info = _probe(ancestor)
        if state == "unmeasured":
            # Закрытый каталог измерить нельзя; root, от которого идёт
            # применение, измерит. Блокировать по неизмеренному нельзя.
            return None
        if state == "present":
            if info is not None and not stat.S_ISDIR(info.st_mode):
                return f"{ancestor} существует и не является каталогом"
            return None
    return None


def check_target(consumer: Consumer) -> list[str]:
    """Проблемы цели до применения. Пустой список — цель пригодна."""
    problems: list[str] = []
    blocked = _creatable(consumer.directory)
    if blocked:
        problems.append(blocked)
    if consumer.kind == "systemd_credential":
        if not consumer.unit:
            problems.append("не указан unit")
        elif not _unit_exists(consumer.unit):
            problems.append(f"unit {consumer.unit} не найден в systemd")
    if consumer.kind == "file_mount" and consumer.compose_file:
        compose_state, _ = _probe(consumer.compose_file)
        if compose_state == "absent":
            problems.append(f"compose-файл {consumer.compose_file} не найден")
        elif compose_state == "present" and consumer.expect_mount_target:
            try:
                text = consumer.compose_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = None
            if text is not None and consumer.expect_mount_target not in text:
                problems.append(
                    f"в {consumer.compose_file} нет монтирования {consumer.expect_mount_target}: "
                    "записанный файл никуда не попадёт"
                )
    return problems


def _unit_exists(unit: str) -> bool:
    try:
        proc = subprocess.run(
            ["systemctl", "list-unit-files", "--no-legend", unit],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode == 0 and proc.stdout.strip():
        return True
    return Path(f"/etc/systemd/system/{unit}").exists()


def verify_written(consumer: Consumer) -> list[str]:
    """Проверка после записи: файл на месте, права те, владелец root."""
    problems: list[str] = []
    for name in SECRET_FIELDS:
        path = consumer.path_for(name)
        state, info = _probe(path)
        if state == "absent":
            problems.append(f"{path} не создан")
            continue
        if info is None:
            problems.append(f"{path}: состояние не измерено — каталог закрыт")
            continue
        mode = stat.S_IMODE(info.st_mode)
        if mode != consumer.file_mode:
            problems.append(f"{path}: права {mode:04o}, ожидается {consumer.file_mode:04o}")
        if mode & 0o077:
            problems.append(f"{path} доступен группе или миру")
        if os.geteuid() == 0 and info.st_uid != 0:
            problems.append(f"{path}: владелец uid={info.st_uid}, ожидается root")
        if info.st_size == 0:
            problems.append(f"{path} пуст")
    return problems


def _write_dropin(consumer: Consumer, rollback: Rollback) -> None:
    if consumer.kind != "systemd_credential" or not consumer.dropin:
        return
    rollback.capture(consumer.dropin)
    consumer.dropin.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    content = DROPIN_TEMPLATE.format(
        api_credential=consumer.credential_names["api_token"],
        api_path=consumer.path_for("api_token"),
        publisher_credential=consumer.credential_names["publisher_id"],
        publisher_path=consumer.path_for("publisher_id"),
    )
    _write_atomically(consumer.dropin, content, 0o644)


def _reload_unit(consumer: Consumer) -> tuple[str, ...]:
    """Перезапуск строго одного unit'а этого потребителя.

    Ни ``daemon-reload`` всей системы без нужды, ни ``restart`` по шаблону:
    «Yami не должен затрагивать Lords» держится тем, что имя unit'а берётся из
    записи потребителя и никак иначе.
    """
    if not consumer.reload.restarts_unit or not consumer.unit:
        return ()
    subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=60)
    subprocess.run(["systemctl", "restart", consumer.unit], check=True, timeout=120)
    return (consumer.unit,)


def apply_consumer(consumer: Consumer, values: dict[str, Secret], *,
                   backup_root: Path | None = None, restart: bool = True) -> ConsumerResult:
    """Применяет значения к одному потребителю с откатом при любой ошибке."""
    result, _ = _apply_consumer(consumer, values, backup_root=backup_root, restart=restart)
    return result


def _apply_consumer(consumer: Consumer, values: dict[str, Secret], *,
                    backup_root: Path | None, restart: bool) -> tuple[ConsumerResult, Rollback]:
    """То же, но возвращает и снимок.

    Снимок нужен уровню направления: если следующий потребитель откажет, вернуть
    надо и этого, а вернуть его можно только тем снимком, который был снят перед
    его перезаписью. Пустой `Rollback`, созданный «на всякий случай», не вернул
    бы ничего — и это была бы худшая разновидность отката: тот, который
    отчитывается об успехе, ничего не сделав.
    """
    problems = check_target(consumer)
    root = backup_root or BACKUP_ROOT
    rollback = Rollback(root / consumer.id / _now_tag())
    if problems:
        return ConsumerResult(consumer.id, "blocked", "; ".join(problems)), rollback

    try:
        _ensure_directory(consumer)
        for name in SECRET_FIELDS:
            rollback.capture(consumer.path_for(name))
        for name in SECRET_FIELDS:
            _write_atomically(consumer.path_for(name), values[name].reveal(), consumer.file_mode)
        if os.geteuid() == 0:
            for name in SECRET_FIELDS:
                shutil.chown(consumer.path_for(name), user=consumer.owner, group=consumer.group)
        _write_dropin(consumer, rollback)

        written_problems = verify_written(consumer)
        if written_problems:
            rollback.restore()
            return ConsumerResult(consumer.id, "failed",
                                  "после записи: " + "; ".join(written_problems)), rollback

        restarted = _reload_unit(consumer) if restart else ()
    except Exception as exc:
        # Текст исключения не содержит значений: сюда попадают только пути и
        # классы ошибок. Значения в этот блок не передаются вовсе.
        rollback.restore()
        return ConsumerResult(
            consumer.id, "failed",
            f"{exc.__class__.__name__}: {exc}. Прежнее состояние возвращено.",
        ), rollback
    return ConsumerResult(consumer.id, "applied", "", restarted), rollback


def apply_portfolio(portfolio: Portfolio, values: dict[str, Secret], *, version: int | None,
                    backup_root: Path | None = None, restart: bool = True) -> ApplyReport:
    """Применяет секрет ко всем потребителям направления.

    Направления изолированы структурно: функция получает один ``Portfolio`` и
    перебирает только его потребителей. Достать отсюда потребителя чужого
    направления невозможно — его тут просто нет.
    """
    report = ApplyReport(portfolio.id, version)
    if portfolio.blocked_target is not None:
        raise BlockedTarget(
            f"Направление «{portfolio.id}»: {portfolio.blocked_target.reason}",
            field=portfolio.id,
            required_input=portfolio.blocked_target.required_input,
            blocks_stage="STAGING_DEPLOY",
        )
    if not portfolio.consumers:
        raise BlockedTarget(
            f"У направления «{portfolio.id}» нет ни одного потребителя: применять некуда.",
            field=portfolio.id,
            required_input="Запись consumers[] в config/secret-hub.json",
            blocks_stage="STAGING_DEPLOY",
        )

    applied: list[tuple[Consumer, Rollback]] = []
    for consumer in portfolio.consumers:
        result, rollback = _apply_consumer(consumer, values, backup_root=backup_root,
                                           restart=restart)
        report.results.append(result)
        if result.status != "applied":
            # Частично применённое направление хуже неприменённого: половина
            # сайтов работала бы на новом токене, половина на старом, и это
            # состояние никак не называется. Возвращаем всё направление назад.
            report.rolled_back, report.rollback_problems = _rollback_applied(
                applied, restart=restart)
            return report
        applied.append((consumer, rollback))
    return report


def _rollback_applied(applied: list[tuple[Consumer, Rollback]], *,
                      restart: bool) -> tuple[bool, list[str]]:
    """Возврат уже применённых потребителей после отказа на следующем.

    Возвращает предыдущие файлы из их собственных снимков — они лежат в каталоге
    бэкапа каждого потребителя и не удаляются. Причина неудачи не проглатывается:
    «откат не сработал» обязано быть видно, а не выводиться из одинокого `False`.
    """
    problems: list[str] = []
    for consumer, rollback in reversed(applied):
        try:
            rollback.restore()
            if restart:
                _reload_unit(consumer)
        except Exception as exc:
            problems.append(f"{consumer.id}: {exc.__class__.__name__}: {exc}")
    return not problems, problems


def describe(portfolio: Portfolio) -> list[dict]:
    """Состояние целей направления для `status` — без единой мутации."""
    out: list[dict] = []
    for consumer in portfolio.consumers:
        problems = check_target(consumer)
        files: list[dict] = []
        for name in SECRET_FIELDS:
            path = consumer.path_for(name)
            state, info = _probe(path)
            entry: dict = {
                "field": name,
                "path": str(path),
                # `present` — троичное: None означает «каталог закрыт для этой
                # учётной записи», а не «файла нет». Разница существенная:
                # первое — норма, второе — повод чинить.
                "present": True if state == "present" else (False if state == "absent" else None),
                "measured": state != "unmeasured",
            }
            if info is not None:
                entry["mode"] = format(stat.S_IMODE(info.st_mode), "04o")
                entry["owner_is_root"] = info.st_uid == 0
                entry["empty"] = info.st_size == 0
            files.append(entry)
        out.append({
            "consumer": consumer.id,
            "kind": consumer.kind,
            "title": consumer.title,
            "unit": consumer.unit,
            "target_ok": not problems,
            "problems": problems,
            "problem": "; ".join(problems),
            "files": files,
        })
    return out
