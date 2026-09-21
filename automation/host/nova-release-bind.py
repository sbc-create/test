#!/usr/bin/env python3
"""Неизменяемые релизы витрин и привязка каждой витрины к своему релизу.

## Что здесь решается

Общий путь `/srv/lords/.frontend/lords-frontend.py` исполняют шесть юнитов трёх
семейств. Пока по нему лежал сам рантайм, выкладка одной витрины переписывала
байты у всех шести. Эта процедура убирает саму возможность: код уезжает в
неизменяемые каталоги `releases/<build_id>/`, а витрина получает символическую
ссылку `sites/<витрина>/current` на свой релиз. Выкладка переставляет одну
ссылку и не может дотянуться до соседа.

## Почему сборка идёт из коммита, а не из рабочих файлов

`git show <commit>:<path>` отдаёт байты, записанные в истории. Копирование
рабочего файла отдаёт то, что лежит на диске прямо сейчас, — и именно так
появился артефакт, собранный из грязного дерева и объявивший `source_dirty=false`.
Здесь такое невозможно: дерево обязано быть чистым, и проверка идёт до сборки,
а байты берутся из объекта коммита.

## Состав релиза

Рантайм импортирует соседей по собственному каталогу (`seo_layer` обязателен,
`collection_contract` необязателен). Поэтому релиз — каталог, а не файл: иначе
после `execv` импорт ушёл бы в общий каталог и неизменяемость релиза была бы
показной.

Подкоманды:

    build            собрать релиз из чистого HEAD
    freeze-legacy    заморозить то, что исполняется сейчас, для витрин вне задания
    bind             привязать витрину к релизу (переставить ссылку)
    install-loader   поставить загрузчик и реестр по общему пути
    status           показать текущие привязки
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import importlib.util
import shutil
import subprocess
import sys
import time

FRONT = pathlib.Path("/srv/lords/.frontend")
RUNTIME_NAME = "lords-frontend.py"

#: Состав релиза: имя в релизе → путь в репозитории. Обязательность важна:
#: отсутствие seo_layer роняет витрину на импорте, отсутствие contract — нет.
СОСТАВ = {
    RUNTIME_NAME: ("automation/host/lords-frontend.py", True),
    "seo_layer.py": ("automation/host/seo_layer.py", True),
    "collection_contract.py": ("automation/host/collection_contract.py", False),
}

OK = 0
ОТКАЗ = 2


class Отказ(Exception):
    """Условие, при котором продолжать нельзя."""


def _реестр() -> dict:
    """Exact-domain реестр: единственный источник имён юнитов и портов."""
    путь = pathlib.Path(__file__).resolve().parent / "nova-runtime-registry.py"
    spec = importlib.util.spec_from_file_location("nova_runtime_registry", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль.build()


def _repo() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=_repo(), capture_output=True, text=True)
    if res.returncode != 0:
        raise Отказ(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def _git_bytes(*args: str) -> bytes:
    res = subprocess.run(["git", *args], cwd=_repo(), capture_output=True)
    if res.returncode != 0:
        raise Отказ(f"git {' '.join(args)}: {res.stderr.decode(errors='replace').strip()}")
    return res.stdout


def требовать_чистое_дерево() -> str:
    """HEAD, если дерево чисто. Иначе отказ — до всякой записи на хост.

    Грязное дерево означает, что байты артефакта нельзя вывести из истории, а
    значит и объявить их происхождение правдиво. Единственный честный выход —
    не собирать.
    """
    статус = _git("status", "--porcelain=v1").strip()
    if статус:
        строки = [s for s in статус.splitlines() if s.strip()]
        raise Отказ(
            f"дерево грязное ({len(строки)} путей), сборка из него запрещена: "
            + "; ".join(строки[:5])
        )
    return _git("rev-parse", "HEAD").strip()


def _записать_неизменяемым(путь: pathlib.Path, данные: bytes) -> str:
    путь.write_bytes(данные)
    путь.chmod(0o444)
    return hashlib.sha256(данные).hexdigest()


def собрать(build_suffix: str = "release") -> dict:
    commit = требовать_чистое_дерево()
    метка = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_id = f"{метка}-{commit[:7]}-{build_suffix}"
    каталог = FRONT / "releases" / build_id
    if каталог.exists():
        raise Отказ(f"релиз уже существует: {каталог}")
    каталог.mkdir(parents=True)

    файлы = {}
    for имя, (путь_в_репо, обязателен) in СОСТАВ.items():
        try:
            данные = _git_bytes("show", f"{commit}:{путь_в_репо}")
        except Отказ:
            if обязателен:
                shutil.rmtree(каталог)
                raise
            continue
        файлы[имя] = {
            "repo_path": путь_в_репо,
            "sha256": _записать_неизменяемым(каталог / имя, данные),
            "bytes": len(данные),
        }

    манифест = {
        "schema_version": 1,
        "build_id": build_id,
        "source_commit": commit,
        # Правда, а не пожелание: дерево проверено выше, иначе сюда не дошли бы.
        "source_dirty": False,
        "built_from": "git object",
        "built_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "release_dir": str(каталог),
        "artifact_sha256": файлы[RUNTIME_NAME]["sha256"],
        "files": файлы,
    }
    (каталог / "RELEASE.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (каталог / "RELEASE.json").chmod(0o444)
    return манифест


def заморозить_текущее() -> dict:
    """Снимок того, что исполняется сейчас, — для витрин вне задания.

    Витрины animedia и zona исполняют тот же общий файл, но в это задание не
    входят. Замораживание даёт им ровно их сегодняшний код: при следующем
    перезапуске они получат то же, что получили бы и без всей этой правки, но
    уже из неизменяемого каталога, недостижимого для чужой выкладки.
    """
    источник = FRONT / RUNTIME_NAME
    if not источник.is_file():
        raise Отказ(f"нет общего файла {источник}")
    цифра = hashlib.sha256(источник.read_bytes()).hexdigest()
    каталог = FRONT / "releases" / f"legacy-{цифра[:12]}"
    if not каталог.exists():
        каталог.mkdir(parents=True)
        файлы = {}
        for имя in СОСТАВ:
            рядом = FRONT / имя
            if рядом.is_file():
                файлы[имя] = _записать_неизменяемым(каталог / имя, рядом.read_bytes())
        (каталог / "RELEASE.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "build_id": каталог.name,
                    "source_commit": "UNKNOWN_FROZEN_FROM_HOST",
                    "source_dirty": "UNKNOWN",
                    "built_from": "снимок общего пути на момент развязки",
                    "frozen_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    "artifact_sha256": цифра,
                    "files": файлы,
                    "note": "происхождение не выводится из истории и объявлено неизвестным намеренно",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (каталог / "RELEASE.json").chmod(0o444)
    переставить_ссылку(FRONT / "releases" / "legacy" / "current", каталог)
    return {"legacy_dir": str(каталог), "artifact_sha256": цифра}


def переставить_ссылку(ссылка: pathlib.Path, цель: pathlib.Path) -> None:
    """Атомная перестановка символической ссылки.

    Через временное имя и `os.replace`: иначе между удалением старой ссылки и
    созданием новой существует окно, в котором витрина не может стартовать.
    """
    ссылка.parent.mkdir(parents=True, exist_ok=True)
    временная = ссылка.parent / f".{ссылка.name}.new"
    if временная.is_symlink() or временная.exists():
        временная.unlink()
    относительный = os.path.relpath(цель, ссылка.parent)
    временная.symlink_to(относительный, target_is_directory=True)
    os.replace(временная, ссылка)


def привязать(витрина: str, build_id: str) -> dict:
    цель = FRONT / "releases" / build_id
    if not (цель / RUNTIME_NAME).is_file():
        raise Отказ(f"в релизе {build_id} нет {RUNTIME_NAME}")
    ссылка = FRONT / "sites" / витрина / "current"
    прежняя = os.readlink(ссылка) if ссылка.is_symlink() else None
    переставить_ссылку(ссылка, цель)
    return {
        "site": витрина,
        "link": str(ссылка),
        "previous_target": прежняя,
        "target": str(цель),
        "artifact_sha256": hashlib.sha256((цель / RUNTIME_NAME).read_bytes()).hexdigest(),
    }


def поставить_загрузчик(реестр_файл: str) -> dict:
    """Загрузчик и реестр по общему пути, с точкой отката до первой записи."""
    загрузчик = pathlib.Path(__file__).resolve().parent / "nova-runtime-dispatch.py"
    if not загрузчик.is_file():
        raise Отказ(f"нет загрузчика {загрузчик}")
    общий = FRONT / RUNTIME_NAME
    метка = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    откат = FRONT / ".rollback" / f"{метка}-pre-loader"
    откат.mkdir(parents=True, exist_ok=True)
    прежний_digest = ""
    if общий.is_file():
        прежний_digest = hashlib.sha256(общий.read_bytes()).hexdigest()
        shutil.copy2(общий, откат / RUNTIME_NAME)

    # Реестр кладётся ДО загрузчика: загрузчик без реестра уводит все витрины
    # в запасной путь, и это выглядело бы как успешная установка.
    shutil.copy2(реестр_файл, FRONT / "lords-runtime-registry.json")

    временный = FRONT / f".{RUNTIME_NAME}.new"
    shutil.copy2(загрузчик, временный)
    временный.chmod(0o755)
    os.replace(временный, общий)
    return {
        "loader_installed_at": str(общий),
        "previous_shared_sha256": прежний_digest,
        "rollback_dir": str(откат),
        "registry": str(FRONT / "lords-runtime-registry.json"),
    }


#: Поля манифеста, принадлежащие витрине, а не сборке. Они переносятся из
#: прежнего манифеста: профиль и домен не меняются оттого, что вышел новый код.
ПОЛЯ_ВИТРИНЫ = (
    "schema_version", "template_family", "design_version", "profile", "domain",
    "player_layout_contract", "core_runtime", "family_template",
)


def переоформить_манифест(витрина: str, build_id: str, реестр: dict) -> dict:
    """Манифест витрины из RELEASE.json: правдиво и с сохранением полей витрины.

    Поля происхождения берутся из релиза, а не из желания: `source_commit`,
    `source_dirty` и `artifact_sha256` уже проверены сборкой, которая
    отказывается работать на грязном дереве.
    """
    запись = (реестр.get("sites") or {}).get(витрина)
    if not запись:
        raise Отказ(f"витрины {витрина} нет в реестре")
    релиз = FRONT / "releases" / build_id
    try:
        сведения = json.loads((релиз / "RELEASE.json").read_text())
    except (OSError, ValueError) as ошибка:
        raise Отказ(f"нет или нечитаем RELEASE.json релиза {build_id}: {ошибка}")

    путь = pathlib.Path(запись["manifest_path"])
    прежний = {}
    if путь.is_file():
        try:
            прежний = json.loads(путь.read_text())
        except ValueError:
            прежний = {}
        метка = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        откат = FRONT / ".rollback" / f"{метка}-{витрина}-manifest"
        откат.mkdir(parents=True, exist_ok=True)
        shutil.copy2(путь, откат / путь.name)

    новый = {ключ: прежний[ключ] for ключ in ПОЛЯ_ВИТРИНЫ if ключ in прежний}
    новый.setdefault("schema_version", 1)
    новый.setdefault("domain", запись.get("exact_domain") or "")
    новый.update({
        "source_commit": сведения["source_commit"],
        "source_dirty": сведения["source_dirty"],
        "build_id": сведения["build_id"],
        "artifact_sha256": сведения["artifact_sha256"],
        "release_dir": сведения["release_dir"],
        "built_at": сведения["built_at"],
        "built_from": сведения["built_from"],
        "bound_release_link": запись["release_link"],
    })
    временный = путь.parent / f".{путь.name}.new"
    временный.write_text(json.dumps(новый, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(временный, путь)
    return {"site": витрина, "manifest": str(путь), "previous": прежний, "current": новый}


def перезапустить(витрина: str, реестр: dict) -> dict:
    """Перезапуск ОДНОЙ витрины с проверкой результата по факту, а не по коду.

    Про сообщение «Failed to allocate directory watch: Too many open files».
    Оно приходит от systemd при исчерпании inotify и НЕ означает, что служба не
    перезапустилась. Поэтому успех определяется не кодом возврата, а сменой PID
    и временем старта нового процесса.
    """
    запись = (реестр.get("sites") or {}).get(витрина)
    if not запись:
        raise Отказ(f"витрины {витрина} нет в реестре")
    юнит = запись["unit"]
    порт = int(запись["port"])

    до = _процесс_на_порту(порт)
    результат = subprocess.run(
        ["systemctl", "restart", юнит], capture_output=True, text=True
    )
    вывод = (результат.stdout + результат.stderr).strip()

    # Ждём смены PID: процесс поднимается не мгновенно.
    после = None
    for _ in range(30):
        после = _процесс_на_порту(порт)
        if после and (not до or после["pid"] != до["pid"]):
            break
        time.sleep(1)

    сменился = bool(после) and (not до or после["pid"] != до["pid"])
    return {
        "site": витрина,
        "unit": юнит,
        "command": f"systemctl restart {юнит}",
        "returncode": результат.returncode,
        "output": вывод,
        "inotify_warning": "Too many open files" in вывод,
        "pid_before": до["pid"] if до else None,
        "pid_after": после["pid"] if после else None,
        "started_after_utc": после["started_utc"] if после else "",
        "restarted": сменился,
        "verdict": "RESTARTED" if сменился else (
            "NOT_RESTARTED_PRIVILEGE_OR_FAILURE" if результат.returncode != 0 else "NOT_RESTARTED"
        ),
    }


def _процесс_на_порту(порт: int) -> dict | None:
    hz = os.sysconf("SC_CLK_TCK")
    btime = 0.0
    for line in pathlib.Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime"):
            btime = float(line.split()[1])
            break
    for запись in pathlib.Path("/proc").iterdir():
        if not запись.name.isdigit():
            continue
        try:
            сырое = (запись / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        части = [ч for ч in сырое.split("\0") if ч]
        if RUNTIME_NAME not in сырое:
            continue
        for i, ч in enumerate(части):
            if ч == "--port" and i + 1 < len(части) and части[i + 1] == str(порт):
                try:
                    поля = (запись / "stat").read_text().rsplit(")", 1)[1].split()
                    начало = _dt.datetime.fromtimestamp(
                        btime + int(поля[19]) / hz, _dt.timezone.utc
                    ).isoformat()
                except (OSError, IndexError, ValueError):
                    начало = ""
                скрипт = next((ч for ч in части[1:] if ч.endswith(".py")), "")
                return {"pid": int(запись.name), "started_utc": начало, "exec_script": скрипт}
    return None


def статус() -> dict:
    sites = {}
    корень = FRONT / "sites"
    if корень.is_dir():
        for каталог in sorted(корень.iterdir()):
            ссылка = каталог / "current"
            if not ссылка.is_symlink():
                continue
            цель = ссылка.resolve(strict=False)
            runtime = цель / RUNTIME_NAME
            sites[каталог.name] = {
                "target": str(цель),
                "artifact_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest()
                if runtime.is_file()
                else "",
            }
    общий = FRONT / RUNTIME_NAME
    return {
        "shared_path": str(общий),
        "shared_sha256": hashlib.sha256(общий.read_bytes()).hexdigest()
        if общий.is_file()
        else "",
        "shared_is_loader": общий.is_file() and b"LORDS_RUNTIME_DISPATCHED" in общий.read_bytes(),
        "bindings": sites,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--suffix", default="release")
    sub.add_parser("freeze-legacy")
    p = sub.add_parser("bind")
    p.add_argument("--site", required=True)
    p.add_argument("--build", required=True)
    i = sub.add_parser("install-loader")
    i.add_argument("--registry", required=True)
    m = sub.add_parser("stage-manifest")
    m.add_argument("--site", required=True)
    m.add_argument("--build", required=True)
    r = sub.add_parser("restart")
    r.add_argument("--site", required=True)
    sub.add_parser("status")
    args = parser.parse_args()

    try:
        if args.cmd == "build":
            результат = собрать(args.suffix)
        elif args.cmd == "freeze-legacy":
            результат = заморозить_текущее()
        elif args.cmd == "bind":
            результат = привязать(args.site, args.build)
        elif args.cmd == "install-loader":
            результат = поставить_загрузчик(args.registry)
        elif args.cmd == "stage-manifest":
            результат = переоформить_манифест(args.site, args.build, _реестр())
        elif args.cmd == "restart":
            результат = перезапустить(args.site, _реестр())
        else:
            результат = статус()
    except Отказ as ошибка:
        print(f"ОТКАЗ: {ошибка}", file=sys.stderr)
        return ОТКАЗ
    print(json.dumps(результат, ensure_ascii=False, indent=2))
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
