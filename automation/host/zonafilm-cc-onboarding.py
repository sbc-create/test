#!/usr/bin/env python3
"""Заведение zonafilm.cc (tenant zona-02) по этапам архитектора.

Второго конвейера здесь нет: этапы, их порядок, ledger и правило «повтор
продолжает, а не начинает заново» берутся из ``factory.cell.onboarding``.
Этот файл — только исполнители этапов для одного конкретного сайта.

Идемпотентность — не украшение. Повторный запуск обязан вернуть тот же
репозиторий, то же назначение шаблона и тот же site_id, а не завести вторые.

Что этот файл не делает намеренно: не переключает DNS, не выпускает
сертификат, не ставит unit и не открывает индексацию. Проверка готовности и
выполнение — разные вещи.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

РЕПО = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(РЕПО))

from factory.cell import onboarding, registry, siterepo  # noqa: E402
from factory.paths import PATHS  # noqa: E402

ORDER_ID = "zona-02-launch-01"
SITE_ID = "zona-02"
DOMAIN = "zonafilm.cc"
ALIASES = ("www.zonafilm.cc",)
FAMILY = "zona"
DEPLOY_TARGET = "claude-control-01"
ORIGIN_IPV4 = "45.131.182.225"

#: Назначение шаблона уже существует и сохраняется. Источник — не манифест
#: пакета, а факт исполнения: template-manifest-zona-02.json и sha256 файла,
#: который витрина исполняет. Пул шаблонов здесь не расходуется: семейства
#: `zona` в нём нет, все четыре шаблона пула закреплены за lords-01..04.
ЗАКРЕПЛЁННЫЙ_ШАБЛОН = {
    "template_id": "zona-general",
    "family": FAMILY,
    "design_version": "1.2.0",
    "pinned_release": "zona-slider-2650fad6",
    "code_sha256": "7ccf094a1d7f2b5e648a38f51f6a63de9627576637d96f6c966fe1759ad8fa1e",
    "source_commit": "5863d296264867f85138bd771f1b90a86ac9c599",
    "manifest": "/srv/lords/.frontend/template-manifest-zona-02.json",
}

РАНТАЙМ = Path("/srv/lords/.frontend")
КОРЕНЬ_САЙТА = РАНТАЙМ / "sites" / SITE_ID
РЕЛИЗ_НА_ДИСКЕ = РАНТАЙМ / "releases" / "zona-02-1015c650d8be"

#: Модули релиза. Перечень закрыт: список файлов, которые витрина реально
#: исполняет, а не «всё, что лежит рядом».
МОДУЛИ_РЕЛИЗА = (
    "lords-frontend.py",
    "collection_contract.py",
    "community_ratings_overlay.py",
    "genre_aliases.py",
    "nova_core_indexability.py",
    "popular_weekly.py",
    "seo_layer.py",
)

PUBLISHER_ID = "10238"


def ledger_root() -> Path:
    root = PATHS.var / "cells" / "onboarding"
    root.mkdir(parents=True, exist_ok=True)
    return root


def заказ() -> onboarding.Order:
    return onboarding.Order(
        order_id=ORDER_ID, site_id=SITE_ID, domain=DOMAIN, family=FAMILY,
        content_profile=ЗАКРЕПЛЁННЫЙ_ШАБЛОН["template_id"],
        deploy_target=DEPLOY_TARGET, aliases=ALIASES,
        publisher_id=PUBLISHER_ID,
        publisher_id_ref="secret://cdnvideohub/lords/lords-01/publisher-id",
        modules=МОДУЛИ_РЕЛИЗА,
    )


# --------------------------------------------------------------------------
# Этапы
# --------------------------------------------------------------------------
def проба_dns(домен: str) -> dict:
    """Что видно про домен отсюда. Неизмеримое называется None, а не False."""
    адреса: list[str] = []
    причина = None
    try:
        адреса = sorted({r[4][0] for r in socket.getaddrinfo(домен, None)})
    except OSError as exc:
        причина = f"{type(exc).__name__}: {exc}"
    # NS отсюда не спросить: `dig` вне профиля, а зона не в inventory/dns-zones.
    # Делегация подтверждена отдельной пробой, её отчёт лежит в evidence.
    делегация = РЕПО / (
        "artifacts/evidence/release-zonafilm-cc-full-cycle-01/03-dns/zonafilm-cc.json")
    ns: list[str] = []
    if делегация.exists():
        отчёт = json.loads(делегация.read_text(encoding="utf-8"))
        ns = list(отчёт.get("expected_ns") or [])
    return {
        "ns": ns,
        "ns_evidence": str(делегация.relative_to(РЕПО)) if делегация.exists() else None,
        "addresses": адреса,
        "address_matches_target": (ORIGIN_IPV4 in адреса) if адреса else False,
        "expected_a": ORIGIN_IPV4,
        "https_ready": None if not адреса else None,
        "resolve_error": причина,
    }


def этап_домен(order: onboarding.Order) -> dict:
    проверка = onboarding.validate_domain(order, probe=проба_dns)
    итог = проверка.to_dict()
    if not итог["ns_present"]:
        raise onboarding.StageBlocked(
            "делегация зоны не подтверждена: отчёт пробы DNS отсутствует")
    # Отсутствие A — не провал этапа: домен делегирован, запись создаётся
    # владельцем в панели. Этап фиксирует ровно то, что видно.
    итог["verdict"] = (
        "DELEGATED_NO_RECORDS" if not итог["observed"]["addresses"] else "RESOLVES")
    итог["cutover_blocked_by"] = (
        [] if итог["ready_for_cutover"]
        else ["A-запись apex и www отсутствуют; зона Cloudflare, учётных данных нет"])
    return итог


def этап_site_id(order: onboarding.Order) -> dict:
    """site_id постоянный и выдан аллокатором. Здесь он сверяется, а не выдаётся."""
    доказательство = РЕПО / (
        "artifacts/evidence/release-zonafilm-cc-full-cycle-01/04-site-creation/allocation.json")
    if not доказательство.exists():
        raise onboarding.StageBlocked("нет отчёта аллокатора: site_id выдавать заново нельзя")
    отчёт = json.loads(доказательство.read_text(encoding="utf-8"))
    выдано = отчёт.get("allocation") or отчёт
    site_id = выдано.get("site_id")
    порт = выдано.get("port")
    юнит = выдано.get("service_name")
    if site_id != SITE_ID:
        raise onboarding.StageBlocked(
            f"аллокатор выдал {site_id}, а задание про {SITE_ID}: расхождение не додумывается")
    # Порт обязан совпасть с живым реестром рантайма, иначе витрина встанет
    # на чужой сокет. Сверяем с реестром, а не с отчётом о самом себе.
    реестр = json.loads((РАНТАЙМ / "lords-runtime-registry.json").read_text(encoding="utf-8"))
    запись = (реестр.get("sites") or {}).get(SITE_ID) or {}
    if запись.get("port") != порт or запись.get("unit") != юнит:
        raise onboarding.StageBlocked(
            f"реестр рантайма называет порт {запись.get('port')} и юнит "
            f"{запись.get('unit')}, аллокатор — {порт} и {юнит}")
    соседи = {k: v.get("port") for k, v in (реестр.get("sites") or {}).items() if k != SITE_ID}
    if порт in соседи.values():
        занял = [k for k, v in соседи.items() if v == порт]
        raise onboarding.StageBlocked(f"порт {порт} уже закреплён за {занял}")
    свободен = socket.socket()
    свободен.settimeout(1.5)
    занят = свободен.connect_ex(("127.0.0.1", порт)) == 0
    свободен.close()
    return {
        "site_id": site_id, "port": порт, "unit": юнит,
        "port_busy_now": занят,
        "neighbour_ports": соседи,
        "evidence": str(доказательство.relative_to(РЕПО)),
        "allocated": False, "reused": True,
    }


def этап_шаблон(order: onboarding.Order) -> dict:
    """Существующее назначение сохраняется. Второй шаблон не расходуется."""
    манифест = Path(ЗАКРЕПЛЁННЫЙ_ШАБЛОН["manifest"])
    if not манифест.exists():
        raise onboarding.StageBlocked(f"манифеста шаблона нет: {манифест}")
    данные = json.loads(манифест.read_text(encoding="utf-8"))
    факт = хеш(РЕЛИЗ_НА_ДИСКЕ / "lords-frontend.py")
    if факт != ЗАКРЕПЛЁННЫЙ_ШАБЛОН["code_sha256"]:
        raise onboarding.StageBlocked(
            f"исполняемый файл релиза {факт} не совпал с закреплённым "
            f"{ЗАКРЕПЛЁННЫЙ_ШАБЛОН['code_sha256']}")
    if данные.get("assignment_scope") != "ZONA_02_ONLY":
        raise onboarding.StageBlocked(
            f"область назначения шаблона {данные.get('assignment_scope')} не ZONA_02_ONLY")
    # Расхождение с соседом называется, а не замалчивается: профиль оформления
    # один и тот же (`zona-general`), байты — разные.
    сосед = РАНТАЙМ / "template-manifest-zona-01.json"
    сосед_данные = json.loads(сосед.read_text(encoding="utf-8")) if сосед.exists() else {}
    return {
        **ЗАКРЕПЛЁННЫЙ_ШАБЛОН,
        "verified_sha256": факт,
        "reserved": False,
        "reused": True,
        "pool_spent": False,
        "pool_note": "семейства zona в config/template-pool.json нет; пул не расходуется",
        "neighbour_zona_01": {
            "profile": сосед_данные.get("profile"),
            "design_version": сосед_данные.get("design_version"),
            "code_file_sha256": сосед_данные.get("code_file_sha256"),
            "same_profile_name": сосед_данные.get("profile") == ЗАКРЕПЛЁННЫЙ_ШАБЛОН["template_id"],
            "same_bytes": сосед_данные.get("code_file_sha256") == факт,
        },
    }


def хеш(путь: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with путь.open("rb") as f:
        for кусок in iter(lambda: f.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def зарегистрировать_ячейку(order: onboarding.Order, шаблон: dict, repo: dict) -> dict:
    """Паспорт ячейки. Повтор перезаписывает свою запись, а не заводит вторую."""
    существующая = None
    try:
        существующая = registry.resolve(SITE_ID)
    except registry.RegistryError:
        pass
    if существующая is not None and существующая.domain != DOMAIN:
        raise onboarding.StageBlocked(
            f"ячейка {SITE_ID} уже держит домен {существующая.domain}")
    cell = registry.Cell(
        site_id=SITE_ID, domain=DOMAIN, aliases=ALIASES,
        repo=repo,
        template={
            "template_id": шаблон["template_id"],
            "order_id": ORDER_ID,
            "family": FAMILY,
            "design_version": шаблон["design_version"],
            "note": (
                "закреплён исполнением: байты релиза zona-slider-2650fad6, "
                "sha256 7ccf094a…, область ZONA_02_ONLY. Из пула не выдавался — "
                "семейства zona в пуле нет. Профиль оформления называется так же, "
                "как у zona-01, но байты разные (у соседа design_version 1.3.0); "
                "расхождение записано в knowledge/DECISIONS.md, индексация закрыта."
            ),
        },
        pins={
            "common_core": шаблон["source_commit"],
            "template": шаблон["pinned_release"],
            "modules": {"runtime": "zona-02-1015c650d8be"},
            "schemas": {"site_manifest": "1", "release_manifest": "1"},
        },
        deploy_target={"ref": DEPLOY_TARGET, "server": None},
        publisher={
            "provider": "cdnvideohub",
            "publisher_id": PUBLISHER_ID,
            "publisher_id_ref": "secret://cdnvideohub/lords/lords-01/publisher-id",
        },
        data={
            "database": f"{КОРЕНЬ_САЙТА}/data/zona-02-community.json",
            "media": f"{КОРЕНЬ_САЙТА}/data/media",
        },
        status="staged",
    )
    registry.register(cell, replace=True)
    return cell.to_dict()


def этап_репозиторий(order: onboarding.Order) -> dict:
    """Создание или повторное использование приватного репозитория сайта."""
    итог = onboarding.create_repo_step(order)
    зарегистрировать_ячейку(
        order, ЗАКРЕПЛЁННЫЙ_ШАБЛОН,
        {"kind": "remote", "path": f"var/site-repos/{onboarding.repo_name_for(SITE_ID, DOMAIN)}",
         "remote": итог["url"]})
    return итог



def _выполнить(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    п = subprocess.run(cmd, capture_output=True, text=True, check=False,
                       cwd=str(cwd) if cwd else None)
    return п.returncode, (п.stdout or "") + (п.stderr or "")


def путь_проекта() -> Path:
    cell = registry.resolve(SITE_ID)
    return РЕПО / cell.repo["path"]


def этап_push(order: onboarding.Order) -> dict:
    """Локальный коммит и удалённый SHA обязаны совпасть.

    Сравнение, а не «push прошёл без ошибки»: push может обновить не ту ветку,
    а успешный код возврата про содержимое удалённой стороны не говорит ничего.
    """
    проект = путь_проекта()
    код, вывод = _выполнить(["git", "rev-parse", "HEAD"], проект)
    if код != 0:
        raise onboarding.StageBlocked(f"нет HEAD проекта: {вывод.strip()[:200]}")
    локальный = вывод.strip()
    код, вывод = _выполнить(["git", "status", "--porcelain"], проект)
    if вывод.strip():
        raise onboarding.StageBlocked(
            "в проекте есть незакоммиченные изменения: выпускать нечего")
    код, вывод = _выполнить(["git", "ls-remote", "origin", ВЕТКА_ПРОЕКТА], проект)
    if код != 0:
        raise onboarding.StageBlocked(f"remote недоступен: {вывод.strip()[:200]}")
    строки = [с for с in вывод.strip().splitlines() if с.strip()]
    if not строки:
        raise onboarding.StageBlocked(f"ветки {ВЕТКА_ПРОЕКТА} на remote нет")
    удалённый = строки[0].split()[0]
    if удалённый != локальный:
        raise onboarding.StageBlocked(
            f"локальный SHA {локальный} и удалённый {удалённый} расходятся")
    return {"branch": ВЕТКА_ПРОЕКТА, "local_sha": локальный, "remote_sha": удалённый,
            "match": True, "repository": f"{onboarding.REPO_NAMESPACE}/"
                                         f"{onboarding.repo_name_for(SITE_ID, DOMAIN)}"}


def этап_ci(order: onboarding.Order) -> dict:
    """CI обязан быть зелёным на том же SHA, что выложен.

    Зелёный прогон другого коммита ничего не доказывает про этот, поэтому
    сверяется headSha, а не «последний успешный прогон».
    """
    проект = путь_проекта()
    код, вывод = _выполнить(["git", "rev-parse", "HEAD"], проект)
    sha = вывод.strip()
    полное = f"{onboarding.REPO_NAMESPACE}/{onboarding.repo_name_for(SITE_ID, DOMAIN)}"
    код, вывод = _выполнить([
        "gh", "run", "list", "--repo", полное, "--limit", "20",
        "--json", "databaseId,headSha,status,conclusion,workflowName"])
    if код != 0:
        raise onboarding.StageBlocked(f"gh run list: {вывод.strip()[:200]}")
    прогоны = [п for п in json.loads(вывод) if п.get("headSha") == sha]
    if not прогоны:
        raise onboarding.StageBlocked(f"прогонов CI для {sha} нет")
    незавершённые = [п for п in прогоны if п.get("status") != "completed"]
    if незавершённые:
        raise onboarding.StageBlocked(
            f"CI для {sha} ещё идёт: {[п['databaseId'] for п in незавершённые]}")
    провалы = [п for п in прогоны if п.get("conclusion") != "success"]
    if провалы:
        raise onboarding.StageBlocked(
            f"CI для {sha} не зелёный: {[(п['databaseId'], п['conclusion']) for п in провалы]}")
    return {"head_sha": sha, "runs": [{"id": п["databaseId"], "workflow": п["workflowName"],
                                       "conclusion": п["conclusion"]} for п in прогоны]}


def этап_релиз(order: onboarding.Order) -> dict:
    """Артефакт собран из чистого коммита, digest записан в паспорт ячейки."""
    cell = registry.resolve(SITE_ID)
    выложено = cell.deployed or {}
    digest = выложено.get("release_digest")
    коммит = выложено.get("source_commit")
    артефакт = выложено.get("artifact")
    if not (digest and коммит and артефакт):
        raise onboarding.StageBlocked("в паспорте ячейки нет digest собранного релиза")
    путь = Path(артефакт)
    if not путь.exists():
        raise onboarding.StageBlocked(f"артефакта нет на диске: {путь}")
    факт = "sha256:" + хеш(путь)
    if факт != digest:
        raise onboarding.StageBlocked(f"digest артефакта {факт} не совпал с записанным {digest}")
    код, вывод = _выполнить(["git", "rev-parse", "HEAD"], путь_проекта())
    if вывод.strip() != коммит:
        raise onboarding.StageBlocked(
            f"релиз собран из {коммит}, а HEAD проекта {вывод.strip()}")
    return {"digest": digest, "source_commit": коммит, "artifact": артефакт,
            "verified_digest": факт}


def этап_сервер(order: onboarding.Order) -> dict:
    """Витрина исполняет код своего релиза. Ответ даёт /proc, а не декларация."""
    текущий = КОРЕНЬ_САЙТА / "current"
    if not текущий.is_symlink():
        raise onboarding.StageBlocked(f"{текущий} не символическая ссылка на релиз")
    релиз = текущий.resolve()
    исполняемые = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            ч = (p / "cmdline").read_bytes().decode("utf-8", "replace").replace("\0", " ").split()
        except OSError:
            continue
        if (len(ч) >= 4 and ч[0].endswith("python3") and ч[1].endswith("lords-frontend.py")
                and "/sites/zona-02/releases/" in ч[1] and ч[2] == "--port"):
            исполняемые.append((int(p.name), ч[1], ч[3]))
    if not исполняемые:
        raise onboarding.StageBlocked("процесс витрины не найден")
    if len(исполняемые) > 1:
        raise onboarding.StageBlocked(f"процессов витрины больше одного: {исполняемые}")
    pid, файл, порт = исполняемые[0]
    if not файл.startswith(str(релиз)):
        raise onboarding.StageBlocked(
            f"процесс исполняет {файл}, а current ведёт в {релиз}")
    здоровье = None
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{порт}/healthz", timeout=20) as о:
            здоровье = о.status
    except Exception as exc:
        raise onboarding.StageBlocked(f"healthz не отвечает: {type(exc).__name__}")
    предыдущий = КОРЕНЬ_САЙТА / "previous"
    return {"current": str(релиз), "previous": str(предыдущий.resolve())
            if предыдущий.exists() else None,
            "pid": pid, "executing": файл, "port": int(порт), "healthz": здоровье,
            "unit_installed": Path("/etc/systemd/system/nova-zona-02.service").exists()}


def этап_данные(order: onboarding.Order) -> dict:
    """Данные вне каталога релиза и переживают смену релиза."""
    данные = КОРЕНЬ_САЙТА / "data"
    релиз = (КОРЕНЬ_САЙТА / "current").resolve()
    файлы = sorted(f for f in данные.iterdir() if f.is_file())
    if not файлы:
        raise onboarding.StageBlocked("каталог данных пуст")
    внутри = [str(f) for f in файлы if str(f).startswith(str(релиз))]
    if внутри:
        raise onboarding.StageBlocked(f"данные лежат внутри релиза: {внутри}")
    отчёт_отката = РЕПО / "artifacts/evidence/zona-02-launch-01/01-local/rollback.json"
    if not отчёт_отката.exists():
        raise onboarding.StageBlocked("нет отчёта об откате: сохранность данных не измерена")
    откат = json.loads(отчёт_отката.read_text(encoding="utf-8"))
    return {"data_root": str(данные), "files": {f.name: f.stat().st_size for f in файлы},
            "inside_release": [], "rollback_evidence": str(отчёт_отката.relative_to(РЕПО)),
            "data_unchanged_across_rollback": откат.get("data_after_rollback") is not None}


def этап_синхронизация(order: onboarding.Order) -> dict:
    отчёт = РЕПО / "artifacts/evidence/zona-02-launch-01/01-local/sync.json"
    if not отчёт.exists():
        raise onboarding.StageBlocked("нет отчёта о доставке обновлений")
    д = json.loads(отчёт.read_text(encoding="utf-8"))["steps"]
    if д["repeat_delivery"]["applied"] or not д["repeat_delivery"]["duplicates"]:
        raise onboarding.StageBlocked("повторная доставка не опознана как дубли")
    if not д["delete_delivery"]["deleted"]:
        raise onboarding.StageBlocked("удаление не доехало")
    return {"first_applied": д["first_delivery"]["applied"],
            "repeat_applied": д["repeat_delivery"]["applied"],
            "repeat_duplicates": д["repeat_delivery"]["duplicates"],
            "deleted": д["delete_delivery"]["deleted"],
            "field_ownership": д["field_ownership"],
            "evidence": str(отчёт.relative_to(РЕПО))}


def этап_seo(order: onboarding.Order) -> dict:
    отчёт = РЕПО / "artifacts/evidence/zona-02-launch-01/01-local/acceptance-own-release.json"
    if not отчёт.exists():
        raise onboarding.StageBlocked("нет отчёта приёмки")
    д = json.loads(отчёт.read_text(encoding="utf-8"))
    итоги = {}

    def обойти(о):
        if isinstance(о, dict):
            if "id" in о and "ok" in о:
                итоги[о["id"]] = о
            for v in о.values():
                обойти(v)
        elif isinstance(о, list):
            for v in о:
                обойти(v)
    обойти(д)
    обязательные = ("seo.noindex_header_and_meta", "seo.canonical_own_domain_only",
                    "seo.robots_txt_closed", "seo.sitemap_matches_closed_canary")
    провалы = [и for и in обязательные if not (итоги.get(и) or {}).get("ok")]
    if провалы:
        raise onboarding.StageBlocked(f"ворота SEO не пройдены: {провалы}")
    return {и: итоги[и]["measured"] for и in обязательные} | {
        "indexing_enabled": False,
        "note": "индексация закрыта намеренно; открытие — отдельная команда владельца",
        "evidence": str(отчёт.relative_to(РЕПО))}


def этап_выкат(order: onboarding.Order) -> dict:
    """Юнит и vhost ставит root. Без них этап не пройден — и не отмечается."""
    юнит = Path("/etc/systemd/system/nova-zona-02.service")
    vhost = Path("/etc/nginx/lords/zona-02.conf")
    нет = [str(p) for p in (юнит, vhost) if not p.exists()]
    if нет:
        raise onboarding.StageBlocked(
            "BLOCKED_ACCESS: не установлены " + ", ".join(нет)
            + "; установка требует root, профиль UNATTENDED_SAFE его не даёт. "
              "Команды — docs/zona-02/OWNER_COMMANDS.md")
    return {"unit": str(юнит), "vhost": str(vhost)}


def этап_приёмка(order: onboarding.Order) -> dict:
    """Публичная приёмка. Без записи A и сертификата выполнить её нечем."""
    import socket
    try:
        адреса = sorted({r[4][0] for r in socket.getaddrinfo(DOMAIN, None)})
    except OSError as exc:
        raise onboarding.StageBlocked(
            f"BLOCKED_INPUT: {DOMAIN} не резолвится ({type(exc).__name__}); "
            f"запись A создаётся в панели Cloudflare, inventory/dns-zones.yaml пуст")
    if ORIGIN_IPV4 not in адреса:
        raise onboarding.StageBlocked(
            f"{DOMAIN} резолвится в {адреса}, а origin стенда {ORIGIN_IPV4}")
    raise onboarding.StageBlocked(
        "запись A появилась; публичная приёмка запускается "
        "automation/host/zonafilm-cc-await-cutover.py")


ВЕТКА_ПРОЕКТА = "claude/bootstrap-zona-02"

ЭТАПЫ = {
    "domain_validated": этап_домен,
    "site_id_assigned": этап_site_id,
    "template_reserved": этап_шаблон,
    "repo_created": этап_репозиторий,
    "repo_pushed": этап_push,
    "ci_verified": этап_ci,
    "release_ready": этап_релиз,
    "server_staged": этап_сервер,
    "data_verified": этап_данные,
    "sync_verified": этап_синхронизация,
    "seo_verified": этап_seo,
    "deployed": этап_выкат,
    "publicly_accepted": этап_приёмка,
}


#: Этапы, которые ПОТРЕБЛЯЮТ ресурс: шаблон пула, репозиторий GitHub.
#: Повтор такого этапа завёл бы второй объект, поэтому пройденный он не
#: повторяется — ради этого журнал и существует.
ПОТРЕБЛЯЮЩИЕ = ("template_reserved", "repo_created")

#: Всё остальное — проверки. Они обязаны выполняться при каждом запуске.
#:
#: Причина конкретная, а не стилистическая. Этап, отмеченный `done`, хранит
#: свою подробность навсегда, и после следующей выкладки журнал продолжал
#: называть прежний релиз текущим: `release_ready` показывал digest прошлого
#: артефакта, `server_staged` — прошлый путь в /proc. Отчёт, собранный по
#: такому журналу, выдал бы историю за настоящее — ровно то, что Definition
#: of Done называет ошибкой отчёта.
ПОВТОРЯЕМЫЕ = tuple(и for и in ЭТАПЫ if и not in ПОТРЕБЛЯЮЩИЕ)


def перепроверить(progress, заказ_: onboarding.Order, root: Path) -> list[str]:
    """Заново выполнить пройденные проверки и обновить их подробности."""
    обновлены = []
    for имя in ПОВТОРЯЕМЫЕ:
        этап = progress.by_name[имя]
        if этап.status != onboarding.DONE:
            continue
        try:
            подробность = ЭТАПЫ[имя](заказ_)
        except onboarding.StageBlocked as exc:
            onboarding.record(progress, имя, onboarding.BLOCKED,
                              {"reason": str(exc)}, root=root)
            обновлены.append(f"{имя}: blocked")
            continue
        except Exception as exc:
            onboarding.record(progress, имя, onboarding.FAILED,
                              {"reason": f"{type(exc).__name__}: {exc}"}, root=root)
            обновлены.append(f"{имя}: failed")
            continue
        onboarding.record(progress, имя, onboarding.DONE, подробность, root=root)
        обновлены.append(имя)
    return обновлены


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="выполнить этапы до указанного включительно")
    ap.add_argument("--no-reverify", action="store_true",
                    help="не перепроверять пройденные этапы (журнал останется прежним)")
    args = ap.parse_args()

    steps = dict(ЭТАПЫ)
    if args.only:
        разрешено = onboarding.STAGES[: onboarding.STAGES.index(args.only) + 1]
        steps = {k: v for k, v in steps.items() if k in разрешено}

    progress = onboarding.run(заказ(), root=ledger_root(), steps=steps,
                              dry_run=args.dry_run)
    if not args.dry_run and not args.no_reverify:
        перепроверить(progress, заказ(), ledger_root())
        # Перепроверка могла открыть путь дальше: этап, стоявший blocked,
        # мог стать done. Продолжаем с того места, куда дошли.
        progress = onboarding.run(заказ(), root=ledger_root(), steps=steps)
    сводка = progress.summary()
    подробно = {s.name: {"status": s.status, "detail": s.detail} for s in progress.stages}
    print(json.dumps({"summary": сводка, "stages": подробно},
                     ensure_ascii=False, indent=2, default=str))
    неудачи = сводка["failed"] + сводка["blocked"]
    return 0 if not неудачи else 1


if __name__ == "__main__":
    raise SystemExit(main())
