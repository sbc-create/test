"""Нестрогое сопоставление запроса с названием.

## Зачем

Зритель набирает с опечаткой, в чужой раскладке, латиницей вместо кириллицы и
без буквы «ё» — её прячет раскладка. Поиск, отвечающий только на точное
совпадение, для такого зрителя не существует.

## Чего здесь нет

Индекса, хранилища и обращения к сети. Это чистое сопоставление: на вход
список записей и строка, на выход — упорядоченная выборка. Где искать и как
доставлять набор — решает вызывающий; смешивать это с правилом сопоставления
значило бы привязать правило к одному способу доставки.

## Главное ограничение

Нестрогость не должна находить всё подряд. Поиск, отвечающий на «зззззз»
половиной каталога, бесполезен ровно так же, как поиск, не отвечающий ничем.
Поэтому порог расстояния растёт с длиной слова, а запрос короче двух символов
не обрабатывается вовсе: один символ совпадает почти с чем угодно.
"""
from __future__ import annotations

import re
import unicodedata

#: Русская раскладка под латинскими клавишами. Нужна для запроса, набранного
#: не в той раскладке: «vfnhbwf» на русской даёт «матрица».
LAYOUT = str.maketrans(
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.`",
    "йцукенгшщзхъфывапролджэячсмитьбюё",
)

#: Транслитерация кириллицы в латиницу — теми же правилами, что и в адресах
#: витрины, иначе запрос «matrica» не нашёл бы «Матрицу», хотя её адрес именно
#: `matrica`.
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

MIN_QUERY = 2
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Приведение к сравнимому виду: регистр, «ё», знаки, пробелы."""
    if not text:
        return ""
    lowered = unicodedata.normalize("NFC", text).lower().replace("ё", "е")
    return _SPACES.sub(" ", _PUNCT.sub(" ", lowered)).strip()


def translit(text: str) -> str:
    """Кириллица латиницей. Латинские символы остаются как есть."""
    return "".join(TRANSLIT.get(ch, ch) for ch in text)


def from_layout(text: str) -> str:
    """Строка, набранная латинскими клавишами вместо русских."""
    return text.translate(LAYOUT)


def distance(left: str, right: str, *, limit: int) -> int:
    """Расстояние Дамерау — Левенштейна с ранним выходом.

    Перестановка соседних букв считается ОДНОЙ ошибкой, а не двумя: «мтарица»
    вместо «матрица» — самая частая опечатка быстрого набора, и наказывать её
    вдвое значило бы не находить именно то, что чаще всего набирают неверно.

    Ранний выход нужен не ради скорости ради скорости: без него сравнение
    длинного запроса со всем каталогом считает полную матрицу для заведомо
    далёких пар.
    """
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous_previous: list[int] = []
    previous = list(range(len(right) + 1))
    for i, lch in enumerate(left, start=1):
        current = [i] + [0] * len(right)
        best = current[0]
        for j, rch in enumerate(right, start=1):
            cost = 0 if lch == rch else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if (i > 1 and j > 1 and lch == right[j - 2] and left[i - 2] == rch):
                current[j] = min(current[j], previous_previous[j - 2] + 1)
            best = min(best, current[j])
        if best > limit:
            return limit + 1
        previous_previous, previous = previous, current
    return previous[-1]


def _forms(item: dict) -> tuple[str, ...]:
    """Все написания записи, по которым её разумно искать."""
    name = normalize(item.get("name") or "")
    original = normalize(item.get("original") or item.get("original_name") or "")
    forms = {name, original, translit(name)}
    return tuple(f for f in forms if f)


def _variants(query: str) -> tuple[str, ...]:
    """Все прочтения запроса: как набрано, из чужой раскладки, латиницей."""
    base = normalize(query)
    if not base:
        return ()
    out = {base, normalize(from_layout(base)), translit(base)}
    return tuple(v for v in out if v)


def _score(form: str, query: str) -> int:
    """Насколько написание отвечает запросу. Ноль — не отвечает."""
    if not form or not query:
        return 0
    if form == query:
        return 100
    if form.startswith(query):
        return 80
    if query in form:
        return 60
    # Нестрогое сравнение — по словам: запрос обычно короче полного названия,
    # и сравнивать его целиком с длинной строкой значило бы не найти ничего.
    limit = max(1, len(query) // 4)
    for word in form.split():
        if abs(len(word) - len(query)) > limit:
            continue
        d = distance(word, query, limit=limit)
        if d <= limit:
            return 40 - d
    return 0


def search(catalog, query: str, *, limit: int = 20) -> list[dict]:
    """Записи, отвечающие запросу, в устойчивом порядке."""
    variants = _variants(query)
    if not variants or max(len(v) for v in variants) < MIN_QUERY:
        return []
    scored: list[tuple[int, str, dict]] = []
    for item in catalog:
        best = 0
        for form in _forms(item):
            for variant in variants:
                best = max(best, _score(form, variant))
        if best > 0:
            scored.append((best, normalize(item.get("name") or ""), item))
    # Порядок устойчив: сначала оценка, затем название. Без второго ключа
    # одинаково оценённые записи меняли бы места между прогонами.
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored[:limit]]


def did_you_mean(catalog, query: str) -> str | None:
    """Что имелось в виду, если поиск НИЧЕГО не нашёл.

    Условие именно такое, и оно установлено опытом. Первая редакция
    подсказывала при отсутствии точного совпадения — и на запрос «поворов»,
    который прекрасно находит «100 поваров» нестрогим сравнением, предлагала
    «Ритм правосудия: поворот в зале суда». Подсказка поверх непустой выдачи
    сбивает: зритель видит нужное и рядом совет искать другое.

    Подсказка уместна ровно в одном случае — выдача пуста, а близкое написание
    существует. При бессмысленном запросе её нет: выдумывать нечего.
    """
    if search(catalog, query, limit=1):
        return None
    variants = _variants(query)
    if not variants or max(len(v) for v in variants) < MIN_QUERY:
        return None
    best_name, best_key = None, None
    for item in catalog:
        for form in _forms(item):
            for variant in variants:
                # Порог мягче, чем у выдачи: подсказка вправе дотянуться туда,
                # куда выдача не дотянулась, — иначе она никогда не появится.
                limit = max(2, len(variant) // 3)
                for word in form.split():
                    if abs(len(word) - len(variant)) > limit:
                        continue
                    d = distance(word, variant, limit=limit)
                    if d > limit:
                        continue
                    # Ничьи по расстоянию разрешаются длиной общего начала.
                    #
                    # Без этого выигрывал первый встреченный, и на «матрза»
                    # подсказкой оказывалась «Акуна Матата»: она отстоит на те
                    # же две правки, что и «Матрица». Общее начало отличает их
                    # честно — «матр» против «мат», — и не требует ни рейтинга,
                    # ни частотности, которых у нас нет.
                    common = 0
                    for a, b in zip(word, variant, strict=False):
                        if a != b:
                            break
                        common += 1
                    # Порядок ключа: ближе по правкам, длиннее общее начало,
                    # затем алфавит — ради устойчивости между прогонами.
                    #
                    # Предел признаётся прямо: среди одинаково близких
                    # вариантов выбрать «правильный» нечем. «Матрица» и
                    # «Матру» отстоят от «матрза» на две правки и делят общее
                    # начало «матр»; какой из них имелся в виду, знает
                    # популярность, а её у нас нет. Выдумывать сигнал
                    # ранжирования хуже, чем признать ограничение: подсказка
                    # честно даёт близкое, а не угадывает намерение.
                    key = (-d, common, item.get("name") or "")
                    if best_key is None or key > best_key:
                        best_key, best_name = key, item.get("name")
    return best_name if best_key and best_key[0] >= -3 else None
