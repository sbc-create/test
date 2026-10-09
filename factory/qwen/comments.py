#!/usr/bin/env python3
"""Редакционные комментарии ПОД КАРТОЧКОЙ. Отдельная сущность от новостей.

Почему отдельный модуль, а не поле у постов
-------------------------------------------

Пост раздела `/posts` и комментарий под карточкой — разные вещи и для
посетителя, и для приложения витрины. Решение владельца 2026-10-09 после
инцидента: «Не добавляй posts-edit для решения этой задачи: посты и
комментарии — разные сущности». Инцидент к этому и привёл: черновик
комментария опубликовали НОВОСТЬЮ
(`yummyani.org/posts/chernaya-koshka-i-klass-vedm-comment`), и на сайте
появился текст, который комментарием не был.

Чем комментарий публикуется
---------------------------

У приложения Yummy комментарии живут в его собственной базе и имеют публичный
интерфейс, который витрина же и показывает:

    GET  /api/comments?titleSlug=<slug>   список опубликованных
    POST /api/comments                    создать (status published сразу)

Это прочитано в коде приложения (`src/modules/comments/service.ts`,
`src/app/api/comments/route.ts`), а не предположено: `createGuestComment`
создаёт запись со `status: CommentStatus.published`, то есть премодерации в
этом приложении нет. Поле `authorName` обязательно — им и называется
«Редакция»; выдуманного зрителя здесь не появляется, подпись говорит, кто
написал.

Приложение само отвергает повтор: `bodyHash` по (slug, сезон, серия, автор,
тело) в окне `COMMENT_DUPLICATE_WINDOW_MS`. Мы всё равно проверяем список ДО
записи — отказ приложения по повтору неотличим от других отказов, а
посетителю и владельцу нужен точный ответ.

Чего здесь нет
--------------

Семейств с нашим рантаймом (lords, zona, animedia, animego) этот путь не
касается: у них комментарии лежат в хранилище сообщества ячейки
(`src/community.py`), а оно — постоянные данные посетителей, и правило
`docs/RUNTIME_DATA_OWNERSHIP.md` разрешает выпуску и установщику только
чтение. Привилегированной операции записи туда нет, и придумывать её здесь
нельзя: это отдельное решение уровня `knowledge/DECISIONS.md`. Для таких
площадок операция отказывает и называет блокер.
"""

from __future__ import annotations

import json
import pathlib
import time
import urllib.error
import urllib.request
from typing import Any

from factory.qwen import actors, editorial, registry

#: Имя файла черновиков комментариев. Рядом с черновиками постов, но ОТДЕЛЬНО:
#: смешать их — значит снова получить комментарий, опубликованный новостью.
ЧЕРНОВИКИ = "comment-drafts.json"

#: Подпись редакции. Одна на сеть, задаётся здесь, а не приходит из вызова:
#: подпись — часть договорённости с владельцем, а не параметр запуска.
ПОДПИСЬ = "Редакция"

#: Семейства, у которых комментарии умеет публиковать приложение витрины.
СЕМЕЙСТВА_С_КОММЕНТАРИЯМИ = ("yummy",)

#: Границы тела, перенесённые из приложения (`comments/constants.ts`).
МИНИМУМ_ТЕЛА = 3
МАКСИМУМ_ТЕЛА = 2000


class ОперацияОтклонена(Exception):
    """Комментарий не записан, и причина названа."""


def _сайт(site: str) -> registry.Сайт:
    return editorial._сайт(site, опрашивать_сеть=False)


def _каталог(s: registry.Сайт) -> pathlib.Path:
    return editorial._каталог(s)


def _требует_семейство(s: registry.Сайт) -> None:
    если = getattr(s, "adapter", "")
    if если in СЕМЕЙСТВА_С_КОММЕНТАРИЯМИ:
        return
    raise ОперацияОтклонена(
        f"{s.domain}: редакционные комментарии под карточкой этой площадкой "
        f"пока не поддерживаются. Семейство {если!r} держит комментарии в "
        "хранилище сообщества ячейки (src/community.py), а это постоянные "
        "данные посетителей: выпуску и установщику разрешено только чтение "
        "(docs/RUNTIME_DATA_OWNERSHIP.md). Нужна узкая привилегированная "
        "операция исполнителя и запись в knowledge/DECISIONS.md — решение "
        "отдельное, подменять его публикацией в /posts запрещено")


def _адрес_карточки(s: registry.Сайт, slug: str) -> str:
    return registry.адрес_тайтла(s, slug)


def _запрос(адрес: str, *, тело: dict | None = None, домен: str) -> tuple[int, str]:
    """Запрос к приложению витрины. Origin обязателен: оно его проверяет."""
    данные = None if тело is None else json.dumps(тело, ensure_ascii=False).encode()
    заголовки = {
        "User-Agent": "site-factory-editorial/1.0",
        "Accept": "application/json",
        "Origin": f"https://{домен}",
        "Referer": f"https://{домен}/",
    }
    if данные is not None:
        заголовки["Content-Type"] = "application/json"
    запрос = urllib.request.Request(адрес, data=данные, headers=заголовки,
                                    method="POST" if данные else "GET")
    try:
        with urllib.request.urlopen(запрос, timeout=45) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ош.read().decode("utf-8", "replace")
    except Exception as ош:  # noqa: BLE001 — недоступность приложения не падение
        return 0, f"{type(ош).__name__}: {ош}"


def состояние(site: str, slug: str) -> dict[str, Any]:
    """Что уже опубликовано под карточкой. Только чтение."""
    s = _сайт(site)
    _требует_семейство(s)
    код, тело = _запрос(f"https://{s.domain}/api/comments?titleSlug={slug}",
                        домен=s.domain)
    if код != 200:
        raise ОперацияОтклонена(
            f"{s.domain}: список комментариев не прочитан (HTTP {код}): "
            f"{тело[:200]}")
    данные = json.loads(тело)
    записи = данные.get("comments") or []
    return {
        "site": s.domain, "slug": slug, "url": _адрес_карточки(s, slug),
        "total": данные.get("total"),
        "comments": [{"id": з.get("id"), "author": з.get("authorName"),
                      "created_at": з.get("createdAt"),
                      "body": з.get("body")} for з in записи],
    }


def _черновики(s: registry.Сайт) -> dict:
    return editorial._прочитать(_каталог(s) / ЧЕРНОВИКИ,
                                {"site": s.domain, "items": {}})


def подготовить(site: str, slug: str, тело: str, *, author: str) -> dict[str, Any]:
    """Записать черновик комментария. Публичного следствия нет."""
    actors.проверить(author, "comment-prepare")
    s = _сайт(site)
    _требует_семейство(s)
    текст = editorial.обрезать(тело)
    if not (МИНИМУМ_ТЕЛА <= len(текст) <= МАКСИМУМ_ТЕЛА):
        raise ОперацияОтклонена(
            f"тело комментария {len(текст)} знаков: приложение принимает от "
            f"{МИНИМУМ_ТЕЛА} до {МАКСИМУМ_ТЕЛА}")
    к = _каталог(s)
    к.mkdir(parents=True, exist_ok=True)
    черновики = _черновики(s)
    черновики.setdefault("items", {})[slug] = {
        "slug": slug, "body": текст, "author": ПОДПИСЬ,
        "prepared_by": author, "prepared_at": editorial._сейчас(),
        "body_digest": editorial.отпечаток(текст),
    }
    editorial._записать_атомарно(к / ЧЕРНОВИКИ, черновики)
    return {"site": s.domain, "slug": slug, "state": "drafted",
            "chars": len(текст), "url": _адрес_карточки(s, slug)}


def опубликовать(site: str, slug: str, *, author: str,
                 тело: str | None = None) -> dict[str, Any]:
    """Опубликовать комментарий под карточкой и подтвердить его видимость.

    Повтор проверяется ДО записи: тем же текстом под тем же слагом комментарий
    второй раз не пишется, и это отказ, а не тихий успех.
    """
    actors.проверить(author, "comment-publish")
    s = _сайт(site)
    _требует_семейство(s)
    текст = editorial.обрезать(тело) if тело else ""
    if not текст:
        черновик = (_черновики(s).get("items") or {}).get(slug) or {}
        текст = str(черновик.get("body") or "")
    if not текст:
        raise ОперацияОтклонена(
            f"для {slug!r} нет ни черновика комментария, ни переданного тела: "
            "публиковать нечего. Выдумывать текст нельзя")
    если = состояние(site, slug)
    for з in если["comments"]:
        if str(з.get("body") or "").strip() == текст.strip():
            raise ОперацияОтклонена(
                f"такой комментарий под карточкой уже есть (id {з.get('id')}, "
                f"автор {з.get('author')!r}, {з.get('created_at')}): повтор не "
                "записывается")
    код, ответ = _запрос(f"https://{s.domain}/api/comments",
                         тело={"titleSlug": slug, "authorName": ПОДПИСЬ,
                               "body": текст},
                         домен=s.domain)
    if код not in (200, 201):
        raise ОперацияОтклонена(
            f"{s.domain}: приложение не приняло комментарий (HTTP {код}): "
            f"{ответ[:300]}")
    данные = json.loads(ответ) if ответ.strip().startswith("{") else {}
    ид = данные.get("id") or (данные.get("comment") or {}).get("id") or ""
    # Подтверждение — чтением списка, а не ответом на запись: ответ говорит,
    # что приложение приняло, а посетителю важно, что оно ОТДАЁТ.
    видно, запись = False, {}
    for _ in range(6):
        time.sleep(2)
        сейчас = состояние(site, slug)
        for з in сейчас["comments"]:
            if (ид and з.get("id") == ид) or str(з.get("body") or "").strip() == текст.strip():
                видно, запись = True, з
                break
        if видно:
            break
    editorial._дописать_историю(_каталог(s), {
        "at": editorial._сейчас(), "op": "publish-comment", "slug": slug,
        "author": ПОДПИСЬ, "prepared_by": author, "comment_id": ид or None,
        "body_digest": editorial.отпечаток(текст), "visible": видно,
    })
    if not видно:
        raise ОперацияОтклонена(
            f"комментарий записан (id {ид or 'не назван'}), но в списке "
            f"карточки не появился за 12 секунд. Проверьте {_адрес_карточки(s, slug)} "
            "прежде чем повторять: повтор создаст второй комментарий")
    return {"site": s.domain, "slug": slug, "state": "published",
            "comment_id": ид or запись.get("id"),
            "author": запись.get("author") or ПОДПИСЬ,
            "created_at": запись.get("created_at"),
            "url": _адрес_карточки(s, slug), "visible_in_list": True}
