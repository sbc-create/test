#!/usr/bin/env python3
"""Один запуск домена от начала до публичной проверки. Существующие части, одна цепочка.

    python3 automation/host/launch-domain.py --domain zonafilm12.site
    python3 automation/host/launch-domain.py --domain zonafilm12.site --act

Без `--act` не выполняется ни одно действие: печатается состояние каждого этапа
и первый, который мешает. С `--act` выполняются только те этапы, которые
выполнимы без root и без отсутствующих входов; всё остальное называется точно.

Почему это не второй способ выкладки. Каждый этап — вызов того же механизма,
которым сайты выпускаются сейчас: реестр ячеек, пул шаблонов, `siterepo`,
`release`, очередь исполнителя, `launch-new-site.sh`. Здесь только порядок,
проверка результата после каждого шага и запись прогресса, чтобы повторный
запуск продолжал незавершённое, а не начинал заново.

Отсутствующий вход — это отказ с именем входа, а не подстановка похожего
значения. Чужой publisher_id, счётчик или профиль шаблона не копируются.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")
sys.path.insert(0, str(КОРЕНЬ))

ОК, НЕТ_ВХОДА, НЕ_СДЕЛАНО, НЕ_МОЁ = "ок", "НЕТ ВХОДА", "не сделано", "нужен root"
#: Замечание, которое не мешает запуску. Смешивать его с отказом нельзя в обе
#: стороны: замечание вместо отказа пропускает недостающий вход, отказ вместо
#: замечания останавливает работающую витрину из-за унаследованной настройки.
ЗАМЕЧАНИЕ = "замечание"
#: Работающая витрина того же хоста. Адрес сервера берётся из неё, а не
#: вписывается числом: числа в коде устаревают молча.
ОБРАЗЕЦ_ХОСТА = "zonafilm.space"
АГЕНТ = {"User-Agent": "site-factory-launch"}


def _ctx() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def этап(имя: str, состояние: str, деталь: str = "", действие: str = "") -> dict:
    return {"stage": имя, "state": состояние, "detail": деталь, "action": действие}


def проверить_днс(домен: str) -> dict:
    try:
        адрес = socket.gethostbyname(домен)
    except OSError as ош:
        return этап(
            "domain_validated",
            НЕТ_ВХОДА,
            f"{домен} не разрешается: {ош.strerror or ош}",
            f"добавить запись A для {домен} и www.{домен}",
        )
    try:
        ожидаемый = socket.gethostbyname(ОБРАЗЕЦ_ХОСТА)
    except OSError:
        return этап("domain_validated", ОК, f"{домен} -> {адрес} (адрес хоста не сверен)")
    if адрес != ожидаемый:
        return этап(
            "domain_validated",
            НЕТ_ВХОДА,
            f"{домен} -> {адрес}, а хост витрин {ожидаемый}",
            "исправить запись A либо подтвердить другой сервер",
        )
    return этап("domain_validated", ОК, f"{домен} -> {адрес}")


def проверить_реестр(домен: str) -> tuple[dict, dict | None]:
    from factory.cell import registry

    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    ячейка = next((c for c in реестр["cells"] if c.get("domain") == домен), None)
    if ячейка is None:
        return этап(
            "site_id_assigned",
            НЕТ_ВХОДА,
            f"{домен} не объявлен в реестре ячеек",
            "добавить запись: site_id, порт, учётная запись, юнит, репозиторий",
        ), None
    рв = ячейка.get("runtime") or {}
    пусто = [к for к in ("unit", "port", "account") if not рв.get(к)]
    if пусто:
        return этап(
            "site_id_assigned",
            НЕТ_ВХОДА,
            f"{ячейка['site_id']}: в runtime нет {пусто}",
            "заполнить размещение в реестре",
        ), ячейка
    try:
        registry.resolve(ячейка["site_id"])
    except registry.RegistryError as ош:
        return этап("site_id_assigned", НЕТ_ВХОДА, f"реестр не разрешает запись: {ош}"), ячейка
    return этап(
        "site_id_assigned",
        ОК,
        f"{ячейка['site_id']} порт {рв['port']} учётная запись {рв['account']}",
    ), ячейка


def уже_выпущена(ячейка: dict) -> bool:
    """Обслуживает ли домен собственный установленный выпуск.

    Признак — манифест выпуска рядом с `current`. Для такой витрины требования
    к ВХОДАМ запуска неприменимы: вход уже когда-то был принят, и объявлять его
    отсутствующим значит останавливать работающий сайт из-за формы записи.
    """
    рв = ячейка.get("runtime") or {}
    ссылка = Path("/srv") / (рв.get("account") or "нет") / "current"
    return (ссылка / "release-manifest.json").is_file()


def проверить_шаблон(ячейка: dict) -> dict:
    ш = ячейка.get("template") or {}
    иден = ш.get("template_id")
    if not иден:
        return этап(
            "template_reserved",
            НЕТ_ВХОДА,
            "профиль шаблона не назначен",
            "назвать утверждённый профиль: либо свободный шаблон из пула, "
            "либо экземпляр проверенного выпуска существующей витрины",
        )
    from factory.cell import templates

    пул = {e["template_id"]: e for e in templates.load()["templates"]}
    if иден in пул:
        чей = пул[иден].get("site_id")
        if чей and чей != ячейка["site_id"]:
            return этап(
                "template_reserved",
                НЕТ_ВХОДА,
                f"шаблон {иден} закреплён за {чей}",
                "выдать свой шаблон: пул пополняет владелец",
            )
        return этап("template_reserved", ОК, f"шаблон {иден} закреплён за витриной")
    # Шаблона нет в пуле — значит это экземпляр проверенного выпуска. Такой
    # источник обязан быть назван в записи, иначе происхождение кода неизвестно.
    источник = ш.get("note") or ""
    if "@" in источник:
        return этап("template_reserved", ОК, f"экземпляр выпуска: {источник[:70]}")
    # Штатное место происхождения шаблона — манифест в самом репозитории сайта:
    # его пишет `siterepo.generate`. Искать источник только в записи реестра
    # значило бы не заметить того, что уже записано там, где положено.
    манифест = (
        КОРЕНЬ / (ячейка.get("repo", {}).get("path") or "") / "config" / "template-manifest.json"
    )
    if манифест.is_file():
        try:
            d = json.loads(манифест.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        if d.get("source_commit"):
            return этап(
                "template_reserved",
                ОК,
                f"шаблон {иден} из {str(d['source_commit'])[:12]} "
                "(config/template-manifest.json)",
            )
    if уже_выпущена(ячейка):
        return этап(
            "template_reserved",
            ОК,
            f"шаблон {иден}: витрина выпущена, происхождение закреплено пинами",
        )
    return этап(
        "template_reserved",
        НЕТ_ВХОДА,
        f"шаблон {иден} не в пуле и источник экземпляра не назван",
        "указать в template.note проверенный выпуск-источник (repo@commit)",
    )


def проверить_издателя(ячейка: dict) -> dict:
    изд = ячейка.get("publisher") or {}
    ссылка = изд.get("publisher_id_ref")
    if ссылка:
        # Значение в реестре не хранится намеренно: оно приходит из Secret Hub
        # и попадает в config/player.json при выкладке. Требовать здесь число
        # значило бы требовать положить секрет в git.
        return этап("player_configured", ОК, f"идентификатор по ссылке {ссылка}")
    свой = изд.get("publisher_id")
    if not свой:
        конфиг = КОРЕНЬ / (ячейка.get("repo", {}).get("path") or "") / "config" / "site.json"
        if конфиг.is_file():
            d = json.loads(конфиг.read_text(encoding="utf-8"))
            свой = d.get("publisher_id_expected")
    if not свой:
        return этап(
            "player_configured",
            НЕТ_ВХОДА,
            "publisher_id домена не назначен",
            "получить publisher_id у провайдера плеера для ЭТОГО домена; " "чужой не переносится",
        )
    # Один и тот же идентификатор на двух домена означает чужие показы в чужом
    # отчёте, поэтому пересечение — отказ, а не предупреждение.
    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    чужие = {
        str((c.get("publisher") or {}).get("publisher_id")): c["site_id"]
        for c in реестр["cells"]
        if c["site_id"] != ячейка["site_id"]
    }
    if str(свой) in чужие:
        # Для НОВОГО домена это отказ: свой идентификатор — обязательный вход.
        # Для уже работающей витрины это унаследованное состояние аккаунта
        # провайдера: 10238 стоит у пяти доменов, 10252 у двух. Останавливать их
        # из-за этого нельзя, но и молчать о совпадении — значит потерять его.
        if уже_выпущена(ячейка):
            return этап(
                "player_configured",
                ЗАМЕЧАНИЕ,
                f"publisher_id {свой} общий с {чужие[str(свой)]}",
                "разделение идентификаторов по доменам — вход владельца",
            )
        return этап(
            "player_configured",
            НЕТ_ВХОДА,
            f"publisher_id {свой} уже принадлежит {чужие[str(свой)]}",
            "получить собственный publisher_id для этого домена",
        )
    return этап("player_configured", ОК, f"publisher_id {свой}")


def проверить_репозиторий(ячейка: dict, *, действовать: bool) -> dict:
    r = ячейка.get("repo") or {}
    remote = r.get("remote")
    путь = КОРЕНЬ / (r.get("path") or "")
    if not remote:
        return этап(
            "repo_created",
            НЕТ_ВХОДА,
            "в реестре нет remote репозитория сайта",
            "создать репозиторий сайта и записать его в реестр",
        )
    проект = "/".join(remote.rstrip("/").removesuffix(".git").split("/")[-2:])
    гот = subprocess.run(
        ["gh", "api", f"repos/{проект}", "--jq", ".full_name"], capture_output=True, text=True
    )
    если_есть = гот.returncode == 0
    if not если_есть:
        return этап(
            "repo_created",
            НЕ_СДЕЛАНО,
            f"{проект}: {(гот.stderr or '').strip()[:80]}",
            f"создать репозиторий {проект} и запушить проект сайта",
        )
    if not (путь / ".git").exists():
        return этап(
            "repo_created",
            НЕ_СДЕЛАНО,
            f"{проект} есть, рабочей копии в {путь} нет",
            f"склонировать {проект} в {путь}",
        )

    def г(*а: str) -> str:
        return subprocess.run(("git", *а), cwd=путь, capture_output=True, text=True).stdout.strip()

    ветка = г("rev-parse", "--abbrev-ref", "HEAD")
    head = г("rev-parse", "HEAD")
    впереди = г("rev-list", "--count", f"origin/{ветка}..HEAD") or "0"
    if впереди != "0":
        if действовать:
            п = subprocess.run(
                ["git", "push", "origin", "HEAD"], cwd=путь, capture_output=True, text=True
            )
            if п.returncode != 0:
                return этап(
                    "repo_pushed", НЕ_СДЕЛАНО, f"push отказал: {(п.stderr or '').strip()[:80]}"
                )
            впереди = "0"
        else:
            return этап(
                "repo_pushed",
                НЕ_СДЕЛАНО,
                f"{впереди} коммитов не запушено (ветка {ветка})",
                "запустить с --act либо запушить вручную",
            )
    return этап("repo_pushed", ОК, f"{проект} ветка {ветка} HEAD {head[:12]}")


def проверить_ci(ячейка: dict) -> dict:
    r = ячейка.get("repo") or {}
    путь = КОРЕНЬ / (r.get("path") or "")
    if not (путь / ".git").exists():
        return этап("ci_verified", НЕ_СДЕЛАНО, "нет рабочей копии")
    проект = "/".join((r.get("remote") or "").rstrip("/").removesuffix(".git").split("/")[-2:])
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=путь, capture_output=True, text=True
    ).stdout.strip()
    гот = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            проект,
            "--commit",
            head,
            "--json",
            "databaseId,status,conclusion",
            "--limit",
            "5",
        ],
        capture_output=True,
        text=True,
    )
    if гот.returncode != 0:
        return этап("ci_verified", НЕ_СДЕЛАНО, f"GitHub не ответил: {(гот.stderr or '')[:70]}")
    try:
        прогоны = json.loads(гот.stdout or "[]")
    except ValueError:
        return этап("ci_verified", НЕ_СДЕЛАНО, "ответ GitHub нечитаем")
    успешные = [п for п in прогоны if п.get("conclusion") == "success"]
    if успешные:
        return этап("ci_verified", ОК, f"прогон {успешные[0]['databaseId']} success на {head[:12]}")
    идут = [п for п in прогоны if п.get("status") != "completed"]
    if идут:
        return этап(
            "ci_verified",
            НЕ_СДЕЛАНО,
            f"прогон {идут[0]['databaseId']} ещё идёт",
            "дождаться завершения",
        )
    return этап(
        "ci_verified",
        НЕ_СДЕЛАНО,
        f"успешного прогона на {head[:12]} нет",
        "починить CI: выпуск ставится только с успешного прогона",
    )


def проверить_хост(ячейка: dict) -> dict:
    рв = ячейка.get("runtime") or {}
    site_id = ячейка["site_id"]
    юнит = Path("/etc/systemd/system") / (рв.get("unit") or "нет")
    conf = Path("/etc/nginx/lords") / f"{site_id}.conf"
    upstream = Path("/etc/nginx/cells") / f"{site_id}.upstream"
    чего_нет = [
        и
        for и, п in (("юнит службы", юнит), ("nginx-конфигурация", conf), ("upstream", upstream))
        if not п.exists()
    ]
    if чего_нет:
        return этап(
            "server_staged",
            НЕ_МОЁ,
            f"нет: {', '.join(чего_нет)}",
            f"sudo bash automation/host/launch-new-site.sh --site {site_id}",
        )
    return этап("server_staged", ОК, "юнит, nginx и upstream на месте")


def _подробности_не_покрывают(фронт: Path, site_id: str) -> str:
    """Покрывают ли подробности позиции каталога. Пустая строка — покрывают.

    Доля, а не факт наличия файла: снимок из нового каталога со старыми
    подробностями даёт карточки без описаний, и ни один код ответа этого не
    показывает.
    """
    к = фронт / f"{site_id}-catalog.json"
    п = фронт / f"{site_id}-details.json"
    try:
        каталог = json.loads(к.read_text(encoding="utf-8"))
        подробности = json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        return f"снимок не читается: {type(ош).__name__}"
    позиции = каталог.get("items") or []
    записи = подробности.get("items") or подробности.get("details") or подробности
    ключи = (set(записи.keys()) if isinstance(записи, dict)
             else {z.get("id") or z.get("entity_id") or z.get("slug") for z in записи})
    если_нет = [z for z in позиции
                if (z.get("id") or z.get("entity_id") or z.get("slug")) not in ключи]
    if not позиции:
        return "каталог пуст"
    доля = 100 * (len(позиции) - len(если_нет)) // len(позиции)
    if доля < 95:
        return (f"подробности покрывают {доля}% каталога "
                f"({len(позиции) - len(если_нет)} из {len(позиции)})")
    return ""


def проверить_снимок(ячейка: dict) -> dict:
    from factory.cell import privileged

    site_id = ячейка["site_id"]
    к = privileged.контракт_данных(site_id)
    фронт = Path("/srv/lords/.frontend")
    нет = [
        ш.format(site=site_id)
        for ш in (к.get("delivered") or ())
        if not (фронт / ш.format(site=site_id)).exists()
    ]
    if not нет:
        # Наличие двух файлов ещё не значит, что подробности относятся к этому
        # каталогу. Выпуск с каталогом без подробностей уже был: витрина
        # показывала карточки без описаний, и снаружи это выглядело рабочим.
        промах = _подробности_не_покрывают(фронт, site_id)
        if промах:
            return этап("data_verified", "НЕ РАБОТАЕТ", промах,
                        f"перепубликовать: nova-catalog-publish.py --sites {site_id} --apply")
    if нет:
        return этап(
            "data_verified",
            НЕТ_ВХОДА,
            f"в источнике нет {нет}",
            f"добавить {site_id} в список витрин производителя каталога "
            "(automation/host/nova-catalog-publish.py, таблица ВИТРИНЫ)",
        )
    return этап("data_verified", ОК, f"снимки источника для {site_id} на месте")


def проверить_публично(домен: str, ячейка: dict) -> dict:
    рв = ячейка.get("runtime") or {}
    корень = Path("/srv") / (рв.get("account") or "нет")
    ссылка = корень / "current"
    установлен = None
    if ссылка.exists():
        try:
            установлен = json.loads(
                (ссылка / "release-manifest.json").read_text(encoding="utf-8")
            ).get("live_build_id")
        except (OSError, ValueError):
            установлен = None
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(f"https://{домен}/", headers=АГЕНТ), timeout=20, context=_ctx()
        )
        живой = r.headers.get("X-Site-Factory-Build-Id")
        код = r.status
    except urllib.error.HTTPError as ош:
        return этап(
            "publicly_accepted", НЕ_СДЕЛАНО, f"HTTP {ош.code}", "выпустить сайт через очередь"
        )
    except (urllib.error.URLError, OSError) as ош:
        return этап("publicly_accepted", НЕ_СДЕЛАНО, f"{type(ош).__name__}")
    if установлен and живой == установлен:
        return этап("publicly_accepted", ОК, f"HTTP {код}, build-id {живой} совпадает с выпуском")
    if установлен:
        return этап(
            "publicly_accepted",
            НЕ_СДЕЛАНО,
            f"живой build-id {живой}, установлен {установлен}",
            "процесс отдаёт не тот код, что установлен: перезапуск выпуском",
        )
    return этап(
        "publicly_accepted",
        НЕ_СДЕЛАНО,
        f"HTTP {код}, build-id {живой}, манифеста выпуска нет",
        "домен обслуживается не своим выпуском",
    )


def _доступ(служба: str, операция: str, ошибка: str) -> str:
    """Причина отказа доступа в одной строке: служба, операция, чего нет."""
    return f"{служба}: операция «{операция}» недоступна — {ошибка}"


def проверить_метрику(ячейка: dict, домен: str, *, действовать: bool) -> dict:
    """Счётчик Метрики: найти существующий или создать. Дубля не заводит.

    Права читаются и записываются РАЗНЫМИ разрешениями, и смешивать их нельзя:
    `metrika:read` позволяет увидеть счётчик, `metrika:write` — создать. Отчёт
    об установленном средстве чтения не доказывает готовности подключения.
    """
    from factory.analytics import registry as ан_реестр

    записи = {z["domain"]: z for z in ан_реестр.load()["properties"]}
    з = записи.get(домен)
    if з is None:
        return этап(
            "metrika_counter",
            НЕТ_ВХОДА,
            f"{домен} не объявлен в реестре аналитики",
            "добавить запись домена в config/analytics.json",
        )
    счёт = з.get("counter_id")
    if счёт:
        # Счётчик обязан относиться к ЭТОМУ домену: чужой собирал бы визиты в
        # чужой отчёт, и заметно это стало бы только по расхождению чисел.
        свои = з.get("allowed_hosts") or []
        if свои != [домен]:
            return этап(
                "metrika_counter",
                НЕ_СДЕЛАНО,
                f"счётчик {счёт} объявлен с allowed_hosts={свои}, а домен {домен}",
                "привести allowed_hosts к собственному домену",
            )
        подтверждено = (ячейка.get("analytics") or {}).get("metrika_verified_at")
        return этап(
            "metrika_counter",
            ОК,
            f"счётчик {счёт}"
            + (
                f", отправка подтверждена {подтверждено}"
                if подтверждено
                else ", отправка ещё не подтверждена"
            ),
        )
    if not действовать:
        return этап(
            "metrika_counter",
            НЕ_СДЕЛАНО,
            "счётчика нет",
            f"запустить с --act: найдёт существующий в аккаунте или создаст "
            f"(python3 -m factory analytics apply --domain {домен} --confirm-writes)",
        )
    # Поимённый вызов: сплошной прогон счётчики незапущенным доменам не заводит.
    import subprocess as _sp

    готово = _sp.run(
        [
            sys.executable,
            "-m",
            "factory",
            "analytics",
            "apply",
            "--domain",
            домен,
            "--confirm-writes",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(КОРЕНЬ),
    )
    вывод = (готово.stdout or "") + (готово.stderr or "")
    if готово.returncode != 0:
        причина = вывод.strip().splitlines()[0][:160] if вывод.strip() else "нет вывода"
        return этап(
            "metrika_counter",
            НЕТ_ВХОДА,
            _доступ("Яндекс Метрика", "создание счётчика", причина),
            "выдать OAuth-токен с правом metrika:write в "
            "/etc/site-factory/secrets/yandex_oauth_token",
        )
    записи = {z["domain"]: z for z in ан_реестр.load()["properties"]}
    новый = (записи.get(домен) or {}).get("counter_id")
    if not новый:
        return этап(
            "metrika_counter",
            НЕ_СДЕЛАНО,
            "прогон завершился, а счётчик в реестре не появился",
            "прочитать вывод `factory analytics apply` целиком",
        )
    return этап("metrika_counter", ОК, f"счётчик {новый} получен")


def проверить_topvisor(ячейка: dict, домен: str, *, действовать: bool) -> dict:
    """Проект Topvisor: найти существующий по домену или создать.

    Строка в манифесте проектом не является, и счётчик Метрики его наличие не
    подтверждает: это внешняя интеграция, и проверяется она ответом аккаунта.
    """
    from factory.topvisor import manifest as тв_манифест

    сохранён = (ячейка.get("analytics") or {}).get("topvisor_project_id")
    в_манифесте = домен in тв_манифест.domains()
    if not в_манифесте:
        return этап(
            "topvisor_project",
            НЕТ_ВХОДА,
            f"{домен} не описан в манифесте проектов Topvisor",
            "добавить ProjectSpec: домен, профиль, группы запросов, "
            "счётчик Метрики; поисковики, регион и расписание берутся "
            "из общих значений манифеста",
        )
    if сохранён:
        подтверждено = (ячейка.get("analytics") or {}).get("topvisor_verified_at")
        if подтверждено:
            return этап("topvisor_project", ОК, f"проект {сохранён}, сверен {подтверждено}")
        return этап(
            "topvisor_project",
            НЕ_СДЕЛАНО,
            f"проект {сохранён} записан, но не сверен с аккаунтом",
            "сверить домен, поисковики, регионы и расписание ответом аккаунта",
        )
    # Ни один шаг не выполняется без учётных данных, и отказ обязан называть
    # службу и операцию, а не «нет доступа».
    try:
        from factory.topvisor.credentials import load as _уд

        _уд()
    except Exception as ош:  # noqa: BLE001 — важна причина, а не тип
        причина = str(getattr(ош, "reason", None) or ош)[:150]
        return этап(
            "topvisor_project",
            НЕТ_ВХОДА,
            _доступ("Topvisor", "чтение проектов и создание проекта", причина),
            "sudo python3 -m factory.topvisor.enroll — скрытый ввод "
            "user-id и api-key в /etc/site-factory/secrets/topvisor",
        )
    if not действовать:
        return этап(
            "topvisor_project",
            НЕ_СДЕЛАНО,
            "проекта нет",
            "запустить с --act: python3 -m factory.topvisor.cli apply",
        )
    import subprocess as _sp

    готово = _sp.run(
        [sys.executable, "-m", "factory.topvisor.cli", "apply"],
        capture_output=True,
        text=True,
        cwd=str(КОРЕНЬ),
    )
    вывод = ((готово.stdout or "") + (готово.stderr or "")).strip()
    if готово.returncode != 0:
        return этап(
            "topvisor_project",
            НЕ_СДЕЛАНО,
            _доступ(
                "Topvisor",
                "создание проекта",
                вывод.splitlines()[0][:150] if вывод else "нет вывода",
            ),
        )
    return этап(
        "topvisor_project",
        НЕ_СДЕЛАНО,
        "apply выполнен; идентификатор проекта надо прочитать из аккаунта",
        "python3 -m factory.topvisor.cli check — взять #id проекта домена",
    )


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--domain", required=True)
    р.add_argument(
        "--act", action="store_true", help="выполнять выполнимое, а не только показывать"
    )
    р.add_argument("--json", action="store_true")
    а = р.parse_args()

    шаги: list[dict] = [проверить_днс(а.domain)]
    шаг_реестра, ячейка = проверить_реестр(а.domain)
    шаги.append(шаг_реестра)
    if ячейка is not None:
        шаги.append(проверить_шаблон(ячейка))
        шаги.append(проверить_издателя(ячейка))
        шаги.append(проверить_репозиторий(ячейка, действовать=а.act))
        шаги.append(проверить_ci(ячейка))
        шаги.append(проверить_снимок(ячейка))
        шаги.append(проверить_хост(ячейка))
        # Аналитика — обязательная часть выпуска, а не следующая задача.
        шаги.append(проверить_метрику(ячейка, а.domain, действовать=а.act))
        шаги.append(проверить_topvisor(ячейка, а.domain, действовать=а.act))
        шаги.append(проверить_публично(а.domain, ячейка))

    первый = next((ш for ш in шаги if ш["state"] not in (ОК, ЗАМЕЧАНИЕ)), None)
    замечания = [ш for ш in шаги if ш["state"] == ЗАМЕЧАНИЕ]
    итог = {
        "domain": а.domain,
        "stages": шаги,
        "blocking_stage": первый["stage"] if первый else None,
        "blocking_reason": первый["detail"] if первый else None,
        "next_action": первый["action"] if первый else None,
        "notes": замечания,
        "complete": первый is None,
    }
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=2))
        return 0 if итог["complete"] else 1
    print(f"домен {а.domain}")
    for ш in шаги:
        метка = "ок  " if ш["state"] == ОК else f"{ш['state']:10}"
        print(f"  {метка} {ш['stage']:20} {ш['detail'][:90]}")
    for ш in замечания:
        print(f"  замечание: {ш['detail']}" + (f" -> {ш['action']}" if ш["action"] else ""))
    if первый:
        print(f"\nмешает: {первый['stage']} — {первый['detail']}")
        if первый["action"]:
            print(f"нужно : {первый['action']}")
        return 1
    print("\nвсе этапы пройдены")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
