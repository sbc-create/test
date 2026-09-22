"""Сообщество Animedia: голоса, комментарии и реакции — без выдуманных людей.

Модуль хранит то, что оставили посетители, и ничего не придумывает: пустое
хранилище означает пустой раздел, а не «пока никто не оставил отзыв» с тремя
готовыми отзывами. Ни одного синтетического автора, ни одной заготовленной
оценки здесь не появляется и появиться не может — записи создаются только
вызовами `добавить_*`.

Почему файл, а не база. Витрине нужен маленький общий счётчик на тайтл и
короткая лента сообщений; отдельная база ради этого — лишняя зависимость,
которой пришлось бы управлять отдельно. Файл пишется атомарно (временный файл
рядом и `os.replace`), а одновременный доступ разводится файловой блокировкой:
процесс витрины многопоточный, и две правки в одну секунду — обычное дело.

Когда хранилище недоступно (каталог не создан, нет прав на запись), модуль
сообщает об этом честно: `доступно = False` и причина. Витрина в этом случае
показывает раздел выключенным и объясняет, чего не хватает, — но не прячет его
и не делает вид, что сообщений нет.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Допустимые реакции. Список закрыт намеренно: произвольная реакция от
#: посетителя — это произвольный текст на странице.
РЕАКЦИИ: tuple[str, ...] = ("огонь", "сердце", "смех", "грусть", "вау")

#: Границы оценки. Шкала та же, что у сводной, иначе их нельзя ставить рядом.
ОЦЕНКА_МИН, ОЦЕНКА_МАКС = 1, 10

#: Предел длины сообщения. Не цензура, а защита страницы от полотна.
ДЛИНА_КОММЕНТАРИЯ = 1200

#: Сколько сообщений держать на тайтл.
ПРЕДЕЛ_КОММЕНТАРИЕВ = 200


@dataclass
class Состояние:
    """Что витрина знает о сообществе конкретного тайтла."""

    slug: str
    голосов: int = 0
    сумма: int = 0
    средняя: float | None = None
    распределение: dict = field(default_factory=dict)
    реакции: dict = field(default_factory=dict)
    комментарии: list = field(default_factory=list)
    мой_голос: int | None = None
    моя_реакция: str | None = None


def _посетитель(ключ: str) -> str:
    """Устойчивый обезличенный идентификатор посетителя.

    Хранить адрес или cookie как есть незачем: для «один голос от одного
    посетителя» достаточно отпечатка. Он не позволяет узнать человека и не
    выдаёт себя за учётную запись, которой у витрины нет.
    """
    return hashlib.sha256(("animedia-community/1.0:" + ключ).encode("utf-8")).hexdigest()[:24]


class Хранилище:
    """Файловое хранилище сообщества одной витрины."""

    def __init__(self, путь: str | os.PathLike) -> None:
        self.путь = Path(путь)
        self.доступно = False
        self.причина = ""
        self._проверить()

    def _проверить(self) -> None:
        try:
            self.путь.parent.mkdir(parents=True, exist_ok=True)
            if not self.путь.exists():
                self._записать({"schema_version": 1, "titles": {}})
            # Проверяется именно запись: каталог может существовать и быть
            # чужим, и тогда «доступно» было бы неправдой.
            if not os.access(self.путь, os.W_OK):
                raise PermissionError(f"нет прав на запись: {self.путь}")
            self.доступно = True
            self.причина = ""
        except OSError as ош:
            self.доступно = False
            self.причина = f"{type(ош).__name__}: {ош}"

    # --- чтение и запись ---------------------------------------------------

    def _прочитать(self) -> dict:
        try:
            return json.loads(self.путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"schema_version": 1, "titles": {}}

    def _записать(self, данные: dict) -> None:
        с, врем = tempfile.mkstemp(dir=str(self.путь.parent),
                                   prefix=self.путь.name, suffix=".tmp")
        try:
            with os.fdopen(с, "w", encoding="utf-8") as ф:
                json.dump(данные, ф, ensure_ascii=False)
            os.replace(врем, self.путь)
        except BaseException:
            Path(врем).unlink(missing_ok=True)
            raise

    def _изменить(self, slug: str, правка) -> dict:
        """Правка под файловой блокировкой: соседний поток не затрёт чужое."""
        if not self.доступно:
            raise RuntimeError(self.причина or "хранилище недоступно")
        замок = self.путь.with_suffix(self.путь.suffix + ".lock")
        with open(замок, "w", encoding="utf-8") as ф:
            fcntl.flock(ф, fcntl.LOCK_EX)
            try:
                данные = self._прочитать()
                запись = данные.setdefault("titles", {}).setdefault(
                    slug, {"votes": {}, "reactions": {}, "comments": []})
                правка(запись)
                данные["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._записать(данные)
                return запись
            finally:
                fcntl.flock(ф, fcntl.LOCK_UN)

    # --- чтение состояния --------------------------------------------------

    def состояние(self, slug: str, ключ_посетителя: str = "") -> Состояние:
        запись = (self._прочитать().get("titles") or {}).get(slug) or {}
        голоса = запись.get("votes") or {}
        значения = [int(v) for v in голоса.values()
                    if isinstance(v, (int, float)) and ОЦЕНКА_МИН <= int(v) <= ОЦЕНКА_МАКС]
        распределение: dict = {}
        for v in значения:
            распределение[str(v)] = распределение.get(str(v), 0) + 1
        я = _посетитель(ключ_посетителя) if ключ_посетителя else ""
        реакции = {р: len(список) for р, список in (запись.get("reactions") or {}).items()
                   if isinstance(список, list) and список}
        моя = next((р for р, список in (запись.get("reactions") or {}).items()
                    if isinstance(список, list) and я and я in список), None)
        комментарии = [с for с in (запись.get("comments") or []) if isinstance(с, dict)]
        return Состояние(
            slug=slug,
            голосов=len(значения),
            сумма=sum(значения),
            средняя=(round(sum(значения) / len(значения), 1) if значения else None),
            распределение=распределение,
            реакции=реакции,
            комментарии=комментарии[:ПРЕДЕЛ_КОММЕНТАРИЕВ],
            мой_голос=(int(голоса.get(я)) if я and голоса.get(я) is not None else None),
            моя_реакция=моя,
        )

    # --- изменения ---------------------------------------------------------

    def добавить_голос(self, slug: str, значение: int, ключ_посетителя: str) -> Состояние:
        значение = int(значение)
        if not ОЦЕНКА_МИН <= значение <= ОЦЕНКА_МАКС:
            raise ValueError(f"оценка вне шкалы {ОЦЕНКА_МИН}–{ОЦЕНКА_МАКС}")
        я = _посетитель(ключ_посетителя)
        self._изменить(slug, lambda з: з.setdefault("votes", {}).__setitem__(я, значение))
        return self.состояние(slug, ключ_посетителя)

    def снять_голос(self, slug: str, ключ_посетителя: str) -> Состояние:
        я = _посетитель(ключ_посетителя)
        self._изменить(slug, lambda з: (з.get("votes") or {}).pop(я, None))
        return self.состояние(slug, ключ_посетителя)

    def переключить_реакцию(self, slug: str, реакция: str,
                            ключ_посетителя: str) -> Состояние:
        if реакция not in РЕАКЦИИ:
            raise ValueError(f"неизвестная реакция: {реакция}")
        я = _посетитель(ключ_посетителя)

        def правка(з: dict) -> None:
            все = з.setdefault("reactions", {})
            for имя, список in list(все.items()):
                if isinstance(список, list) and я in список:
                    список.remove(я)
                    if not список:
                        все.pop(имя, None)
                    if имя == реакция:
                        return  # повторное нажатие снимает реакцию
            все.setdefault(реакция, []).append(я)

        self._изменить(slug, правка)
        return self.состояние(slug, ключ_посетителя)

    def добавить_комментарий(self, slug: str, имя: str, текст: str,
                             ключ_посетителя: str) -> Состояние:
        текст = re.sub(r"\s+", " ", str(текст or "")).strip()
        имя = re.sub(r"\s+", " ", str(имя or "")).strip()[:40]
        if not текст:
            raise ValueError("пустое сообщение")
        if len(текст) > ДЛИНА_КОММЕНТАРИЯ:
            raise ValueError(f"сообщение длиннее {ДЛИНА_КОММЕНТАРИЯ} знаков")
        if not имя:
            # Имя не выдумывается за посетителя: он либо назвался, либо
            # остаётся гостем, и это видно в ленте.
            имя = "Гость"
        запись = {
            "id": hashlib.sha256(
                f"{slug}|{текст}|{time.time_ns()}".encode("utf-8")).hexdigest()[:16],
            "name": имя,
            "text": текст,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "author_key": _посетитель(ключ_посетителя),
        }
        self._изменить(slug, lambda з: з.setdefault("comments", []).insert(0, запись))
        return self.состояние(slug, ключ_посетителя)


def открыть(путь: str | os.PathLike | None) -> Хранилище | None:
    """Хранилище по пути или None, если путь не задан вовсе."""
    if not путь:
        return None
    return Хранилище(путь)
