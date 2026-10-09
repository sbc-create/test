#!/usr/bin/env python3
"""Сверка комментариев «Редакции»: под одной карточкой — один наш комментарий.

    python3 automation/local/comment-audit.py            # все витрины из журналов
    python3 automation/local/comment-audit.py <домен> …   # только названные

Зачем отдельный инструмент. Правило владельца запрещает несколько похожих
комментариев под одной карточкой, а проверка повтора в операции публикации
ловила только ДОСЛОВНОЕ совпадение. 2026-10-09 из-за этого под двумя
карточками оказались по два наших комментария: ночной заход и часовой запуск
редактора выбрали их независимо, с разницей в пять минут. Запрет теперь выражен
в самой операции (`FACTORY_COMMENT_SECOND_REASON`), но у запрета есть дыра во
времени: служба моста исполняет код, загруженный при старте, и до перезапуска
правка не действует. Эта сверка закрывает именно её — и остаётся полезной
после, как независимая проверка по факту, а не по обещанию.

Что делает: берёт карточки из НАШИХ журналов публикаций
(`history.jsonl` хранилищ накладок), читает для каждой список комментариев с
витрины и печатает те, где записей «Редакции» больше одной.

Инструмент ТОЛЬКО ЧИТАЕТ: ничего не публикует и не снимает. Снятие лишнего —
отдельное осознанное действие (`unpublish_comment` с конкретным id).

Выход: 0 — двойных нет; 1 — есть (перечень напечатан); 2 — читать нечем.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Где лежат журналы публикаций. Тот же перечень, что у реестра хранилищ:
#: дублировать его здесь нельзя, поэтому берём из самого реестра.
def _корни() -> list[pathlib.Path]:
    sys.path.insert(0, str(КОРЕНЬ))
    from factory.qwen import registry
    return [pathlib.Path(п) for п in dict(registry.КОРНИ_ХРАНИЛИЩ).values()]


def _карточки(домены: list[str]) -> dict[tuple[str, str], int]:
    """Карточки с нашими публикациями: (домен, слаг) → сколько раз публиковали."""
    итог: dict[tuple[str, str], int] = {}
    for корень in _корни():
        if not корень.is_dir():
            continue
        for каталог in sorted(корень.iterdir()):
            if домены and каталог.name not in домены:
                continue
            журнал = каталог / "history.jsonl"
            if not журнал.is_file():
                continue
            for строка in журнал.read_text(encoding="utf-8").splitlines():
                try:
                    запись = json.loads(строка)
                except ValueError:
                    continue
                if запись.get("op") == "publish-comment" and запись.get("slug"):
                    ключ = (каталог.name, str(запись["slug"]))
                    итог[ключ] = итог.get(ключ, 0) + 1
    return итог


def _комментарии(домен: str, слаг: str) -> list[dict]:
    готово = subprocess.run(
        ["python3", "automation/local/bridge_call.py", "comments_status",
         json.dumps({"site": домен, "slug": слаг}, ensure_ascii=False)],
        capture_output=True, text=True, timeout=240, cwd=str(КОРЕНЬ))
    try:
        ответ = json.loads(готово.stdout)
    except ValueError:
        raise RuntimeError((готово.stdout or готово.stderr)[:200]) from None
    если = ответ.get("comments") or ответ
    return [з for з in (если.get("comments") or [])
            if (з.get("author") or "") == "Редакция"]


def главное(argv: list[str]) -> int:
    карточки = _карточки([a.strip() for a in argv if a.strip()])
    if not карточки:
        print("в журналах публикаций комментариев нет", file=sys.stderr)
        return 2
    двойные = []
    for (домен, слаг) in sorted(карточки):
        try:
            наши = _комментарии(домен, слаг)
        except RuntimeError as ош:
            print(f"{домен:16} {слаг[:48]:48} НЕ ПРОЧИТАНО: {ош}")
            continue
        метка = "ДВОЙНОЙ" if len(наши) > 1 else "ок"
        print(f"{домен:16} {слаг[:48]:48} наших={len(наши)} {метка}")
        if len(наши) > 1:
            двойные.append((домен, слаг, [(з.get("id"), з.get("created_at"))
                                          for з in наши]))
    print(f"\nкарточек проверено: {len(карточки)}; с двумя и более нашими: "
          f"{len(двойные)}")
    for домен, слаг, записи in двойные:
        print(f"  {домен}/{слаг}")
        for ид, когда in записи:
            print(f"    id={ид} {когда}")
    return 1 if двойные else 0


if __name__ == "__main__":
    raise SystemExit(главное(sys.argv[1:]))
