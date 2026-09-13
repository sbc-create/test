"""Извлечение проверяемых утверждений и сверка их с фактами.

Проверяется готовый текст, а не замысел. Причина простая: замысел мог быть
безупречным, а в предложение попало лишнее слово — и утверждение появилось.
Поэтому разбор идёт по тому, что увидит человек.

Четыре исхода, и третий важнее остальных:

* `SUPPORTED` — утверждение сошлось с фактом и несёт его `fact_id`;
* `CONTRADICTED` — факт есть и говорит другое;
* `UNSUPPORTED` — утверждение проверяемое, а факта под ним нет;
* `NON_FACTUAL_STYLE` — оборот вообще ничего не утверждает.

`UNSUPPORTED` — это не «мы не нашли источник». Это «текст утверждает то,
чего мы не знаем». Существенное такое утверждение блокирует черновик
наравне с опровергнутым: недоказанное и ложное для читателя неразличимы.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .draft import Claim, ClaimVerdict
from .factpack import SEOFactPack, VideoAvailability
from . import lexicon as LEX

ГОД = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
КОЛИЧЕСТВО_СЕЗОНОВ = re.compile(
    r"\b(\d{1,3})\s+сезон(?:а|ов)?\b", re.I)
КОЛИЧЕСТВО_СЕРИЙ = re.compile(
    r"\b(\d{1,4})\s+сери(?:я|и|й)\b", re.I)
НОМЕР_СЕРИИ = re.compile(
    r"(?:\bсери(?:я|и|ю|е)\s*[№#]?\s*(\d{1,4})\b"
    r"|\b(\d{1,4})[-‐-―]?\s*(?:я|ая|й)\s+сери(?:я|и|ю|е))", re.I)
НОМЕР_СЕЗОНА = re.compile(
    r"(?:\bсезон\s*[№#]?\s*(\d{1,3})\b|\b(\d{1,3})[-‐-―]?\s*(?:й|ый|ой)\s+сезон)",
    re.I)
КАВЫЧКИ = re.compile(r"[«\"]([^»\"]{2,80})[»\"]")
ИМЯ = re.compile(r"\b([А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,}){0,2})")
ПРЕДЛОЖЕНИЕ = re.compile(r"[^.!?]+[.!?]?")

#: Слова с большой буквы, которые именами не являются.
НЕ_ИМЕНА = {LEX.стем(с) for с in (
    "Сериал", "Фильм", "Аниме", "Сезон", "Серия", "История", "Действие",
    "Главный", "Герой", "Мир", "Жанр", "Режиссёр", "Автор", "Премьера",
    "Однако", "Именно", "Каждый", "Первый", "Второй", "Третий", "Этот",
    "Когда", "После", "Здесь", "Там", "Все", "Весь", "Что", "Как", "Для",
    "Сюжет", "Персонаж", "Конфликт", "Формат", "Экранизация", "Оригинал",
    "Студия", "Сценарист", "Продюсер", "Актёр", "Роль", "Эпизод", "Финал",
    "Событие", "Место", "Время", "Год", "Страна", "Возраст", "Рейтинг",
)} | {LEX.стем(ч) for с in LEX.СТРАНЫ for ч in с.split()} \
    | {LEX.стем(ч) for с in LEX.СТРАНА_РОДИТЕЛЬНЫЙ.values() for ч in с.split()} \
    | {LEX.стем(ч) for с in LEX.ЖАНРЫ for ч in с.split()} \
    | {LEX.стем(ч) for формы in LEX.РОДОВОЕ.values() for с in формы[:3]
       for ч in с.split()}


#: Слова, рядом с которыми оборот действительно говорит о выходе работы.
КОНТЕКСТ_ВЫХОДА = re.compile(
    r"статус|сериал|сезон|фильм|аниме|мультсериал|проект|премьер|эпизод|"
    r"сери[яий]|производств|выход")


def _в_контексте_выхода(текст: str, м: re.Match, окно: int = 45) -> bool:
    начало = max(0, м.start() - окно)
    конец = min(len(текст), м.end() + окно)
    return bool(КОНТЕКСТ_ВЫХОДА.search(текст[начало:конец]))


def _существенное(тип: str) -> bool:
    """Существенное утверждение — то, ошибка в котором меняет понимание.

    Год, название, тип, страна, жанр, имена, числа сезонов и серий, статус и
    доступность просмотра существенны. Стилистический оборот — нет.
    """
    return тип not in ("style",)


@dataclass
class ClaimReport:
    claims: list[Claim]

    def by_verdict(self, verdict: ClaimVerdict) -> list[Claim]:
        return [c for c in self.claims if c.verdict is verdict]

    @property
    def contradicted(self) -> list[Claim]:
        return self.by_verdict(ClaimVerdict.CONTRADICTED)

    @property
    def unsupported_material(self) -> list[Claim]:
        return [c for c in self.by_verdict(ClaimVerdict.UNSUPPORTED) if c.material]

    @property
    def player_false(self) -> list[Claim]:
        """Ложные утверждения о доступности просмотра.

        Сюда входит не только прямое противоречие факту, но и обещание
        просмотра при неизмеренной доступности: для читателя «мы не
        проверяли» и «доступно» — не одно и то же, а обещание он прочтёт
        одинаково.
        """
        return [c for c in self.claims if c.claim_type == "video_availability"
                and c.verdict in (ClaimVerdict.CONTRADICTED,
                                  ClaimVerdict.UNSUPPORTED)]

    def to_dict(self) -> dict[str, Any]:
        return {"total": len(self.claims),
                "supported": len(self.by_verdict(ClaimVerdict.SUPPORTED)),
                "contradicted": len(self.contradicted),
                "unsupported": len(self.by_verdict(ClaimVerdict.UNSUPPORTED)),
                "unsupported_material": len(self.unsupported_material),
                "non_factual_style": len(
                    self.by_verdict(ClaimVerdict.NON_FACTUAL_STYLE)),
                "claims": [c.to_dict() for c in self.claims]}


class ClaimExtractor:
    """Разбор текста на утверждения и сверка каждого с пакетом фактов."""

    def __init__(self, pack: SEOFactPack):
        self.pack = pack
        self._счётчик = 0

    # --- вспомогательное ---------------------------------------------------

    def _claim(self, *, text: str, field: str, claim_type: str,
               verdict: ClaimVerdict, fact_id: str | None = None,
               detail: str = "") -> Claim:
        self._счётчик += 1
        return Claim(claim_id=f"c{self._счётчик:04d}", text=text, field=field,
                     claim_type=claim_type, verdict=verdict, fact_id=fact_id,
                     detail=detail, material=_существенное(claim_type))

    def _сверить(self, *, путь: str, ожидаемые: Iterable[Any], найденное: Any,
                 текст: str, поле: str, тип: str, как_строку=str) -> Claim:
        факт = self.pack.fact_id_for(путь)
        значения = {LEX.нормализовать(как_строку(з)) for з in ожидаемые
                    if з is not None}
        найденное_н = LEX.нормализовать(как_строку(найденное))
        if not значения:
            return self._claim(text=текст, field=поле, claim_type=тип,
                               verdict=ClaimVerdict.UNSUPPORTED,
                               detail=f"факта {путь} в пакете нет")
        if найденное_н in значения:
            return self._claim(text=текст, field=поле, claim_type=тип,
                               verdict=ClaimVerdict.SUPPORTED, fact_id=факт)
        return self._claim(text=текст, field=поле, claim_type=тип,
                           verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                           detail=f"в тексте {найденное!r}, в фактах "
                                  f"{sorted(значения)}")

    # --- разбор ------------------------------------------------------------

    def extract(self, тексты: dict[str, str]) -> ClaimReport:
        утверждения: list[Claim] = []
        for поле, текст in sorted(тексты.items()):
            if not текст:
                continue
            утверждения.extend(self._из_текста(поле, текст))
        return ClaimReport(утверждения)

    def _из_текста(self, поле: str, текст: str) -> list[Claim]:
        найдено: list[Claim] = []
        найдено.extend(self._годы(поле, текст))
        найдено.extend(self._тип_произведения(поле, текст))
        найдено.extend(self._названия(поле, текст))
        найдено.extend(self._страны(поле, текст))
        найдено.extend(self._жанры(поле, текст))
        найдено.extend(self._имена(поле, текст))
        найдено.extend(self._числа(поле, текст))
        найдено.extend(self._статус(поле, текст))
        найдено.extend(self._доступность(поле, текст))
        найдено.extend(self._стиль(поле, текст, найдено))
        return найдено

    def _годы(self, поле: str, текст: str) -> list[Claim]:
        год = self.pack.value("/year")
        конец = self.pack.value("/year_end")
        допустимые: set[int] = set()
        if год is not None:
            допустимые.add(int(год))
            if конец is not None:
                допустимые.update(range(int(год), int(конец) + 1))
        итог: list[Claim] = []
        for м in ГОД.finditer(текст):
            найденный = int(м.group(1))
            факт = self.pack.fact_id_for("/year")
            цитата = (self._цитата_из_факта(текст, м)
                      if найденный not in допустимые else None)
            if цитата is not None and цитата != факт:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="year",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=цитата,
                    detail="год назван внутри факта с собственным источником, "
                           "а не как год выпуска"))
                continue
            if not допустимые:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="year",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="года в фактах нет, а текст его называет"))
            elif найденный in допустимые:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="year",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
            else:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="year",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {найденный}, в фактах "
                           f"{sorted(допустимые)}"))
        return итог

    def _тип_произведения(self, поле: str, текст: str) -> list[Claim]:
        """Тип произведения — по основам слов, с вытеснением короткой формы.

        Сравнение идёт по основам, потому что «документальным фильмом» — то
        же словосочетание, что «документальный фильм», а посимвольно не
        совпадает ни одна его половина. Зато «фильмом» совпало бы с «фильм»,
        и документальный фильм объявлялся бы ещё и художественным — причём
        «опровергнутым».
        """
        факт_тип = self.pack.value("/work_type")
        факт = self.pack.fact_id_for("/work_type")
        формы = {форма: канон for канон, сп in LEX.ТИПЫ.items() for форма in сп}
        найдено = LEX.найти_фразы(текст, формы.keys())
        замечено = {формы[ф] for ф in найдено}
        итог: list[Claim] = []
        if not замечено:
            return итог
        позиции = {формы[ф]: найдено[ф] for ф in найдено}
        for канон in sorted(замечено):
            if факт_тип is not None and канон != факт_тип:
                i, j = позиции[канон]
                цитата = self._цитата_по_позиции(текст, i, j)
                if цитата is not None and цитата != факт:
                    итог.append(self._claim(
                        text=канон, field=поле, claim_type="work_type",
                        verdict=ClaimVerdict.SUPPORTED, fact_id=цитата,
                        detail="слово взято из значения факта, а не заявляет "
                               "тип произведения"))
                    continue
            if факт_тип is None:
                итог.append(self._claim(
                    text=канон, field=поле, claim_type="work_type",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="тип произведения в фактах не указан"))
            elif канон == факт_тип:
                итог.append(self._claim(
                    text=канон, field=поле, claim_type="work_type",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
            else:
                итог.append(self._claim(
                    text=канон, field=поле, claim_type="work_type",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {канон}, в фактах {факт_тип}"))
        return итог

    def _допустимые_названия(self) -> set[str]:
        имена: set[str] = set()
        for путь in ("/canonical_title_ru", "/original_title", "/episode_title"):
            з = self.pack.value(путь)
            if з:
                имена.add(LEX.нормализовать(str(з)))
        альт = self.pack.value("/alternative_titles") or []
        for а in альт:
            имена.add(LEX.нормализовать(str(а)))
        return {и for и in имена if и}

    def _названия(self, поле: str, текст: str) -> list[Claim]:
        """Кавычки не всегда означают название произведения.

        «Студия „Северный контур"» и «повесть „Сухое русло"» тоже стоят в
        кавычках. Поэтому содержимое кавычек сперва ищется среди значений
        фактов: нашлось — утверждение подтверждено тем фактом, в котором оно
        стоит. Не нашлось нигде — вот тогда это чужое название.
        """
        допустимые = self._допустимые_названия()
        итог: list[Claim] = []
        for м in КАВЫЧКИ.finditer(текст):
            найденное = LEX.нормализовать(м.group(1))
            факт = self.pack.fact_id_for("/canonical_title_ru")
            из_факта = self._факт_со_строкой(м.group(1))
            if найденное not in допустимые and из_факта is not None:
                итог.append(self._claim(
                    text=м.group(1), field=поле, claim_type="quoted_name",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=из_факта,
                    detail="имя собственное названо внутри факта с источником"))
                continue
            if найденное in допустимые:
                итог.append(self._claim(
                    text=м.group(1), field=поле, claim_type="title",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
            elif допустимые:
                итог.append(self._claim(
                    text=м.group(1), field=поле, claim_type="title",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {м.group(1)!r}, разрешённые названия "
                           f"{sorted(допустимые)}"))
            else:
                итог.append(self._claim(
                    text=м.group(1), field=поле, claim_type="title",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="названия в фактах нет"))
        return итог

    def _страны(self, поле: str, текст: str) -> list[Claim]:
        """Страна — по основам, чтобы «производства Японии» тоже считалось.

        Литеральное сравнение пропускало бы родительный падеж целиком: в
        готовом тексте страна почти всегда стоит именно в нём, и проверка
        молчала бы ровно там, где должна работать.
        """
        факт_страны = list(self.pack.value("/countries") or [])
        разрешённые = {LEX.нормализовать(с) for с in факт_страны}
        факт = self.pack.fact_id_for("/countries")
        найдено = LEX.найти_фразы(текст, LEX.СТРАНЫ)
        имена = self._известные_имена()
        слова_текста = LEX.токены(текст)
        итог: list[Claim] = []
        for страна in sorted(найдено, key=lambda с: найдено[с][0]):
            i, j = найдено[страна]
            куски = слова_текста[i:j]
            основы = [LEX.стем(к) for к in куски]
            # Короткая основа совпадает со слишком многим: «Дан» из «Павел
            # Дан» даёт ту же основу, что «Дания». Поэтому короткое
            # совпадение принимается, только если слово написано ровно как
            # название страны, и отвергается, если это подтверждённое имя.
            if any(len(о) <= 3 for о in основы) and \
                    " ".join(куски) != LEX.нормализовать(страна):
                continue
            if any(о in имена for о in основы):
                continue
            if LEX.нормализовать(страна) not in разрешённые:
                цитата = self._цитата_по_позиции(текст, i, j)
                if цитата is not None and цитата != факт:
                    итог.append(self._claim(
                        text=страна, field=поле, claim_type="country",
                        verdict=ClaimVerdict.SUPPORTED, fact_id=цитата,
                        detail="страна названа внутри факта с собственным "
                               "источником"))
                    continue
            if LEX.нормализовать(страна) in разрешённые:
                итог.append(self._claim(
                    text=страна, field=поле, claim_type="country",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
            elif разрешённые:
                итог.append(self._claim(
                    text=страна, field=поле, claim_type="country",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {страна}, в фактах {sorted(факт_страны)}"))
            else:
                итог.append(self._claim(
                    text=страна, field=поле, claim_type="country",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="стран в фактах нет"))
        return итог

    def _жанры(self, поле: str, текст: str) -> list[Claim]:
        """Жанр — по основам, но «военный городок» жанром не является.

        Жанровые слова — обычные русские прилагательные, и встречаются они не
        только в перечне жанров. Поэтому слово, взятое из значения факта,
        подтверждается этим фактом, а не опровергает перечень жанров.
        """
        факт_жанры = list(self.pack.value("/genres") or [])
        # Жанр бывает из двух слов: «научная фантастика». Сравнивать по одной
        # основе нельзя — «научн» не совпадёт ни с чем, и жанр, стоящий в
        # фактах, объявился бы опровергнутым самим собой.
        разрешённые = {tuple(LEX.основы_токенов(ж)) for ж in факт_жанры}
        факт = self.pack.fact_id_for("/genres")
        найдено = LEX.найти_фразы(текст, LEX.ЖАНРЫ)
        итог: list[Claim] = []
        for жанр in sorted(найдено, key=lambda ж: найдено[ж][0]):
            основа = tuple(LEX.основы_токенов(жанр))
            i, j = найдено[жанр]
            if основа in разрешённые:
                итог.append(self._claim(
                    text=жанр, field=поле, claim_type="genre",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
                continue
            цитата = self._цитата_по_позиции(текст, i, j)
            if цитата is not None and цитата != факт:
                итог.append(self._claim(
                    text=жанр, field=поле, claim_type="genre",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=цитата,
                    detail="слово взято из значения факта, а не заявляет жанр"))
            elif разрешённые:
                итог.append(self._claim(
                    text=жанр, field=поле, claim_type="genre",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {жанр}, в фактах {sorted(факт_жанры)}"))
            else:
                итог.append(self._claim(
                    text=жанр, field=поле, claim_type="genre",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="жанров в фактах нет"))
        return итог

    def _известные_имена(self) -> set[str]:
        """Основы имён из подтверждённых персонажей и создателей."""
        известные: set[str] = set()
        for путь in ("/characters", "/creators"):
            for запись in self.pack.value(путь) or []:
                for ключ in ("name", "actor"):
                    имя = (запись.get(ключ) if isinstance(запись, dict)
                           else (запись if ключ == "name" else None))
                    for слово in re.findall(r"[А-ЯЁа-яёA-Za-z-]{2,}",
                                            str(имя or "")):
                        известные.add(LEX.стем(слово))
        return известные

    def _основы_всех_фактов(self) -> set[str]:
        """Основы всех слов, встречающихся в значениях фактов.

        Имя, названное внутри другого факта — например, в описании завязки, —
        источник имеет: у этого факта есть `source_id`, снимок и время. Поэтому
        такое имя подтверждается, но не тем же `fact_id`, что персонажи, а
        тем фактом, в котором оно действительно стоит. Имени, которого нет ни
        в одном факте, взяться неоткуда — и оно остаётся `UNSUPPORTED`.
        """
        основы: set[str] = set()
        for ф in self.pack.facts:
            if self.pack.value(ф.field_path) is None:
                continue
            основы.update(LEX.стем(с) for с in
                          re.findall(r"[А-ЯЁа-яёA-Za-z]{2,}", str(ф.value)))
        return основы

    def _фразы_фактов(self) -> list[tuple[str, list[str]]]:
        """Последовательности основ по каждому факту. Считается один раз."""
        if getattr(self, "_кэш_фраз", None) is None:
            self._кэш_фраз = [
                (ф.fact_id, LEX.основы_токенов(str(ф.value)))
                for ф in self.pack.facts
                if self.pack.value(ф.field_path) is not None]
        return self._кэш_фраз

    def _цитата_из_факта(self, текст: str, м: re.Match) -> str | None:
        """Факт, из которого текст дословно взял это место.

        Слово в готовом тексте не всегда утверждение о том, чем кажется.
        «В военном городке» — не заявление жанра «военный», «фильма 1979
        года» внутри описания особенности — не заявление года выпуска. Но и
        отмахнуться нельзя: слово там действительно стоит.

        Проверка простая и проверяемая: берётся пара соседних слов вокруг
        найденного места, и если такая же пара стоит в значении какого-то
        факта, утверждение подтверждается ИМЕННО ЭТИМ фактом — со ссылкой на
        его `fact_id`, а не на поле, о котором мы сперва подумали. Если пары
        нет ни в одном факте, место в тексте появилось само по себе, и
        разбор продолжается как обычно.
        """
        начало = max(0, м.start() - 40)
        окрестность = LEX.основы_токенов(текст[начало:м.end() + 40])
        цель = LEX.основы_токенов(м.group(0))
        if not цель or not окрестность:
            return None
        # Биграммы, в которые входит само найденное место.
        биграммы: list[list[str]] = []
        for i, о in enumerate(окрестность):
            if о not in цель:
                continue
            if i > 0:
                биграммы.append(окрестность[i - 1:i + 1])
            if i + 1 < len(окрестность):
                биграммы.append(окрестность[i:i + 2])
        for fact_id, основы in self._фразы_фактов():
            for б in биграммы:
                for j in range(len(основы) - 1):
                    if основы[j:j + 2] == б:
                        return fact_id
        return None

    def _цитата_по_позиции(self, текст: str, i: int, j: int) -> str | None:
        """То же, что `_цитата_из_факта`, но по позициям токенов."""
        основы = LEX.основы_токенов(текст)
        биграммы: list[list[str]] = []
        if i > 0:
            биграммы.append(основы[i - 1:i + 1])
        if j < len(основы):
            биграммы.append(основы[j - 1:j + 1])
        биграммы = [б for б in биграммы if len(б) == 2]
        for fact_id, поле_основы in self._фразы_фактов():
            for б in биграммы:
                for k in range(len(поле_основы) - 1):
                    if поле_основы[k:k + 2] == б:
                        return fact_id
        return None

    def _факт_со_строкой(self, строка: str) -> str | None:
        """Факт, в значении которого эта строка встречается дословно."""
        игла = LEX.нормализовать(строка)
        if len(игла) < 2:
            return None
        for ф in self.pack.facts:
            if self.pack.value(ф.field_path) is None:
                continue
            if игла in LEX.нормализовать(str(ф.value)):
                return ф.fact_id
        return None

    def _факт_с_именем(self, основы: Sequence[str]) -> str | None:
        for ф in self.pack.facts:
            if self.pack.value(ф.field_path) is None:
                continue
            слова = {LEX.стем(с) for с in
                     re.findall(r"[А-ЯЁа-яёA-Za-z]{2,}", str(ф.value))}
            if all(о in слова for о in основы):
                return ф.fact_id
        return None

    def _имена(self, поле: str, текст: str) -> list[Claim]:
        известные = self._известные_имена()
        факт = self.pack.fact_id_for("/characters") or \
            self.pack.fact_id_for("/creators")
        разрешённые_названия = set()
        for н in self._допустимые_названия():
            разрешённые_названия.update(LEX.стем(с) for с in
                                        re.findall(r"[а-яёa-z0-9-]+", н))
        итог: list[Claim] = []
        видели: set[str] = set()
        # Первое слово предложения отбрасывается: заглавная там — пунктуация,
        # а не имя.
        for предложение in ПРЕДЛОЖЕНИЕ.findall(текст):
            хвост = предложение.strip()
            if not хвост:
                continue
            первое = re.match(r"\s*[«\"]?([А-ЯЁA-Z][\w-]*)", хвост)
            начало = первое.end() if первое else 0
            for м in ИМЯ.finditer(хвост[начало:]):
                кандидат = м.group(1).strip()
                основы = [LEX.стем(с) for с in кандидат.split()]
                if any(о in НЕ_ИМЕНА or о in разрешённые_названия for о in основы):
                    continue
                ключ = LEX.нормализовать(кандидат)
                if ключ in видели:
                    continue
                видели.add(ключ)
                if all(о in известные for о in основы):
                    итог.append(self._claim(
                        text=кандидат, field=поле, claim_type="person",
                        verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
                    continue
                из_факта = self._факт_с_именем(основы)
                if из_факта is not None:
                    итог.append(self._claim(
                        text=кандидат, field=поле, claim_type="person",
                        verdict=ClaimVerdict.SUPPORTED, fact_id=из_факта,
                        detail="имя названо внутри факта с собственным "
                               "источником"))
                else:
                    итог.append(self._claim(
                        text=кандидат, field=поле, claim_type="person",
                        verdict=ClaimVerdict.UNSUPPORTED,
                        detail="имени нет ни в подтверждённых персонажах и "
                               "создателях, ни в значении какого-либо факта"))
        return итог

    def _числа(self, поле: str, текст: str) -> list[Claim]:
        итог: list[Claim] = []
        сезонов = self.pack.value("/season_count")
        факт_с = self.pack.fact_id_for("/season_count")
        номер_сезона = self.pack.value("/season_number")
        for м in КОЛИЧЕСТВО_СЕЗОНОВ.finditer(текст):
            найдено = int(м.group(1))
            # «1 сезон» по-русски читается и как «один сезон», и как «сезон
            # первый». Если пакет описывает сезон с этим номером, это
            # порядковый номер: считать его количеством значило бы придумать
            # утверждение, которого в тексте нет.
            if номер_сезона is not None and найдено == int(номер_сезона):
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="season_number",
                    verdict=ClaimVerdict.SUPPORTED,
                    fact_id=self.pack.fact_id_for("/season_number"),
                    detail="порядковый номер сезона, не количество"))
                continue
            if сезонов is None:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="season_count",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="числа сезонов в фактах нет"))
            elif найдено == int(сезонов):
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="season_count",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт_с))
            else:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="season_count",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт_с,
                    detail=f"в тексте {найдено}, в фактах {сезонов}"))

        заявлено = self.pack.value("/declared_episode_count")
        фактически = self.pack.value("/actual_episode_count")
        факт_э = self.pack.fact_id_for("/actual_episode_count") or \
            self.pack.fact_id_for("/declared_episode_count")
        допустимые = {int(з) for з in (заявлено, фактически) if з is not None}
        for м in КОЛИЧЕСТВО_СЕРИЙ.finditer(текст):
            найдено = int(м.group(1))
            if not допустимые:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="episode_count",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="числа серий в фактах нет"))
            elif найдено in допустимые:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="episode_count",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт_э))
            else:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type="episode_count",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт_э,
                    detail=f"в тексте {найдено}, в фактах {sorted(допустимые)}"))

        итог.extend(self._номер(поле, текст, НОМЕР_СЕРИИ, "episode_number",
                                ("/episode_display_number",
                                 "/episode_in_season_number")))
        итог.extend(self._номер(поле, текст, НОМЕР_СЕЗОНА, "season_number",
                                ("/season_number",)))
        return итог

    def _номер(self, поле: str, текст: str, шаблон: re.Pattern, тип: str,
               пути: Sequence[str]) -> list[Claim]:
        значения = {int(з) for з in (self.pack.value(п) for п in пути)
                    if з is not None}
        факт = next((self.pack.fact_id_for(п) for п in пути
                     if self.pack.fact_id_for(п)), None)
        итог: list[Claim] = []
        for м in шаблон.finditer(текст):
            найдено = int(next(г for г in м.groups() if г))
            if not значения:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type=тип,
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail=f"номера ({', '.join(пути)}) в фактах нет"))
            elif найдено in значения:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type=тип,
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
            else:
                итог.append(self._claim(
                    text=м.group(0), field=поле, claim_type=тип,
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {найдено}, в фактах {sorted(значения)}"))
        return итог

    def _статус(self, поле: str, текст: str) -> list[Claim]:
        """Статус выхода — только там, где речь о выходе произведения.

        «Библиотекарь закрытого фонда» содержит «закрыт», но ничего не
        сообщает о судьбе сериала. Поэтому форма засчитывается лишь рядом со
        словом, обозначающим произведение или сам статус: иначе проверка
        опровергала бы утверждение, которого в тексте не было.
        """
        н = LEX.нормализовать(текст)
        факт_статус = self.pack.value("/release_status")
        факт = self.pack.fact_id_for("/release_status")
        итог: list[Claim] = []
        for канон, формы in LEX.СТАТУСЫ.items():
            если_есть = [м for ф in формы
                         for м in re.finditer(rf"\b{re.escape(ф)}", н)]
            if not если_есть:
                continue
            if not any(_в_контексте_выхода(н, м) for м in если_есть):
                continue
            if факт_статус is None:
                итог.append(self._claim(
                    text=канон, field=поле, claim_type="release_status",
                    verdict=ClaimVerdict.UNSUPPORTED,
                    detail="статуса выхода в фактах нет"))
            elif канон == факт_статус:
                итог.append(self._claim(
                    text=канон, field=поле, claim_type="release_status",
                    verdict=ClaimVerdict.SUPPORTED, fact_id=факт))
            else:
                итог.append(self._claim(
                    text=канон, field=поле, claim_type="release_status",
                    verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
                    detail=f"в тексте {канон}, в фактах {факт_статус}"))
        return итог

    def _доступность(self, поле: str, текст: str) -> list[Claim]:
        н = LEX.нормализовать(текст)
        найдено = [ш for ш in LEX.ДОСТУПНОСТЬ if re.search(ш, н)]
        if not найдено:
            return []
        значение = self.pack.value("/video_availability")
        факт = self.pack.fact_id_for("/video_availability")
        if значение == VideoAvailability.AVAILABLE.value:
            return [self._claim(text=найдено[0], field=поле,
                                claim_type="video_availability",
                                verdict=ClaimVerdict.SUPPORTED, fact_id=факт)]
        if значение is None:
            return [self._claim(
                text=найдено[0], field=поле, claim_type="video_availability",
                verdict=ClaimVerdict.UNSUPPORTED,
                detail="доступность просмотра не измерена, а текст её "
                       "утверждает")]
        return [self._claim(
            text=найдено[0], field=поле, claim_type="video_availability",
            verdict=ClaimVerdict.CONTRADICTED, fact_id=факт,
            detail=f"текст обещает просмотр, а доступность — {значение}")]

    def _стиль(self, поле: str, текст: str, уже: Sequence[Claim]) -> list[Claim]:
        """Предложения, ничего не утверждающие.

        Помечаются отдельно, чтобы «нет проверяемых утверждений» не
        выглядело как «всё проверено». Текст из одних оборотов пройдёт
        фактическую проверку и обязан провалить полезность.
        """
        покрытые = {c.text for c in уже if c.field == поле}
        итог: list[Claim] = []
        for предложение in ПРЕДЛОЖЕНИЕ.findall(текст):
            п = предложение.strip()
            if len(п) < 12:
                continue
            if any(т and т in п for т in покрытые):
                continue
            if ГОД.search(п) or КОЛИЧЕСТВО_СЕРИЙ.search(п):
                continue
            итог.append(self._claim(
                text=п[:120], field=поле, claim_type="style",
                verdict=ClaimVerdict.NON_FACTUAL_STYLE))
        return итог


def extract_and_verify(pack: SEOFactPack, тексты: dict[str, str]) -> ClaimReport:
    return ClaimExtractor(pack).extract(тексты)
