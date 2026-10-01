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
РЕЕСТР_ЯЧЕЕК = КОРЕНЬ / "config" / "site-cells.json"
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
        "display": "читатель приложения Next.js (проверено на yummyani.site)",
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

#: Операции, которые требуют соответствующей возможности адаптера.
ТРЕБУЕТ_ВОЗМОЖНОСТИ = {
    "facts": "facts",
    "prepare": "facts",
    "publish": "deliver",
    "unpublish": "deliver",
    "restore": "deliver",
    "rollback": "deliver",
    "confirm": "display",
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


def _домены_сети() -> list[str]:
    """Домены по сетевому списку: реестр ячеек сети НЕ равен."""
    try:
        строки = СЕТЕВОЙ_СПИСОК.read_text(encoding="utf-8").split("\n")
    except OSError:
        return []
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
    return итог


def _ячейки() -> list[dict]:
    данные = json.loads(РЕЕСТР_ЯЧЕЕК.read_text(encoding="utf-8"))
    сп = данные.get("cells") or данные.get("sites") or []
    return сп if isinstance(сп, list) else list(сп.values())


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

        # опубликованная версия — ТОЛЬКО с диска и с домена, не из поля реестра
        аккаунт = ((я.get("runtime") or {}).get("account")
                   or домен.replace(".", "-"))
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
        # хранилище редакционных материалов
        хран = корень_хранилища(s.adapter) / домен / "title-overlays.json"
        s.editorial_store = str(хран)
        if хран.is_file():
            try:
                s.editorial_items = len(
                    json.loads(хран.read_text(encoding="utf-8")).get("items") or [])
            except ValueError:
                s.editorial_items = None
                s.notes.append("файл хранилища не читается как JSON")

        s.delivery, s.handover_state, s.handover_reason, s.operations = _передача(s)
        итог.append(s)
    return итог


ОПЕРАЦИИ_ЧТЕНИЯ = ["sites", "facts", "verify", "status", "diagnose", "indexing-show"]
ОПЕРАЦИИ_ЗАПИСИ = ["prepare", "publish", "unpublish", "restore", "rollback"]


def _передача(s: Сайт) -> tuple[str, str, str, list[str]]:
    """Механизм доставки и состояние передачи — по фактам, без списка домен."""
    if not s.adapter:
        return ("неизвестен",
                "unknown",
                f"точка входа {s.template_entrypoint!r} не сопоставлена ни одному "
                "адаптеру; добавьте её в АДАПТЕРЫ_ПО_РАНТАЙМУ после проверки",
                list(ОПЕРАЦИИ_ЧТЕНИЯ))
    доставка = {
        "animedia": "наложение title-overlays.json, читает рантайм витрины",
        "lords": "наложение title-overlays.json (читатель в рантайме ещё не выпущен)",
        "animego": "наложение title-overlays.json (читатель в рантайме ещё не выпущен)",
        "yummy": "наложение title-overlays.json, читает приложение Next.js",
        "zona-serve": "механизм не установлен",
    }.get(s.adapter, "неизвестен")

    if not s.public_http:
        # Сеть не опрашивали: утверждать «не выпущен» нельзя — это разные
        # утверждения, и путать их значит объявлять живой сайт мёртвым.
        return (доставка, "unknown",
                "домен не опрашивался (опрашивать_сеть=False): состояние "
                "передачи без ответа домена не определяется",
                list(ОПЕРАЦИИ_ЧТЕНИЯ))
    if s.public_http != "200" or not s.published_release:
        return (доставка, "not_released",
                f"публичный ответ {s.public_http}, "
                f"выпуск {s.published_release or 'не найден'}",
                list(ОПЕРАЦИИ_ЧТЕНИЯ))
    умеет = ВОЗМОЖНОСТИ_АДАПТЕРА.get(s.adapter, {})
    операции = ["sites", "status", "diagnose", "indexing-show"]
    for оп, нужна in ТРЕБУЕТ_ВОЗМОЖНОСТИ.items():
        if нужна in умеет:
            операции.append(оп)
    нет = [н for н in ("facts", "deliver", "display") if н not in умеет]
    if "deliver" not in умеет or "display" not in умеет:
        return (доставка, "pending_adapter",
                f"семейство {s.adapter!r}: не хватает возможностей {нет} — "
                "записанный материал на странице не появится",
                sorted(set(операции)))
    if "facts" not in умеет:
        return (доставка, "managed_no_facts",
                f"семейство {s.adapter!r}: доставка и отображение работают, но "
                "источника фактов нет — текст должен приходить с уже "
                "проверенными фактами извне",
                sorted(set(операции)))
    return (доставка, "managed", "", sorted(set(операции)))


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
