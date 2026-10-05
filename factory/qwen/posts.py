#!/usr/bin/env python3
"""Редакционные НОВОСТИ витрины: черновик, публикация, снятие.

Что это за данные и откуда они берутся
--------------------------------------

Раздел `/posts` и новостной блок главной у витрин Yummy отдаёт приложение
Next.js, в которое проксирует витрина-ячейка (проверено 2026-10-05: ответы
ячейки на 9131 и контейнера на 3102 совпадают байт в байт, 57 477 байт).
Приложение читает записи ИЗ ФАЙЛА при обработке запроса:

    src/modules/editorial/editorial-post.ts
      FILE_PATH = join(process.cwd(), "content/editorial-posts.json")
      readFileSync(FILE_PATH, "utf8") + statSync  -> перечитывание по mtime

Файл проверяется схемой Zod, и `status: "draft"` НИКОГДА не показывается
публично — то есть черновик в этом механизме уже предусмотрен самим
приложением, и для проверки не нужно ни отдельного стенда, ни публикации.

Чего в приложении НЕТ: переменной окружения для пути к этому файлу. У
накладок описаний она есть (`TITLE_OVERLAYS_PATH`), и каталог накладок
смонтирован в контейнер (`/app/content/overlays`, только чтение). У новостей
файл запечён в образ. Поэтому доставка новой записи требует ОДНОГО
инфраструктурного действия — монтирования файла доставки на
`/app/content/editorial-posts.json`; код приложения при этом не меняется, и
образ не пересобирается.

Почему доставляемый файл обязан нести и прежние записи
------------------------------------------------------

Монтирование файла ЗАМЕНЯЕТ файл образа целиком. Доставить только новую
новость значило бы убрать двенадцать существующих — это потеря контента, а не
публикация. Поэтому файл доставки ЗАСЕВАЕТСЯ авторитетным содержимым (читается
из работающего контейнера) и дальше только дополняется. Пустой или
непрочитанный посев — отказ, а не повод начать с нуля.

Что здесь НЕ делается

* ничего не придумывается: ни заголовок, ни дата, ни автор, ни адрес. Пустое
  обязательное поле — отказ (`BLOCKED_INPUT`), а не умолчание;
* публичное состояние не меняется подготовкой черновика;
* снятие публикации НЕ удаляет запись: оно переводит её в `draft`, и
  приложение перестаёт её показывать. Запись остаётся, снятие обратимо, и
  история не теряется;
* повтор не создаёт дубля: совпадающий отпечаток — `nothing-to-do`.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
from typing import Any

from factory.qwen import editorial, registry

#: Версия файла. Приложение требует ровно её (`z.literal(1)`).
ВЕРСИЯ_ФАЙЛА = 1

#: Перечни приложения, перенесённые дословно из `editorial-post.ts`.
#: Расхождение закрепляет тест: он читает сам файл приложения.
ТИПЫ = ("news", "review", "videoblog", "announcement")
СОСТОЯНИЯ = ("draft", "published")
ИСТОЧНИКИ = ("editorial", "old.yummyani.me")

#: Поля записи и их обязательность — по той же схеме Zod.
ОБЯЗАТЕЛЬНЫЕ = ("slug", "type", "status", "title", "excerpt", "body",
                "publishedAt", "updatedAt", "authorName", "source")
ОБНУЛЯЕМЫЕ = ("channelName", "externalUrl", "thumbnailUrl")
СЛАГ = re.compile(r"^[a-z0-9-]+$", re.IGNORECASE)

#: Имя файла доставки. Лежит в том же каталоге, что накладки описаний: он
#: смонтирован в контейнер, и доставку туда уже умеет штатная операция.
ИМЯ_ДОСТАВКИ = "editorial-posts.json"

#: Куда приложение ждёт файл внутри контейнера. Нужно не для записи, а для
#: отчёта: по нему владелец видит, что именно монтировать.
ПУТЬ_В_КОНТЕЙНЕРЕ = "/app/content/editorial-posts.json"

#: Черновики новостей фабрики. Рядом с черновиками описаний, но отдельным
#: файлом: это разные виды материала с разными полями, и смешивать их в одном
#: хранилище значило бы проверять одно по правилам другого.
ЧЕРНОВИКИ = "post-drafts.json"
ИСТОРИЯ = "post-history.jsonl"


class ОперацияОтклонена(RuntimeError):
    """Операция остановлена с названной причиной. Публичного не менялось."""


def _сейчас() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def отпечаток(запись: dict) -> str:
    """Отпечаток СОДЕРЖАНИЯ записи: по нему повтор отличается от правки.

    Служебные поля времени в отпечаток не входят: иначе повторная подача того
    же текста выглядела бы новой работой только потому, что прошла минута.
    """
    значимое = {к: з for к, з in sorted(запись.items())
                if к not in ("updatedAt", "publishedAt")}
    сырое = json.dumps(значимое, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return hashlib.sha256(сырое.encode("utf-8")).hexdigest()


def проверить_запись(запись: dict) -> list[str]:
    """Беды записи по схеме ПРИЛОЖЕНИЯ. Пустой список — запись годна.

    Проверка повторяет Zod-схему `editorial-post.ts`, а не приблизительную
    идею о ней: отклонённый приложением файл означал бы, что раздел `/posts`
    перестал отдаваться целиком, — ошибка одной записи стоила бы всей
    страницы.
    """
    беды: list[str] = []
    for поле in ОБЯЗАТЕЛЬНЫЕ:
        if поле not in запись:
            беды.append(f"нет обязательного поля {поле}")
    слаг = str(запись.get("slug") or "")
    if not слаг:
        беды.append("slug пуст")
    elif not СЛАГ.match(слаг):
        беды.append(f"slug {слаг!r}: допустимы только буквы, цифры и дефис")
    if запись.get("type") not in ТИПЫ:
        беды.append(f"type {запись.get('type')!r} не из {list(ТИПЫ)}")
    if запись.get("status") not in СОСТОЯНИЯ:
        беды.append(f"status {запись.get('status')!r} не из {list(СОСТОЯНИЯ)}")
    if запись.get("source") not in ИСТОЧНИКИ:
        беды.append(f"source {запись.get('source')!r} не из {list(ИСТОЧНИКИ)}")
    for поле in ("title", "authorName"):
        if not str(запись.get(поле) or "").strip():
            беды.append(f"{поле} пуст: придумывать его нельзя")
    if not isinstance(запись.get("excerpt"), str):
        беды.append("excerpt обязан быть строкой")
    тело = запись.get("body")
    if not isinstance(тело, list) or not all(isinstance(а, str) for а in тело):
        беды.append("body обязан быть списком строк (абзацы)")
    elif запись.get("type") in ("news", "review") and not [
            а for а in тело if а.strip()]:
        беды.append(f"body пуст, а для типа {запись.get('type')} текст обязателен")
    for поле in ("publishedAt", "updatedAt"):
        значение = str(запись.get(поле) or "")
        if not значение:
            беды.append(f"{поле} пуст")
            continue
        try:
            _dt.datetime.fromisoformat(значение.replace("Z", "+00:00"))
        except ValueError:
            беды.append(f"{поле} {значение!r} не разбирается как ISO-8601")
    for поле in ОБНУЛЯЕМЫЕ:
        значение = запись.get(поле, None)
        if значение is None:
            continue
        if not isinstance(значение, str) or not значение.strip():
            беды.append(f"{поле}: либо строка, либо null")
        elif поле != "channelName" and not значение.startswith("https://"):
            беды.append(f"{поле} обязан начинаться с https://")
    лишние = set(запись) - set(ОБЯЗАТЕЛЬНЫЕ) - set(ОБНУЛЯЕМЫЕ)
    if лишние:
        беды.append(f"неизвестные поля {sorted(лишние)}: приложение их не ждёт")
    return беды


def проверить_файл(данные: Any) -> list[str]:
    """Беды файла целиком: версия, список, уникальность слагов."""
    беды: list[str] = []
    if not isinstance(данные, dict):
        return ["файл не объект"]
    if данные.get("version") != ВЕРСИЯ_ФАЙЛА:
        беды.append(f"version {данные.get('version')!r} вместо {ВЕРСИЯ_ФАЙЛА}")
    записи = данные.get("posts")
    if not isinstance(записи, list):
        return беды + ["posts не список"]
    видено: set[str] = set()
    for н, з in enumerate(записи):
        if not isinstance(з, dict):
            беды.append(f"запись {н} не объект")
            continue
        for беда in проверить_запись(з):
            беды.append(f"запись {з.get('slug') or н}: {беда}")
        слаг = str(з.get("slug") or "")
        if слаг in видено:
            беды.append(f"слаг {слаг} повторяется: публичный адрес обязан быть один")
        видено.add(слаг)
    return беды


def _сайт(site: str) -> registry.Сайт:
    return editorial._сайт(site, опрашивать_сеть=False)


def путь_доставки(s: registry.Сайт) -> pathlib.Path:
    """Файл доставки новостей этой витрины."""
    return registry.корень_хранилища(s.adapter) / s.domain / ИМЯ_ДОСТАВКИ


def _каталог_черновиков(s: registry.Сайт) -> pathlib.Path:
    return editorial._каталог(s)


def апстрим(s: registry.Сайт) -> str:
    """`host:port` приложения, в которое проксирует витрина, по её ВЫПУСКУ.

    Значение объявлено в `config/site.json: environment.LORDS_LEGACY_UPSTREAM`
    установленного выпуска. Это единственная измеряемая связь витрины с её
    приложением; гадать по имени нельзя.
    """
    for корень in (f"/srv/{s.account}/current", f"/srv/{s.account}/app"):
        п = pathlib.Path(корень) / "config" / "site.json"
        if not п.is_file():
            continue
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        return str((д.get("environment") or {}).get("LORDS_LEGACY_UPSTREAM") or "")
    return ""


def контейнер(s: registry.Сайт) -> str:
    """Имя контейнера ЭТОЙ витрины или пустая строка. Только чтение.

    Связь устанавливается по ПОРТУ, который витрина объявила своим апстримом, и
    по порту, который контейнер публикует. По имени искать нельзя: измерено
    2026-10-05 на собственной первой версии этой функции — подстрочный поиск
    возвращал `yummyani-staging-web-org-1` для всех пяти витрин семейства, и
    посев новостей взял бы содержимое ЧУЖОГО сайта. Это cross-site утечка, а
    не неточность.
    """
    из_среды = os.environ.get("YUMMY_POSTS_CONTAINER", "").strip()
    if из_среды:
        return из_среды
    адрес = апстрим(s)
    порт = адрес.rpartition(":")[2].strip()
    if not порт.isdigit():
        return ""
    try:
        о = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    if о.returncode != 0:
        return ""
    подошли = [строка.split("\t")[0] for строка in о.stdout.splitlines()
               if f":{порт}->" in строка]
    # Ровно один: два контейнера на одном порту невозможны, а ноль означает,
    # что приложение витрины не запущено — и это ДРУГОЙ ответ, чем «не нашли».
    return подошли[0] if len(подошли) == 1 else ""


def посев(s: registry.Сайт) -> dict:
    """Авторитетное содержимое новостей ИЗ РАБОТАЮЩЕГО контейнера.

    Читается именно контейнер: он и отдаёт раздел, значит его файл —
    единственное значение, относительно которого «дополнить» имеет смысл.
    Не прочитали — отказ. Начать с пустого списка нельзя: монтирование
    заменяет файл образа целиком, и пустой посев снял бы с публикации всё
    существующее.
    """
    имя = контейнер(s)
    if not имя:
        raise ОперацияОтклонена(
            f"{s.domain}: контейнер витрины не определён, прочитать исходные "
            "новости нечем. Посев пустым списком запрещён: он снял бы с "
            "публикации всё, что уже опубликовано")
    цель = pathlib.Path(os.environ.get(
        "TMPDIR", "/tmp")) / f"posts-seed-{s.domain}.json"
    о = subprocess.run(["docker", "cp", f"{имя}:{ПУТЬ_В_КОНТЕЙНЕРЕ}", str(цель)],
                       capture_output=True, text=True, timeout=120)
    if о.returncode != 0:
        raise ОперацияОтклонена(
            f"{s.domain}: {ПУТЬ_В_КОНТЕЙНЕРЕ} из контейнера {имя} не прочитан: "
            f"{о.stderr.strip()[:200]}")
    try:
        данные = json.loads(цель.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise ОперацияОтклонена(
            f"{s.domain}: посев не разбирается: {type(ош).__name__}") from None
    finally:
        цель.unlink(missing_ok=True)
    беды = проверить_файл(данные)
    if беды:
        raise ОперацияОтклонена(
            f"{s.domain}: содержимое контейнера не проходит собственную схему "
            f"приложения: {беды[:3]}")
    return данные


def доставленное(s: registry.Сайт) -> dict | None:
    """Что лежит в файле доставки, или None, если его ещё нет."""
    п = путь_доставки(s)
    if not п.is_file():
        return None
    try:
        return json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise ОперацияОтклонена(
            f"{п} не читается: {type(ош).__name__}") from None


def состояние(site: str) -> dict:
    """Что опубликовано, что в черновиках, чем доставляется. Только чтение."""
    s = _сайт(site)
    файл = доставленное(s)
    посеяно = None
    if файл is None:
        try:
            посеяно = len((посев(s).get("posts") or []))
        except ОперацияОтклонена as ош:
            посеяно = f"посев недоступен: {ош}"
    черновики = editorial._прочитать(
        _каталог_черновиков(s) / ЧЕРНОВИКИ, {"site": s.domain, "items": {}})
    записи = (файл or {}).get("posts") or []
    return {
        "site": s.domain,
        "delivery_file": str(путь_доставки(s)),
        "delivery_present": файл is not None,
        "container_path": ПУТЬ_В_КОНТЕЙНЕРЕ,
        "mount_required": файл is None or not _смонтировано(s),
        "published": sorted(з.get("slug") for з in записи
                            if з.get("status") == "published"),
        "drafted_in_delivery": sorted(з.get("slug") for з in записи
                                      if з.get("status") == "draft"),
        "factory_drafts": sorted((черновики.get("items") or {})),
        "seed_posts": посеяно,
        "problems": проверить_файл(файл) if файл is not None else [],
    }


def _смонтировано(s: registry.Сайт) -> bool:
    """Видит ли контейнер файл доставки. Только чтение, без догадок."""
    имя = контейнер(s)
    if not имя:
        return False
    try:
        о = subprocess.run(
            ["docker", "inspect", имя, "--format",
             "{{range .Mounts}}{{.Source}}->{{.Destination}} {{end}}"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    if о.returncode != 0:
        return False
    return f"{путь_доставки(s)}->{ПУТЬ_В_КОНТЕЙНЕРЕ}" in о.stdout.replace(" ", "")


def подготовить(site: str, slug: str, *, title: str, excerpt: str,
                body: list[str], author: str, тип: str = "news",
                channel: str | None = None, external_url: str | None = None,
                thumbnail_url: str | None = None,
                source: str = "editorial") -> dict:
    """Сохранить ЧЕРНОВИК новости. Публичного ничего не меняется.

    Черновик лежит в хранилище фабрики и в файл доставки не попадает. Это и
    есть предварительный просмотр механизма: запись проверена схемой
    приложения, а на сайте её нет.
    """
    s = _сайт(site)
    # СЛАГ — ЛИЧНОСТЬ ЗАПИСИ, а не качество текста, и проверяется ДО записи.
    #
    # Беды содержания сохраняются вместе с черновиком: редактор видит их и
    # правит текст, не теряя работу. С негодным слагом так нельзя — запись
    # никогда не станет публикуемой, и черновик под таким ключом был бы
    # мусором в хранилище (измерено 2026-10-05: инструмент принял слаг с
    # пробелами и кириллицей и завёл черновик, который нельзя опубликовать).
    if not СЛАГ.match(str(slug or "")):
        raise ОперацияОтклонена(
            f"slug {slug!r}: допустимы только латинские буквы, цифры и дефис — "
            "это публичный адрес записи, и приложение другого не примет")
    запись = {
        "slug": slug, "type": тип, "status": "draft", "title": title,
        "excerpt": excerpt, "body": list(body or []),
        "publishedAt": _сейчас(), "updatedAt": _сейчас(),
        "authorName": author, "channelName": channel,
        "externalUrl": external_url, "thumbnailUrl": thumbnail_url,
        "source": source,
    }
    беды = проверить_запись(запись)
    к = _каталог_черновиков(s)
    черновики = editorial._прочитать(к / ЧЕРНОВИКИ, {"site": s.domain, "items": {}})
    черновики.setdefault("items", {})[slug] = {
        **запись, "digest": отпечаток(запись),
        "prepared_at": _сейчас(), "author": author,
        "state": "verified" if not беды else "prepared",
        "quality_problems": беды,
    }
    черновики["site"] = s.domain
    editorial._записать_атомарно(к / ЧЕРНОВИКИ, черновики)
    editorial._дописать_историю(к, {"at": _сейчас(), "op": "prepare-post",
                                    "slug": slug, "author": author,
                                    "problems": беды})
    return {"site": s.domain, "slug": slug,
            "state": черновики["items"][slug]["state"],
            "quality_problems": беды,
            "draft_store": str(к / ЧЕРНОВИКИ),
            "public": False,
            "note": ("черновик в файл доставки не попадает; приложение "
                     "никогда не показывает status=draft")}


def _записать_доставку(s: registry.Сайт, данные: dict, *, author: str,
                       операция: str, slug: str) -> dict:
    """Проверить файл ЦЕЛИКОМ и записать его атомарно.

    Проверка целиком обязательна: приложение разбирает файл одной схемой, и
    одна негодная запись лишает раздел `/posts` всех остальных. Поэтому
    отклонённый файл не записывается вовсе.
    """
    беды = проверить_файл(данные)
    if беды:
        raise ОперацияОтклонена(
            f"{s.domain}: файл доставки не прошёл схему приложения и НЕ "
            f"записан: {беды[:4]}")
    п = путь_доставки(s)
    п.parent.mkdir(parents=True, exist_ok=True)
    рядом = п.with_name(п.name + ".new")
    рядом.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    os.replace(рядом, п)
    editorial._дописать_историю(_каталог_черновиков(s), {
        "at": _сейчас(), "op": операция, "slug": slug, "author": author,
        "delivery_file": str(п), "posts": len(данные.get("posts") or [])})
    return {"delivery_file": str(п), "posts": len(данные.get("posts") or [])}


def опубликовать(site: str, slug: str, *, author: str) -> dict:
    """Перенести черновик в файл доставки со статусом `published`.

    Повтор дубля не создаёт: совпадающий отпечаток содержания отвечает
    `nothing-to-do` и файла не касается. Изменённый текст той же новости —
    это ПРАВКА: запись обновляется, `publishedAt` сохраняется, `updatedAt`
    сдвигается.
    """
    s = _сайт(site)
    к = _каталог_черновиков(s)
    черновики = editorial._прочитать(к / ЧЕРНОВИКИ, {"site": s.domain, "items": {}})
    черновик = (черновики.get("items") or {}).get(slug)
    if not черновик:
        raise ОперацияОтклонена(
            f"{s.domain}: черновика {slug} нет. Публиковать нечего: текст "
            "сначала готовится операцией подготовки")
    if черновик.get("quality_problems"):
        raise ОперацияОтклонена(
            f"{s.domain}: черновик {slug} не прошёл проверку: "
            f"{черновик['quality_problems'][:4]}")

    файл = доставленное(s)
    засеяно = False
    if файл is None:
        файл = посев(s)
        засеяно = True
    записи = list(файл.get("posts") or [])

    запись = {к2: черновик[к2] for к2 in list(ОБЯЗАТЕЛЬНЫЕ) + list(ОБНУЛЯЕМЫЕ)
              if к2 in черновик}
    запись["status"] = "published"
    прежняя = next((з for з in записи if з.get("slug") == slug), None)
    if прежняя is not None:
        # ЗАЩИТА ОТ ДУБЛЯ. Та же новость с тем же содержанием — не работа.
        if (прежняя.get("status") == "published"
                and отпечаток(прежняя) == отпечаток(запись)):
            return {"site": s.domain, "slug": slug, "status": "nothing-to-do",
                    "public_url": f"https://{s.domain}/posts/{slug}",
                    "delivery_file": str(путь_доставки(s)),
                    "note": "запись уже опубликована с этим содержанием"}
        запись["publishedAt"] = прежняя.get("publishedAt") or запись["publishedAt"]
        запись["updatedAt"] = _сейчас()
        записи = [запись if з.get("slug") == slug else з for з in записи]
        исход = "updated"
    else:
        записи.insert(0, запись)
        исход = "created"
    файл = {"version": ВЕРСИЯ_ФАЙЛА, "posts": записи}
    шаги = _записать_доставку(s, файл, author=author, операция="publish-post",
                              slug=slug)
    return {"site": s.domain, "slug": slug, "status": исход,
            "seeded_from_container": засеяно,
            "public_url": f"https://{s.domain}/posts/{slug}",
            "mounted": _смонтировано(s),
            **шаги,
            "note": ("файл записан; публичным он станет, когда контейнер видит "
                     "его по пути " + ПУТЬ_В_КОНТЕЙНЕРЕ)}


def снять(site: str, slug: str, *, author: str) -> dict:
    """Снять КОНКРЕТНУЮ публикацию: запись переводится в `draft`.

    Удаления нет сознательно: приложение не показывает черновики, то есть
    публичного следа не остаётся, а запись и её история сохраняются. Снятие
    обратимо повторной публикацией.
    """
    s = _сайт(site)
    файл = доставленное(s)
    if файл is None:
        raise ОперацияОтклонена(
            f"{s.domain}: файла доставки нет — снимать нечего. Публичные "
            "записи приезжают из образа контейнера, и операция их не трогает")
    записи = list(файл.get("posts") or [])
    цель = next((з for з in записи if з.get("slug") == slug), None)
    if цель is None:
        raise ОперацияОтклонена(
            f"{s.domain}: записи {slug} в файле доставки нет")
    if цель.get("status") == "draft":
        return {"site": s.domain, "slug": slug, "status": "nothing-to-do",
                "note": "запись уже снята с публикации"}
    обновлённая = {**цель, "status": "draft", "updatedAt": _сейчас()}
    записи = [обновлённая if з.get("slug") == slug else з for з in записи]
    шаги = _записать_доставку(s, {"version": ВЕРСИЯ_ФАЙЛА, "posts": записи},
                              author=author, операция="unpublish-post", slug=slug)
    return {"site": s.domain, "slug": slug, "status": "unpublished", **шаги,
            "note": ("запись переведена в draft: приложение черновиков не "
                     "показывает, запись и история сохранены")}
