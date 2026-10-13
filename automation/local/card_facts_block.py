"""Блок характеристик карточки: вырезать именно его, а не страницу целиком.

Зачем отдельный модуль. Жанры тайтла живут в блоке характеристик, а на той же
странице стоит сквозная навигация по жанрам. Признак, считающий жанровые ссылки
по всей странице, не различает «карточка ссылается на СВОИ жанры» и «на
странице есть меню жанров» — а это разные вещи: первое связывает карточку с её
разделом, второе есть на каждой странице и ничего про карточку не говорит.

Измерено 13.10, и первый подход был неверным дважды:

1. сравнение двух карточек: наборы жанровых ссылок совпали — но это оказались
   две индийские драмы с одними жанрами, а не сквозной блок;
2. вычитание сквозного блока: жанр, который И в меню, И свой у тайтла,
   вычитался вместе с меню — то есть настоящая связь терялась.

Поэтому блок вырезается разбором разметки, а не вычитанием. Контейнеры у
семейств разные и названы явно; **нераспознанный контейнер — НЕ ноль, а отказ
измерять**: ноль утверждал бы «связей нет», чего из неизвестной разметки не
следует.
"""
from __future__ import annotations

from html.parser import HTMLParser

#: Контейнер блока характеристик по семействам. Измерено на живых карточках
#: 13.10: Lords — `facts`, Zona и Animedia — `ztitle__facts`, AnimeGo —
#: `ag-facts`, Yummy — `portal-meta-list`.
КОНТЕЙНЕРЫ = ("facts", "ztitle__facts", "ag-facts", "portal-meta-list")


class _Вырезка(HTMLParser):
    """Собирает разметку элемента, у которого класс входит в список."""

    def __init__(self, классы: tuple[str, ...]) -> None:
        super().__init__(convert_charrefs=False)
        self._классы = классы
        self._глубина = 0
        self._внутри = False
        self._куски: list[str] = []
        self.найдено: list[str] = []
        self.какой: str | None = None

    @staticmethod
    def _атрибут(атрибуты, имя):
        for к, з in атрибуты:
            if к == имя:
                return з or ""
        return ""

    def handle_starttag(self, tag, attrs):
        классы = set((self._атрибут(attrs, "class") or "").split())
        совпало = классы & set(self._классы)
        if not self._внутри and совпало:
            self._внутри = True
            self._глубина = 1
            self.какой = sorted(совпало)[0]
            self._куски = []
            return
        if self._внутри:
            # Пустые элементы вложенность не увеличивают.
            if tag not in ("br", "img", "input", "meta", "link", "hr", "source"):
                self._глубина += 1
            self._куски.append(self.get_starttag_text() or "")

    def handle_startendtag(self, tag, attrs):
        if self._внутри:
            self._куски.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag):
        if not self._внутри:
            return
        self._глубина -= 1
        if self._глубина <= 0:
            self._внутри = False
            self.найдено.append("".join(self._куски))
            self._куски = []
            return
        self._куски.append(f"</{tag}>")

    def handle_data(self, data):
        if self._внутри:
            self._куски.append(data)

    def handle_entityref(self, name):
        if self._внутри:
            self._куски.append(f"&{name};")

    def handle_charref(self, name):
        if self._внутри:
            self._куски.append(f"&#{name};")


def блок(тело: str, классы: tuple[str, ...] = КОНТЕЙНЕРЫ) -> tuple[str, str] | None:
    """(разметка блока, имя контейнера) или None, если контейнер не распознан.

    None — отказ измерять, а не «блока нет»: разметка семейства может быть
    новой, и ноль связей из неё не следует.
    """
    р = _Вырезка(классы)
    try:
        р.feed(тело)
        р.close()
    except Exception:                                  # noqa: BLE001
        # Разбитая разметка — тоже предел измерения, а не ноль связей.
        return None
    if not р.найдено or not р.какой:
        return None
    # Контейнер может встретиться дважды (карточка и соседний блок): берётся
    # самый ОБЪЁМНЫЙ — характеристики длиннее любого повторения заголовка.
    return max(р.найдено, key=len), р.какой
