"""Новый сайт семейства — из ШАБЛОНА, а не с чужого домена.

Зачем отдельно от `extract.py`
------------------------------

`extract.py` выделяет ДЕЙСТВУЮЩИЙ сайт: исполняемые файлы он берёт из каталога
релиза, на который смотрит `current` на хосте. Для выделения это правильно —
переносить надо то, что работает. Для НОВОГО сайта это тупик: он получал бы
рантайм, снятый с соседнего домена, то есть ровно то ручное копирование, из-за
которого исправление, внесённое в шаблон, до новых витрин не доезжает.

Здесь исходник — сам репозиторий шаблона:

    automation/host/lords-frontend.py      рантайм семейства
    automation/host/collection_contract.py контракт подборок
    automation/host/seo_layer.py           слой SEO
    automation/host/lords_sections.py      классификация разделов
    automation/host/community_http.py      обвязка сообщества
    blueprints/lords/profiles/<профиль>.yaml   профиль витрины

и закрепляются они КОММИТОМ ЭТОГО РЕПОЗИТОРИЯ. Тем самым `pins.lock.json`
нового сайта отвечает на вопрос «из какой версии шаблона он собран» одним
значением, а не описанием чужой машины.

Чего здесь по-прежнему нет
--------------------------

Ни домена, ни publisher_id, ни прав на содержимое из воздуха не берётся:
пустое поле — это `BLOCKED_INPUT`, а не умолчание. Канонический модуль
сообщества (`community.py`) сюда не копируется: он принадлежит своему выпуску
и приезжает в ячейку отдельно, закреплённый по версии.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.cell import extract

#: Файлы рантайма семейства. Порядок не важен, состав — важен: недостающий
#: модуль означает витрину, которая молча теряет половину поведения.
РАНТАЙМ_LORDS = (
    "lords-frontend.py",
    "collection_contract.py",
    "seo_layer.py",
    "lords_sections.py",
    "community_http.py",
)

#: Модули, которые в проект НЕ копируются: у них свой владелец и свой выпуск.
ПОСТАВЛЯЕТСЯ_ОТДЕЛЬНО = {
    "community.py": {
        "owner": "claude/community-comments-platform-01 (канонический модуль сообщества)",
        "note": ("Канонический модуль сообщества. Приезжает в ячейку отдельным "
                 "выпуском и закрепляется по версии; копия здесь завела бы "
                 "вторую его реализацию."),
    },
}


class NewSiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class Заказ:
    """Всё, чего в заказе нет, — отсутствующий вход, а не умолчание."""

    site_id: str
    domain: str
    profile: str
    port: int
    family: str = "lords"
    site_name: str = ""

    def пробелы(self) -> list[str]:
        нет = [имя for имя in ("site_id", "domain", "profile", "port")
               if not getattr(self, имя)]
        return нет


def _sha(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def _коммит(корень: Path) -> tuple[str, bool]:
    коммит = subprocess.run(["git", "-C", str(корень), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    грязно = bool(subprocess.run(["git", "-C", str(корень), "status", "--porcelain"],
                                 capture_output=True, text=True,
                                 check=True).stdout.strip())
    return коммит, грязно


def _профиль(корень: Path, семейство: str, профиль: str) -> Path:
    путь = корень / "blueprints" / семейство / "profiles" / f"{профиль}.yaml"
    if not путь.is_file():
        доступные = sorted(
            p.stem for p in (корень / "blueprints" / семейство / "profiles").glob("*.yaml"))
        raise NewSiteError(
            f"профиля {профиль!r} нет в шаблоне; есть: {', '.join(доступные)}")
    return путь


def создать(заказ: Заказ, *, корень: Path, куда: Path,
            force: bool = False) -> dict[str, Any]:
    """Собрать проект нового сайта из шаблона этого репозитория."""
    пробелы = заказ.пробелы()
    if пробелы:
        raise NewSiteError(f"BLOCKED_INPUT: в заказе нет {', '.join(пробелы)}")
    коммит, грязно = _коммит(корень)
    if грязно:
        # Собранное из грязного дерева невоспроизводимо: закрепление назвало бы
        # коммит, которому содержимое файлов не соответствует.
        raise NewSiteError(
            "рабочее дерево шаблона грязное: закрепление по коммиту было бы неправдой")

    профиль_файл = _профиль(корень, заказ.family, заказ.profile)
    источник = корень / "automation" / "host"

    if куда.exists():
        if not force:
            raise NewSiteError(f"{куда} уже существует; нужен force")
        shutil.rmtree(куда)
    куда.mkdir(parents=True)

    аккаунт = extract.account_for(заказ.domain.replace(".", "-"))
    корень_сайта = f"/srv/{аккаунт}"

    # --- рантайм и закрепление ---------------------------------------------
    src = куда / "src"
    src.mkdir()
    files: dict[str, Any] = {}
    for имя in РАНТАЙМ_LORDS:
        откуда = источник / имя
        if not откуда.is_file():
            raise NewSiteError(f"в шаблоне нет файла рантайма {имя}")
        shutil.copy2(откуда, src / имя)
        files[имя] = {
            "sha256": _sha(откуда),
            "bytes": откуда.stat().st_size,
            "verified_against": "git",
            "repo_path": f"automation/host/{имя}",
        }
    for имя, сведения in ПОСТАВЛЯЕТСЯ_ОТДЕЛЬНО.items():
        files[имя] = dict(сведения, sha256="", bytes=0,
                          verified_against="", repo_path="")

    (куда / "pins.lock.json").write_text(json.dumps({
        "schema_version": 1,
        "site_id": заказ.site_id,
        "note": ("Закреплённые версии. Плавающих значений здесь не бывает: "
                 "latest/main/HEAD сделали бы завтрашнюю сборку другой."),
        "pins": {
            "source_commit": коммит,
            "build_id": f"template-{коммит[:12]}",
            "template": заказ.profile,
            "entrypoint": "lords-frontend.py",
            "python": "3.10",
        },
        "files": files,
        "provenance_note": (
            "verified_against: git — байты совпали с исходным коммитом шаблона; "
            "пусто — файл поставляется отдельным выпуском, и его происхождение "
            "здесь не доказывается."),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- настройки ----------------------------------------------------------
    config = {
        "schema_version": 1,
        "site_id": заказ.site_id,
        "domain": заказ.domain,
        "family": заказ.family,
        "port": заказ.port,
        "entrypoint": "lords-frontend.py",
        "template": {"template_id": заказ.profile},
        "publisher_id_ref": f"secret://cdnvideohub/{заказ.family}/publisher-id",
        "publisher_id_expected": None,
        "environment": {
            "LORDS_SITE_ID": заказ.site_id,
            "LORDS_SITE_DOMAIN": заказ.domain,
            "LORDS_SITE_NAME": заказ.site_name or заказ.domain,
            "LORDS_TEMPLATE_MANIFEST": "{app}/config/template-manifest.json",
            "LORDS_PLAYER_CONFIG": "{app}/config/player.json",
            "LORDS_CATALOG": "{data}/" + f"{заказ.site_id}-catalog.json",
            "LORDS_DETAILS": "{data}/" + f"{заказ.site_id}-details.json",
            "LORDS_LEGACY_ROOT": "{data}/site",
        },
        "neighbour_site_ids": [],
        "neighbour_note": (
            "Умолчания рантайма ведут к соседним сайтам. Запуск отказывает, "
            "если хоть один путь указывает на соседа."),
        "indexing_note": "Режим индексации задаёт владелец до публикации.",
        "deployment": {
            "root": корень_сайта,
            "release_parent": f"{корень_сайта}/releases",
            "current_link": f"{корень_сайта}/current",
            "data_dir": f"{корень_сайта}/data",
            "unit": f"nova-{аккаунт}.service",
            "account": аккаунт,
            "port": заказ.port,
            "note": ("Выпуски лежат рядом в releases/<12 знаков коммита>, "
                     "работает тот, на который смотрит ссылка current."),
        },
    }
    (куда / "config").mkdir()
    (куда / "config" / "site.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (куда / "config" / "player.json.example").write_text(
        json.dumps({"_note": "Образец. Настоящий player.json в git не попадает.",
                    "publisher_id": "<из Secret Hub>",
                    "source_mode": "provider-id"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    # --- манифест шаблона ---------------------------------------------------
    #
    # Сведения о выпуске пусты: заполненное здесь значение пережило бы свой
    # выпуск и продолжило бы называть его цифры. Проставляет их сборка.
    манифест = {
        "schema_version": 1,
        "template_family": заказ.family,
        "design_version": версия_шаблона(корень),
        "profile": заказ.profile,
        extract.ПОЛЕ_ПРОИСХОЖДЕНИЯ: {
            "source_commit": коммит,
            "build_id": f"template-{коммит[:12]}",
            "template_family": заказ.family,
            "design_version": версия_шаблона(корень),
            "note": "Происхождение закреплённого шаблона. Сборкой не меняется.",
        },
        "build_id": "worktree-unbuilt",
    }
    for поле in extract.ПОЛЯ_ВЫПУСКА:
        if поле in ("source_dirty", "site_repo_dirty"):
            манифест.setdefault(поле, False)
        else:
            манифест.setdefault(поле, "")
    манифест["build_id"] = "worktree-unbuilt"
    (куда / "config" / "template-manifest.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    shutil.copy2(профиль_файл, куда / "config" / "profile.yaml")

    # --- запуск, проверки, выкладка ----------------------------------------
    (куда / "run.py").write_text(
        extract.LAUNCHER.format(domain=заказ.domain), encoding="utf-8")
    (куда / "run.py").chmod(0o755)
    (куда / ".gitignore").write_text(
        "# Данные и секреты сайта в Git не хранятся.\n"
        "config/player.json\ndata/\nvar/\ndist/\n*-catalog.json\n*-details.json\n"
        "*community*.json\n__pycache__/\n*.pyc\n", encoding="utf-8")

    extract.add_tooling(куда, заказ.site_id, заказ.domain)
    extract.add_deploy(куда, site_id=заказ.site_id, domain=заказ.domain,
                       account=аккаунт, old_unit="", port=заказ.port,
                       old_root="")

    (куда / "README.md").write_text(
        f"# {заказ.domain}\n\nСайт `{заказ.site_id}` семейства "
        f"`{заказ.family}`, профиль `{заказ.profile}`.\n\n"
        f"Собран из шаблона `sbc-create/test` коммита `{коммит[:12]}` — не с "
        f"чужого домена. Исправления семейства приезжают сюда продвижением "
        f"версии в `pins.lock.json`, а не копированием файлов.\n\n"
        "## Запуск с чистого клона\n\n```bash\n"
        "cp config/player.json.example config/player.json   # значение из Secret Hub\n"
        f"python3 run.py --check --data-dir {корень_сайта}/data\n"
        f"python3 run.py --port {заказ.port} --data-dir {корень_сайта}/data\n```\n\n"
        "## Чего здесь нет\n\nСнимков каталога, страниц, комментариев, голосов и "
        "секретов: это данные, они доставляются отдельно. Канонического модуля "
        "сообщества тоже нет — он приезжает своим выпуском.\n",
        encoding="utf-8")
    (куда / "AGENTS.md").write_text(
        f"# AGENTS.md — проект сайта {заказ.site_id}\n\n"
        f"Этот репозиторий — один сайт: **{заказ.domain}**.\n\n"
        "1. Только этот сайт. Задача не переходит в соседний проект.\n"
        "2. Массовая замена по всей фабрике запрещена.\n"
        "3. Общее ядро меняется отдельной задачей в репозитории шаблона и "
        "приезжает сюда отдельным коммитом, поднимающим версию в "
        "`pins.lock.json`.\n"
        "4. Плавающих версий не бывает.\n"
        "5. Данные и секреты не коммитятся.\n"
        "6. Живой код по SSH не правится.\n", encoding="utf-8")

    return {
        "site_id": заказ.site_id,
        "domain": заказ.domain,
        "profile": заказ.profile,
        "path": str(куда),
        "template_commit": коммит,
        "design_version": версия_шаблона(корень),
        "runtime_files": list(РАНТАЙМ_LORDS),
        "delivered_separately": sorted(ПОСТАВЛЯЕТСЯ_ОТДЕЛЬНО),
    }


def версия_шаблона(корень: Path) -> str:
    """Версия оформления семейства из журнала версий шаблона."""
    путь = корень / "status" / "lords-template-version.json"
    try:
        return str(json.loads(путь.read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError) as ош:
        raise NewSiteError(
            f"версия шаблона не объявлена в {путь}: {ош}") from ош
