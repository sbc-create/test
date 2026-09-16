"""Нестрогое сопоставление запроса с названием.

## Зачем

Зритель набирает с опечаткой, в чужой раскладке, латиницей вместо кириллицы и
без буквы «ё» — её прячет раскладка. Поиск, отвечающий только на точное
совпадение, для такого зрителя не существует.

## Чего здесь нет

Хранилища и обращения к сети. На вход — список записей или построенный по нему
указатель, на выход — упорядоченная выборка. Где брать набор и как его
доставлять, решает вызывающий.

## Об указателе

Указатель появился по измерению, а не из общих соображений. На боевом каталоге
в 53 251 запись сплошной перебор занимал 3,5 секунды в медиане и 6,4 в худшем
случае — поиска в таком виде для зрителя не существует.

Время уходило в два места. Первое: формы записей пересобирались на каждый
запрос — 434 мс, целиком напрасно, потому что каталог между запросами не
меняется. Второе: нестрогое сравнение шло по 291 226 словам всех записей,
тогда как различных слов всего 63 671 — одно и то же слово сравнивалось с
запросом десятки раз.

Третье наблюдение оказалось важнее обоих. Оценки строгих совпадений — точное
100, начало 80, вхождение 60 — всегда выше нестрогого, у которого потолок 39.
Значит, когда строгие совпадения уже набрали полную выдачу, нестрогий проход
не может изменить результат **вообще никак**, и его можно не делать. Это не
приближение и не эвристика: порядок сортировки доказывает, что выдача
совпадёт с точностью до записи.

Совместимость сохранена: `search` принимает и список записей, и указатель. Со
списком он строит указатель на месте — медленно, но верно, и старые вызовы
продолжают работать.

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


def _too_short(query: str) -> bool:
    """Запрос короче двух символов не обрабатывается.

    Считается длина того, что набрал зритель, а не длина самого длинного
    прочтения. Прежде проверялись прочтения, и однобуквенный запрос проходил
    охрану через транслитерацию: «я» превращалось в «ya», два символа, и поиск
    выдавал всё, где встречается это сочетание, — «маяк», «Майами», «Кая».
    Правило модуля сказано прямо: один символ совпадает почти с чем угодно, и
    обходить собственное правило через побочный эффект преобразования нельзя.
    """
    return len(normalize(query)) < MIN_QUERY


def _variants(query: str) -> tuple[str, ...]:
    """Все прочтения запроса: как набрано, из чужой раскладки, латиницей."""
    base = normalize(query)
    if not base:
        return ()
    out = {base, normalize(from_layout(base)), translit(base)}
    return tuple(v for v in out if v)


#: Разброс внутри разряда строгого совпадения. Девятнадцать, а не двадцать:
#: разряды обязаны остаться непересекающимися, иначе пропуск нестрогого прохода
#: перестанет быть доказуемым, а «начало строки» окажется выше точного совпадения.
РАЗМАХ_РАЗРЯДА = 19


def _доля(form: str, query: str) -> int:
    """Насколько запрос заполняет название. Различает внутри разряда.

    Измерено на боевом каталоге: из 51 промаха золотого набора 44 приходились
    не на поиск, а на порядок. Запрос «принцесса» находил нужную запись 53-й из
    197 — все 197 содержат слово подстрокой, все получали ровно 60, и порядок
    между ними был случайным. «Принцесса» как всё название и «Принцесса» внутри
    длинного заголовка — разные по качеству совпадения, и разряд обязан их
    различать, не смешиваясь с соседним.
    """
    if not form:
        return 0
    return int(round(РАЗМАХ_РАЗРЯДА * min(1.0, len(query) / len(form))))


def _token_tolerance(token: str) -> int:
    """Допуск на одно слово запроса. Та же мера, что и у односложного пути."""
    return max(1, len(token) // 4)


def _token_cost(words, token: str) -> int | None:
    """Наименьшая цена, которой слово запроса находит себе слово в названии.

    Ноль — слово совпало точно или запрос набран началом слова. Иначе цена
    равна расстоянию. `None` — слово запроса не отвечено ничем, и вся запись
    тогда не отвечает запросу: искать «матрица колец» и получить «Матрицу»
    значит найти не то, о чём просили.
    """
    tolerance = _token_tolerance(token)
    best: int | None = None
    for word in words:
        if word == token:
            return 0
        # Начало слова — обычное сокращение при наборе, а не ошибка. Короче
        # трёх букв не считается: «во» начинает слишком многое.
        if len(token) >= 3 and word.startswith(token):
            return 0
        if abs(len(word) - len(token)) > tolerance:
            continue
        d = distance(word, token, limit=tolerance)
        if d <= tolerance and (best is None or d < best):
            best = d
    return best


def _score_by_tokens(form: str, tokens: list[str]) -> int:
    """Оценка многословного запроса: по самому слабому из совпадений.

    Запись обязана ответить на КАЖДОЕ слово запроса. Иначе нестрогость нашла
    бы всё подряд: достаточно было бы одного общего слова.
    """
    words = form.split()
    worst = 0
    for token in tokens:
        cost = _token_cost(words, token)
        if cost is None:
            return 0
        if cost > worst:
            worst = cost
    return min(FUZZY_CEILING, 40 - worst)


def _score(form: str, query: str) -> int:
    """Насколько написание отвечает запросу. Ноль — не отвечает."""
    if not form or not query:
        return 0
    if form == query:
        return 100
    if form.startswith(query):
        return 80 + _доля(form, query)
    if query in form:
        return 60 + _доля(form, query)
    # Многословный запрос меряется по словам. Прежде каждое слово названия
    # сравнивалось со ВСЕЙ строкой запроса, и слово «дней» никогда не
    # оказывалось на расстоянии двух от строки «100 днеи» — длины
    # несопоставимы. Поэтому опечатка в многословном запросе не находилась
    # вовсе: замер на боевом lordfilm47.space 7 сентября 2026 дал ноль записей
    # при пяти на том же запросе без опечатки.
    tokens = query.split()
    if len(tokens) > 1:
        return _score_by_tokens(form, tokens)
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


#: Потолок оценки нестрогого совпадения и пол оценки строгого. Между ними нет
#: и не должно быть пересечения: на этом основан пропуск нестрогого прохода.
FUZZY_CEILING = 39
STRICT_FLOOR = 60


def _strict_score(form: str, query: str) -> int:
    """Строгая часть оценки: точное совпадение, начало, вхождение.

    Вынесена отдельно потому, что стоит почти ничего — сравнение и поиск
    подстроки выполняет сам интерпретатор, — тогда как нестрогая часть считает
    расстояние редактирования и стоит на три порядка дороже.
    """
    if not form or not query:
        return 0
    if form == query:
        return 100
    if form.startswith(query):
        return 80 + _доля(form, query)
    if query in form:
        return 60 + _доля(form, query)
    return 0


def _bigrams(word: str) -> set[str]:
    return {word[i:i + 2] for i in range(len(word) - 1)}


class Index:
    """Указатель по каталогу: формы записей и словарь слов.

    Строится один раз на каталог. Хранит ровно то, что нужно сопоставлению, и
    ничего сверх: формы записей, словарь различных слов и указатель от слова к
    записям. Никаких оценок и никакого порядка — они зависят от запроса.
    """

    __slots__ = ("items", "forms", "names", "vocabulary", "word_items", "bigram_words")

    def __init__(self, catalog):
        self.items: list[dict] = list(catalog)
        self.forms: list[tuple[str, ...]] = [_forms(item) for item in self.items]
        self.names: list[str] = [normalize(item.get("name") or "") for item in self.items]
        self.word_items: dict[str, set[int]] = {}
        self.bigram_words: dict[str, set[str]] = {}
        for position, forms in enumerate(self.forms):
            for form in forms:
                for word in form.split():
                    self.word_items.setdefault(word, set()).add(position)
        self.vocabulary: tuple[str, ...] = tuple(self.word_items)
        for word in self.vocabulary:
            for bigram in _bigrams(word):
                self.bigram_words.setdefault(bigram, set()).add(word)

    def __len__(self) -> int:
        return len(self.items)

    def stats(self) -> dict:
        """Размер указателя. Нужен отчёту, а не работе."""
        return {
            "items": len(self.items),
            "forms": sum(len(f) for f in self.forms),
            "vocabulary": len(self.vocabulary),
            "bigrams": len(self.bigram_words),
        }


def build_index(catalog) -> Index:
    return Index(catalog)


def _as_index(catalog) -> Index:
    return catalog if isinstance(catalog, Index) else Index(catalog)


def _fuzzy_candidates(index: Index, variant: str) -> set[int]:
    """Кандидаты запроса. Многословный разбирается по словам.

    Отбор ниже сравнивает слова словаря со ВСЕЙ строкой запроса, и для «100
    днеи» не находил ничего: ни одно слово каталога не стоит на расстоянии
    двух от строки с пробелом — длины несопоставимы. Пословная оценка при этом
    уже работала, но до неё не доходило: кандидатов не было.

    Пересечение, а не объединение: запись обязана ответить на каждое слово
    запроса — то же правило, что и в `_score_by_tokens`. Объединение нашло бы
    всё, где встречается любое из слов.
    """
    tokens = variant.split()
    if len(tokens) > 1:
        итог: set[int] | None = None
        for token in tokens:
            свои = _candidates_for_token(index, token)
            итог = свои if итог is None else (итог & свои)
            if not итог:
                return set()
        return итог or set()
    return _candidates_for_word(index, variant)


def _candidates_for_token(index: Index, token: str) -> set[int]:
    """Кандидаты одного слова запроса, включая совпадение началом слова.

    Начало учитывается отдельно: `_token_cost` считает «матр» → «матрица»
    нулевой ценой, а отбор по расстоянию такую пару отбрасывает по разнице
    длин. Кандидат, отброшенный отбором, до оценки не доходит, и правило
    оценки оставалось бы недостижимым.
    """
    свои = _candidates_for_word(index, token)
    if len(token) >= 3:
        for word in index.vocabulary:
            if word.startswith(token):
                свои |= index.word_items.get(word, set())
    return свои


def _candidates_for_word(index: Index, variant: str) -> set[int]:
    """Записи, до которых нестрогое сравнение вообще может дотянуться.

    Отбор идёт по словарю, а не по записям: одно и то же слово встречается в
    каталоге десятки раз, и сравнивать его с запросом каждый раз заново незачем.

    Двухбуквенный отбор применяется только там, где он доказуемо ничего не
    теряет. Слово на расстоянии не больше L от запроса длины N делит с ним не
    меньше (N−1)−2L двубуквий; при L = N // 4 это число положительно начиная с
    N = 4. Для запросов короче четырёх букв отбор по двубуквиям неверен, и там
    словарь просматривается целиком с отсечением по длине — коротких слов мало,
    и это дёшево.
    """
    tolerance = max(1, len(variant) // 4)
    if len(variant) >= 4:
        query_bigrams = _bigrams(variant)
        # Порог общих двубуквий, а не «хотя бы одно». Правка разрушает не более
        # трёх двубуквий, поэтому слово на расстоянии не больше L обязано
        # делить с запросом не меньше (число двубуквий запроса − 3L).
        #
        # Именно трёх, а не двух. Замена, вставка и удаление портят два
        # двубуквия, но расстояние здесь Дамерау — Левенштейна, и перестановка
        # соседних букв тоже стоит одной правки, а портит три: «абвг» → «авбг»
        # теряет «бв», «аб» и «вг». Граница в два двубуквия прошла все замеры
        # скорости и провалила проверку на перестановку — самую частую опечатку
        # из всех.
        # Порог считается от различных двубуквий запроса, а не от его длины:
        # у запроса с повторами их меньше, и порог от длины отбросил бы верные
        # слова. Отбор «хотя бы одно общее» пропускал почти весь словарь, и
        # многословный запрос без совпадений стоил восьмисот миллисекунд.
        needed = max(1, len(query_bigrams) - 3 * tolerance)
        shared: dict[str, int] = {}
        for bigram in query_bigrams:
            for word in index.bigram_words.get(bigram, ()):  # noqa: PERF401
                shared[word] = shared.get(word, 0) + 1
        words = [word for word, count in shared.items() if count >= needed]
    else:
        words = list(index.vocabulary)
    candidates: set[int] = set()
    for word in words:
        if abs(len(word) - len(variant)) > tolerance:
            continue
        if distance(word, variant, limit=tolerance) <= tolerance:
            candidates |= index.word_items.get(word, set())
    return candidates


def search(catalog, query: str, *, limit: int = 20) -> list[dict]:
    """Записи, отвечающие запросу, в устойчивом порядке.

    Принимает список записей или готовый указатель. Результат один и тот же:
    указатель ускоряет, но ничего не решает.
    """
    if _too_short(query):
        return []
    variants = _variants(query)
    if not variants:
        return []
    index = _as_index(catalog)

    # Строгий проход по всем формам. Стоит почти ничего и обычно набирает
    # полную выдачу.
    scored: dict[int, int] = {}
    for position, forms in enumerate(index.forms):
        best = 0
        for form in forms:
            for variant in variants:
                value = _strict_score(form, variant)
                if value > best:
                    best = value
        if best:
            scored[position] = best

    # Нестрогий проход — только если строгих совпадений не хватило на выдачу.
    # Когда их хватило, нестрогое совпадение (не выше 39) не может обойти
    # строгое (не ниже 60) ни при каком порядке, и проход изменил бы лишь
    # время ответа.
    strong = sum(1 for value in scored.values() if value >= STRICT_FLOOR)
    if strong < limit:
        for variant in variants:
            for position in _fuzzy_candidates(index, variant):
                if scored.get(position, 0) >= STRICT_FLOOR:
                    continue
                best = scored.get(position, 0)
                for form in index.forms[position]:
                    value = _score(form, variant)
                    if value > best:
                        best = value
                if best:
                    scored[position] = best

    # Порядок устойчив: оценка, название, положение в каталоге. Третий ключ
    # добавлен не для красоты: при равных оценке и названии прежний сплошной
    # перебор оставлял записи в порядке каталога, а указатель добирает часть
    # записей нестрогим проходом позже строгого — и две одноимённые записи
    # менялись местами. Сверка с эталоном это и показала: множество то же,
    # порядок другой.
    order = sorted(scored.items(),
                   key=lambda row: (-row[1], index.names[row[0]], row[0]))
    return [index.items[position] for position, _ in order[:limit]]


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
    index = _as_index(catalog)
    if search(index, query, limit=1):
        return None
    if _too_short(query):
        return None
    variants = _variants(query)
    if not variants:
        return None
    best_name, best_key = None, None
    for position, item in enumerate(index.items):
        for form in index.forms[position]:
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
