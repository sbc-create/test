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
import json as _json
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
    # Ссылка на секрет — такой же признак «плеер нужен», как и ожидаемое
    # значение, и появилась она позже. Пока условие смотрело только на
    # `publisher_id_expected`, витрина с `publisher_id_ref` (значение приходит
    # из Secret Hub и в git не хранится) не получала файла плеера вовсе:
    # исполнитель считал его ненужным, а рантайм витрины отказывался стартовать
    # словами «нет config/player.json». Кандидат lords-05 так и не поднялся
    # 2026-09-28, и причина выглядела как поломка выпуска.
    return bool(str(данные.get("publisher_id_expected") or "").strip()
                or str(данные.get("publisher_id_ref") or "").strip())


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
    ожидается = _объявленный_издатель(выпуск)
    отвергнуто: list[str] = []
    for откуда in источники:
        # Ссылку не берём: она увела бы за пределы перечисленных источников.
        if not откуда.is_file() or откуда.is_symlink():
            continue
        # Перенос «как было» верен, пока витрина не СМЕНИЛА издателя. Когда
        # выпуск объявляет другой `publisher_id_expected`, действующий файл —
        # это ровно прежнее значение, и копировать его значит выложить
        # конфигурацию, которая тут же провалит проверку готовности витрины
        # («publisher_id X, а сайт объявляет Y»). Владелец назначил бы новое
        # значение, а выкладка молча возвращала бы старое — каждый раз.
        #
        # Поэтому источник, расходящийся с объявлением выпуска, пропускается:
        # перебор идёт дальше, к каталогу производителя, где значение и меняют.
        # Ни один сайт, у которого издатель не менялся, этого не замечает:
        # у него действующий файл и объявление совпадают.
        нашли = _издатель_файла(откуда)
        if ожидается and нашли not in ("", ожидается):
            отвергнуто.append(f"{откуда} объявляет {нашли}")
            continue
        цель.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(откуда, цель)
        shutil.chown(цель, п.account, п.account)
        os.chmod(цель, 0o600)
        return [ФАЙЛ_ПЛЕЕРА]
    if отвергнуто:
        raise PrivilegedRefused(
            f"{п.site_id}: выпуск объявляет publisher_id {ожидается}, а "
            f"{ФАЙЛ_ПЛЕЕРА} с этим значением нет ни в одном разрешённом "
            f"источнике ({'; '.join(отвергнуто)}). Подставить прежнее нельзя: "
            "витрина откажется стартовать со словами «publisher_id X, а сайт "
            f"объявляет {ожидается}». Обновите "
            f"{ПЛЕЕР_ПРОИЗВОДИТЕЛЯ}/player-{п.site_id}.json")
    raise PrivilegedRefused(
        f"{п.site_id}: витрина объявляет publisher_id, но {ФАЙЛ_ПЛЕЕРА} не найден "
        f"ни в действующем выпуске, ни у производителя. Без него витрина не "
        "стартует — выкладывать нечего")


def _объявленный_издатель(выпуск: Path) -> str:
    """Какого издателя объявляет САМ выпуск (`publisher_id_expected`).

    Значение публичное: оно стоит в разметке страницы атрибутом
    `data-publisher-id`. Секретом здесь является не число, а пара учётных
    данных провайдера, которая живёт в Secret Hub и сюда не попадает.
    """
    try:
        данные = json.loads((выпуск / "config" / "site.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(данные.get("publisher_id_expected") or "").strip()


def _издатель_файла(путь: Path) -> str:
    """`publisher_id` из файла плеера. Нечитаемый файл — пустая строка.

    Пустая строка означает «сказать нечего», и такой источник НЕ отбраковывается:
    прежнее поведение (взять первый читаемый файл) для него сохраняется.
    """
    try:
        return str(json.loads(путь.read_text(encoding="utf-8")).get(
            "publisher_id") or "").strip()
    except (OSError, ValueError):
        return ""


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
        временный, site_id=site_id, commit=commit, digest=факт, account=п.account,
        имя_выпуска=имя)
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
                            digest: str, account: str,
                            имя_выпуска: str = "") -> dict[str, Any]:
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

    # Манифест шаблона лежит у разных семейств по-разному: у одних в `config/`,
    # у других в корне дерева. Читаются оба.
    #
    # И читается не любое значение, а только такое, которое НАЗЫВАЕТ этот
    # выпуск. Ключ `build_id` у разных семейств означает разное: у zona-01 в
    # нём `<commit12>-<site_id>`, то есть метка выпуска, а у zona-02 —
    # `zona-02-0fb857b26f85`, ревизия ЗАКРЕПЛЁННОГО шаблона, одинаковая у всех
    # её выпусков. Записать второе в поле «метка выпуска» — та же ошибка, что
    # сверяться по заголовку X-Site-Factory-Build-Id: значение выглядит
    # правильным и ничего не различает. У zona-02 поле выходило пустым, и файл,
    # существующий затем, чтобы назвать выпуск, выпуска не называл.
    ожидаемая = f"{имя_выпуска}-{site_id}" if имя_выпуска else ""
    живой = ""
    for кандидат in (выпуск / "config" / "template-manifest.json",
                     выпуск / "template-manifest.json"):
        if not кандидат.is_file():
            continue
        try:
            объявлено = _json.loads(кандидат.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ключ in ("live_build_id", "build_id"):
            значение = str(объявлено.get(ключ) or "").strip()
            # Пока имя выпуска неизвестно (старые вызовы), берём объявленное
            # как есть: проверять не с чем, а молчать хуже, чем сказать.
            if значение and (not ожидаемая or значение == ожидаемая):
                живой = значение
                break
        if живой:
            break
    # Запасной путь — то же правило, по которому метку строит сама витрина:
    # имя каталога выпуска плюс site_id. Оно не «придумано здесь»: ровно это
    # значение витрина отдаёт мета-тегом, и ровно с ним сверяется приёмка.
    if not живой:
        живой = ожидаемая

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
        # Окончательное имя каталога, а не временное. Запись идёт ДО атомарного
        # переименования, и `выпуск.name` здесь — ещё `.<commit12>.new`: имя
        # служебного каталога, которого через мгновение не будет. Файл
        # происхождения с несуществующим путём внутри вводил в заблуждение
        # соседнюю сессию, читавшую его как объявление выпуска.
        "release": имя_выпуска or выпуск.name,
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
    # Смена владельца необязательна: учётной записи может не быть (стенд), а
    # прав на chown — не хватать. Манифест при этом уже записан, и это главное.
    with contextlib.suppress(LookupError, PermissionError):
        shutil.chown(файл, account, account)
    return {"file": имя, "live_build_id": живой, "entrypoint": точка}


def применить_правки(site_id: str, содержимое: dict[str, Any], *,
                     dry_run: bool = True,
                     площадка: Площадка | None = None) -> dict[str, Any]:
    """Положить правки редактора в хранилище витрины.

    Пишет ИСПОЛНИТЕЛЬ, а не управляющий слой: у админки нет и не должно быть
    доступа к данным витрин — её ошибка обязана остаться ошибкой планирования,
    а не порчей чужого состояния. То же решение уже принято для инвалидации
    кэша, и здесь оно не изобретается заново.

    Файл объявлен `user_writable`, поэтому доставка каталога его не
    перезаписывает: правка переживает импорт по построению, а не по удаче.

    Владелец — учётная запись сайта: витрина читает файл своим пользователем,
    и файл, принадлежащий кому-то ещё, она прочитать не сможет.
    """
    п = площадка or Площадка.из_реестра(site_id)
    контракт = контракт_данных(site_id, площадка=п)
    имя = ИМЯ_ПРАВОК
    if имя not in [ш.format(site=site_id) for ш in контракт["user_writable"]]:
        raise PrivilegedRefused(
            f"{site_id}: {имя} не объявлен `user_writable` в контракте сайта — "
            "доставка каталога затирала бы правки на первом же обновлении")
    if содержимое.get("site_id") != site_id:
        raise PrivilegedRefused(
            f"правки подготовлены для {содержимое.get('site_id')!r}, "
            f"а применяются к {site_id!r}")
    цель = п.data / имя
    записей = len(содержимое.get("overrides") or {})
    if dry_run:
        return {"operation": "editorial", "site_id": site_id, "dry_run": True,
                "path": str(цель), "entries": записей}
    _нужен_root()
    из_хранилища = json.dumps(содержимое, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")) + "\n"
    врем = цель.with_suffix(".json.new")
    врем.write_text(из_хранилища, encoding="utf-8")
    shutil.chown(врем, п.account, п.account)
    врем.chmod(0o644)
    os.replace(врем, цель)
    return {"operation": "editorial", "site_id": site_id, "dry_run": False,
            "path": str(цель), "entries": записей, "owner": п.account}


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
    # Включение — часть выпуска, а не отдельная обязанность владельца.
    # Без него сайт работает до первой перезагрузки, а потом не поднимается
    # вовсе либо возвращается прежняя служба из общего дерева: у lordfilm47.space
    # и 1lordserials1.online ячейка обслуживала домен, не будучи включённой, и
    # снаружи это выглядело завершённым выпуском. `enable` идемпотентен, повтор
    # выпуска ничего не удваивает.
    включение = _systemctl("enable", п.unit, проверять=False)
    шаги.append(f"enable {п.unit}: rc={включение.returncode}")
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
    import urllib.request

    п = Площадка.из_реестра(site_id, path=path)
    цель = порт or п.port
    итог: dict[str, Any] = {"operation": "verify", "site_id": site_id,
                            "port": цель, "routes": {}}
    # Первый запрос после перезапуска у крупной витрины холодный: рантайм читает
    # снимок подробностей (у lords-05 это 13 МБ) и отвечает дольше тридцати
    # секунд. Ровно на этом приёмка объявила исправный выпуск провалившимся:
    # verify получил TimeoutError на обоих маршрутах, сработал откат — и его
    # собственная проверка, дошедшая до сайта позже, увидела HTTP 200. Откат по
    # нетерпению выключает работающий сайт.
    #
    # Поэтому попытка не одна: пределы нарастают, сумма даёт время на прогрев, а
    # быстрая витрина по-прежнему проверяется первой же попыткой.
    ПРЕДЕЛЫ = (30, 60, 120)
    for м in маршруты:
        for номер, предел in enumerate(ПРЕДЕЛЫ, 1):
            последняя = номер == len(ПРЕДЕЛЫ)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{цель}{м}", timeout=предел) as r:
                    тело = r.read(400000)
                    итог["routes"][м] = {"status": r.status, "bytes": len(тело),
                                         "попытка": номер}
                    if м == "/":
                        итог["build_id"], итог["build_id_source"] = _метка_выпуска(
                            r.headers.get("X-Site-Factory-Build-Id"), тело)
                    break
            except Exception as exc:  # noqa: BLE001 — любой отказ это отказ приёмки
                if последняя:
                    итог["routes"][м] = {"error": type(exc).__name__,
                                         "попыток": len(ПРЕДЕЛЫ),
                                         "суммарное_ожидание_с": sum(ПРЕДЕЛЫ)}
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
#: Имена мета-тегов с меткой ИМЕННО ЭТОГО выпуска, в порядке предпочтения.
#: Семейства называют её по-разному: zona-02 пишет `site-factory-release-id`
#: («метка выпуска», имя каталога релиза + site_id), остальные —
#: `site-factory-build-id`. Читать надо оба: в приёмке важно не имя атрибута, а
#: то, меняется ли значение от выпуска к выпуску.
МЕТА_ВЫПУСКА = (b"site-factory-release-id", b"site-factory-build-id")


def _метка_выпуска(заголовок: str | None, тело: bytes) -> tuple[str | None, str]:
    """Метка выпуска и источник, из которого она взята.

    Порядок ИМЕННО такой: сначала разметка, потом заголовок. Раньше было
    наоборот, и это стоило выпуска.

    `X-Site-Factory-Build-Id` берётся из манифеста ЗАКРЕПЛЁННОГО шаблона. Он
    одинаков у всех выпусков витрины и читается процессом один раз при старте,
    поэтому после переключения `current` показывает прежний выпуск и при этом
    выглядит правильным. Ровно об этом предупреждает `написать_release_json` в
    этом же файле — а приёмка всё равно спрашивала сначала его. Кандидат
    zona-02, поднявшийся из нужного коммита и отвечавший 200 на обоих
    маршрутах, был откачен с `build_matches: false`: заголовок назвал
    `zona-02-0fb857b26f85`, то есть ревизию шаблона, а не выпуск.

    Мета-тег, наоборот, пишет сам процесс выпуска и меняет с каждым.

    Заголовок остаётся запасным источником и не убран: витрины Yummy ставят
    перед собой прокси над сторонним приложением, разметки не пишут и мета-тега
    не имеют. Для них заголовок — единственное, что есть, и отказ от него
    означал бы откат исправного кандидата. Источник называется в отчёте, чтобы
    «сверено по заголовку» нельзя было прочитать как «сверено по выпуску».
    """
    import re  # noqa: PLC0415 — модуль импортируется по месту, как и в verify()

    for имя in МЕТА_ВЫПУСКА:
        найдено = re.search(имя + rb'" content="([^"]+)"', тело)
        if найдено:
            return найдено.group(1).decode("utf-8", "replace"), "мета-тег"
    if заголовок:
        return заголовок, "заголовок (ревизия шаблона, не выпуска)"
    return None, "нет"


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


def слой_индексации(site_id: str, *, mode: str, домен: str = "",
                    dry_run: bool = True) -> dict[str, Any]:
    """Переключить слой nginx для ОДНОГО сайта: включаемый файл, -t, reload.

    Зачем здесь, а не отдельным скриптом владельца. Пока это был root-скрипт,
    редактор не мог открыть домен без ручного действия человека — а значит
    штатной операции открытия не существовало. Привилегированная сторона
    делает ровно то, что делал скрипт, и ровно в том же порядке.

    Что делается:

      1. находятся ВСЕ живые конфигурации с серверным именем этого домена.
         Одного файла не хватает: у `lords-05` блок `:80` лежит в
         `lords/lords-05.conf`, а блок `:443` — в `lords/lords-05-tls.conf`,
         и правка одного оставила бы домен закрытым;
      2. в каждой из них фиксированная строка заголовка один раз переводится
         на переменную `map $uri` с `include` — тем же приёмом, которым
         переключается upstream. Перегенерации нет намеренно: в живых файлах
         есть ограничение соединений, формат журнала и include маркера
         Вебмастера, которых в заготовке нет;
      3. пишется включаемый файл режима. Дальше РЕЖИМ меняется только им;
      4. `nginx -t`; при отказе ВСЕ файлы возвращаются из резервных копий и
         перезагрузки не происходит;
      5. `nginx -s reload`.

    Идемпотентность: повторный запуск в том же режиме не меняет ни одного
    файла конфигурации и сообщает об этом (`changed: false`).
    """
    from factory.cell import nginx_indexing as ни

    режим = (mode or "").strip().upper()
    if режим not in ("OPEN", "CLOSED"):
        raise PrivilegedRefused(f"режим {mode!r} неизвестен: OPEN или CLOSED")
    площадка = Площадка.из_реестра(site_id)
    домен = домен or (runtime.размещение(site_id).domain or "")
    if not домен:
        raise PrivilegedRefused(
            f"{site_id}: домен не объявлен в реестре — какой слой переключать, "
            "неизвестно")
    файлы = ни.конфиги_сайта(site_id, домен)
    итог: dict[str, Any] = {"operation": "indexing_nginx", "site_id": site_id,
                            "domain": домен, "mode": режим,
                            "configs": [str(ф) for ф in файлы],
                            "dry_run": dry_run}
    if not файлы:
        raise PrivilegedRefused(
            f"{site_id} ({домен}): живых конфигураций с этим серверным именем "
            f"не найдено в {ни.КОРЕНЬ_NGINX}")

    # Что предстоит сделать — считается ДО единой записи.
    план: list[dict] = []
    #: Объявлена ли уже переменная режима в каком-нибудь файле домена. Одно
    #: объявление на весь контекст http: второе — ошибка nginx.
    уже_объявлен = False
    for ф in файлы:
        try:
            текст = ф.read_text(encoding="utf-8")
        except OSError as ош:
            if not dry_run:
                # Исполнитель работает от root: нечитаемая конфигурация для
                # него — настоящая беда, и переключать слой по непрочитанному
                # файлу нельзя.
                raise PrivilegedRefused(
                    f"{ф} не читается: {type(ош).__name__}. Переключать слой "
                    "по непрочитанной конфигурации нельзя") from None
            # Сухой прогон может идти под учётной записью без прав на часть
            # файлов (`/etc/nginx/conf.d/*` бывает 0600). Это ограничение
            # ПРОГОНА, а не отказ: план остаётся полезным, и неполнота названа.
            план.append({"path": str(ф), "unreadable": type(ош).__name__,
                         "serving_blocks": None, "will_convert": 0,
                         "already_on_variable": None, "new_text": "",
                         "old_text": ""})
            итог["dry_run_incomplete"] = True
            continue
        отдающие = ни.блоки_страницы(текст, домен)
        фиксированных = sum(
            1 for б in отдающие for с in б["add_header_lines"]
            if ни.ФИКСИРОВАННАЯ in с)
        # Объявление переменной ставится РОВНО В ОДИН файл. Конфигурации
        # `lords/<site>.conf` и `lords/<site>-tls.conf` попадают в один
        # контекст http (их включает `conf.d/lords.conf`).
        #
        # Измерено 2026-10-03 настоящим nginx 1.18.0: второе объявление той
        # же переменной он ПРИНИМАЕТ (rc 0). Причина правила не в отказе, а
        # в том, что при двух объявлениях nginx молча пользуется ОДНИМ —
        # каким, не определено, — и режим из включаемого файла второго
        # перестал бы действовать без единой ошибки.
        уже_есть = ни.map_объявлен(текст, site_id)
        объявлять = not (уже_объявлен or уже_есть)
        новый, переведено = ни.перевести_на_переменную(
            текст, site_id, объявлять_map=объявлять)
        if уже_есть or (объявлять and переведено):
            уже_объявлен = True
        план.append({"path": str(ф), "serving_blocks": len(отдающие),
                     "fixed_lines_in_serving": фиксированных,
                     "already_on_variable": ни.уже_на_переменной(текст, site_id),
                     "map_declared_here": bool(уже_есть
                                               or (объявлять and переведено)),
                     "will_convert": переведено, "new_text": новый,
                     "old_text": текст})
    включаемый = ни.путь_включаемого(site_id)
    тело = ни.тело_включаемого(режим)
    прежнее_тело = (включаемый.read_text(encoding="utf-8")
                    if включаемый.is_file() else None)
    итог["include_file"] = str(включаемый)
    итог["plan"] = [{к: з for к, з in ш.items()
                     if к not in ("new_text", "old_text")} for ш in план]
    итог["include_changes"] = прежнее_тело != тело

    # Ни одна конфигурация не несёт ни фиксированной строки, ни переменной —
    # переключать нечего, и выдумывать строку в чужом файле нельзя.
    if not any(ш["will_convert"] or ш["already_on_variable"] for ш in план):
        raise PrivilegedRefused(
            f"{site_id} ({домен}): ни в одной из {len(файлы)} конфигураций нет "
            f"ни строки {ни.ФИКСИРОВАННАЯ!r}, ни заголовка на переменной. "
            "Править наугад нельзя: в этих файлах живут настройки, которых "
            "нет в заготовке")

    if dry_run:
        итог["changed"] = bool(итог["include_changes"]
                               or any(ш["will_convert"] for ш in план))
        return итог

    _нужен_root()
    nginx = os.environ.get("SITE_NGINX", "nginx")
    копии: list[tuple[Path, str]] = []
    включаемый.parent.mkdir(parents=True, exist_ok=True)
    каталог_копий = ни.КОРЕНЬ_NGINX / "backups"
    каталог_копий.mkdir(parents=True, exist_ok=True)
    # Метка копии — время в UTC без знаков, недопустимых в имени файла.
    метка = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    сделано: list[str] = []
    try:
        for ш in план:
            ф = Path(ш["path"])
            if ш["will_convert"]:
                копия = каталог_копий / f"{ф.name}.bak.indexing.{метка}"
                копия.write_text(ш["old_text"], encoding="utf-8")
                копии.append((ф, ш["old_text"]))
                ф.write_text(ш["new_text"], encoding="utf-8")
                сделано.append(f"{ф}: заголовок переведён на переменную "
                               f"(копия {копия})")
        if итог["include_changes"]:
            врем = включаемый.with_suffix(".robots.new")
            врем.write_text(тело, encoding="utf-8")
            os.replace(врем, включаемый)
            os.chmod(включаемый, 0o644)
            сделано.append(f"{включаемый}: режим {режим}")
        if not сделано:
            # Менять было нечего: ни одной конфигурации не переведено и
            # включаемый файл уже в нужном режиме. Проверять и перечитывать
            # конфигурацию в этом случае не за чем — а перезагрузка не
            # бесплатна: она заменяет рабочие процессы ВСЕГО сервера, то есть
            # задевает все сайты хоста ради заявки, которая ничего не изменила.
            # Измерено на изолированном стенде 2026-10-03: повторная заявка на
            # уже достигнутый режим возвращала `nothing-to-do` и при этом
            # исправно звала `nginx -s reload`.
            итог["nginx_test"] = {"skipped": True,
                                  "reason": "ни один файл не изменён"}
            итог["nginx_reload"] = {"skipped": True,
                                    "reason": "ни один файл не изменён: "
                                              "перезагружать нечего"}
            итог["changed"] = False
            итог["steps"] = сделано
            итог["previous_include"] = прежнее_тело
            return итог
        проверка = subprocess.run([nginx, "-t"], capture_output=True, text=True)
        # Итог проверки и перезагрузки попадает В ОТВЕТ. Без этого
        # доказательство приходилось искать по времени запуска рабочих
        # процессов в /proc: исход `applied` говорил, что отказа не было, но
        # не говорил, что именно ответил nginx.
        итог["nginx_test"] = {
            "rc": проверка.returncode,
            "output": (проверка.stderr or проверка.stdout).strip()[-300:]}
        if проверка.returncode != 0:
            raise PrivilegedRefused(
                f"nginx -t отказал, слой НЕ переключён: "
                f"{проверка.stderr.strip()[-300:]}")
        перезагрузка = subprocess.run([nginx, "-s", "reload"],
                                      capture_output=True, text=True)
        итог["nginx_reload"] = {
            "rc": перезагрузка.returncode,
            "output": (перезагрузка.stderr or перезагрузка.stdout).strip()[-300:],
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if перезагрузка.returncode != 0:
            raise PrivilegedRefused(
                f"nginx reload отказал: {перезагрузка.stderr.strip()[-300:]}")
    except Exception:
        # Любая беда после первой записи — возврат ВСЕГО к исходному виду.
        # Частично переведённая конфигурация хуже непереведённой: часть
        # блоков читала бы переменную, которой нет.
        for ф, прежний in копии:
            ф.write_text(прежний, encoding="utf-8")
        if прежнее_тело is None:
            включаемый.unlink(missing_ok=True)
        else:
            включаемый.write_text(прежнее_тело, encoding="utf-8")
        subprocess.run([nginx, "-t"], capture_output=True, text=True)
        итог["restored"] = True
        raise
    итог["changed"] = bool(сделано)
    итог["steps"] = сделано
    итог["previous_include"] = прежнее_тело
    return итог


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

#: Имя файла правок редактора в хранилище витрины.
ИМЯ_ПРАВОК = "editorial-overrides.json"


def _домен_сайта(site_id: str) -> str:
    """Домен сайта из реестра ячеек. Нужен воротам защищённых данных.

    У `Площадка` поля домена нет — она описывает ПУТИ, а не адрес, и добавлять
    его туда значило бы расширять её смысл ради одной проверки.
    """
    try:
        from factory.cell import registry as _реестр
        return _реестр.resolve(site_id).domain or ""
    except Exception:  # noqa: BLE001 — нет в реестре: домена нет
        return ""


def засеять_пользовательское(site_id: str, источник: Path, *,
                             dry_run: bool = True,
                             площадка: Площадка | None = None,
                             репозиторий: Path | None = None) -> dict[str, Any]:
    """Положить в хранилище ячейки то, что дальше принадлежит посетителям.

    Делается РОВНО ОДИН РАЗ, при первом выпуске: дальше файл живёт своей
    жизнью, и доставка каталога его не трогает (она подключает его ссылкой).
    Повторный засев затёр бы принятые оценки.

    Базу SQLite нельзя копировать как файл: рядом могут лежать `-wal` и
    `-shm`, и побайтовая копия под запись отдаёт либо устаревшее состояние,
    либо испорченное. Поэтому используется штатное резервное копирование
    SQLite — `Connection.backup()`, которое отдаёт согласованный снимок и на
    открытой под запись базе.

    Владелец меняется на учётную запись сайта. Это не косметика: сейчас
    `/srv/lords/.frontend/yummy-readmodel.sqlite3` принадлежит root в каталоге
    claude, а служба работает под `lords` — то есть путь записи оценок мёртв,
    и в таблице `user_rating` ноль строк. После засева он впервые становится
    рабочим, и это изменение поведения, а не побочный эффект: записано здесь и
    названо в отчёте.
    """
    from factory.cell import protected

    п = площадка or Площадка.из_реестра(site_id)
    контракт = контракт_данных(site_id, площадка=п, репозиторий=репозиторий)
    итоги: list[dict[str, Any]] = []
    for шаблон in контракт["user_writable"]:
        имя = шаблон.format(site=site_id)
        цель = п.data / имя
        откуда = Path(источник) / имя
        если = ("уже на месте" if цель.exists() or цель.is_symlink()
                else "в источнике нет" if not откуда.exists() else None)
        if если:
            # Файл на месте — писать нечего, и ворота спрашивать не о чем.
            #
            # Прежде ворота стояли ПЕРЕД этой проверкой, и это измерено на
            # живом выпуске: активация an1meg0.site была отклонена сообщением
            # «операция seed_user_writable пытается изменить защищённые данные
            # ['site_declared']», хотя засев ничего бы не тронул — хранилище
            # сообщества на месте. Так защита запрещала любой выпуск сайта,
            # у которого эти данные ЕСТЬ, то есть ровно того, что защищает.
            #
            # Правило владельца про другое: постоянные данные нельзя МЕНЯТЬ.
            # «Файл уже есть» — не изменение; «файла нет у переданного сайта» —
            # остановка с диагностикой, и её даёт ветка ниже.
            итоги.append({"name": имя, "skipped": если})
            continue
        # ВОРОТА. Сюда доходит только случай, когда засев ДЕЙСТВИТЕЛЬНО писал
        # бы: файла нет, а источник есть. У переданного сайта это запрещено —
        # пропавший файл означает утрату, и подстановка шаблонного значения в
        # этот момент худшее из возможных действий.
        protected.проверить_запись(site_id, _домен_сайта(site_id), цель,
                                   операция="seed_user_writable")
        if dry_run:
            итоги.append({"name": имя, "would_seed": str(откуда)})
            continue
        _нужен_root()
        if откуда.is_dir():
            shutil.copytree(откуда, цель)
        elif имя.endswith((".sqlite3", ".sqlite", ".db")):
            import sqlite3
            источник_бд = sqlite3.connect(f"file:{откуда}?mode=ro", uri=True)
            цель_бд = sqlite3.connect(str(цель))
            try:
                источник_бд.backup(цель_бд)
            finally:
                цель_бд.close()
                источник_бд.close()
        else:
            shutil.copy2(откуда, цель)
        for путь in ([цель, *цель.rglob("*")] if цель.is_dir() else [цель]):
            shutil.chown(путь, п.account, п.account)
        итоги.append({"name": имя, "seeded": True, "from": str(откуда),
                      "method": "sqlite backup" if имя.endswith(
                          (".sqlite3", ".sqlite", ".db")) else "copy",
                      "owner": п.account})
    return {"operation": "seed_user_writable", "site_id": site_id,
            "dry_run": dry_run, "contract": контракт["source"], "entries": итоги}


def контракт_данных(site_id: str, *, площадка: Площадка | None = None,
                    репозиторий: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Что для этого сайта доставляется, а что принадлежит посетителям.

    Набор файлов был ОДИН на всю фабрику: каталог плюс подробности
    обязательно, `site-data` — пользовательское. Для семейства Yummy он не
    подходит ни одной из трёх частей:

      * подробностей у него нет в природе, и требование обязательного
        `{site}-details.json` отказало бы выпуску на отсутствии файла, которого
        никто не производит;
      * витрина читает `yummy-readmodel.sqlite3`, и это не снимок: в нём
        таблица `user_rating`, куда сам слой витрины ПИШЕТ
        (`yummy_readmodel.py`, INSERT ... ON CONFLICT DO UPDATE);
      * значит копировать его при каждой доставке нельзя ровно по той причине,
        по которой не копируется `site-data`: оценки, принятые во время
        прогрева кандидата, остались бы в хранилище, которое потом выбросят.

    Поэтому контракт объявляет сам сайт — в `config/site.json`, ключом
    `data_contract` с полями `delivered` и `user_writable`. Источник истины
    здесь тот же, что у всей фабрики: файлы конкретного сайта, а не таблица в
    общем коде, которую пришлось бы править из-за каждого нового семейства.

    Читается сначала из УСТАНОВЛЕННОГО выпуска (то, что исполняется), затем из
    репозитория (первый выпуск, когда установленного ещё нет), и лишь потом
    берётся прежний общий набор. Порядок именно такой: доставка обязана
    следовать контракту работающего кода, а не того, который только собираются
    выложить.
    """
    источники: list[Path] = []
    if площадка is not None:
        источники += [площадка.current / "config" / "site.json",
                      площадка.app / "config" / "site.json"]
    if репозиторий is None:
        # Репозиторий ищется сам, а не ждёт, пока его передадут. Без этого
        # ПЕРВЫЙ выпуск ячейки читал контракт из установленного релиза,
        # которого ещё нет, и брал умолчание фабрики. Поймано первым же
        # настоящим переносом Yummy: `stage_snapshot` вызывается из засева, но
        # контракт разрешает заново и путь репозитория до него не доезжал —
        # отказ «в источнике нет файлов снимка ['yummy-biz-details.json']».
        # Параметр остаётся: он нужен проверкам и вызову с чужим деревом.
        try:
            from factory.cell import registry as _registry
            репозиторий = _registry.resolve(site_id).repo_path
        except Exception:  # noqa: BLE001 — нет реестра, нет и подсказки
            репозиторий = None
    if репозиторий is not None:
        источники.append(Path(репозиторий) / "config" / "site.json")
    for путь in источники:
        try:
            объявлено = _json.loads(путь.read_text(encoding="utf-8")).get("data_contract")
        except (OSError, ValueError):
            continue
        if not isinstance(объявлено, dict):
            continue
        доставляемые = tuple(объявлено.get("delivered") or ())
        пользовательские = tuple(объявлено.get("user_writable") or ())
        if доставляемые:
            return {"delivered": доставляемые,
                    "user_writable": пользовательские or (ПОЛЬЗОВАТЕЛЬСКИЕ,),
                    "source": str(путь)}
    return {"delivered": СНИМОК, "user_writable": (ПОЛЬЗОВАТЕЛЬСКИЕ,),
            "source": "умолчание фабрики"}


def снимок_совпадает(источник: Path, цель: Path, site_id: str,
                     доставляемые: tuple[str, ...] | None = None) -> bool:
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

    for шаблон in (*(доставляемые or СНИМОК), *ДОПОЛНЕНИЯ):
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
    контракт = контракт_данных(site_id, площадка=п)
    имена = [ш.format(site=site_id) for ш in контракт["delivered"]]
    свои = [ш.format(site=site_id) for ш in контракт["user_writable"]]
    отсутствуют = [и for и in имена if not (источник / и).is_file()]
    if отсутствуют:
        raise PrivilegedRefused(
            f"{site_id}: в источнике нет файлов снимка {отсутствуют}; "
            "половина снимка хуже прежнего целого")

    если_тот_же = снимок_совпадает(источник, п.data, site_id,
                                   контракт["delivered"])
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
        if запись.name in имена:
            continue
        цель = п.data_candidate / запись.name
        # Пользовательское — ссылкой, и файл тоже, а не только каталог. База
        # оценок Yummy это файл, и копия её означала бы, что оценки, принятые
        # во время прогрева кандидата, останутся в хранилище, которое потом
        # выбросят. Причина та же, что у `site-data`, — значит и обращение
        # должно быть тем же.
        if запись.name in свои or запись.is_dir():
            цель.symlink_to(запись)
        else:
            shutil.copy2(запись, цель)
    for имя in имена:
        shutil.copy2(источник / имя, п.data_candidate / имя)
    # Дополнения переносятся, только если производитель их дал.
    for имя in (ш.format(site=site_id) for ш in ДОПОЛНЕНИЯ):
        if (источник / имя).is_file():
            shutil.copy2(источник / имя, п.data_candidate / имя)
    for имя in свои:
        общие = п.data / имя
        ссылка = п.data_candidate / имя
        if общие.exists() and not ссылка.exists() and not ссылка.is_symlink():
            ссылка.symlink_to(общие)
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
