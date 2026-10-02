"""Штатная операция смены режима индексации одного сайта.

Что было до неё
---------------

Механизма не было. Запрет стоял буквальными строками в четырёх местах рантайма
и одной строкой в конфигурации nginx; поле `indexing_enabled` в
`config/site.json` существовало, но его не читал никто. «Открыть сайт»
означало править исходник и выпускать его заново — поэтому попытка это
сделать скриптом закончилась ничем: работа упиралась не в команду, а в
отсутствующий механизм.

Четыре слоя, и ни один не открывает сайт сам
--------------------------------------------

    1. РАЗРЕШЕНИЕ ВЛАДЕЛЬЦА   config/site-cells.json: cells[].indexing.desired_state
    2. РАЗРЕШЕНИЕ ВЫПУСКА     config/site.json: indexing.release_permits_open
    3. СОСТОЯНИЕ              /srv/sites/indexing/<домен>.json: desired_state
    4. ЗАГОЛОВОК NGINX        X-Robots-Tag в серверном блоке сайта

Эта операция меняет ТОЛЬКО слой 3 — единственный, который живёт вне выпуска и
вне root. Слои 1 и 2 — разрешения: их выдаёт владелец и несёт выпуск, поэтому
следующий деплой запрет не возвращает, но и сам ничего не открывает. Слой 4
принадлежит root и снимается однократным запуском владельца на сайт;
операция его ИЗМЕРЯЕТ и, пока он отдаёт noindex, открытым сайт не называет.

Разделение не формальность. Разрешение и состояние — разные утверждения, и
хранить их в одном месте значило бы, что операция может выдать себе право.

Что операция делает в порядке выполнения
----------------------------------------

    предпроверка -> снимок прежнего состояния -> запись -> проверка публичного
    ответа -> итог, посчитанный ПО ОТВЕТУ, а не по тому, что команда не упала

Повторный запуск в том же режиме ничего не меняет и говорит об этом. При
несовпадении ожидаемого выпуска операция останавливается до единой записи.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from factory.qwen import editorial, registry

ОТКРЫТ = "OPEN"
ЗАКРЫТ = "CLOSED"
СХЕМА = 1

#: Корень файлов состояния. То же значение по умолчанию, что у читателя
#: витрины (`src/indexing_mode.py: КОРЕНЬ`): расхождение означало бы запись в
#: один файл и чтение другого. Совпадение закрепляет тест.
КОРЕНЬ = pathlib.Path(os.environ.get("QWEN_INDEXING_ROOT", "/srv/sites/indexing"))

#: Куда складываются снимки прежнего состояния и журнал операций.
ЖУРНАЛ = pathlib.Path(
    os.environ.get("QWEN_INDEXING_LOG", "/srv/sites/indexing/_log"))

#: Сколько ждать, пока публичный ответ переменится. Витрина перечитывает файл
#: состояния по времени файла с окном в пять секунд; запас взят на кэш nginx и
#: на то, что ответ приходит не мгновенно.
ОЖИДАНИЕ_С = int(os.environ.get("QWEN_INDEXING_WAIT", "60"))
ШАГ_С = 5

#: Семейства, рантайм которых умеет читать режим. Проверяется не по семейству,
#: а по ВЫПУЩЕННОМУ файлу: модуль есть в репозитории одного сайта и
#: отсутствует в выпуске другого, и судить по рабочей копии значило бы
#: обещать переключение там, где его не произойдёт.
ИМЯ_ЧИТАТЕЛЯ = "indexing_mode.py"

#: КОНТРАКТ РЕЖИМА ПО СЕМЕЙСТВАМ. Путь читателя — пример, а не обязанность:
#: у каждого семейства своё устройство рантайма, и требовать от всех
#: `src/indexing_mode.py` значило бы требовать переписать работающее.
#:
#: `reader` — чем выпуск читает режим; `permit` — где живёт разрешение
#: ВЫПУСКА; `mode_owner` — кто фактически переключает режим.
#:
#: Yummy объявлен отдельно не для удобства. У него режим УЖЕ работает и
#: работает иначе: `isIndexingEnabled` в `src/lib/seo/config.ts` требует
#: `SEO_INDEXING_ENABLED`, `APP_ENV=production` и публичного HTTPS-origin, а
#: значение приходит ПЕРЕМЕННОЙ КОНТЕЙНЕРА по тенанту. Измерено 2026-10-02:
#: web-site и web-org — `true`, web-biz и оба yummyani7 — `false`, и
#: yummyani.site с yummyani.org ОТКРЫТЫ. Подкладывать им второй, файловый
#: читатель значило бы завести второе решение о том же и закрыть два
#: работающих открытых домена при первом же прогоне fail-closed.
КОНТРАКТ_РЕЖИМА = {
    "animedia": {
        "reader": "src/indexing_mode.py",
        "permit": "config/site.json: indexing.release_permits_open",
        "mode_owner": "operation",
    },
    "lords": {
        "reader": "src/indexing_mode.py",
        "permit": "config/site.json: indexing.release_permits_open",
        "mode_owner": "operation",
    },
    "animego": {
        "reader": "src/indexing_mode.py",
        "permit": "config/site.json: indexing.release_permits_open",
        "mode_owner": "operation",
    },
    "zona-serve": {
        "reader": "src/indexing_mode.py",
        "permit": "config/site.json: indexing.release_permits_open",
        "mode_owner": "operation",
    },
    "yummy": {
        "reader": "container:SEO_INDEXING_ENABLED",
        "permit": "container:SEO_INDEXING_ENABLED + APP_ENV=production",
        "mode_owner": "compose",
    },
}


def контракт(adapter: str) -> dict:
    """Контракт режима для семейства. Неизвестное семейство — не умолчание."""
    return dict(КОНТРАКТ_РЕЖИМА.get(adapter) or {})


class Отказано(RuntimeError):
    """Операция остановлена с названной причиной. Слепой повтор запрещён."""


def _сейчас() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def корни_выпуска(аккаунт: str) -> tuple[str, ...]:
    """Где лежит ВЫПУЩЕННЫЙ код учётной записи, в порядке доверия.

    Одно определение на весь модуль: решение о режиме принимает тот код,
    который РАБОТАЕТ. `current` — ссылка на действующий выпуск; `app` —
    прямая установка у витрин, заведённых до появления выпусков. Рабочая
    копия репозитория доказательством не является: в ней может лежать
    что угодно, и к посетителю это не приедет.
    """
    return (f"/srv/{аккаунт}/current", f"/srv/{аккаунт}/app")


def читатель_режима(аккаунт: str, adapter: str = "") -> pathlib.Path | None:
    """Чем ВЫПУЩЕННЫЙ рантайм читает режим, или None.

    Файл ищется по контракту СЕМЕЙСТВА, а не по одному зашитому пути: у Yummy
    читателя-файла нет вовсе — режим решает код приложения по переменной
    контейнера, и требовать от него файл значило бы объявить работающий
    механизм отсутствующим.
    """
    if not аккаунт:
        return None
    к = контракт(adapter)
    путь = к.get("reader") or f"src/{ИМЯ_ЧИТАТЕЛЯ}"
    if путь.startswith("container:"):
        return None          # читатель не файл; проверяется отдельно
    for корень in корни_выпуска(аккаунт):
        п = pathlib.Path(корень) / путь
        if п.is_file():
            return п
    return None


def читатель_контейнера(домен: str) -> dict:
    """Решает ли режим КОД ПРИЛОЖЕНИЯ по переменной контейнера.

    Для Yummy это и есть читатель: `isIndexingEnabled` требует
    `SEO_INDEXING_ENABLED`, `APP_ENV=production` и публичного HTTPS-origin.
    Значение читается у ФАКТИЧЕСКИ запущенного контейнера: compose-файл уже
    однажды разошёлся с тем, что работает.
    """
    import shutil
    import subprocess as _sp
    итог = {"source": "container", "domain": домен, "found": False}
    if not shutil.which("docker"):
        итог["reason"] = "docker недоступен: переменную контейнера не прочитать"
        return итог
    try:
        имена = _sp.run(["docker", "ps", "--format", "{{.Names}}"],
                        capture_output=True, text=True, timeout=20)
        if имена.returncode != 0:
            итог["reason"] = "docker ps отказал"
            return итог
        for имя in имена.stdout.split():
            св = _sp.run(["docker", "inspect", имя], capture_output=True,
                         text=True, timeout=20)
            if св.returncode != 0:
                continue
            данные = json.loads(св.stdout)[0]
            окр = dict(кв.split("=", 1)
                       for кв in (данные.get("Config") or {}).get("Env") or []
                       if "=" in кв)
            if домен not in (окр.get("SITE_URL") or ""):
                continue
            итог.update({
                "found": True, "container": имя,
                "SEO_INDEXING_ENABLED": окр.get("SEO_INDEXING_ENABLED"),
                "APP_ENV": окр.get("APP_ENV"),
                "SITE_URL": окр.get("SITE_URL"),
            })
            итог["permits_open"] = (
                (окр.get("SEO_INDEXING_ENABLED") or "").lower() == "true"
                and окр.get("APP_ENV") == "production"
                and (окр.get("SITE_URL") or "").startswith("https://"))
            return итог
    except Exception as ош:  # noqa: BLE001
        итог["reason"] = f"{type(ош).__name__}: {ош}"
        return итог
    итог["reason"] = f"контейнера с SITE_URL для {домен} среди запущенных нет"
    return итог


def разрешение_выпуска(аккаунт: str, adapter: str = "",
                       домен: str = "") -> tuple[bool, str]:
    """Разрешение ВЫПУСКА на открытие — по контракту семейства.

    У Yummy разрешение живёт не в файле выпуска, а в переменной контейнера, и
    спрашивать у него `config/site.json` значило бы объявить «не разрешено»
    там, где механизм работает и два домена открыты.
    """
    к = контракт(adapter)
    if (к.get("permit") or "").startswith("container:"):
        св = читатель_контейнера(домен)
        if not св.get("found"):
            return False, f"контейнер не опрошен: {св.get('reason')}"
        разрешено = bool(св.get("permits_open"))
        return разрешено, (
            f"{св['container']}: SEO_INDEXING_ENABLED="
            f"{св.get('SEO_INDEXING_ENABLED')!r}, APP_ENV="
            f"{св.get('APP_ENV')!r}, SITE_URL={св.get('SITE_URL')!r}")
    return _разрешение_в_конфиге(аккаунт)


def _разрешение_в_конфиге(аккаунт: str) -> tuple[bool, str]:
    """Что о режиме говорит ВЫПУЩЕННЫЙ config/site.json.

    Читается выпуск, а не рабочая копия: решение принимает тот код, который
    работает. Строгость та же, что у рантайма — разрешением считается только
    булево `true`.
    """
    for корень in корни_выпуска(аккаунт):
        п = pathlib.Path(корень) / "config" / "site.json"
        if not п.is_file():
            continue
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError) as ош:
            return False, f"{п} не читается: {type(ош).__name__}"
        значение = (д.get("indexing") or {}).get("release_permits_open")
        if значение is True:
            return True, str(п)
        return False, (
            f"{п}: indexing.release_permits_open = {значение!r}, "
            "а разрешением считается только булево true")
    return False, f"выпущенного config/site.json у учётной записи {аккаунт} нет"


def разрешение_владельца(site_id: str) -> tuple[bool, str, str]:
    """(разрешено ли открытие, объявленный режим, пояснение).

    Разрешение и состояние — РАЗНЫЕ поля реестра ячеек, и это не формальность.
    `desired_state` говорит, какой режим объявлен сейчас; `open_authorized` —
    можно ли его менять на OPEN вообще. Будь это одно поле, операция выдавала
    бы право себе: тот же признак служил бы и разрешением, и результатом его
    применения.

    Отсутствие `open_authorized` означает «не разрешено». Пустое поле здесь не
    умолчание в пользу открытия.
    """
    try:
        ячейки = registry._ячейки()
    except (OSError, ValueError) as ош:
        return False, "", f"реестр ячеек не читается: {type(ош).__name__}"
    for я in ячейки:
        if я.get("site_id") != site_id:
            continue
        инд = я.get("indexing") or {}
        объявлен = str(инд.get("desired_state") or "").strip().upper()
        разрешено = инд.get("open_authorized") is True
        пояснение = str(инд.get("open_authorization_note")
                        or инд.get("reason") or "")
        if not инд:
            return False, "", (
                f"у {site_id} в реестре ячеек нет раздела indexing: "
                "разрешение владельца не объявлено")
        if not разрешено:
            return False, объявлен, (
                f"indexing.open_authorized = {инд.get('open_authorized')!r}: "
                "разрешением считается только булево true. "
                + (пояснение or "пояснения в реестре нет"))
        return True, объявлен, пояснение
    return False, "", f"{site_id} нет в реестре ячеек"


def _файл(домен: str, *, корень: pathlib.Path | None = None) -> pathlib.Path:
    к = корень or КОРЕНЬ
    п = к / f"{домен}.json"
    if п.resolve().parent != к.resolve():
        raise Отказано(f"{п} вне корня {к}: запись отклонена")
    return п


def текущее(домен: str, *, корень=None) -> dict:
    """Что лежит в файле состояния. Отсутствие файла — это тоже ответ."""
    п = _файл(домен, корень=корень)
    if not п.is_file():
        return {"present": False, "desired_state": "", "path": str(п)}
    try:
        д = json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        return {"present": True, "desired_state": "", "path": str(п),
                "unreadable": f"{type(ош).__name__}"}
    return {"present": True, "path": str(п),
            "desired_state": str(д.get("desired_state") or "").strip().upper(),
            "revision": д.get("revision"), "site": д.get("site"),
            "changed_at": д.get("changed_at"), "authorized_by": д.get("authorized_by"),
            "policy_digest": д.get("policy_digest")}


# ------------------------------------------------------- публичные сигналы
def _ответ(url: str, таймаут: int = 20) -> tuple[str, list[str], str]:
    """(код, ВСЕ значения X-Robots-Tag, тело).

    Значения берутся через `get_all`, а не из словаря заголовков. Это
    исправленная ошибка измерения: на :443 заголовок добавляют и nginx, и
    приложение, а `dict(ответ.headers)` оставляет только ПОСЛЕДНЕЕ вхождение
    одноимённого заголовка. После открытия приложения такой замер показал бы
    один «index, follow» и объявил бы открытым сайт, которому nginx всё ещё
    запрещает обход, — то есть ровно то, чего эта операция не должна делать.
    """
    код, значения, тело, _ = _ответ_с_цепочкой(url, таймаут)
    return код, значения, тело


def всё(сообщение) -> list[str]:
    """ВСЕ значения `X-Robots-Tag` ответа, в порядке получения.

    Отдельной функцией на уровне модуля: её зовут оба замера, и копия внутри
    одного из них однажды уже разошлась бы с другим.
    """
    if сообщение is None:
        return []
    значения = сообщение.get_all("X-Robots-Tag") or []
    return [str(з).strip() for з in значения]


def _ответ_с_цепочкой(url: str, таймаут: int = 20,
                      прыжков: int = 3) -> tuple[str, list[str], str, list[str]]:
    """То же, но перенаправления проходятся ЯВНО и называются.

    Зачем. Заголовки ответа-перенаправления — это заголовки ПЕРЕНАПРАВЛЕНИЯ, а
    не страницы. На `http://yummyani.site/` стоит 308 на https, и у самого 308
    есть `X-Robots-Tag: noindex, nofollow`; страница по адресу перенаправления
    при этом отдаёт `index, follow` и разрешающий robots.txt. Прежний замер
    приписывал заголовок перенаправления странице и объявлял домен закрытым —
    то есть ровно обратное действительности.

    Почему не хватало `urlopen`. 301/302/303/307 он проходит сам, а 308 в
    Python 3.10 не проходит: он приходит как `HTTPError`, и в прежней ветке
    брались именно его заголовки.

    Переход делается только на ТОТ ЖЕ хост: перенаправление на чужой домен —
    это уже не страница этого сайта, и судить по ней о его индексации нельзя.
    """
    цепочка: list[str] = []
    текущий = url
    из_хоста = urllib.parse.urlsplit(url).hostname or ""
    for _ in range(прыжков + 1):
        try:
            req = urllib.request.Request(
                текущий, headers={"User-Agent": "qwen-indexing"})
            о = urllib.request.urlopen(req, timeout=таймаут)
            код, заголовки = str(о.status), о.headers
            тело = о.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            код, заголовки, тело = str(e.code), e.headers, ""
        except Exception as e:  # noqa: BLE001 — сетевая беда тоже ответ
            return type(e).__name__, [], "", цепочка
        куда = (заголовки.get("Location") or "") if заголовки is not None else ""
        if код.isdigit() and 300 <= int(код) < 400 and куда:
            цель = urllib.parse.urljoin(текущий, куда)
            if (urllib.parse.urlsplit(цель).hostname or "") != из_хоста:
                # Чужой хост: дальше не идём и сигналы оттуда не берём.
                цепочка.append(f"{код} -> {цель} (чужой хост, не прошли)")
                return код, всё(заголовки), тело, цепочка
            цепочка.append(f"{код} -> {цель}")
            текущий = цель
            continue
        return код, всё(заголовки), тело, цепочка
    цепочка.append("слишком много перенаправлений")
    return "LoopError", [], "", цепочка


def порт_приложения(site_id: str) -> int:
    """Порт витрины из манифеста рантайма, 0 — если неизвестен."""
    if not site_id:
        return 0
    try:
        from factory.cell import runtime as _р
        return int(_р.размещение(site_id).port or 0)
    except Exception:  # noqa: BLE001 — неизвестный порт не ломает диагностику
        return 0


def сигналы(домен: str, *, порт: int = 0) -> dict:
    """Четыре сигнала на живом домене, каждый отдельной величиной.

    X-Robots-Tag читается ПЕРЕЧНЕМ значений, а не одной строкой: на :443 его
    добавляют и nginx, и приложение, и слитая строка скрыла бы, что одно из
    двух ещё запрещает обход.

    `порт` — собственный порт витрины. Проба на нём отличает вклад приложения
    ТОЧНО: до неё вклад приложения выводился из ответа на :80 в расчёте, что
    серверный блок там заголовка не добавляет. У витрин Lords это неправда —
    `add_header ... always` стоит в обоих блоках, — и на :80 было видно два
    заголовка без возможности сказать, чьи они.
    """
    итог: dict = {"domain": домен, "at": _сейчас()}
    if порт:
        кп, значения_п, тело_п = _ответ(f"http://127.0.0.1:{порт}/")
        итог["app_port"] = порт
        итог["app_port_http"] = кп
        итог["x_robots_values_app"] = значения_п
        мп = re.search(r'<meta name="robots" content="([^"]*)"', тело_п)
        итог["meta_robots_app"] = мп.group(1) if мп else "не объявлен"
        _, _, роботс_п = _ответ(f"http://127.0.0.1:{порт}/robots.txt")
        итог["robots_txt_app"] = роботс_п
    for схема, метка in (("https", ""), ("http", "_http80")):
        код, значения, тело, цепочка = _ответ_с_цепочкой(f"{схема}://{домен}/")
        итог[f"home_http{метка}"] = код
        итог[f"x_robots_values{метка}"] = значения
        итог[f"x_robots_count{метка}"] = len(значения)
        if цепочка:
            итог[f"redirects{метка}"] = цепочка
        if метка == "":
            м = re.search(r'<meta name="robots" content="([^"]*)"', тело)
            итог["meta_robots_home"] = м.group(1) if м else "не объявлен"
    кр, _, роботс = _ответ(f"https://{домен}/robots.txt")
    итог["robots_txt_http"] = кр
    итог["robots_txt"] = роботс
    кс, _, _ = _ответ(f"https://{домен}/sitemap.xml")
    итог["sitemap_http"] = кс
    # Проба служебного пути. Нужна, чтобы отличить вклад nginx от вклада
    # приложения: в открытом режиме nginx сохраняет запрет на служебных путях,
    # и заголовков там на один больше, чем на обычной странице. Один заголовок
    # в ответе источника не называет, и операция однажды на этом ошиблась.
    ск, служебные, _ = _ответ(f"https://{домен}{ПРОБА_СЛУЖЕБНОГО}")
    итог["service_path"] = ПРОБА_СЛУЖЕБНОГО
    итог["service_path_http"] = ск
    итог["x_robots_values_service"] = служебные
    итог["x_robots_count_service"] = len(служебные)
    return итог


# --------------------------------------------------- слой nginx: кто добавил
#: Где искать конфигурацию сайта. Порядок тот же, что у root-скрипта: иначе
#: операция судила бы по одному файлу, а владелец правил другой.
КОРЕНЬ_NGINX = pathlib.Path(os.environ.get("QWEN_NGINX_ROOT", "/etc/nginx"))

#: Служебный путь, который в ОТКРЫТОМ режиме остаётся закрытым заголовком
#: nginx. Он и служит пробой: если на нём заголовков на один больше, чем на
#: обычной странице, значит добавляет именно nginx, и добавляет избирательно.
ПРОБА_СЛУЖЕБНОГО = "/healthz"


#: Где лежат живые конфигурации. Резервные копии исключены отдельно: nginx
#: грузит `sites-enabled/*` целиком, и файл `.bak.*` там был бы живым, но
#: судить по нему о режиме нельзя — это слепок прошлого.
КАТАЛОГИ_NGINX = ("lords", "sites-available", "sites-enabled", "conf.d")


def _резервная(путь: pathlib.Path) -> bool:
    имя = путь.name
    return (".bak" in имя or имя.endswith("~") or "backup" in имя
            or "backups" in путь.parts)


def конфиги_сайта(site_id: str, домен: str) -> list[pathlib.Path]:
    """ВСЕ живые файлы, объявляющие серверное имя этого домена.

    Прежде брался первый подошедший по имени, и этого не хватало: у lords-05
    блок :80 лежит в `lords/lords-05.conf`, а блок :443 — в отдельном
    `lords/lords-05-tls.conf` (он ставится после выпуска сертификата). То
    есть операция судила о слое по файлу, которого краулер не видит.
    """
    найдено: list[pathlib.Path] = []
    for каталог in КАТАЛОГИ_NGINX:
        корень = КОРЕНЬ_NGINX / каталог
        if not корень.is_dir():
            continue
        for путь in sorted(корень.iterdir()):
            if not путь.is_file() or _резервная(путь) or путь.suffix != ".conf":
                continue
            try:
                текст = путь.read_text(encoding="utf-8", errors="replace")
            except OSError:
                # Нечитаемая КОНФИГУРАЦИЯ — не «ничего нет»: она попадает в
                # перечень, и по ней одной слой открытым не объявляется.
                найдено.append(путь)
                continue
            по_имени = (путь.stem == site_id
                        or путь.stem.startswith(f"{site_id}-")
                        or путь.stem == домен
                        or путь.stem == f"www.{домен}")
            по_содержимому = bool(re.search(
                rf"(?m)^\s*server_name\s+[^;]*\b{re.escape(домен)}\b", текст))
            if по_имени or по_содержимому:
                найдено.append(путь)
    # Дедупликация по РАЗРЕШЁННОМУ пути: `sites-enabled/x.conf` — обычно
    # ссылка на `sites-available/x.conf`, и считать их двумя источниками
    # значило бы удваивать каждую строку заголовка.
    итог: list[pathlib.Path] = []
    видено: set = set()
    for путь in найдено:
        ключ = str(путь.resolve()) if путь.exists() else str(путь)
        if ключ in видено:
            continue
        видено.add(ключ)
        итог.append(путь)
    return итог


def _конфиг_сайта(site_id: str, домен: str) -> pathlib.Path | None:
    """Первый живой файл домена. Оставлен для совместимости вызовов."""
    файлы = конфиги_сайта(site_id, домен)
    return файлы[0] if файлы else None


def _значение_переменной(конфиг: str, имя: str) -> tuple[str | None, str]:
    """(значение по умолчанию для обычных страниц или None, откуда взято).

    Переменная объявляется блоком `map $uri $имя { include <файл>; }`, и
    значение для обычных страниц — это строка `default` включаемого файла.
    Разбирается именно он, а не догадка по ответу: включаемый файл и есть
    источник, его пишет root-скрипт.

    `None` означает «не определено»: нет объявления, файл не читается, нет
    строки `default`. Возвращать пустую строку в этих случаях нельзя — пустое
    значение здесь ОЗНАЧАЕТ открытый режим, и нечитаемый файл стал бы
    разрешением. Поймано тестом: до правки нечитаемый include давал
    `denying: False`.
    """
    м = re.search(r"map\s+\$uri\s+\$" + re.escape(имя) + r"\s*\{(.*?)\}",
                  конфиг, re.S)
    if not м:
        return None, f"объявления map ${имя} в конфигурации нет"
    тело = м.group(1)
    вкл = re.search(r"include\s+([^\s;]+)\s*;", тело)
    источник = тело
    откуда = "блок map"
    if вкл:
        п = pathlib.Path(вкл.group(1))
        try:
            источник = п.read_text(encoding="utf-8")
            откуда = str(п)
        except OSError as ош:
            return None, f"{п} не читается: {type(ош).__name__}"
    по_умолчанию = re.search(r'(?m)^\s*default\s+"?([^";]*)"?\s*;', источник)
    if по_умолчанию is None:
        return None, f"{откуда}: строки default нет"
    return по_умолчанию.group(1).strip(), откуда


def _обработчик_корня(блок: str) -> str:
    """"serve" | "redirect" | "unknown" — чем блок отвечает на `/`.

    Разбирается именно `location /` (и `location = /`), а не весь блок:
    `location ^~ /.well-known/...` с `root` есть у каждого домена под ACME и
    о странице ничего не говорит.
    """
    строки = блок.split("\n")
    i = 0
    тело_корня = None
    while i < len(строки):
        if re.match(r"^\s*location\s+(=\s*)?/\s*\{", строки[i]):
            глубина = 0
            собрано = []
            while i < len(строки):
                глубина += строки[i].count("{") - строки[i].count("}")
                собрано.append(строки[i])
                i += 1
                if глубина <= 0:
                    break
            тело_корня = "\n".join(собрано)
            break
        i += 1
    область = тело_корня if тело_корня is not None else блок
    if re.search(r"\breturn\s+30\d\b", область):
        return "redirect"
    if re.search(r"\b(proxy_pass|fastcgi_pass|uwsgi_pass|grpc_pass|root|alias|"
                 r"try_files)\b", область):
        return "serve"
    # Ни перехода, ни источника: решает серверный уровень.
    if re.search(r"(?m)^\s*return\s+30\d\b", блок):
        return "redirect"
    if re.search(r"(?m)^\s*(root|proxy_pass)\b", блок):
        return "serve"
    return "unknown"


def серверные_блоки(текст: str) -> list[dict]:
    """Серверные блоки конфигурации: имена, перенаправление, строки заголовка.

    Считается по фигурным скобкам, а не регулярным выражением: вложенные
    `location` и `if` ломают любой «от server до }».
    """
    блоки: list[dict] = []
    строки = текст.split("\n")
    i = 0
    while i < len(строки):
        if not re.match(r"^\s*server\s*\{", строки[i]):
            i += 1
            continue
        глубина = 0
        тело: list[str] = []
        while i < len(строки):
            глубина += строки[i].count("{") - строки[i].count("}")
            тело.append(строки[i])
            i += 1
            if глубина <= 0:
                break
        текст_блока = "\n".join(тело)
        имена: list[str] = []
        for м in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", текст_блока):
            имена.extend(м.group(1).split())
        # Отдаёт ли блок страницы — решает обработчик КОРНЕВОГО пути, а не
        # наличие хоть какого-то `root`. Блок :80 у Yummy имеет `root` в
        # location для ACME и `return 308` в `location /`: страниц он не
        # отдаёт, и его заголовок — заголовок перехода.
        корневой = _обработчик_корня(текст_блока)
        переход = корневой == "redirect"
        # Неразобранный блок считается ОТДАЮЩИМ: его заголовок может дойти до
        # страницы, и пропустить его значило бы объявить домен открытым по
        # незнанию. Исключается только явное перенаправление.
        отдаёт = not переход
        блоки.append({
            "server_name": имена,
            "redirect_only": переход and not отдаёт,
            "add_header_lines": [с.strip() for с in тело
                                 if re.search(r"^\s*add_header\s+X-Robots-Tag\s", с)],
            "listen": [м.group(1).strip() for м in
                       re.finditer(r"(?m)^\s*listen\s+([^;]+);", текст_блока)],
        })
    return блоки


def блоки_страницы(текст: str, домен: str) -> list[dict]:
    """Блоки, которые ОТДАЮТ страницы этого домена.

    Блок-перенаправление отбрасывается: его заголовок — заголовок перехода, а
    не страницы. Так и вышло у Yummy: `add_header X-Robots-Tag "noindex"`
    стоит в блоке :80 и в блоке `www` — оба только перенаправляют, — а в
    каноническом блоке его нет, и домен фактически открыт. Операция же
    называла слой nginx запрещающим, потому что искала строку по всему файлу.
    """
    годные = []
    for б in серверные_блоки(текст):
        if б["redirect_only"]:
            continue
        имена = б["server_name"]
        # Блок без имён обслуживает всё, что дошло: его учитываем.
        if имена and домен not in имена and f"www.{домен}" not in имена:
            continue
        годные.append(б)
    return годные


def слой_nginx(site_id: str, домен: str, сиг: dict | None = None) -> dict:
    """Добавляет ли САМ nginx запрет на страницах этого домена.

    Почему не по публичному ответу целиком. Один заголовок в ответе источника
    не называет: его мог поставить и nginx, и приложение. Операция на этом
    месте уже ошибалась дважды, и оба раза в сторону неправды:

      * считала слой закрытым по ЛЮБОМУ запрещающему заголовку — и после
        снятия запрета в nginx продолжала показывать `denying: true`, потому
        что закрыто было приложение;
      * искала строку `add_header` по ВСЕМУ файлу — и называла закрытым
        домен, у которого эта строка стоит только в блоках-перенаправлениях
        (так вышло у `yummyani.site`: канонический блок :443 заголовка не
        несёт, и домен фактически открыт).

    Поэтому источник определяется по КОНФИГУРАЦИИ, и притом:

      * берутся ВСЕ живые файлы, объявляющие серверное имя домена (у lords-05
        блок :443 лежит отдельным файлом от блока :80);
      * внутри файлов — только блоки, которые ОТДАЮТ страницы: блок, чей
        `location /` отвечает `return 30x`, страницу не отдаёт;
      * фиксированная строка `add_header X-Robots-Tag "noindex…"` → закрыт;
        заголовок на переменной `map $uri` → решает `default` включаемого
        файла; строки нет → своего запрета nginx не добавляет.

    Нечитаемая конфигурация не читается как «запрета нет»: при ней открытым
    слой называется ТОЛЬКО если это подтверждает измерение — надбавка nginx к
    заголовкам приложения равна нулю.
    """
    итог: dict = {"site_id": site_id, "managed_by_this_operation": False}
    файлы = конфиги_сайта(site_id, домен)
    итог["configs"] = [str(ф) for ф in файлы]
    итог["config"] = str(файлы[0]) if файлы else ""
    if not файлы:
        итог.update({"mode": "unknown", "denying": None,
                     "evidence": f"конфигурации с серверным именем {домен} не "
                                 f"найдено в {КОРЕНЬ_NGINX}: слой не определён"})
        return итог

    нечитаемые: list[str] = []
    отдающие: list[tuple[pathlib.Path, dict]] = []
    в_переходах = 0
    видено_содержимое: set = set()
    for ф in файлы:
        try:
            текст = ф.read_text(encoding="utf-8")
        except OSError as ош:
            нечитаемые.append(f"{ф}: {type(ош).__name__}")
            continue
        отпечаток = hashlib.sha256(текст.encode("utf-8")).hexdigest()
        if отпечаток in видено_содержимое:
            continue          # копия того же файла (sites-available/enabled)
        видено_содержимое.add(отпечаток)
        for б in серверные_блоки(текст):
            имена = б["server_name"]
            свой = (not имена) or домен in имена or f"www.{домен}" in имена
            if not свой:
                continue
            if б["redirect_only"]:
                в_переходах += len(б["add_header_lines"])
                continue
            отдающие.append((ф, б))
    if нечитаемые:
        итог["unreadable_configs"] = нечитаемые
    if в_переходах:
        итог["add_header_in_redirect_blocks"] = в_переходах

    строки = [(ф, с) for ф, б in отдающие for с in б["add_header_lines"]]
    итог["add_header_lines"] = [с for _, с in строки]
    if not отдающие:
        итог.update({"mode": "unknown", "denying": None,
                     "evidence": f"ни один серверный блок не отдаёт страницы "
                                 f"{домен}: слой не определён"})
    elif not строки:
        пояснение = ("в блоках, отдающих страницы, add_header X-Robots-Tag нет "
                     "— своего запрета nginx не добавляет")
        if в_переходах:
            пояснение += (f"; в блоках-перенаправлениях таких строк "
                          f"{в_переходах} — это заголовок перехода, а не "
                          "страницы")
        итог.update({"mode": "open", "denying": False, "evidence": пояснение})
    else:
        режимы: list[str] = []
        пояснения: list[str] = []
        for ф, с in строки:
            зн = re.search(r"add_header\s+X-Robots-Tag\s+(\S+)", с.strip())
            значение = зн.group(1) if зн else ""
            if значение.startswith("$"):
                try:
                    текст = ф.read_text(encoding="utf-8")
                except OSError:
                    текст = ""
                по_умолчанию, откуда = _значение_переменной(текст, значение[1:])
                if по_умолчанию is None:
                    режимы.append("unknown")
                    пояснения.append(f"{значение}: {откуда}")
                elif "noindex" in по_умолчанию.lower():
                    режимы.append("closed")
                    пояснения.append(f"{откуда}: default \"{по_умолчанию}\"")
                else:
                    режимы.append("open")
                    пояснения.append(
                        f"{откуда}: default пуст — заголовок не добавляется")
                итог["managed_by_this_operation"] = True
            elif "noindex" in значение.lower():
                режимы.append("closed")
                пояснения.append(f"{ф}: {с}")
            else:
                режимы.append("open")
                пояснения.append(f"{ф}: {с}")
        режим = ("closed" if "closed" in режимы
                 else "unknown" if "unknown" in режимы else "open")
        итог.update({"mode": режим,
                     "denying": None if режим == "unknown" else режим == "closed",
                     "evidence": "; ".join(пояснения)})

    if сиг:
        обычная = сиг.get("x_robots_count")
        служебная = сиг.get("x_robots_count_service")
        разница = (None if обычная is None or служебная is None
                   else служебная - обычная)
        итог["cross_check"] = {
            "headers_on_home_https": обычная,
            "headers_on_service_path_https": служебная,
            "service_path": ПРОБА_СЛУЖЕБНОГО,
            "nginx_adds_on_service_path": None if разница is None else разница > 0,
            "agrees_with_config": None,
        }
        # Надбавка nginx: сколько заголовков ответа НЕ от приложения. Считается
        # только когда вклад приложения измерен на его собственном порту —
        # вычитать неизмеренное значило бы считать домыслом.
        свои = сиг.get("x_robots_values_app")
        if свои is not None and обычная is not None:
            надбавка = обычная - len(свои)
            итог["cross_check"]["nginx_extra_headers"] = надбавка
            итог["cross_check"]["app_headers"] = len(свои)
        else:
            надбавка = None
        if разница is not None and итог.get("mode") in ("open", "closed"):
            # Ожидание «на служебном пути заголовков на один больше» верно
            # ТОЛЬКО там, где слоем распоряжается эта операция: запрет стоит на
            # переменной `map $uri`, и служебные пути из него исключены. Если
            # заголовка в блоке нет вовсе (его убрали целиком, как у
            # yummyani.site), служебный путь ничем не отличается от обычного —
            # и объявлять это расхождением было бы ложной тревогой.
            if итог["mode"] == "open" and not итог["managed_by_this_operation"]:
                итог["cross_check"]["agrees_with_config"] = None
                итог["cross_check"]["note"] = (
                    "слоем распоряжается не эта операция: заголовка нет ни на "
                    "обычной странице, ни на служебном пути — сверять по "
                    "разнице нечего")
            else:
                ожидается = (разница > 0 if итог["mode"] == "open"
                             else разница == 0)
                итог["cross_check"]["agrees_with_config"] = bool(ожидается)
        # Нечитаемая конфигурация: «открыт» подтверждается измерением или не
        # объявляется вовсе.
        if нечитаемые and итог.get("mode") == "open":
            if надбавка == 0:
                итог["evidence"] += (
                    f"; часть конфигураций не читается ({len(нечитаемые)}), но "
                    "измерение согласуется: надбавки nginx к заголовкам "
                    "приложения нет")
            else:
                итог.update({
                    "mode": "unknown", "denying": None,
                    "evidence": итог["evidence"]
                    + f"; часть конфигураций не читается ({нечитаемые}), а "
                      "измерение открытости не подтверждает: "
                      f"надбавка nginx = {надбавка}"})
    elif нечитаемые and итог.get("mode") == "open":
        итог.update({"mode": "unknown", "denying": None,
                     "evidence": итог["evidence"]
                     + f"; часть конфигураций не читается ({нечитаемые}), а "
                       "измерения нет: открытым слой не объявляется"})
    return итог


def слой_приложения(сиг: dict) -> dict:
    """Что добавляет само приложение. Измеряется на :80.

    На порту 80 серверный блок сайта заголовка не добавляет — проверено по
    конфигурации, — поэтому там виден ровно вклад приложения. Если на :80
    заголовков больше одного, вывод не делается: значит заголовок добавляет
    кто-то ещё, и приписывать его приложению нельзя.
    """
    на_порту = "x_robots_values_app" in сиг
    if на_порту:
        # Точное измерение: собственный порт витрины, минуя nginx.
        значения = сиг.get("x_robots_values_app") or []
        мета = str(сиг.get("meta_robots_app") or "")
        тело_роботс = сиг.get("robots_txt_app") or ""
    else:
        значения = сиг.get("x_robots_values_http80") or []
        мета = str(сиг.get("meta_robots_home") or "")
        тело_роботс = сиг.get("robots_txt") or ""
    запрещает = any("noindex" in з.lower() for з in значения) or \
        "noindex" in мета.lower()
    итог = {
        "measured_on": (f"127.0.0.1:{сиг.get('app_port')}" if на_порту
                        else "http://:80"),
        "x_robots": значения,
        "meta_robots": мета or None,
        "robots_txt_closed": bool(
            re.search(r"(?mi)^\s*Disallow:\s*/\s*$", тело_роботс)),
    }
    итог["denying"] = bool(запрещает or итог["robots_txt_closed"])
    if not на_порту and len(значения) > 1:
        итог["note"] = (
            f"на :80 заголовков {len(значения)} — вклад приложения отдельно не "
            "выделяется: заголовок добавляет кто-то ещё, а порт витрины "
            "неизвестен")
    if на_порту and not значения:
        итог["note"] = (
            f"витрина на 127.0.0.1:{сиг.get('app_port')} заголовка не "
            "добавляет: по его отсутствию нельзя отличить открытый режим от "
            "витрины, которая про режим не знает")
    return итог

def оценить(сиг: dict) -> tuple[str, list[str]]:
    """(что сайт отдаёт фактически, перечень запрещающих сигналов).

    Открытым считается только сайт, у которого НИ ОДИН сигнал не запрещает
    обход. Один запрещающий заголовок делает открытыми остальные три
    бессмысленными, поэтому «частично открыт» здесь не состояние, а список
    причин.
    """
    запрещают: list[str] = []
    for метка, где in (("", "https"), ("_http80", "http")):
        for значение in сиг.get(f"x_robots_values{метка}") or []:
            if "noindex" in значение.lower():
                запрещают.append(f"X-Robots-Tag ({где}): {значение}")
    если_мета = str(сиг.get("meta_robots_home") or "")
    if "noindex" in если_мета.lower():
        запрещают.append(f"meta robots: {если_мета}")
    if если_мета == "не объявлен":
        запрещают.append("meta robots не объявлен: режим страницы неизвестен")
    тело = сиг.get("robots_txt") or ""
    if re.search(r"(?mi)^\s*Disallow:\s*/\s*$", тело):
        запрещают.append("robots.txt: Disallow: /")
    if сиг.get("robots_txt_http") != "200":
        запрещают.append(f"robots.txt ответил {сиг.get('robots_txt_http')}")
    return (ЗАКРЫТ if запрещают else ОТКРЫТ), запрещают


# ----------------------------------------------------------- предпроверка
def проверить(site: str, *, mode: str, expect_release: str = "") -> dict:
    """Всё, что можно проверить ДО единой записи. Ничего не меняет."""
    режим = (mode or "").strip().upper()
    if режим not in (ОТКРЫТ, ЗАКРЫТ):
        raise Отказано(f"режим {mode!r} неизвестен: open или closed")
    s = editorial._сайт(site)

    итог: dict = {"site": s.domain, "site_id": s.site_id, "requested": режим,
                  "account": s.account, "published_release": s.published_release,
                  "ok": False, "blockers": [], "notes": []}

    # 1. Ожидаемый выпуск. Сверяется ИМЯ КАТАЛОГА ВЫПУСКА, а не поле манифеста:
    #    у animedia.space манифест объявляет source_commit efdef56e…, а
    #    выложен e84b4be48d86 — манифест сборщик не пересчитывает, и доверять
    #    ему значило бы сверяться с устаревшей записью.
    if expect_release:
        ожид = expect_release.strip().lower()
        факт = (s.published_release or "").strip().lower()
        if not (факт.startswith(ожид) or ожид.startswith(факт)):
            raise Отказано(
                f"{s.domain}: выложен выпуск {факт or 'не найден'}, а ожидался "
                f"{ожид}. Операция остановлена до единой записи: менять режим "
                "у другой версии нельзя — проверьте "
                "`python3 -m factory.qwen sites` и повторите с верным значением")
        итог["release_matches_expectation"] = True

    # 2. Читатель режима — по контракту СЕМЕЙСТВА, а не по одному пути.
    к = контракт(s.adapter)
    итог["contract"] = к or {"reason": f"семейство {s.adapter!r} контракта не объявило"}
    итог["mode_owner"] = к.get("mode_owner") or "unknown"
    if not к:
        итог["blockers"].append(
            f"семейство {s.adapter or 'не определено'} не объявило контракт "
            "режима индексации: ни читателя, ни источника разрешения. "
            "Операция остановлена — BLOCKED")
    elif (к.get("reader") or "").startswith("container:"):
        # Режим решает код приложения по переменной контейнера. Читатель
        # существует, но файлом не является: требовать файл значило бы
        # объявить работающий механизм отсутствующим.
        св = читатель_контейнера(s.domain)
        итог["runtime_reader"] = (f"{св.get('container')}: "
                                  f"{к['reader'].split(':',1)[1]}"
                                  if св.get("found") else "")
        итог["container"] = св
        if not св.get("found"):
            итог["blockers"].append(
                f"контейнер домена не опрошен: {св.get('reason')}. Чем "
                "приложение решает режим — не установлено, BLOCKED")
    else:
        читатель = читатель_режима(s.account, s.adapter)
        итог["runtime_reader"] = str(читатель) if читатель else ""
        if читатель is None:
            итог["blockers"].append(
                f"в выпущенном рантайме нет {к['reader']}: витрина режим не "
                "читает, и запись файла состояния ничего бы не изменила. "
                "BLOCKED до выпуска читателя")

    # 2б. Режим, которым распоряжается не операция, операцией не меняется.
    if режим and к.get("mode_owner") == "compose" :
        итог["blockers"].append(
            f"режимом этого семейства распоряжается {к['mode_owner']}: "
            "значение приходит переменной контейнера "
            "(SEO_INDEXING_ENABLED), и сменить его может только пересборка "
            "окружения владельцем. Операция не вправе подменять его файлом "
            "состояния — это завело бы второе решение о том же. BLOCKED")

    # 3. Разрешение выпуска.
    разрешено, откуда = разрешение_выпуска(s.account, s.adapter, s.domain)
    итог["release_permits_open"] = разрешено
    итог["release_config"] = откуда
    if режим == ОТКРЫТ and not разрешено:
        итог["blockers"].append(f"выпуск не разрешает открытие: {откуда}")

    # 4. Разрешение владельца.
    разрешил, объявлен, пояснение = разрешение_владельца(s.site_id)
    итог["owner_authorized_open"] = разрешил
    итог["owner_declared_state"] = объявлен or None
    итог["owner_note"] = пояснение
    if режим == ОТКРЫТ and not разрешил:
        итог["blockers"].append(
            f"владелец не разрешал открытие {s.domain}: {пояснение}")

    # 5. Фактические публичные сигналы и состояние файла.
    итог["current_state_file"] = текущее(s.domain)
    сиг = сигналы(s.domain, порт=порт_приложения(s.site_id))
    итог["public_now"] = сиг
    фактически, запрещают = оценить(сиг)
    итог["public_mode_now"] = фактически
    итог["denying_signals_now"] = запрещают

    # 6. Слои запрета ПООТДЕЛЬНО. Заголовок nginx операция не меняет и не
    #    может: конфигурация принадлежит root. Но назвать его обязана — иначе
    #    «открыто» в файле состояния разошлось бы с закрытым сайтом.
    #
    #    Источник определяется по КОНФИГУРАЦИИ, а не по числу заголовков в
    #    ответе. Ровно здесь операция однажды и ошибалась: она объявляла слой
    #    nginx закрытым всякий раз, когда запрещал ЛЮБОЙ `X-Robots-Tag`, и
    #    после успешного снятия запрета в nginx продолжала показывать
    #    `denying: true` — потому что закрыто было ПРИЛОЖЕНИЕ (файла состояния
    #    нет, fail-closed). Один заголовок в ответе источника не называет.
    слой_ng = слой_nginx(s.site_id, s.domain, сиг)
    слой_ng["owner_command"] = (
        f"sudo bash automation/host/apply-indexing-nginx-root.sh "
        f"--site {s.site_id} --mode {'open' if режим == ОТКРЫТ else 'closed'}")
    итог["nginx_layer"] = слой_ng
    итог["app_layer"] = слой_приложения(сиг)

    # 7. Повтор.
    итог["already"] = (итог["current_state_file"].get("desired_state") == режим
                       and фактически == режим)
    итог["ok"] = not итог["blockers"]
    return итог


# ----------------------------------------------------------------- запись
def _отпечаток(запись: dict) -> str:
    основа = {k: запись[k] for k in ("site", "desired_state", "revision",
                                     "authorized_by")}
    return "sha256:" + hashlib.sha256(
        json.dumps(основа, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode()).hexdigest()


def _снимок(s, сиг: dict, прежнее: dict) -> pathlib.Path:
    ЖУРНАЛ.mkdir(parents=True, exist_ok=True)
    п = ЖУРНАЛ / f"{s.domain}.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.before.json"
    п.write_text(json.dumps({"site": s.domain, "site_id": s.site_id,
                             "at": _сейчас(), "state_file": прежнее,
                             "public": сиг}, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return п


def _записать(п: pathlib.Path, запись: dict) -> None:
    п.parent.mkdir(parents=True, exist_ok=True)
    врем = п.with_name(п.name + f".tmp.{os.getpid()}")
    текст = json.dumps(запись, ensure_ascii=False, indent=1) + "\n"
    with open(врем, "w", encoding="utf-8") as fh:
        fh.write(текст)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(врем, п)
    try:
        дк = os.open(str(п.parent), os.O_RDONLY)
        try:
            os.fsync(дк)
        finally:
            os.close(дк)
    except OSError:
        pass
    json.loads(п.read_text(encoding="utf-8"))  # битое не оставляем


def _дописать_журнал(запись: dict) -> None:
    ЖУРНАЛ.mkdir(parents=True, exist_ok=True)
    with (ЖУРНАЛ / "operations.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")


def установить(site: str, *, mode: str, author: str,
               expect_release: str = "", корень=None) -> dict:
    """Сменить режим одного сайта и проверить результат на его ответе."""
    режим = (mode or "").strip().upper()
    пред = проверить(site, mode=режим, expect_release=expect_release)
    if not пред["ok"]:
        raise Отказано(
            f"{пред['site']}: предпроверка не пройдена — "
            + "; ".join(пред["blockers"]))
    s = editorial._сайт(site)
    прежнее = пред["current_state_file"]
    снимок = _снимок(s, пред["public_now"], прежнее)

    if прежнее.get("desired_state") == режим:
        # Повтор не пишет ничего: иначе в журнале появлялась бы операция,
        # которая ничего не изменила, а время файла сдвигалось бы впустую.
        итог = подтвердить(site, ожидаемый=режим)
        итог.update({"changed": False, "state_file": прежнее,
                     "note": "файл состояния уже в этом режиме — запись не велась",
                     "snapshot": str(снимок)})
        return итог

    ревизия = int(прежнее.get("revision") or 0) + 1
    запись = {
        "schema_version": СХЕМА,
        "site": s.domain,
        "site_id": s.site_id,
        "desired_state": режим,
        "revision": ревизия,
        "changed_at": _сейчас(),
        "authorized_by": author,
        "owner_authorized_open": пред["owner_authorized_open"],
        "owner_note": пред["owner_note"],
        "release": s.published_release,
        "note": ("Состояние читает рантайм витрины (src/indexing_mode.py). "
                 "Разрешения живут отдельно: у владельца — в реестре ячеек, у "
                 "выпуска — в config/site.json. Этот файл один сайт не "
                 "открывает."),
    }
    запись["policy_digest"] = _отпечаток(запись)
    п = _файл(s.domain, корень=корень)
    _записать(п, запись)
    _дописать_журнал({"at": _сейчас(), "op": "set", "site": s.domain,
                      "from": прежнее.get("desired_state") or "(нет файла)",
                      "to": режим, "revision": ревизия, "author": author,
                      "snapshot": str(снимок), "state_file": str(п)})

    итог = подтвердить(site, ожидаемый=режим)
    итог.update({"changed": True, "revision": ревизия, "state_file": str(п),
                 "snapshot": str(снимок),
                 "nginx_layer": пред["nginx_layer"]})
    return итог


def подтвердить(site: str, *, ожидаемый: str = "", ждать: bool = True) -> dict:
    """Что сайт ОТДАЁТ сейчас. Итог считается по ответу, а не по команде."""
    s = editorial._сайт(site)
    ожид = (ожидаемый or "").strip().upper()
    предел = time.time() + (ОЖИДАНИЕ_С if (ждать and ожид) else 0)
    попыток = 0
    while True:
        попыток += 1
        сиг = сигналы(s.domain, порт=порт_приложения(s.site_id))
        фактически, запрещают = оценить(сиг)
        if not ожид or фактически == ожид or time.time() >= предел:
            break
        time.sleep(ШАГ_С)
    итог = {
        "site": s.domain, "site_id": s.site_id,
        "expected": ожид or None,
        "public_mode": фактически,
        "confirmed": (фактически == ожид) if ожид else None,
        "denying_signals": запрещают,
        "attempts": попыток,
        "signals": сиг,
        "state_file": текущее(s.domain),
    }
    if ожид == ОТКРЫТ and запрещают:
        # Причина обязана называть СЛОЙ, а не просто перечислять заголовки:
        # иначе «снимите запрет в nginx» звучало бы и тогда, когда nginx уже
        # открыт, а закрыто приложение.
        слой_ng = слой_nginx(s.site_id, s.domain, сиг)
        слой_пр = слой_приложения(сиг)
        итог["nginx_layer"] = слой_ng
        итог["app_layer"] = слой_пр
        части = ["сайт отдаёт запрет: " + "; ".join(запрещают)]
        if слой_ng.get("denying"):
            части.append(
                "запрет добавляет nginx — этой операцией он не управляется, "
                "нужен однократный запуск владельца "
                f"automation/host/apply-indexing-nginx-root.sh "
                f"--site {s.site_id} --mode open. Основание: "
                + str(слой_ng.get("evidence") or ""))
        elif слой_ng.get("denying") is None:
            части.append(
                "слой nginx не определён: " + str(слой_ng.get("evidence") or ""))
        else:
            части.append(
                "слой nginx открыт (" + str(слой_ng.get("evidence") or "")
                + "); запрет приходит от приложения")
        if слой_пр.get("denying") and not текущее(s.domain).get("present"):
            части.append(
                "приложение закрыто штатно: файла состояния нет, а без него "
                "режим вычисляется закрытым (fail-closed). Это и снимает "
                "indexing-set --mode open")
        итог["reason"] = ". ".join(части)
    return итог


def откатить(site: str, *, author: str) -> dict:
    """Вернуть прежнее состояние по журналу. Адресно и только этому сайту."""
    s = editorial._сайт(site)
    файл = ЖУРНАЛ / "operations.jsonl"
    если_нет = f"журнала операций нет: {файл}"
    try:
        строки = [json.loads(с) for с in файл.read_text(encoding="utf-8").split("\n")
                  if с.strip()]
    except OSError:
        raise Отказано(если_нет) from None
    свои = [з for з in строки if з.get("site") == s.domain and з.get("op") == "set"]
    if not свои:
        raise Отказано(f"в журнале нет смен режима для {s.domain}: откатывать нечего")
    последняя = свои[-1]
    куда = str(последняя.get("from") or "")
    if куда == "(нет файла)":
        п = _файл(s.domain)
        прежнее = текущее(s.domain)
        п.unlink(missing_ok=True)
        _дописать_журнал({"at": _сейчас(), "op": "rollback", "site": s.domain,
                          "from": прежнее.get("desired_state"), "to": "(нет файла)",
                          "author": author, "undo_of": последняя.get("revision")})
        итог = подтвердить(site, ожидаемый=ЗАКРЫТ)
        итог.update({"rolled_back_to": "(нет файла)", "changed": True})
        return итог
    итог = установить(site, mode=куда, author=author)
    итог["rolled_back_to"] = куда
    итог["undo_of"] = последняя.get("revision")
    return итог


def состояние(site: str) -> dict:
    """Всё, что известно о режиме этого сайта, без единой записи."""
    s = editorial._сайт(site)
    разрешено, откуда = разрешение_выпуска(s.account, s.adapter, s.domain)
    разрешил, объявлен, пояснение = разрешение_владельца(s.site_id)
    сиг = сигналы(s.domain, порт=порт_приложения(s.site_id))
    фактически, запрещают = оценить(сиг)
    читатель = читатель_режима(s.account, s.adapter)
    return {
        "site": s.domain, "site_id": s.site_id,
        "public_mode": фактически,
        "denying_signals": запрещают,
        "layers": {
            "owner_authorization": {"open_authorized": разрешил,
                                    "declared_state": объявлен or None,
                                    "note": пояснение or None,
                                    "source": str(registry.РЕЕСТР_ЯЧЕЕК)},
            "release_permission": {"permits_open": разрешено, "source": откуда},
            "state_file": текущее(s.domain),
            "nginx_header": слой_nginx(s.site_id, s.domain, сиг),
            "app": слой_приложения(сиг),
        },
        "runtime_reader": str(читатель) if читатель else "",
        "signals": сиг,
        "log": str(ЖУРНАЛ / "operations.jsonl"),
    }
