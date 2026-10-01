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


class Отказано(RuntimeError):
    """Операция остановлена с названной причиной. Слепой повтор запрещён."""


def _сейчас() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def читатель_режима(аккаунт: str) -> pathlib.Path | None:
    """Путь к читателю режима в ВЫПУЩЕННОМ рантайме, иначе None."""
    if not аккаунт:
        return None
    for корень in (f"/srv/{аккаунт}/current/src", f"/srv/{аккаунт}/app/src"):
        п = pathlib.Path(корень) / ИМЯ_ЧИТАТЕЛЯ
        if п.is_file():
            return п
    return None


def разрешение_выпуска(аккаунт: str) -> tuple[bool, str]:
    """Что о режиме говорит ВЫПУЩЕННЫЙ config/site.json.

    Читается выпуск, а не рабочая копия: решение принимает тот код, который
    работает. Строгость та же, что у рантайма — разрешением считается только
    булево `true`.
    """
    for корень in (f"/srv/{аккаунт}/current", f"/srv/{аккаунт}/app"):
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
    def всё(сообщение) -> list[str]:
        if сообщение is None:
            return []
        значения = сообщение.get_all("X-Robots-Tag") or []
        return [str(з).strip() for з in значения]

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "qwen-indexing"})
        о = urllib.request.urlopen(req, timeout=таймаут)
        return str(о.status), всё(о.headers), о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return str(e.code), всё(e.headers), ""
    except Exception as e:  # noqa: BLE001 — сетевая беда тоже ответ
        return type(e).__name__, [], ""


def сигналы(домен: str) -> dict:
    """Четыре сигнала на живом домене, каждый отдельной величиной.

    X-Robots-Tag читается ПЕРЕЧНЕМ значений, а не одной строкой: на :443 его
    добавляют и nginx, и приложение, и слитая строка скрыла бы, что одно из
    двух ещё запрещает обход.
    """
    итог: dict = {"domain": домен, "at": _сейчас()}
    for схема, метка in (("https", ""), ("http", "_http80")):
        код, значения, тело = _ответ(f"{схема}://{домен}/")
        итог[f"home_http{метка}"] = код
        итог[f"x_robots_values{метка}"] = значения
        итог[f"x_robots_count{метка}"] = len(значения)
        if метка == "":
            м = re.search(r'<meta name="robots" content="([^"]*)"', тело)
            итог["meta_robots_home"] = м.group(1) if м else "не объявлен"
    кр, _, роботс = _ответ(f"https://{домен}/robots.txt")
    итог["robots_txt_http"] = кр
    итог["robots_txt"] = роботс
    кс, _, _ = _ответ(f"https://{домен}/sitemap.xml")
    итог["sitemap_http"] = кс
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

    # 2. Читатель режима в ВЫПУЩЕННОМ рантайме.
    читатель = читатель_режима(s.account)
    итог["runtime_reader"] = str(читатель) if читатель else ""
    if читатель is None:
        итог["blockers"].append(
            f"в выпущенном рантайме нет src/{ИМЯ_ЧИТАТЕЛЯ}: витрина режим не "
            "читает, и запись файла состояния ничего бы не изменила")

    # 3. Разрешение выпуска.
    разрешено, откуда = разрешение_выпуска(s.account)
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
    сиг = сигналы(s.domain)
    итог["public_now"] = сиг
    фактически, запрещают = оценить(сиг)
    итог["public_mode_now"] = фактически
    итог["denying_signals_now"] = запрещают

    # 6. Заголовок nginx. Его операция не меняет и не может: конфигурация
    #    принадлежит root. Но назвать его обязана — иначе «открыто» в файле
    #    состояния разошлось бы с закрытым сайтом.
    nginx_запрещает = [з for з in запрещают if з.startswith("X-Robots-Tag")]
    итог["nginx_layer"] = {
        "managed_by_this_operation": False,
        "denying": bool(nginx_запрещает),
        "evidence": nginx_запрещает,
        "owner_command": (
            f"sudo bash automation/host/apply-indexing-nginx-root.sh "
            f"--site {s.site_id} --mode {'open' if режим == ОТКРЫТ else 'closed'}"),
    }

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
        сиг = сигналы(s.domain)
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
        itog_nginx = [з for з in запрещают if з.startswith("X-Robots-Tag")]
        итог["reason"] = (
            "сайт отдаёт запрет: " + "; ".join(запрещают)
            + (". Заголовок nginx этой операцией не управляется — нужен "
               "однократный запуск владельца "
               f"automation/host/apply-indexing-nginx-root.sh --site {s.site_id} "
               "--mode open" if itog_nginx else ""))
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
    разрешено, откуда = разрешение_выпуска(s.account)
    разрешил, объявлен, пояснение = разрешение_владельца(s.site_id)
    сиг = сигналы(s.domain)
    фактически, запрещают = оценить(сиг)
    читатель = читатель_режима(s.account)
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
            "nginx_header": {"denying": any(
                з.startswith("X-Robots-Tag") for з in запрещают),
                "managed_by_this_operation": False},
        },
        "runtime_reader": str(читатель) if читатель else "",
        "signals": сиг,
        "log": str(ЖУРНАЛ / "operations.jsonl"),
    }
