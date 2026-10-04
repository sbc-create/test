"""Обнаружение сайтов и состояние передачи в управление редактору.

Состояние передачи ВЫЧИСЛЯЕТСЯ, а не хранится списком
-----------------------------------------------------

`handover_state` — новое поле этой задачи (2026-10-01), его раньше не было, и
в документации оно описано как новое. Значение не записывается руками: оно
выводится из фактов, которые уже есть в реестре и на диске. Иначе появился бы
второй список домен, который расходится с первым, — та самая ошибка, из-за
которой инвентаризация однажды пропустила два работающих сайта.

Состояния:

* `managed`      — выпуск активирован, адаптер семейства поддержан, хранилище
                   редакционных материалов на месте: редактор может работать;
* `pending_adapter` — сайт выпущен и жив, но семейство шаблона ещё не умеет
                   принимать материалы (нет читателя наложения в рантайме);
* `not_released` — выпуска нет (нет ссылки `current` либо домен не отвечает);
* `unknown`      — чего-то из фактов не хватает, и об этом сказано прямо.

Закрытая индексация на состояние НЕ влияет: готовить и публиковать контент на
закрытом сайте можно, и это записано отдельным полем `indexing`.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
#: Реестр ячеек. Переменная `SITE_CELLS_REGISTRY` — та же, что у
#: `factory.cell.registry.registry_path()`: изолированному стенду нужен свой
#: реестр, и подменять боевой файл ради проверки нельзя. Два слоя обязаны
#: искать реестр ОДИНАКОВО — расхождение путей уже стоило операции, когда один
#: и тот же путь внутри пакета указывал на два разных файла.
РЕЕСТР_ЯЧЕЕК = pathlib.Path(
    os.environ.get("SITE_CELLS_REGISTRY") or КОРЕНЬ / "config" / "site-cells.json")
СЕТЕВОЙ_СПИСОК = КОРЕНЬ / "inventory" / "network-allowlist.yaml"

#: Корень хранилищ редакционных материалов — СВОЙ У КАЖДОГО СЕМЕЙСТВА.
#:
#: Единый корень был ошибкой: путь `/srv/sites/animedia/runtime/overlays`
#: зашит в выпущенный рантайм Animedia, и подкладывать под него витрину Lords
#: значило бы хранить материалы Lords в каталоге с чужим именем, а читателю
#: Lords всё равно смотреть в другое место. Корень отдаёт адаптер.
КОРНИ_ХРАНИЛИЩ = {
    # Этот путь читает ВЫПУЩЕННЫЙ рантайм Animedia (seo_overlay.КОРЕНЬ).
    "animedia": "/srv/sites/animedia/runtime/overlays",
    # Эти два пути заведены под будущих читателей и пока только готовятся.
    "lords": "/srv/sites/lords/runtime/overlays",
    "animego": "/srv/sites/animego/runtime/overlays",
    # Yummy уже читает свой каталог приложением Next.js.
    "yummy": "/srv/sites/yummyani-staging/runtime/overlays",
}

#: Запасной корень для семейства без собственного: материалы не теряются, но
#: читателя у них нет, и состояние передачи это показывает.
КОРЕНЬ_ПО_УМОЛЧАНИЮ = "/srv/sites/editorial/overlays"


def корень_хранилища(adapter: str) -> pathlib.Path:
    из_среды = os.environ.get("QWEN_EDITORIAL_ROOT")
    if из_среды:
        return pathlib.Path(из_среды)
    return pathlib.Path(КОРНИ_ХРАНИЛИЩ.get(adapter, КОРЕНЬ_ПО_УМОЛЧАНИЮ))


#: Оставлено для обратной совместимости вызовов, которые корень не выбирают.
ХРАНИЛИЩЕ = pathlib.Path(
    os.environ.get("QWEN_EDITORIAL_ROOT", КОРНИ_ХРАНИЛИЩ["animedia"]))

#: Какое семейство какой механизм доставки использует. Выводится из точки входа
#: рантайма, а не из имени домена: имя домена о шаблоне ничего не говорит.
АДАПТЕРЫ_ПО_РАНТАЙМУ = {
    "animedia-frontend.py": "animedia",
    "lords-frontend.py": "lords",
    "lords01-frontend.py": "lords",
    "lords02-frontend.py": "lords",
    "animego-frontend.py": "animego",
    "yummy-frontend.py": "yummy",
    "serve.py": "zona-serve",
}

#: Что УМЕЕТ каждый адаптер — по операциям, а не «поддержан/нет».
#:
#: Грубое деление оказалось неверным. У Yummy доставка и отображение работают
#: (текст наложения виден на yummyani.site — проверено), но ФАКТЫ оттуда взять
#: нечем: у витрин Yummy нет снимка подробностей, их каталог живёт в Postgres.
#: Объявить семейство «поддержанным» целиком значило бы обещать операцию,
#: которой нет. Поэтому возможности перечислены поимённо.
ВОЗМОЖНОСТИ_АДАПТЕРА = {
    "animedia": {
        "facts": "снимок /srv/lords/.frontend/<site_id>-details.json",
        "deliver": "наложение title-overlays.json",
        "display": "читатель в выпущенном рантайме (проверено на живых страницах)",
    },
    "yummy": {
        "deliver": "наложение title-overlays.json",
        # `display` НЕ объявляется семейством: приложение читает наложение
        # только там, где контейнеру задан TITLE_OVERLAYS_PATH и смонтирован
        # каталог этого домена. Измерено: так настроены yummyani.site и
        # yummyani.org, а у yummyani.biz, yummyani7.site и yummyani7.info ни
        # переменной, ни монтирования нет. Объявить отображение семейством
        # значило бы пообещать его трём сайтам, где файл никто не читает.
        # факты отсутствуют намеренно: источника нет
    },
    "lords": {
        "facts": "снимок /srv/lords/.frontend/<site_id>-details.json",
        # доставка и отображение отсутствуют: читателя в рантайме нет
    },
    "animego": {
        "facts": "снимок /srv/lords/.frontend/<site_id>-details.json",
    },
    "zona-serve": {},
}

#: Форма адреса страницы тайтла — У КАЖДОГО СЕМЕЙСТВА СВОЯ, и она проверена
#: запросом, а не выведена из общего вида.
#:
#: Угадывать её нельзя, и это не предосторожность: инструмент уже строил всем
#: семействам `/title/<slug>/`, а Yummy отвечает на этот адрес 308-м редиректом
#: на `/anime/<slug>`. Проверка подтверждения получала «страница ответила 308»
#: и объявляла текст отсутствующим — при том, что текст на странице был
#: (проверено на /anime/009-1, фрагмент наложения найден в видимом теле).
ФОРМА_АДРЕСА = {
    # проверено: https://animedia.space/title/<slug>/ → 200
    "animedia": "/title/{slug}/",
    # проверено: https://zonafilm.space/title/<slug>/ → 200, ссылки главной
    # имеют ту же форму; то же у zonafilm.cc и an1mego.site
    "lords": "/title/{slug}/",
    "animego": "/title/{slug}/",
    "zona-serve": "/title/{slug}/",
    # проверено: https://yummyani.site/anime/<slug> → 200;
    # /title/<slug>/ → 308
    "yummy": "/anime/{slug}",
}


def адрес_тайтла(s: "Сайт", slug: str) -> str:
    """Публичный адрес страницы тайтла. Форма берётся из проверенной таблицы."""
    форма = ФОРМА_АДРЕСА.get(s.adapter)
    if not форма:
        raise KeyError(
            f"{s.domain}: форма адреса страницы тайтла для семейства "
            f"{s.adapter or 'не определено'} не проверена — угадывать её нельзя")
    return f"https://{s.domain}" + форма.format(slug=slug)


#: Семейства, рантайм которых УМЕЕТ нести читателя редакторских правок
#: (`src/editorial_overlay.py`). Умеет — не значит несёт: модуль есть в
#: выпущенном рантайме одной витрины из восьми, и проверяется он по ВЫПУСКУ, а
#: не по рабочей копии. Рабочая копия может содержать читателя, которого на
#: сайте нет, — тогда записанное на странице не появится.
СЕМЕЙСТВА_ПРАВОК = ("lords", "animego")

#: Имя файла правок в хранилище витрины. То же имя объявлено `user_writable` в
#: `config/site.json` подключённых витрин и то же читает `editorial_overlay`.
ИМЯ_ПРАВОК = "editorial-overrides.json"


def читатель_правок(аккаунт: str) -> pathlib.Path | None:
    """Путь к читателю правок в ВЫПУЩЕННОМ рантайме, иначе None."""
    if not аккаунт:
        return None
    п = pathlib.Path(f"/srv/{аккаунт}/current/src/editorial_overlay.py")
    if п.is_file():
        return п
    п = pathlib.Path(f"/srv/{аккаунт}/app/src/editorial_overlay.py")
    return п if п.is_file() else None


#: Сколько ждать `docker inspect`. Контейнеров пять, опрос дешёвый, но он
#: внешний, и без предела один зависший вызов остановил бы перечень сайтов.
ОПРОС_КОНТЕЙНЕРА_С = 20


#: Разобранные контейнеры: домен -> путь наложения внутри контейнера.
#:
#: Считается ОДИН раз на процесс. Без кэша перечень сайтов опрашивал
#: `docker inspect` для каждой витрины Yummy по всем запущенным контейнерам —
#: около сотни внешних вызовов на один `sites`, и операции стали заметно
#: медленнее. Состав контейнеров за время одной операции не меняется.
_контейнеры: dict[str, str] | None = None


def _разобрать_контейнеры() -> dict[str, str]:
    """Домен -> путь наложения, по ФАКТИЧЕСКИ запущенным контейнерам.

    Проверяется запущенный контейнер, а не compose-файл: в прочитанном
    `compose.staging.yaml` у web-org наложений нет вовсе, а в работающем
    контейнере и переменная, и монтирование есть — файл разошёлся с тем, что
    работает. Судить по файлу значило бы объявить настроенный сайт
    ненастроенным.

    Чего это НЕ доказывает: что текст появится на странице. У yummyani.org
    переменная и монтирование на месте, записей 25, отпечатки сходятся — а
    текста на странице нет (проверено 2026-10-01). Поэтому настройка даёт
    только возможность `display`, а публикация всё равно заканчивается
    проверкой страницы и без текста остаётся в состоянии `written`.
    """
    import shutil
    итог: dict[str, str] = {}
    if not shutil.which("docker"):
        return итог
    try:
        список = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                                capture_output=True, text=True,
                                timeout=ОПРОС_КОНТЕЙНЕРА_С)
    except (OSError, subprocess.SubprocessError):
        return итог
    if список.returncode != 0:
        return итог
    имена = список.stdout.split()
    if not имена:
        return итог
    try:
        св = subprocess.run(["docker", "inspect", *имена], capture_output=True,
                            text=True, timeout=ОПРОС_КОНТЕЙНЕРА_С * 3)
    except (OSError, subprocess.SubprocessError):
        return итог
    if св.returncode != 0:
        return итог
    try:
        все = json.loads(св.stdout)
    except ValueError:
        return итог
    for данные in все:
        окр = dict(кв.split("=", 1)
                   for кв in (данные.get("Config") or {}).get("Env") or []
                   if "=" in кв)
        адрес = окр.get("SITE_URL") or ""
        путь = (окр.get("TITLE_OVERLAYS_PATH") or "").strip()
        if not адрес or not путь:
            continue
        домен = адрес.split("//", 1)[-1].strip("/").lower()
        if not домен:
            continue
        # Монтирование должно вести в каталог ИМЕННО этого домена: иначе
        # контейнер читал бы наложение соседа.
        свой = any(домен in str(m.get("Source") or "")
                   for m in данные.get("Mounts") or [])
        if свой:
            итог[домен] = путь
    return итог


def наложение_в_контейнере(домен: str) -> str:
    """Читает ли контейнер этого домена каталог наложений ЭТОГО домена."""
    global _контейнеры
    if _контейнеры is None:
        _контейнеры = _разобрать_контейнеры()
    return _контейнеры.get(домен.lower(), "")


def возможности(s: "Сайт") -> dict[str, str]:
    """Что умеет ЭТОТ сайт. Возможности семейства — только основа.

    Возможности нельзя объявлять семейством целиком: читатель правок выпущен
    на zona-01 и не выпущен на остальных шести витринах того же семейства с
    той же точкой входа. Объявить семейство умеющим доставку значило бы
    пообещать публикацию шести сайтам, где текст не появится.
    """
    умеет = dict(ВОЗМОЖНОСТИ_АДАПТЕРА.get(s.adapter, {}))
    if s.adapter == "yummy":
        путь = наложение_в_контейнере(s.domain)
        if путь:
            умеет["display"] = (f"контейнер читает {путь} и монтирует каталог "
                                "этого домена")
    if s.adapter in СЕМЕЙСТВА_ПРАВОК:
        читатель = читатель_правок(s.account)
        if читатель is not None:
            умеет["deliver"] = ("правки через очередь выпуска, операция "
                                "editorial (factory.cell.editorial_store)")
            умеет["display"] = f"читатель в выпущенном рантайме: {читатель}"
    return умеет


def механизм(s: "Сайт") -> str:
    """Каким путём материал попадает на сайт. Пусто — пути нет."""
    if s.adapter in ("animedia", "yummy"):
        return "overlay"
    if s.adapter in СЕМЕЙСТВА_ПРАВОК and читатель_правок(s.account) is not None:
        return "editorial-queue"
    return ""


def путь_доставки(s: "Сайт") -> str:
    """Файл, который читает ВЫПУЩЕННЫЙ рантайм этого сайта."""
    if механизм(s) == "editorial-queue":
        return f"/srv/{s.account}/data/{ИМЯ_ПРАВОК}"
    return str(корень_хранилища(s.adapter) / s.domain / "title-overlays.json")


#: Какие возможности нужны операции. ВСЕ перечисленные, а не любая из них.
#:
#: Публикация требует и доставки, и отображения. Одной доставки мало: запись в
#: файл, который никто не читает, — не публикация, и предлагать её значит
#: обещать результат, которого не будет. Измерено на yummyani.biz,
#: yummyani7.site и yummyani7.info: каталог наложений существует, а контейнер
#: его не монтирует и переменной TITLE_OVERLAYS_PATH не имеет.
ТРЕБУЕТ_ВОЗМОЖНОСТИ = {
    "facts": ("facts",),
    "prepare": ("facts",),
    "publish": ("deliver", "display"),
    "unpublish": ("deliver", "display"),
    "restore": ("deliver", "display"),
    # Откат тоже требует отображения: откатывать хранилище, которого никто не
    # читает, незачем — публичного состояния, которое надо вернуть, там нет.
    "rollback": ("deliver", "display"),
    "confirm": ("display",),
}


@dataclass
class Сайт:
    site_id: str
    domain: str
    repo_path: str = ""
    repo_remote: str = ""
    work_branch: str = ""
    work_head: str = ""
    published_release: str = ""
    published_build_id: str = ""
    template_entrypoint: str = ""
    template_family: str = ""
    adapter: str = ""
    account: str = ""
    delivery_backend: str = ""
    delivery: str = ""
    editorial_store: str = ""
    editorial_items: int | None = None
    indexing: str = ""
    public_http: str = ""
    handover_state: str = "unknown"
    handover_reason: str = ""
    operations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git(каталог: pathlib.Path, *арг: str) -> str:
    if not (каталог / ".git").exists():
        return ""
    r = subprocess.run(["git", *арг], cwd=каталог, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


class РеестрНедоступен(RuntimeError):
    """Реестр не прочитан. Пустой ответ вместо этого — ложь об окружении.

    Прежде нечитаемый сетевой список молча давал пустой перечень доменов, и
    «сайта нет в реестрах» становилось неотличимо от «реестр не открылся».
    Qwen по такому ответу делает неверный вывод: домена нет — значит и
    механизма нет. Поэтому отказ доступа называется отказом.
    """


#: Состояние источников после последнего `собрать()`. Заполняется ВСЕГДА:
#: по нему видно, какой файл читался, сколько записей дал и чем ответил.
ИСТОЧНИКИ: dict[str, dict] = {}


def состояние_источников() -> dict[str, dict]:
    """Копия состояния источников реестра: путь, читаемость, число записей."""
    return {к: dict(з) for к, з in ИСТОЧНИКИ.items()}


def _домены_сети() -> list[str]:
    """Домены по сетевому списку: реестр ячеек сети НЕ равен."""
    запись = ИСТОЧНИКИ.setdefault("network_allowlist", {})
    запись.update({"path": str(СЕТЕВОЙ_СПИСОК), "ok": False, "count": 0,
                   "error": None})
    try:
        строки = СЕТЕВОЙ_СПИСОК.read_text(encoding="utf-8").split("\n")
    except OSError as ош:
        # Не «доменов нет», а «список не прочитан»: разница видна в ответе.
        запись["error"] = f"{type(ош).__name__}: {ош}"
        raise РеестрНедоступен(
            f"сетевой список {СЕТЕВОЙ_СПИСОК} не читается: "
            f"{type(ош).__name__}. Перечень доменов неизвестен, и пустой "
            "ответ вместо него был бы неправдой") from None
    итог: list[str] = []
    это_сайт = False
    for строка in строки:
        г = строка.strip()
        if г.startswith("- ref:"):
            это_сайт = г.split(":", 1)[1].strip().startswith("site-")
        elif это_сайт and г.startswith("host:"):
            хост = г.split(":", 1)[1].strip()
            if хост and хост not in итог:
                итог.append(хост)
            это_сайт = False
    запись["ok"] = True
    запись["count"] = len(итог)
    return итог


def _ячейки() -> list[dict]:
    """Ячейки из реестра. Нечитаемый или пустой реестр — ОТКАЗ, не пустота.

    Пустой успешный ответ здесь опаснее исключения: по нему любой домен
    выглядит «отсутствующим в реестре», то есть беда окружения читается как
    факт о сайте.
    """
    запись = ИСТОЧНИКИ.setdefault("site_cells", {})
    запись.update({"path": str(РЕЕСТР_ЯЧЕЕК), "ok": False, "count": 0,
                   "error": None})
    try:
        текст = РЕЕСТР_ЯЧЕЕК.read_text(encoding="utf-8")
    except OSError as ош:
        запись["error"] = f"{type(ош).__name__}: {ош}"
        raise РеестрНедоступен(
            f"реестр ячеек {РЕЕСТР_ЯЧЕЕК} не читается: {type(ош).__name__}"
        ) from None
    try:
        данные = json.loads(текст)
    except ValueError as ош:
        запись["error"] = f"JSONDecodeError: {ош}"
        raise РеестрНедоступен(
            f"реестр ячеек {РЕЕСТР_ЯЧЕЕК} не разбирается как JSON: {ош}"
        ) from None
    сп = данные.get("cells") or данные.get("sites") or []
    сп = сп if isinstance(сп, list) else list(сп.values())
    if not сп:
        запись["error"] = "в реестре нет ни одной ячейки"
        raise РеестрНедоступен(
            f"реестр ячеек {РЕЕСТР_ЯЧЕЕК} не содержит ни одной ячейки: "
            "это состояние окружения, а не ответ о сайте")
    запись["ok"] = True
    запись["count"] = len(сп)
    return сп


def _страница(url: str, таймаут: int = 15) -> tuple[str, str]:
    """(код, тело). Код строкой: сетевая беда — тоже ответ, а не исключение."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "qwen-site-tool"})
        о = urllib.request.urlopen(req, timeout=таймаут)
        return str(о.status), о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return str(e.code), ""
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, ""


def _режим_индексации(тело: str) -> str:
    м = re.search(r'name="robots"[^>]*content="([^"]*)"', тело)
    return м.group(1) if м else "не объявлен"


def собрать(*, опрашивать_сеть: bool = True) -> list[Сайт]:
    """Все сайты из действующих реестров, с вычисленным состоянием передачи."""
    из_реестра = {я.get("domain"): я for я in _ячейки() if я.get("domain")}
    известные = list(из_реестра)
    для_сети = [d for d in _домены_сети() if d not in известные]
    итог: list[Сайт] = []

    for домен in известные + для_сети:
        я = из_реестра.get(домен) or {}
        s = Сайт(site_id=я.get("site_id") or f"(вне реестра) {домен}", domain=домен)
        путь = (я.get("repo") or {}).get("path") or ""
        if путь:
            репо = КОРЕНЬ / путь
            s.repo_path = str(репо)
            s.repo_remote = _git(репо, "remote", "get-url", "origin")
            s.work_branch = _git(репо, "rev-parse", "--abbrev-ref", "HEAD")
            s.work_head = _git(репо, "rev-parse", "HEAD")
            кф = репо / "config" / "site.json"
            if кф.is_file():
                try:
                    кд = json.loads(кф.read_text(encoding="utf-8"))
                    s.template_entrypoint = кд.get("entrypoint") or ""
                except ValueError:
                    s.notes.append("config/site.json не читается как JSON")
        else:
            s.notes.append("репозитория в реестре нет: сайт вне очереди выпуска")

        # точка входа: из конфигурации, иначе по наличию рантайма
        if not s.template_entrypoint and s.repo_path:
            найдено = sorted(p.name for p in (pathlib.Path(s.repo_path) / "src").glob("*frontend*.py")) \
                if (pathlib.Path(s.repo_path) / "src").is_dir() else []
            s.template_entrypoint = найдено[0] if найдено else ""
        s.template_family = (я.get("template") or {}).get("template_id") or ""
        s.adapter = АДАПТЕРЫ_ПО_РАНТАЙМУ.get(s.template_entrypoint, "")
        if not s.adapter:
            # Рабочей копии у витрины может не быть вовсе: часть сайтов
            # заведена вне этой очереди и выпускается не отсюда. Тогда точку
            # входа взять негде, и семейство остаётся пустым — а пустое
            # семейство означает «контракта режима нет», то есть беду учёта
            # выдаёт за факт о сайте.
            #
            # Второй источник — ОБЪЯВЛЕННОЕ семейство реестра
            # (`template.family`). Оно не догадка: у animego-02/03 оно
            # записано по измерению на хосте — `/healthz` каждой витрины
            # называет свой `runtime_path` (`src/animego-frontend.py`).
            # Принимается только значение, которое есть среди адаптеров:
            # произвольная строка семейством не становится.
            объявлено = str((я.get("template") or {}).get("family") or "").strip()
            if объявлено in set(АДАПТЕРЫ_ПО_РАНТАЙМУ.values()):
                s.adapter = объявлено
                s.notes.append(
                    f"семейство {объявлено!r} взято из реестра "
                    "(template.family): рабочей копии нет, точку входа взять "
                    "негде")

        # опубликованная версия — ТОЛЬКО с диска и с домена, не из поля реестра
        аккаунт = ((я.get("runtime") or {}).get("account")
                   or домен.replace(".", "-"))
        s.account = аккаунт
        ссылка = pathlib.Path(f"/srv/{аккаунт}/current")
        if ссылка.exists():
            s.published_release = pathlib.Path(ссылка.resolve()).name
        elif pathlib.Path(f"/srv/{аккаунт}/app").is_dir():
            s.published_release = "без releases/: прямая установка"
        else:
            s.published_release = ""

        if опрашивать_сеть:
            код, тело = _страница(f"https://{домен}/")
            s.public_http = код
            if код == "200":
                s.indexing = _режим_индексации(тело)
                кодz, телоz = _страница(f"https://{домен}/healthz")
                if кодz == "200" and телоz:
                    try:
                        s.published_build_id = json.loads(телоz).get("build_id") or ""
                    except ValueError:
                        s.published_build_id = ""
        # Хранилище редакционных материалов — то, что читает ВЫПУЩЕННЫЙ
        # рантайм этого сайта. Путь зависит от механизма доставки: наложение
        # лежит у производителя, правки — в хранилище самой витрины.
        s.delivery_backend = механизм(s)
        s.editorial_store = путь_доставки(s)
        хран = pathlib.Path(s.editorial_store)
        if хран.is_file():
            данные = {}
            try:
                данные = json.loads(хран.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                s.notes.append("файл хранилища не читается как JSON")
            if isinstance(данные, dict):
                пункты = (данные.get("items") if "items" in данные
                          else данные.get("overrides"))
                s.editorial_items = len(пункты) if пункты is not None else 0

        s.delivery, s.handover_state, s.handover_reason, s.operations = _передача(s)
        итог.append(s)
    return итог


#: Перечни называют ИМЕНА КОМАНД CLI, а не роли. Прежние значения `verify` и
#: `indexing-show` командами не были: инструмент объявлял сайту операцию,
#: которую нельзя вызвать, и редактор искал бы её в помощи напрасно.
#: Согласование закрепляет тест.
ОПЕРАЦИИ_ЧТЕНИЯ = ["sites", "facts", "status", "diagnose", "indexing"]
ОПЕРАЦИИ_ЗАПИСИ = ["prepare", "publish", "unpublish", "restore", "rollback"]


def доступные_операции(s: Сайт, *, мех: str = "") -> list[str]:
    """Команды, которые на ЭТОМ сайте действительно сработают.

    Читающие команды доступны всегда — кроме `facts`: источник фактов есть не у
    каждого семейства, и объявлять его сайту без адаптера значило бы обещать
    отказ. Прочие операции фильтруются по возможностям сайта целиком.
    """
    умеет = возможности(s)
    операции = ["sites", "status", "diagnose", "indexing"]
    for оп, нужны in ТРЕБУЕТ_ВОЗМОЖНОСТИ.items():
        if all(н in умеет for н in нужны):
            операции.append(оп)
    # Откат хранилища есть только у наложения: у файла правок нет ни поколений,
    # ни last-good — его роль играют адресное снятие и восстановление. Оставить
    # `rollback` в перечне значило бы предложить операцию, которая откажет.
    if (мех or механизм(s)) == "editorial-queue" and "rollback" in операции:
        операции.remove("rollback")
    return sorted(set(операции))


def _передача(s: Сайт) -> tuple[str, str, str, list[str]]:
    """Механизм доставки и состояние передачи — по фактам, без списка домен."""
    if not s.adapter:
        return ("неизвестен",
                "unknown",
                f"точка входа {s.template_entrypoint!r} не сопоставлена ни одному "
                "адаптеру; добавьте её в АДАПТЕРЫ_ПО_РАНТАЙМУ после проверки",
                доступные_операции(s))
    мех = механизм(s)
    доставка = {
        "overlay": ("наложение title-overlays.json, читает рантайм витрины"
                    if s.adapter == "animedia"
                    else "наложение title-overlays.json, читает приложение Next.js"),
        "editorial-queue": ("правки editorial-overrides.json: подготовка в "
                            "управляющем слое, установка операцией editorial, "
                            "чтение рантаймом по mtime"),
    }.get(мех, "")
    if not доставка:
        доставка = ("механизм не установлен: читателя правок в выпущенном "
                    f"рантайме нет ({s.adapter or 'адаптер не определён'})")

    if not s.public_http:
        # Сеть не опрашивали: утверждать «не выпущен» нельзя — это разные
        # утверждения, и путать их значит объявлять живой сайт мёртвым.
        return (доставка, "unknown",
                "домен не опрашивался (опрашивать_сеть=False): состояние "
                "передачи без ответа домена не определяется",
                доступные_операции(s, мех=мех))
    if s.public_http != "200" or not s.published_release:
        return (доставка, "not_released",
                f"публичный ответ {s.public_http}, "
                f"выпуск {s.published_release or 'не найден'}",
                доступные_операции(s, мех=мех))
    умеет = возможности(s)
    операции = доступные_операции(s, мех=мех)
    нет = [н for н in ("facts", "deliver", "display") if н not in умеет]
    if "deliver" not in умеет or "display" not in умеет:
        подсказка = ""
        if s.adapter in СЕМЕЙСТВА_ПРАВОК:
            подсказка = (": в выпущенном рантайме нет src/editorial_overlay.py — "
                         "читатель есть в репозитории zonafilm-space и переносится "
                         "выпуском, а не правкой хранилища")
        return (доставка, "pending_adapter",
                f"сайт {s.domain}: не хватает возможностей {нет} — "
                f"записанный материал на странице не появится{подсказка}",
                операции)
    if "facts" not in умеет:
        return (доставка, "managed_no_facts",
                f"сайт {s.domain} ({s.adapter}): доставка и отображение работают, но "
                "источника фактов нет — текст должен приходить с уже "
                "проверенными фактами извне",
                операции)
    return (доставка, "managed", "", операции)


def обеспечить_передачу(site_id_или_домен: str) -> dict:
    """Идемпотентно подготовить хранилище материалов домена и вернуть состояние.

    Вызывается штатным выпуском (`factory.cell.trigger`) после успешной подачи
    заявки и может вызываться вручную. Повторный вызов ничего не создаёт
    заново: каталог либо есть, либо создаётся один раз.

    Состояние передачи ЗДЕСЬ НЕ ЗАПИСЫВАЕТСЯ. Оно вычисляется из фактов при
    каждом запросе — поэтому второго списка домен не возникает, и сайт
    становится доступен редактору сам, без нового промпта и без правок кода.
    Эта функция лишь готовит место под материалы.
    """
    сайты = {s.domain: s for s in собрать(опрашивать_сеть=True)}
    по_ид = {s.site_id: s for s in сайты.values()}
    s = сайты.get(site_id_или_домен) or по_ид.get(site_id_или_домен)
    if s is None:
        return {"ok": False,
                "reason": f"{site_id_или_домен!r} нет в действующих реестрах"}
    к = корень_хранилища(s.adapter) / s.domain
    было = к.is_dir()
    к.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "site": s.domain, "site_id": s.site_id,
            "editorial_store_dir": str(к), "created_now": not было,
            "handover_state": s.handover_state,
            "handover_reason": s.handover_reason,
            "operations": s.operations}
