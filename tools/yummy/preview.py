#!/usr/bin/env python3
"""Изолированный локальный предпросмотр трёх витрин Yummy.

Зачем отдельный инструмент
--------------------------

Проверять паритет на боевых процессах нельзя: они принадлежат выкату, их
порты заняты другими контурами, а перезапуск запрещён. Проверять на фикстуре
недостаточно: фикстура описывает контракт, но не отвечает на вопрос «что
увидит посетитель на настоящем каталоге».

Поэтому здесь поднимается СВОЙ рантайм из рабочего дерева на СВОИХ портах,
против СНИМКА боевых данных и того же приложения, что стоит наверху у боевых
витрин. Ничего в `/srv` не пишется, чужие процессы не трогаются.

Что берётся откуда
------------------

* код — из рабочего дерева (`automation/host/`), а не из `/srv`;
* каталог и read-model — снимок, сделанный заранее (`--data`);
* приложение наверху — те же адреса, что объявлены юнитами `nova-yummy-*`;
  запросы к нему только читающие.

Манифест собирается здесь же и объявляет ПРАВДУ о предпросмотре: ревизию
рабочего дерева и sha256 по шести выкатываемым модулям. Подставлять сюда
манифест боевой сборки нельзя — витрина объявила бы версию, которой не
соответствует её собственный код.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ХОСТ = КОРЕНЬ / "automation" / "host"

#: Шесть выкатываемых модулей. Хэш артефакта считается по всем: правка в любом
#: обязана его двигать, иначе «та же версия» перестаёт что-либо значить.
МОДУЛИ = ("yummy-frontend.py", "yummy_pages.py", "yummy_entity.py",
          "yummy_contract.py", "yummy_readmodel.py", "yummy_variants.py")

#: Профиль → (домен, верховое приложение, variant_id). Адреса приложения взяты
#: из юнитов `nova-yummy-*`, а не угаданы.
ПРОФИЛИ = {
    "site": ("yummyani.site", "127.0.0.1:3101", "catalog-search"),
    "org": ("yummyani.org", "127.0.0.1:3102", "episodes-schedule"),
    "biz": ("yummyani.biz", "127.0.0.1:3103", "editorial-guide"),
}

#: Порт предпросмотра по профилю. 9130–9148 занято боевыми и чужими контурами;
#: 9142/9143 принадлежат активному контуру индексации и не трогаются.
ПОРТЫ = {"site": 9310, "org": 9311, "biz": 9312}


def артефакт() -> str:
    ч = hashlib.sha256()
    for имя in МОДУЛИ:
        ч.update((ХОСТ / имя).read_bytes())
    return ч.hexdigest()


def ревизия() -> str:
    try:
        return subprocess.run(["git", "-C", str(КОРЕНЬ), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "0" * 40


def манифест(куда: Path, профиль: str) -> Path:
    домен, _, вариант = ПРОФИЛИ[профиль]
    голова = ревизия()
    файл = куда / f"manifest-{профиль}.json"
    файл.write_text(json.dumps({
        "schema_version": 1,
        "template_family": "yummy",
        # Предпросмотр не выдаёт себя за боевую сборку: суффикс назван прямо.
        "design_version": f"{версия_дерева()}+preview",
        "source_commit": голова,
        "build_id": f"preview-{голова[:8]}-{профиль}",
        "artifact_sha256": артефакт(),
        "profile": "yummy-anime",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_version": "1.2.0",
        "variant_id": вариант,
        "variant_version": "1.0.0",
        "preview": True,
        "preview_domain": домен,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return файл


def версия_дерева() -> str:
    """Версия шаблона берётся из документа готовности, а не придумывается."""
    док = КОРЕНЬ / "docs" / "YUMMY-TEMPLATE-READINESS.md"
    try:
        for строка in док.read_text(encoding="utf-8").splitlines():
            if строка.startswith("Версия шаблона:"):
                return строка.split("**")[1].strip()
    except (OSError, IndexError):
        pass
    return "0.0.0"


def свободен(порт: int) -> bool:
    с = socket.socket()
    с.settimeout(0.3)
    занят = с.connect_ex(("127.0.0.1", порт)) == 0
    с.close()
    return not занят


def окружение(куда: Path, данные: Path, профиль: str) -> dict:
    домен, верх, _ = ПРОФИЛИ[профиль]
    о = dict(os.environ)
    о.update({
        "LORDS_TEMPLATE_MANIFEST": str(манифест(куда, профиль)),
        "LORDS_CATALOG": str(данные / f"catalog-{профиль}.json"),
        "LORDS_SITE_NAME": "YummyAnime",
        "LORDS_LEGACY_UPSTREAM": верх,
        "LORDS_LEGACY_ROOT": str(куда / "нет-статического-корня"),
        "YUMMY_VARIANT_DOMAIN": домен,
        "YUMMY_READMODEL": str(данные / "readmodel.sqlite3"),
        "LORDS_TEMPLATE_REVISION": ревизия(),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return о


def поднять(куда: Path, данные: Path, профили: list[str], ждать: float) -> int:
    куда.mkdir(parents=True, exist_ok=True)
    беда = 0
    for профиль in профили:
        порт = ПОРТЫ[профиль]
        if not свободен(порт):
            print(f"[preview] {профиль}: порт {порт} занят — не поднимаю", file=sys.stderr)
            беда = 1
            continue
        журнал = (куда / f"{профиль}.log").open("wb")
        процесс = subprocess.Popen(
            [sys.executable, str(ХОСТ / "yummy-frontend.py"), "--port", str(порт)],
            env=окружение(куда, данные, профиль), stdout=журнал,
            stderr=subprocess.STDOUT, start_new_session=True)
        (куда / f"{профиль}.pid").write_text(str(процесс.pid), encoding="utf-8")
        if not дождаться(порт, ждать):
            print(f"[preview] {профиль}: не ответил на /healthz за {ждать} с "
                  f"— смотри {куда / (профиль + '.log')}", file=sys.stderr)
            беда = 1
            continue
        print(f"[preview] {профиль} → http://127.0.0.1:{порт} (pid {процесс.pid})")
    return беда


def дождаться(порт: int, предел: float) -> bool:
    край = time.time() + предел
    while time.time() < край:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{порт}/healthz", timeout=2).read()
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    return False


def погасить(куда: Path, профили: list[str]) -> int:
    """Гасятся только СВОИ процессы: pid берётся из своего же pid-файла."""
    for профиль in профили:
        файл = куда / f"{профиль}.pid"
        if not файл.is_file():
            continue
        try:
            pid = int(файл.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        # Проверка владения: чужой процесс не гасится, даже если pid совпал.
        if not наш(pid):
            print(f"[preview] {профиль}: pid {pid} не наш — не трогаю", file=sys.stderr)
            файл.unlink(missing_ok=True)
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[preview] {профиль}: остановлен pid {pid}")
        except ProcessLookupError:
            pass
        файл.unlink(missing_ok=True)
    return 0


def наш(pid: int) -> bool:
    try:
        строка = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except OSError:
        return False
    return "yummy-frontend.py" in строка and str(ХОСТ) in строка


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("действие", choices=("up", "down", "ports"))
    р.add_argument("--data", required=False, help="каталог со снимком данных")
    р.add_argument("--run", required=True, help="каталог для pid, логов и манифестов")
    р.add_argument("--profiles", default="site,org,biz")
    р.add_argument("--wait", type=float, default=30.0)
    а = р.parse_args()
    профили = [п.strip() for п in а.profiles.split(",") if п.strip()]
    неизвестные = [п for п in профили if п not in ПРОФИЛИ]
    if неизвестные:
        print(f"неизвестные профили: {неизвестные}", file=sys.stderr)
        return 2
    куда = Path(а.run)
    if а.действие == "ports":
        for п in профили:
            print(f"{п} {ПОРТЫ[п]} {'свободен' if свободен(ПОРТЫ[п]) else 'занят'}")
        return 0
    if а.действие == "down":
        return погасить(куда, профили)
    if not а.data:
        print("--data обязателен для up", file=sys.stderr)
        return 2
    return поднять(куда, Path(а.data), профили, а.wait)


if __name__ == "__main__":
    raise SystemExit(main())
