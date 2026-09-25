"""Привилегированные операции: их исполняет root-овый код, а не скрипт из репы.

Почему не `deploy/activate.sh`
-----------------------------

Исполнитель умел запускать сценарий активации из репозитория сайта. Репозиторий
доступен на запись обычной учётной записи, а исполнитель работает от root — то
есть право писать в репозиторий превращалось в право выполнить что угодно от
root. Проверки коммита, чистого дерева и CI это не закрывают: CI описан тем же
репозиторием, и владелец репозитория владеет и проверкой.

Поэтому привилегированная сторона не исполняет ничего, что пришло из репозитория.
Репозиторий поставляет ДАННЫЕ: проверенный артефакт и объявления в
`config/site.json`. Шаги, шаблон юнита и порядок переключения живут здесь, в
root-овой копии пакета, и меняются только переустановкой исполнителя.

Что разрешено делать
--------------------

Ровно перечисленное в `ОПЕРАЦИИ`. «Выполнить команду», «запустить скрипт» и
«взять путь из заявки» отсутствуют как понятия, а не запрещены проверкой.
"""
from __future__ import annotations

import contextlib
import json
import os
import pwd
import shutil
import socket
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.cell import runtime

#: Закрытый набор. Расширяется только правкой этого файла и переустановкой.
ОПЕРАЦИИ = ("prepare", "install_release", "stage_snapshot", "warm_up",
            "switch_route", "promote", "promote_snapshot", "verify",
            "rollback")

#: Куда разрешено раскладывать сайты. Любой путь вне этого корня — отказ.
КОРЕНЬ_САЙТОВ = Path("/srv")


class PrivilegedRefused(Exception):
    """Операция отклонена. Ничего не изменено."""


@dataclass
class Площадка:
    """Пути сайта. Выводятся из реестра, а не принимаются аргументом."""

    site_id: str
    account: str
    root: Path
    app: Path
    data: Path
    unit: str
    previous_unit: str | None
    port: int

    @property
    def releases(self) -> Path:
        """Каталог выпусков. Каждый распакованный артефакт — отдельная папка.

        Кандидат и действующая версия обязаны исполнять РАЗНЫЙ код
        одновременно. Один каталог `app` на двоих означал бы, что распаковка
        нового выпуска меняет код действующей службы под ней.
        """
        return self.root / "releases"

    @property
    def current(self) -> Path:
        """Ссылка на выпуск, который обслуживает посетителей."""
        return self.root / "current"

    @property
    def candidate(self) -> Path:
        """Ссылка на прогреваемый выпуск."""
        return self.root / "candidate"

    @property
    def data_candidate(self) -> Path:
        """Хранилище данных кандидата.

        Отдельное, потому что прогрев на новом снимке обязан идти, пока
        работающий процесс отдаёт прежний: один каталог на двоих означал бы,
        что новый снимок виден действующей версии сразу, и прогрев ничего бы
        не значил.
        """
        return self.root / "data-candidate"

    @property
    def candidate_unit(self) -> str:
        return f"{self.unit.removesuffix('.service')}-candidate.service"

    @property
    def candidate_port(self) -> int:
        return порт_кандидата(self.port)

    @classmethod
    def из_реестра(cls, site_id: str, *, path: Path | None = None) -> Площадка:
        р = runtime.размещение(site_id, path=path)
        if not р.account or not р.port:
            raise PrivilegedRefused(
                f"{site_id}: в реестре нет учётной записи или порта — "
                "исполнять по такому описанию нельзя")
        корень = (КОРЕНЬ_САЙТОВ / р.account).resolve()
        if not str(корень).startswith(str(КОРЕНЬ_САЙТОВ) + os.sep):
            raise PrivilegedRefused(
                f"{site_id}: каталог {корень} вне {КОРЕНЬ_САЙТОВ}")
        return cls(site_id=site_id, account=р.account, root=корень,
                   app=корень / "app", data=корень / "data",
                   unit=р.unit or f"nova-{р.account}.service",
                   previous_unit=р.previous_unit, port=int(р.port))


def _нужен_root() -> None:
    if os.geteuid() != 0:
        raise PrivilegedRefused("операция требует root")


def безопасные_члены(архив: tarfile.TarFile, назначение: Path):
    """Члены архива, которые разрешено распаковывать.

    Проверяется каждое имя: `..`, абсолютный путь и символическая ссылка наружу
    дают выход за каталог назначения. Один такой член превращает распаковку
    артефакта в запись куда угодно от root.
    """
    корень = назначение.resolve()
    for член in архив.getmembers():
        цель = (корень / член.name).resolve()
        if not str(цель).startswith(str(корень) + os.sep):
            raise PrivilegedRefused(
                f"артефакт содержит путь за пределами назначения: {член.name!r}")
        if член.issym() or член.islnk():
            связь = (цель.parent / член.linkname).resolve()
            if not str(связь).startswith(str(корень) + os.sep):
                raise PrivilegedRefused(
                    f"ссылка {член.name!r} ведёт наружу: {член.linkname!r}")
        if not (член.isfile() or член.isdir() or член.issym()):
            raise PrivilegedRefused(
                f"в артефакте недопустимый тип записи: {член.name!r}")
        yield член


def prepare(site_id: str, *, dry_run: bool = True) -> dict[str, Any]:
    """Учётная запись и каталоги. Повтор ничего не ломает."""
    п = Площадка.из_реестра(site_id)
    шаги = []
    try:
        pwd.getpwnam(п.account)
        есть = True
    except KeyError:
        есть = False
    if not есть:
        шаги.append(f"useradd --system {п.account}")
        if not dry_run:
            _нужен_root()
            subprocess.run(["useradd", "--system", "--home", str(п.root),
                            "--shell", "/usr/sbin/nologin", п.account], check=True)
    for каталог in (п.root, п.app, п.data):
        шаги.append(f"каталог {каталог}")
        if not dry_run:
            _нужен_root()
            каталог.mkdir(parents=True, exist_ok=True)
            shutil.chown(каталог, п.account, п.account)
            каталог.chmod(0o755)
    return {"operation": "prepare", "site_id": site_id, "dry_run": dry_run,
            "account_existed": есть, "steps": шаги}


#: Настройка МЕСТА: в артефакте её нет намеренно, а без неё витрина не стартует.
#:
#: `config/player.json` содержит publisher_id витрины, поэтому сборщик исключает
#: его явно (`SKIP_FILES`), а `run.py` отказывается стартовать, если сайт объявил
#: ожидаемый publisher_id. Первый настоящий выпуск из-за этого развернулся, но
#: кандидат не поднялся: «нет config/player.json: плеер без publisher_id не
#: заработает». Это не ошибка сборщика и не ошибка витрины — это настройка места,
#: и переносить её обязан тот, кто ставит выпуск.
ФАЙЛ_ПЛЕЕРА = "config/player.json"

#: Каталог производителя, где лежит plеер каждой витрины. Нужен для ПЕРВОГО
#: выпуска, когда действующего ещё нет и переносить неоткуда.
#:
#: Подмену это не открывает: сайт сам сверяет publisher_id из этого файла с
#: `publisher_id_expected`, а тот приходит в артефакте, чей digest уже проверен
#: по прогону CI. Не совпало — кандидат не проходит проверку готовности и
#: трафик не получает.
ПЛЕЕР_ПРОИЗВОДИТЕЛЯ = Path("/srv/lords/.frontend")


def _плеер_обязателен(выпуск: Path) -> bool:
    """Требует ли витрина файла плеера.

    У витрин Yummy воспроизведением занимается верхний поток Next.js, своего
    `player.json` у них нет и не должно быть. Требовать его со всех значило бы
    заваливать исправную конфигурацию, поэтому вопрос задаётся конфигурации
    САМОЙ ВИТРИНЫ, а не семейству по имени.
    """
    конфиг = выпуск / "config" / "site.json"
    if not конфиг.is_file():
        return False
    try:
        данные = json.loads(конфиг.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(str(данные.get("publisher_id_expected") or "").strip())


def _перенести_локальную_настройку(выпуск: Path, п: Площадка) -> list[str]:
    """Взять настройку места в новый выпуск.

    Источники строго перечислены и все — root-side константы: действующий
    выпуск площадки, её рабочий каталог, каталог производителя. Ни одного пути
    из заявки или из манифеста репозитория: иначе «перенести настройку»
    означало бы «прочитать любой файл от root и положить его на сайт».
    """
    if not _плеер_обязателен(выпуск):
        return []
    цель = выпуск / ФАЙЛ_ПЛЕЕРА
    if цель.exists():
        return []
    источники = [п.current / ФАЙЛ_ПЛЕЕРА, п.app / ФАЙЛ_ПЛЕЕРА,
                 ПЛЕЕР_ПРОИЗВОДИТЕЛЯ / f"player-{п.site_id}.json"]
    for откуда in источники:
        # Ссылку не берём: она увела бы за пределы перечисленных источников.
        if not откуда.is_file() or откуда.is_symlink():
            continue
        цель.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(откуда, цель)
        shutil.chown(цель, п.account, п.account)
        os.chmod(цель, 0o600)
        return [ФАЙЛ_ПЛЕЕРА]
    raise PrivilegedRefused(
        f"{п.site_id}: витрина объявляет publisher_id, но {ФАЙЛ_ПЛЕЕРА} не найден "
        f"ни в действующем выпуске, ни у производителя. Без него витрина не "
        "стартует — выкладывать нечего")


def install_release(site_id: str, артефакт: Path, digest: str, *,
                    commit: str = "", dry_run: bool = True,
                    path: Path | None = None) -> dict[str, Any]:
    """Распаковать проверенный артефакт в ОТДЕЛЬНЫЙ выпуск.

    Не поверх работающего кода: действующая служба продолжает исполнять свой
    выпуск, а кандидат получает свой. Ссылка `candidate` переводится на него —
    ссылка, а не копия, потому что подмена ссылки атомарна.
    """
    import hashlib

    п = Площадка.из_реестра(site_id, path=path)
    артефакт = Path(артефакт)
    if not артефакт.is_file():
        raise PrivilegedRefused(f"артефакта нет: {артефакт}")
    факт = "sha256:" + hashlib.sha256(артефакт.read_bytes()).hexdigest()
    if факт != digest:
        raise PrivilegedRefused(
            f"digest артефакта {факт} не совпал с заявленным {digest}")

    имя = (commit or факт.split(":")[1])[:12]
    выпуск = п.releases / имя
    if dry_run:
        with tarfile.open(артефакт) as tf:
            имена = [ч.name for ч in безопасные_члены(tf, выпуск)]
        return {"operation": "install_release", "site_id": site_id, "dry_run": True,
                "digest": факт, "release": str(выпуск), "members": len(имена)}

    _нужен_root()
    временный = п.releases / f".{имя}.new"
    if временный.exists():
        shutil.rmtree(временный)
    временный.mkdir(parents=True)
    with tarfile.open(артефакт) as tf:
        tf.extractall(временный, members=безопасные_члены(tf, временный))
    for путь in временный.rglob("*"):
        shutil.chown(путь, п.account, п.account)
    shutil.chown(временный, п.account, п.account)
    перенесено = _перенести_локальную_настройку(временный, п)
    происхождение = _записать_происхождение(
        временный, site_id=site_id, commit=commit, digest=факт, account=п.account)
    if выпуск.exists():
        shutil.rmtree(выпуск)
    временный.rename(выпуск)

    # Ссылка подменяется через os.replace: окна без ссылки не возникает.
    врем_ссылка = п.root / ".candidate.new"
    if врем_ссылка.exists() or врем_ссылка.is_symlink():
        врем_ссылка.unlink()
    врем_ссылка.symlink_to(выпуск)
    os.replace(врем_ссылка, п.candidate)
    return {"operation": "install_release", "site_id": site_id, "dry_run": False,
            "digest": факт, "release": str(выпуск), "candidate_link": str(п.candidate),
            "local_config": перенесено, "provenance": происхождение}


#: Имя файла происхождения внутри каталога выпуска. Оно же читают затворы
#: активации соседних витрин, поэтому меняться не должно.
ФАЙЛ_ПРОИСХОЖДЕНИЯ = "release-manifest.json"
ФАЙЛ_ПРОИСХОЖДЕНИЯ_ЗАПАСНОЙ = "release-installed.json"


def _записать_происхождение(выпуск: Path, *, site_id: str, commit: str,
                            digest: str, account: str) -> dict[str, Any]:
    """Положить рядом с кодом ответ на вопрос «откуда этот выпуск».

    Без этого файла происхождение выпуска знает только очередь: каталог
    `releases/<commit12>` называет двенадцать знаков коммита и больше ничего —
    ни прогона CI, ни digest, ни времени установки. Проверить постфактум, что
    исполняемый выпуск пришёл штатным путём, можно было только сверкой с
    результатами в /var/lib/site-cells, а они живут отдельно от сайта и могут
    быть недоступны тому, кто смотрит на сайт.

    Отдельная причина — затворы активации. Подтверждать выпуск по заголовку
    `X-Site-Factory-Build-Id` нельзя там, где build_id берётся из манифеста
    ЗАКРЕПЛЁННОГО шаблона: такое значение одинаково у всех выпусков витрины и
    даже у соседей семейства, то есть не различает то, что должно различать.
    Здесь лежит метка именно этого выпуска.

    Файл пишется ВНУТРЬ каталога выпуска и потому не входит в артефакт: digest
    артефакта от него не меняется. Если артефакт уже содержит файл с таким
    именем, он не затирается — своё уходит под запасное имя.
    """
    import json as _json
    from datetime import datetime, timezone

    живой = ""
    манифест_шаблона = выпуск / "config" / "template-manifest.json"
    if манифест_шаблона.is_file():
        try:
            живой = str(_json.loads(манифест_шаблона.read_text(encoding="utf-8"))
                        .get("build_id") or "")
        except (OSError, ValueError):
            живой = ""

    точка = ""
    конфиг = выпуск / "config" / "site.json"
    if конфиг.is_file():
        try:
            точка = str(_json.loads(конфиг.read_text(encoding="utf-8"))
                        .get("entrypoint") or "")
        except (OSError, ValueError):
            точка = ""

    запись = {
        "schema_version": 1,
        "site_id": site_id,
        "commit": commit,
        "digest": digest,
        "release": выпуск.name,
        # Метка, которую витрина объявит в ответах. Берётся из манифеста
        # ЭТОГО дерева, а не собирается по правилу: правило может разойтись
        # со сборщиком, а манифест — то, что рантайм действительно прочитает.
        "live_build_id": живой,
        "entrypoint": точка,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "installed_by": "cell-executor",
    }
    имя = (ФАЙЛ_ПРОИСХОЖДЕНИЯ if not (выпуск / ФАЙЛ_ПРОИСХОЖДЕНИЯ).exists()
           else ФАЙЛ_ПРОИСХОЖДЕНИЯ_ЗАПАСНОЙ)
    файл = выпуск / имя
    файл.write_text(_json.dumps(запись, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    try:
        shutil.chown(файл, account, account)
    except (LookupError, PermissionError):
        pass
    return {"file": имя, "live_build_id": живой, "entrypoint": точка}


def _каталог_юнитов() -> Path:
    return Path(os.environ.get("SITE_UNIT_DIR", "/etc/systemd/system"))


def _дропин_прежнего(п: Площадка) -> Path:
    return _каталог_юнитов() / f"{п.previous_unit}.d" / "cell-port-owner.conf"


def погасить_прежнюю(п: Площадка) -> list[str]:
    """Освободить основной порт от прежней службы.

    Новый юнит слушает ТОТ ЖЕ порт. Пока прежняя служба жива, она держит сокет,
    а новая либо не встаёт, либо отвечает второй — и повышение получает старый
    build-id при честном 200. Ровно это и случилось на lords-01: на порту 9110
    оказались два процесса, приёмка увидела `20260921T134330Z-515fcf0-cardfix`
    вместо `c323e1822308-lords-01` и откатилась.

    Момент выбран не случайно: к повышению трафик уже на кандидате, и на
    основном порту никого нет — остановка никому не видна.

    Drop-in `RefuseManualStart` нужен потому, что конвейеры содержимого зовут
    `systemctl restart` по своему расписанию: без него прежняя служба вернулась
    бы на порт через несколько минут после успешного выпуска.
    """
    if not п.previous_unit:
        return []
    шаги = [f"stop {п.previous_unit}", f"disable {п.previous_unit}"]
    _systemctl("stop", п.previous_unit, проверять=False)
    _systemctl("disable", п.previous_unit, проверять=False)
    дропин = _дропин_прежнего(п)
    дропин.parent.mkdir(parents=True, exist_ok=True)
    дропин.write_text(ЗАЩИТА_ШАБЛОН.format(port=п.port, account=п.account),
                      encoding="utf-8")
    _systemctl("daemon-reload")
    шаги.append(f"{дропин.name}: RefuseManualStart")
    return шаги


def вернуть_прежнюю(п: Площадка, *, предел: int) -> dict[str, Any]:
    """Поднять прежнюю службу обратно — откат после погашения.

    Без этого откат вернул бы маршрут на порт, где уже никого нет: прежнюю
    службу остановили, новая не прошла приёмку. Поэтому сначала она отвечает,
    и только потом трафик идёт обратно.
    """
    if not п.previous_unit:
        return {"restored": False, "reason": "прежней службы нет"}
    дропин = _дропин_прежнего(п)
    if дропин.exists():
        дропин.unlink()
        with contextlib.suppress(OSError):
            дропин.parent.rmdir()
    _systemctl("daemon-reload")
    _systemctl("enable", п.previous_unit, проверять=False)
    _systemctl("start", п.previous_unit, проверять=False)
    состояние = готов(п.port, предел=предел,
                      жив=lambda: _systemctl("is-active", "--quiet",
                                             п.previous_unit,
                                             проверять=False).returncode == 0)
    return {"restored": True, "unit": п.previous_unit, "ready": состояние}


def promote(site_id: str, *, dry_run: bool = True, предел: int = 600,
            ожидаемый_build: str = "", path: Path | None = None) -> dict[str, Any]:
    """Перевести основную службу на выпуск кандидата и вернуть ей трафик.

    Делается ПОСЛЕ того, как кандидат принял трафик: основная служба в этот
    момент никого не обслуживает, и её перезапуск ничего не стоит. Конечное
    состояние всегда одно — трафик на основном порту, — иначе следующий выпуск
    не знал бы, откуда начинать.
    """
    п = Площадка.из_реестра(site_id, path=path)
    шаги = ["current -> выпуск кандидата", f"restart {п.unit}",
            f"ждать готовности {п.port}", f"вернуть маршрут на {п.port}",
            f"stop {п.candidate_unit}"]
    if dry_run:
        return {"operation": "promote", "site_id": site_id, "dry_run": True,
                "steps": шаги}

    _нужен_root()
    цель = п.candidate.resolve()
    врем = п.root / ".current.new"
    if врем.exists() or врем.is_symlink():
        врем.unlink()
    врем.symlink_to(цель)
    os.replace(врем, п.current)

    # Юнит основной службы переписывается ЗДЕСЬ, из шаблона исполнителя.
    # Без этого перезапуск поднимал бы прежний ExecStart: служба стартовала бы
    # успешно и отвечала бы старым выпуском, а приёмка объявляла бы расхождение
    # версий, не назвав причины.
    каталог = Path(os.environ.get("SITE_UNIT_DIR", "/etc/systemd/system"))
    (каталог / п.unit).write_text(
        ЮНИТ_ШАБЛОН.format(domain=runtime.размещение(site_id, path=path).domain,
                           site_id=site_id, account=п.account, link=п.current,
                           data=п.data, port=п.port), encoding="utf-8")
    шаги_прежней = погасить_прежнюю(п)
    _systemctl("daemon-reload")
    _systemctl("restart", п.unit)
    состояние = готов(п.port, предел=предел,
                      жив=lambda: _systemctl("is-active", "--quiet", п.unit,
                                             проверять=False).returncode == 0)
    итог = {"operation": "promote", "site_id": site_id, "dry_run": False,
            "steps": шаги + шаги_прежней, "ready": состояние, "release": str(цель)}
    if not состояние.get("ready"):
        return итог
    итог["verify"] = verify(site_id, ожидаемый_build=ожидаемый_build,
                            порт=п.port, path=path)
    if not итог["verify"].get("ok"):
        return итог
    switch_route(site_id, п.port, dry_run=False, path=path)
    # Дренаж перед остановкой кандидата. При `nginx -s reload` прежние воркеры
    # дорабатывают уже принятые соединения СО СТАРОЙ конфигурацией — это
    # документированное поведение. Кандидат, погашенный сразу, обрывал бы их:
    # на стенде это дало 4 отказа из 244 запросов, по одному на маршрут.
    дренаж = float(os.environ.get("SITE_DRAIN_SEC", "5"))
    time.sleep(дренаж)
    _systemctl("stop", п.candidate_unit, проверять=False)
    итог["drain_sec"] = дренаж
    итог["traffic_on"] = п.port
    return итог


def готов(port: int, *, предел: int = 600, шаг: float = 3.0,
          запрос: float = 5.0, жив=None) -> dict[str, Any]:
    """Ждать готовности приложения. Три исхода, и смешивать их нельзя."""
    import urllib.error
    import urllib.request

    начало = time.monotonic()
    while True:
        прошло = time.monotonic() - начало
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz",
                                        timeout=запрос) as r:
                if r.status == 200:
                    return {"ready": True, "elapsed_sec": round(прошло, 1)}
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        if жив is not None and not жив():
            return {"ready": False, "reason": "процесс не работает",
                    "elapsed_sec": round(прошло, 1)}
        if прошло >= предел:
            return {"ready": False, "reason": "предел ожидания",
                    "elapsed_sec": round(прошло, 1)}
        time.sleep(шаг)


def verify(site_id: str, *, ожидаемый_build: str = "", порт: int | None = None,
           path: Path | None = None,
           маршруты: tuple[str, ...] = ("/", "/healthz")) -> dict[str, Any]:
    """Приёмка по ответу, а не по состоянию юнита."""
    import re
    import urllib.request

    п = Площадка.из_реестра(site_id, path=path)
    цель = порт or п.port
    итог: dict[str, Any] = {"operation": "verify", "site_id": site_id,
                            "port": цель, "routes": {}}
    for м in маршруты:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{цель}{м}", timeout=30) as r:
                тело = r.read(400000)
                итог["routes"][м] = {"status": r.status, "bytes": len(тело)}
                if м == "/":
                    найдено = re.search(rb'site-factory-build-id" content="([^"]+)"', тело)
                    итог["build_id"] = найдено.group(1).decode() if найдено else None
        except Exception as exc:  # noqa: BLE001 — любой отказ это отказ приёмки
            итог["routes"][м] = {"error": type(exc).__name__}
    итог["ok"] = all(о.get("status") == 200 for о in итог["routes"].values())
    if ожидаемый_build:
        итог["build_matches"] = итог.get("build_id") == ожидаемый_build
        итог["ok"] = итог["ok"] and итог["build_matches"]
    return итог


def описать_границу() -> dict[str, Any]:
    """Что исполнитель может и чего не может. Для проверки перед установкой."""
    return {
        "operations": list(ОПЕРАЦИИ),
        "runs_repository_scripts": False,
        "accepts_paths_from_request": False,
        "site_root": str(КОРЕНЬ_САЙТОВ),
        "unit_template_source": "root-owned package copy",
        "artifact_members_checked": ["traversal", "symlink escape", "member type"],
    }


#: Шаблон юнита живёт ЗДЕСЬ, в root-овой копии пакета, а не в репозитории сайта.
#: Юнит, собранный из строк репозитория, означал бы, что право писать в
#: репозиторий — это право задать ExecStart, User и всё остальное от root.
ЮНИТ_ШАБЛОН = """# Служба {domain} ({site_id}). Собрана исполнителем, не репозиторием.
[Unit]
Description={domain} ({site_id}), выделенная ячейка
After=network-online.target

[Service]
Type=simple
User={account}
Group={account}
WorkingDirectory={link}
ExecStart=/usr/bin/python3 {link}/run.py --port {port} --data-dir {data}
Restart=on-failure
RestartSec=2

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={data}
ProtectKernelTunables=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
"""

#: Drop-in, закрывающий прежнюю службу от ручного запуска. `systemctl mask`
#: здесь не годится: он кладёт ссылку на /dev/null по пути юнита, а файл юнита
#: существует — systemd отвечает «File ... already exists».
ЗАЩИТА_ШАБЛОН = """# Порт {port} принадлежит {account}. Прежняя служба не поднимается вручную:
# конвейеры содержимого вызывают `systemctl restart` и заняли бы порт.
[Unit]
RefuseManualStart=yes
"""


def собрать_без_прав(repo: Path, куда: Path, account: str) -> tuple[Path, dict[str, Any]]:
    """Собрать артефакт из репозитория ПОД НЕПРИВИЛЕГИРОВАННОЙ учётной записью.

    Сборщик — код репозитория, а репозиторий доступен на запись обычной учётной
    записи. Запустить его от root значит отдать root тому, кто может туда
    писать. Поэтому привилегии сбрасываются до сборки, а root получает только
    готовый файл, который потом сверяется по digest.
    """
    import json as _json
    import pwd as _pwd

    сборщик = repo / "tools" / "build_release.py"
    if not сборщик.is_file():
        raise PrivilegedRefused(f"в репозитории нет {сборщик}")
    куда.mkdir(parents=True, exist_ok=True)

    подготовка = None
    if os.geteuid() == 0:
        запись = _pwd.getpwnam(account)
        shutil.chown(куда, account, account)

        def подготовка():  # noqa: F811 — назначается только под root
            os.setgid(запись.pw_gid)
            os.setuid(запись.pw_uid)

    # Репозиторий принадлежит другой учётной записи, а сборка идёт под учётной
    # записью сайта: с Git 2.35.2 это «dubious ownership», и сборщик падает на
    # первом же `git rev-parse`. Путь берётся из реестра и уже проверен, поэтому
    # доверие здесь не шире самой операции.
    окружение = dict(os.environ)
    было = int(окружение.get("GIT_CONFIG_COUNT", "0") or 0)
    окружение["GIT_CONFIG_COUNT"] = str(было + 1)
    окружение[f"GIT_CONFIG_KEY_{было}"] = "safe.directory"
    окружение[f"GIT_CONFIG_VALUE_{было}"] = str(repo)
    окружение["HOME"] = str(куда)
    # Сборка идёт под учётной записью САЙТА, а рабочая копия принадлежит другой
    # учётной записи и под `ProtectHome=read-only` ещё и смонтирована только на
    # чтение. `git status` при этом пытается освежить индекс, то есть записать в
    # чужой каталог. Без этого выпуск зависел бы от того, успел ли кто-то
    # тронуть файлы репозитория после последнего `git status`.
    окружение["GIT_OPTIONAL_LOCKS"] = "0"
    готово = subprocess.run(
        ["/usr/bin/python3", str(сборщик), "--output", str(куда)],
        cwd=str(repo), capture_output=True, text=True, preexec_fn=подготовка,
        env=окружение)
    if готово.returncode != 0:
        raise PrivilegedRefused(
            f"сборка не удалась под {account}: {готово.stderr.strip()[-600:]}")
    манифест = _json.loads((куда / "release-manifest.json").read_text(encoding="utf-8"))
    артефакт = куда / манифест["artifact"]
    if not артефакт.is_file():
        raise PrivilegedRefused(f"сборщик не оставил артефакта {артефакт}")
    return артефакт, манифест


def _systemctl(*args: str, проверять: bool = True) -> subprocess.CompletedProcess:
    команда = os.environ.get("SITE_SYSTEMCTL", "systemctl")
    готово = subprocess.run([команда, *args], capture_output=True, text=True)
    if проверять and готово.returncode != 0:
        raise PrivilegedRefused(
            f"systemctl {' '.join(args)} отказал: {готово.stderr.strip()[:300]}")
    return готово


def rollback(site_id: str, *, dry_run: bool = True, предел: int = 600,
             path: Path | None = None) -> dict[str, Any]:
    """Вернуть трафик действующей версии и погасить кандидата.

    Порядок именно такой: сначала маршрут, потом остановка. Обратный порядок
    оставил бы посетителей на порту, где уже никого нет.
    """
    п = Площадка.из_реестра(site_id, path=path)
    шаги = [f"маршрут -> {п.port}", f"stop {п.candidate_unit}",
            "проверить ответом"]
    if dry_run:
        return {"operation": "rollback", "site_id": site_id, "dry_run": True,
                "steps": шаги}

    _нужен_root()
    # Сначала прежняя служба отвечает, и только потом трафик идёт обратно.
    # Обратный порядок вернул бы посетителей на порт, где уже никого нет.
    восстановление = вернуть_прежнюю(п, предел=предел)
    switch_route(site_id, п.port, dry_run=False, path=path)
    _systemctl("stop", п.candidate_unit, проверять=False)
    состояние = готов(п.port, предел=предел,
                      жив=lambda: _systemctl("is-active", "--quiet", п.unit,
                                             проверять=False).returncode == 0)
    итог = {"operation": "rollback", "site_id": site_id, "dry_run": False,
            "steps": шаги, "ready": состояние, "previous_unit": восстановление}
    итог["verify"] = verify(site_id, порт=п.port, path=path)
    return итог



#: Файл upstream целевого сайта. Переключение трафика — атомарная замена
#: ОДНОГО этого файла: правка общей конфигурации nginx задела бы соседей.
UPSTREAM_КАТАЛОГ = Path(os.environ.get("SITE_NGINX_UPSTREAMS", "/etc/nginx/cells"))


def порт_кандидата(основной: int) -> int:
    """Порт для прогрева. Рядом с основным, но заведомо не его.

    Кандидат обязан подниматься, пока действующая версия отвечает: один порт на
    двоих означает, что старую надо остановить до старта новой, а старт стоит
    минут. Смещение фиксировано, чтобы порт был предсказуем и в отчёте, и в
    правиле firewall.
    """
    return основной + 1000


def warm_up(site_id: str, *, dry_run: bool = True, предел: int = 600,
            ожидаемый_build: str = "", данные: Path | None = None,
            path: Path | None = None) -> dict[str, Any]:
    """Поднять кандидата НА ОТДЕЛЬНОМ порту и дождаться его готовности.

    Действующая версия всё это время обслуживает посетителей: её никто не
    останавливал. Переключение произойдёт только после того, как кандидат
    ответит и назовёт ожидаемый выпуск.
    """
    п = Площадка.из_реестра(site_id, path=path)
    кандидат = п.candidate_port
    юнит = п.candidate_unit
    каталог = Path(os.environ.get("SITE_UNIT_DIR", "/etc/systemd/system"))
    текст = ЮНИТ_ШАБЛОН.format(
        domain=runtime.размещение(site_id, path=path).domain, site_id=site_id,
        account=п.account, link=п.candidate, data=данные or п.data,
        port=кандидат)
    if dry_run:
        return {"operation": "warm_up", "site_id": site_id, "dry_run": True,
                "candidate_unit": юнит, "candidate_port": кандидат}

    _нужен_root()
    # Прежний кандидат гасится ДО записи юнита и старта. Без этого порт
    # оставался занят предыдущей попыткой, новый процесс падал на bind, и
    # прогрев объявлял «процесс не работает» — то есть выпуск отвергался по
    # следу прошлой операции, а не по своему состоянию.
    _systemctl("stop", юнит, проверять=False)
    свободен = False
    for _ in range(50):
        проба = socket.socket()
        проба.settimeout(0.2)
        try:
            проба.connect(("127.0.0.1", кандидат))
        except OSError:
            свободен = True
            break
        finally:
            проба.close()
        time.sleep(0.2)
    if not свободен:
        raise PrivilegedRefused(
            f"порт кандидата {кандидат} занят и не освободился за 10 с; "
            "прогрев не начат")
    (каталог / юнит).write_text(текст, encoding="utf-8")
    _systemctl("daemon-reload")
    _systemctl("restart", юнит)
    состояние = готов(кандидат, предел=предел,
                      жив=lambda: _systemctl("is-active", "--quiet", юнит,
                                             проверять=False).returncode == 0)
    итог = {"operation": "warm_up", "site_id": site_id, "dry_run": False,
            "candidate_unit": юнит, "candidate_port": кандидат, "ready": состояние}
    if not состояние.get("ready"):
        return итог
    # Готовность — это ответ, а не состояние юнита. Но и ответа мало: кандидат
    # обязан назвать ТОТ выпуск, ради которого его поднимали.
    итог["verify"] = verify(site_id, ожидаемый_build=ожидаемый_build,
                            порт=кандидат)
    return итог


def _upstream_включён(файл: Path) -> bool:
    """Ссылается ли конфигурация nginx на этот файл.

    Ищем буквальное упоминание пути в конфигурации: точный разбор include с
    подстановками дороже и здесь не нужен — нам достаточно знать, что файл
    кто-то читает.
    """
    корень = Path(os.environ.get("SITE_NGINX_CONF", "/etc/nginx"))
    if not корень.is_dir():
        return False
    for путь in корень.rglob("*"):
        if not путь.is_file() or путь.suffix in {".bak", ".old"}:
            continue
        try:
            if str(файл) in путь.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def switch_route(site_id: str, порт: int, *, dry_run: bool = True,
                 path: Path | None = None) -> dict[str, Any]:
    """Перевести трафик на указанный порт: один upstream, nginx -t, reload."""
    # Площадка запрашивается ради проверки: сайт обязан быть зарегистрирован,
    # иначе маршрут можно было бы перевести на что угодно.
    Площадка.из_реестра(site_id, path=path)
    файл = UPSTREAM_КАТАЛОГ / f"{site_id}.upstream"
    текст = f"server 127.0.0.1:{порт};\n"
    if dry_run:
        return {"operation": "switch_route", "site_id": site_id, "dry_run": True,
                "upstream_file": str(файл), "port": порт}

    _нужен_root()
    # Файл upstream обязан быть ВКЛЮЧЁН в конфигурацию nginx. Иначе запись в
    # него проходит, `nginx -t` доволен, reload выполняется — и трафик не
    # двигается. Это худший исход из возможных: операция выглядит успешной, а
    # посетители остаются на прежней версии.
    if not _upstream_включён(файл):
        raise PrivilegedRefused(
            f"{файл} не включён ни в одну конфигурацию nginx: переключение "
            "маршрута ничего бы не изменило. Добавьте в server-блок сайта "
            f"`upstream` с `include {файл};` и повторите")
    файл.parent.mkdir(parents=True, exist_ok=True)
    прежний = файл.read_text(encoding="utf-8") if файл.is_file() else None
    врем = файл.with_suffix(".upstream.new")
    врем.write_text(текст, encoding="utf-8")
    os.replace(врем, файл)

    nginx = os.environ.get("SITE_NGINX", "nginx")
    проверка = subprocess.run([nginx, "-t"], capture_output=True, text=True)
    if проверка.returncode != 0:
        # Конфигурация не прошла проверку — возвращаем прежнюю и не перезагружаем:
        # reload со сломанным конфигом оставил бы nginx на старом, но следующий
        # чужой reload уронил бы его целиком.
        if прежний is not None:
            файл.write_text(прежний, encoding="utf-8")
        else:
            файл.unlink(missing_ok=True)
        raise PrivilegedRefused(
            f"nginx -t отказал, маршрут не переключён: {проверка.stderr.strip()[-300:]}")
    перезагрузка = subprocess.run([nginx, "-s", "reload"], capture_output=True, text=True)
    if перезагрузка.returncode != 0:
        raise PrivilegedRefused(
            f"nginx reload отказал: {перезагрузка.stderr.strip()[-300:]}")
    return {"operation": "switch_route", "site_id": site_id, "dry_run": False,
            "upstream_file": str(файл), "port": порт, "previous": прежний}


#: Файлы согласованного снимка. Каталог и подробности — одно целое: витрина
#: читает их вместе, и новый каталог со старыми подробностями показал бы
#: карточки без описаний.
СНИМОК = ("{site}-catalog.json", "{site}-details.json")

#: Файлы, которые витрина читает из хранилища, но без которых работает.
#:
#: `{site}-popular-weekly.json` витрина ищет рядом с каталогом — то есть в
#: СВОЁМ хранилище, а производитель кладёт его в общий каталог. У выделенной
#: витрины он туда не попадал вовсе, и блок недельного выбора оставался пустым
#: без единой ошибки: страница отвечала 200, раздела просто не было.
#:
#: Обязательными их делать нельзя: у части витрин такого файла нет в принципе
#: (у lords-01, например), и требование уронило бы им обновление каталога —
#: то есть отсутствие дополнительного блока стоило бы свежести всего каталога.
ДОПОЛНЕНИЯ = ("{site}-popular-weekly.json",)

#: Каталог пользовательских записей. Он ОДИН на сайт и между версиями не
#: копируется: две копии означали бы, что часть комментариев и голосов
#: останется в той, которую выбросят.
ПОЛЬЗОВАТЕЛЬСКИЕ = "site-data"


def снимок_совпадает(источник: Path, цель: Path, site_id: str) -> bool:
    """Тот же снимок уже стоит. Повтор не должен ничего менять.

    Сравниваются и ДОПОЛНЕНИЯ, а не только пара «каталог + подробности».
    Это повтор ошибки, уже исправленной в засеве хранилища: там «наполнено»
    считалось по одному каталогу, и витрина выкладывалась без подробностей.
    Здесь та же ошибка дала другой симптом — доставка отвечала `unchanged` и
    не привозила недельный снимок, появившийся у производителя впервые:
    каталог-то не менялся. Наблюдалось на zona-01.

    Правило одно и для обоих случаев: «не изменилось» — это про ВСЁ, что
    доставляется, а не про часть.
    """
    import hashlib

    for шаблон in (*СНИМОК, *ДОПОЛНЕНИЯ):
        имя = шаблон.format(site=site_id)
        a, b = источник / имя, цель / имя
        if not a.is_file():
            continue
        if not b.is_file():
            return False
        if (hashlib.sha256(a.read_bytes()).hexdigest()
                != hashlib.sha256(b.read_bytes()).hexdigest()):
            return False
    return True


def stage_snapshot(site_id: str, источник: Path, *, dry_run: bool = True,
                   path: Path | None = None) -> dict[str, Any]:
    """Собрать хранилище кандидата: новый снимок плюс общие пользовательские данные.

    Пользовательские записи не копируются, а подключаются ссылкой на тот же
    каталог: копия означала бы, что комментарии и голоса, принятые во время
    прогрева, окажутся в хранилище, которое потом выбросят.
    """
    п = Площадка.из_реестра(site_id, path=path)
    источник = Path(источник)
    имена = [ш.format(site=site_id) for ш in СНИМОК]
    отсутствуют = [и for и in имена if not (источник / и).is_file()]
    if отсутствуют:
        raise PrivilegedRefused(
            f"{site_id}: в источнике нет файлов снимка {отсутствуют}; "
            "половина снимка хуже прежнего целого")

    если_тот_же = снимок_совпадает(источник, п.data, site_id)
    if dry_run:
        return {"operation": "stage_snapshot", "site_id": site_id, "dry_run": True,
                "unchanged": если_тот_же, "files": имена,
                "data_candidate": str(п.data_candidate)}
    if если_тот_же:
        return {"operation": "stage_snapshot", "site_id": site_id, "dry_run": False,
                "unchanged": True, "files": имена}

    _нужен_root()
    if п.data_candidate.exists():
        shutil.rmtree(п.data_candidate)
    п.data_candidate.mkdir(parents=True)
    # Всё, что витрина читает из хранилища, кроме снимка и пользовательских
    # записей, переносится как есть: страницы прежнего релиза, манифест и т. п.
    for запись in п.data.iterdir():
        if запись.name in имена or запись.name == ПОЛЬЗОВАТЕЛЬСКИЕ:
            continue
        цель = п.data_candidate / запись.name
        if запись.is_dir():
            цель.symlink_to(запись)
        else:
            shutil.copy2(запись, цель)
    for имя in имена:
        shutil.copy2(источник / имя, п.data_candidate / имя)
    # Дополнения переносятся, только если производитель их дал.
    for имя in (ш.format(site=site_id) for ш in ДОПОЛНЕНИЯ):
        if (источник / имя).is_file():
            shutil.copy2(источник / имя, п.data_candidate / имя)
    общие = п.data / ПОЛЬЗОВАТЕЛЬСКИЕ
    if общие.exists():
        (п.data_candidate / ПОЛЬЗОВАТЕЛЬСКИЕ).symlink_to(общие)
    for путь in [п.data_candidate, *п.data_candidate.rglob("*")]:
        if not путь.is_symlink():
            shutil.chown(путь, п.account, п.account)
    return {"operation": "stage_snapshot", "site_id": site_id, "dry_run": False,
            "unchanged": False, "files": имена,
            "data_candidate": str(п.data_candidate)}


def promote_snapshot(site_id: str, *, dry_run: bool = True,
                     path: Path | None = None) -> dict[str, Any]:
    """Перенести проверенный снимок в рабочее хранилище.

    Делается после того, как кандидат принял трафик: действующий процесс в
    этот момент никого не обслуживает, и подмена файлов под ним никому не
    видна. Пользовательские записи не трогаются вовсе — они лежат в общем
    каталоге, на который обе версии смотрят одной и той же ссылкой.
    """
    п = Площадка.из_реестра(site_id, path=path)
    # Дополнения повышаются вместе со снимком: перенести их в кандидата и не
    # перенести в рабочее хранилище значило бы отдать их только прогреву.
    имена = [ш.format(site=site_id) for ш in (*СНИМОК, *ДОПОЛНЕНИЯ)]
    if dry_run:
        return {"operation": "promote_snapshot", "site_id": site_id,
                "dry_run": True, "files": имена}
    _нужен_root()
    for имя in имена:
        источник = п.data_candidate / имя
        if not источник.is_file():
            continue
        врем = п.data / f".{имя}.new"
        shutil.copy2(источник, врем)
        shutil.chown(врем, п.account, п.account)
        os.replace(врем, п.data / имя)
    return {"operation": "promote_snapshot", "site_id": site_id,
            "dry_run": False, "files": имена}


def отпечаток_снимка(источник: Path, site_id: str) -> str:
    """Отпечаток согласованной пары «каталог + подробности».

    Считается по обоим файлам сразу: снимок — это пара, и изменение одного из
    них означает новый снимок целиком.
    """
    import hashlib

    h = hashlib.sha256()
    for шаблон in СНИМОК:
        путь = Path(источник) / шаблон.format(site=site_id)
        if путь.is_file():
            h.update(путь.read_bytes())
    return h.hexdigest()
