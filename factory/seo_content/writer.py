"""Контракт Writer и три его исполнения.

Тексты в будущем пишет Qwen. Чтобы это можно было включить, не переделывая
контур, здесь зафиксирован сам контракт: что Writer получает, что обязан
вернуть и чего ему не позволено.

Три исполнения:

* `DeterministicWriter` — `FAKE_SHADOW`. Складывает предложения из фактов
  по правилам. Ничего не выдумывает не потому, что «старается», а потому,
  что нечем: предложение строится из значения факта, и без факта
  предложения не появляется. Повторяемость полная — один пакет даёт один
  текст и один отпечаток.
* `RecordedWriter` — воспроизводит записанные ответы по отпечатку запроса.
  Нужен, чтобы проверять разбор чужого текста, не обращаясь к модели.
* `LiveQwenWriter` — живой вызов. Выключен и остаётся выключенным, пока нет
  отдельного разрешения владельца: скачивание модели и платный API — не
  наше решение. Попытка вызова отклоняется ДО обращения, а не после.

Ни одно исполнение не получает прав `approve`, `apply` и `publish`: их нет
в контракте вовсе, и «забыть проверить» тут нечего.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from . import injection, lexicon as LEX
from .draft import reject_model_overreach
from .factpack import SEOFactPack, VideoAvailability, canonical_json
from .language import СЧЁТНЫЕ, форма_числительного

ПРОМПТЫ = Path(__file__).parent / "prompts"

QWEN_MODES = ("FAKE_SHADOW", "RECORDED", "LIVE")

#: Права, которых у автора текста нет ни в одном режиме.
ЗАПРЕЩЁННЫЕ_ПРАВА = ("approve", "apply", "publish", "durable_write")


class WriterRefused(RuntimeError):
    """Writer отказался работать. Причина — машинный код."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class WriteRequest:
    """То, что Writer видит. Больше он не видит ничего."""

    entity_type: str
    prompt_name: str
    prompt_version: str
    prompt_body: str
    data_block: str          # ограждённый блок с фактами
    fence_label: str
    locale: str
    #: Разрешённый отображаемый номер, если сущность — серия. Приходит уже
    #: разрешённым: выводить его Writer не вправе.
    display_number: int | None = None
    season_number: int | None = None
    generation_parameters: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json({
            "entity_type": self.entity_type, "prompt": self.prompt_name,
            "prompt_version": self.prompt_version, "data": self.data_block,
            "locale": self.locale, "display_number": self.display_number,
            "season_number": self.season_number,
            "generation_parameters": dict(self.generation_parameters),
        }).encode()).hexdigest()


class Writer(Protocol):
    model_version: str
    mode: str
    live_calls: int

    def write(self, request: WriteRequest) -> dict[str, Any]: ...


# --- подготовка запроса ----------------------------------------------------

def _промпт(имя: str) -> tuple[str, str]:
    файл = ПРОМПТЫ / f"{имя}.v1.md"
    тело = файл.read_text("utf-8")
    м = re.search(r"^#\s*(seo\.prompt/\S+)", тело, re.M)
    return тело, (м.group(1) if м else f"seo.prompt/{имя}/1.0.0")


def build_request(pack: SEOFactPack, *, display_number: int | None = None,
                  season_number: int | None = None,
                  generation_parameters: Mapping[str, Any] | None = None,
                  prompt_name: str | None = None) -> WriteRequest:
    """Собрать запрос: факты — внутрь ограждённого блока, и только туда."""
    имя = prompt_name or pack.entity_type
    тело, версия = _промпт(имя)
    данные = canonical_json({
        "entity_type": pack.entity_type, "locale": pack.locale,
        "facts": {ф.field_path: ф.value for ф in pack.facts
                  if pack.value(ф.field_path) is not None},
        "fact_ids": {ф.field_path: ф.fact_id for ф in pack.facts},
        "display_number": display_number, "season_number": season_number,
    })
    блок, метка = injection.fence(данные)
    return WriteRequest(
        entity_type=pack.entity_type, prompt_name=имя, prompt_version=версия,
        prompt_body=тело, data_block=блок, fence_label=метка,
        locale=pack.locale, display_number=display_number,
        season_number=season_number,
        generation_parameters=dict(generation_parameters or
                                   {"temperature": 0.0, "top_p": 1.0}))


# --- русская сборка --------------------------------------------------------

ТИП_СЛОВО = {
    "movie": "фильм", "series": "сериал", "anime": "аниме",
    "anime_movie": "полнометражное аниме", "cartoon": "мультсериал",
    "ova": "OVA", "documentary": "документальный фильм",
}

#: Родительный падеж для «производства …». Список закрыт словарём стран.
РОДИТЕЛЬНЫЙ = {
    "Россия": "России", "СССР": "СССР", "США": "США", "Япония": "Японии",
    "Южная Корея": "Южной Кореи", "Корея": "Кореи", "Китай": "Китая",
    "Франция": "Франции", "Германия": "Германии",
    "Великобритания": "Великобритании", "Испания": "Испании",
    "Италия": "Италии", "Канада": "Канады", "Индия": "Индии",
    "Турция": "Турции", "Польша": "Польши", "Швеция": "Швеции",
    "Дания": "Дании", "Норвегия": "Норвегии", "Бразилия": "Бразилии",
    "Мексика": "Мексики", "Австралия": "Австралии",
    "Новая Зеландия": "Новой Зеландии", "Украина": "Украины",
    "Казахстан": "Казахстана", "Чехия": "Чехии", "Нидерланды": "Нидерландов",
    "Бельгия": "Бельгии", "Аргентина": "Аргентины", "Израиль": "Израиля",
    "Тайвань": "Тайваня", "Гонконг": "Гонконга", "Таиланд": "Таиланда",
    "Финляндия": "Финляндии", "Ирландия": "Ирландии",
    "Швейцария": "Швейцарии", "Австрия": "Австрии",
}

#: Родовое слово в родительном падеже: «сезонов у сериала», не «у сериал».
РОДОВОЕ_РОДИТЕЛЬНЫЙ = {
    "фильм": "фильма", "сериал": "сериала", "аниме": "аниме",
    "полнометражное аниме": "полнометражного аниме",
    "мультсериал": "мультсериала", "OVA": "OVA",
    "документальный фильм": "документального фильма",
    "произведение": "произведения",
}


def _с_заглавной(текст: str) -> str:
    т = (текст or "").strip()
    return т[:1].upper() + т[1:] if т else т


СТАТУС_СЛОВО = {
    "released": "вышел полностью", "ongoing": "выходит",
    "completed": "завершён", "announced": "анонсирован",
    "cancelled": "отменён", "delayed": "перенесён",
}


#: Варианты оборотов для одних и тех же фактов.
#:
#: Нужны не ради «уникальности»: перестановка слов ценности не создаёт, и
#: считать её содержанием было бы самообманом. Нужны потому, что одинаковая
#: обвязка у тысяч страниц — сама по себе дефект: двенадцать одинаковых слов
#: подряд у двух разных произведений означают, что читатель видит одну и ту
#: же болванку, чем бы её ни заполнили. Смысл по-прежнему приносят факты;
#: здесь меняется только способ их назвать.
#: Все обороты подставляют значение в ИМЕНИТЕЛЬНОМ падеже либо целым
#: придаточным. Это ограничение, а не стиль: «Сюжет следует за {}» требует
#: творительного, и подстановка даёт «следует за смотритель водонапорной
#: башни». Склонять произвольную именную группу без морфологии мы не умеем,
#: а значит и предлагать такие рамки не вправе — каждая из них производила бы
#: ошибку согласования, которой наша же проверка не видит.
ОБОРОТЫ = {
    "premise": ("В центре истории — {}", "Главное действующее лицо — {}",
                "Центральная фигура — {}", "Основной герой — {}"),
    "setting": ("действие происходит {}", "события разворачиваются {}",
                "всё это разворачивается {}"),
    "conflict": ("Исходное положение: {}", "Завязка: {}",
                 "Отправная точка — {}", "Начинается с того, что {}"),
    "genres": ("Заявленные жанры — {}", "Жанровая отметка каталога — {}",
               "По каталогу это {}"),
    "structure": ("В каталоге — {}", "Каталог содержит {}", "Всего {}",
                  "На витрине — {}"),
    "roles": ("В ролях: {}", "Роли исполняют: {}", "Исполнители ролей: {}",
              "Актёрский состав: {}"),
    "feature": ("Отличительная черта — {}", "Что выделяет работу: {}",
                "Особенность — {}", "Отдельно стоит отметить: {}"),
    "source": ("Первоисточник — {}", "В основе — {}",
               "Литературная основа — {}"),
}


def оборот(слот: str, ключ: str, смещение: int = 0) -> str:
    """Вариант оборота, выбранный по личности сущности.

    Выбор детерминированный: один и тот же идентификатор всегда даёт один и
    тот же оборот, иначе повторная генерация меняла бы текст без изменения
    фактов и создавала лишнюю ревизию.
    """
    варианты = ОБОРОТЫ[слот]
    н = int(hashlib.sha256(f"{слот}|{ключ}".encode()).hexdigest()[:8], 16)
    return варианты[(н + смещение) % len(варианты)]


#: Возможные порядки необязательных предложений. Смысл от перестановки не
#: меняется — меняется стык между предложениями, а именно на стыках и
#: возникают совпадающие цепочки у разных произведений.
ПОРЯДКИ = (
    ("roles", "source", "feature", "structure"),
    ("feature", "roles", "structure", "source"),
    ("structure", "feature", "source", "roles"),
    ("source", "structure", "roles", "feature"),
    ("roles", "feature", "structure", "source"),
    ("feature", "structure", "roles", "source"),
)


def порядок(ключ: str) -> tuple[str, ...]:
    н = int(hashlib.sha256(f"порядок|{ключ}".encode()).hexdigest()[:8], 16)
    return ПОРЯДКИ[н % len(ПОРЯДКИ)]


def счётная(n: int, ключ: str) -> str:
    формы = СЧЁТНЫЕ[ключ]
    return f"{n} {формы[форма_числительного(n)]}"


def перечислить(элементы: Sequence[str], союз: str = "и") -> str:
    э = [str(x) for x in элементы if x]
    if not э:
        return ""
    if len(э) == 1:
        return э[0]
    return ", ".join(э[:-1]) + f" {союз} " + э[-1]


def _страны_род(страны: Sequence[str]) -> str:
    return перечислить([РОДИТЕЛЬНЫЙ.get(с, с) for с in страны])


def _обрезать(текст: str, предел: int) -> str:
    if len(текст) <= предел:
        return текст
    кусок = текст[:предел]
    пробел = кусок.rfind(" ")
    return (кусок[:пробел] if пробел > предел * 0.6 else кусок).rstrip(" ,;—-")


class DeterministicWriter:
    """Сборка текста из фактов. Ни одно предложение не появляется без факта."""

    mode = "FAKE_SHADOW"

    def __init__(self, model_version: str = "deterministic-composer/1.0.0"):
        self.model_version = model_version
        self.live_calls = 0
        self.model_downloads = 0
        self.calls = 0
        self.rights: tuple[str, ...] = ()   # approve/apply/publish отсутствуют

    # --- контракт ---------------------------------------------------------

    def write(self, request: WriteRequest) -> dict[str, Any]:
        self.calls += 1
        pack = _pack_из_запроса(request)
        сборщик = {"title": self._тайтл, "season": self._сезон,
                   "episode": self._серия}[request.entity_type]
        ответ = сборщик(pack, request)
        reject_model_overreach(ответ)   # автор не назначает себе служебных полей
        return ответ

    # --- тайтл ------------------------------------------------------------

    def _тайтл(self, pack: "_Факты", request: WriteRequest) -> dict[str, Any]:
        название = pack.v("/canonical_title_ru")
        if not название:
            return {"outcome": "NEEDS_FACTS",
                    "missing": ["/canonical_title_ru"]}

        предложения: list[str] = []
        использованные: set[str] = set()

        тип = ТИП_СЛОВО.get(pack.v("/work_type") or "", None)
        год = pack.v("/year")
        год_конец = pack.v("/year_end")
        страны = pack.v("/countries") or []
        оригинал = pack.v("/original_title")

        # 1. О каком именно произведении речь.
        части = [f"«{название}»"]
        if оригинал and оригинал != название:
            части.append(f"({оригинал})")
        опора = " ".join(части)
        хвост = []
        if тип:
            хвост.append(тип)
            использованные.add("/work_type")
        if год is not None:
            хвост.append(f"{год}–{год_конец} годов" if год_конец
                         else f"{год} года")
            использованные.add("/year")
        if страны:
            хвост.append(f"производства {_страны_род(страны)}")
            использованные.add("/countries")
        # Определение склеивается пробелом, а не перечислением: «сериал 2023
        # года производства США» — одна именная группа, и запятая с союзом
        # разрывали бы её на мнимый список.
        предложения.append(f"{опора} — {' '.join(хвост)}." if хвост
                           else f"{опора}.")
        использованные.add("/canonical_title_ru")

        # 2. Кто или что в центре.
        ключ_оборота = pack.v("/canonical_title_ru") or ""
        центр = pack.v("/premise_subject")
        место = pack.v("/setting")
        if центр:
            фраза = оборот("premise", ключ_оборота).format(центр)
            if место:
                фраза += "; " + оборот("setting", ключ_оборота).format(место)
                использованные.add("/setting")
            предложения.append(фраза + ".")
            использованные.add("/premise_subject")

        # 3. Исходный конфликт.
        конфликт = pack.v("/premise_conflict")
        if конфликт:
            предложения.append(
                оборот("conflict", ключ_оборота).format(конфликт) + ".")
            использованные.add("/premise_conflict")

        # 4. Жанровое обещание — как заявленный жанр, а не как оценка.
        жанры = pack.v("/genres") or []
        if жанры:
            предложения.append(
                оборот("genres", ключ_оборота).format(
                    перечислить(list(жанры))) + ".")
            использованные.add("/genres")

        # Порядок необязательных предложений меняется вместе с личностью.
        #
        # Причина не в «уникальности»: перестановка ничего не добавляет.
        # Причина в том, что совпадающая цепочка слов чаще всего проходит
        # ЧЕРЕЗ границу двух предложений — «…снят одним оператором на плёнку.
        # На витрине — 3 сезона и 12 серий» — и постоянный порядок делает
        # такие стыки одинаковыми у всего корпуса. Разный порядок рвёт стык,
        # не притворяясь, что содержание стало другим.
        # 4a. Кто играет и на чём основано — тоже факты, а не украшения.
        персонажи = pack.v("/characters") or []
        роли = [f"{c['actor']} — {c['name']}" for c in персонажи
                if isinstance(c, dict) and c.get("actor") and c.get("name")]
        имена = [c.get("name") for c in персонажи
                 if isinstance(c, dict) and c.get("name")]
        необязательные: dict[str, str] = {}
        if роли:
            необязательные["roles"] = (
                оборот("roles", ключ_оборота).format(перечислить(роли[:4])) + ".")
            использованные.add("/characters")
        elif имена:
            необязательные["roles"] = (
                f"Центральные персонажи — {перечислить(имена[:4])}.")
            использованные.add("/characters")

        основа_текста = pack.v("/source_material")
        if основа_текста:
            необязательные["source"] = (
                оборот("source", ключ_оборота).format(основа_текста) + ".")
            использованные.add("/source_material")

        # 5. Подтверждённая отличительная особенность.
        особенность = pack.v("/distinctive_feature")
        if особенность:
            необязательные["feature"] = (
                оборот("feature", ключ_оборота).format(особенность) + ".")
            использованные.add("/distinctive_feature")

        # 6. Устройство: сезоны, серии, статус.
        структура = self._структура(pack, использованные, ключ_оборота)
        if структура:
            необязательные["structure"] = структура
        предложения.extend(
            необязательные[имя] for имя in порядок(ключ_оборота)
            if имя in необязательные)

        # Доступность просмотра в тело не попадает намеренно. Она меняется
        # чаще текста, одинакова у сотен страниц и закрывала бы собой конец
        # каждого описания: девяносто восемь процентов корпуса заканчивались
        # бы одной фразой. Её место — FAQ, разметка и технические
        # рекомендации, где она и проверяется.
        использованные.add("/video_availability")

        тело = " ".join(п for п in предложения if п)
        достаточно = bool(центр or конфликт) and bool(жанры or тип)
        if not достаточно:
            return {"outcome": "NEEDS_FACTS",
                    "missing": [п for п in ("/premise_subject",
                                            "/premise_conflict", "/genres")
                                if not pack.v(п)],
                    "meta_title": self._meta_title(pack),
                    "h1_recommendation": название}

        return {
            "meta_title": self._meta_title(pack),
            "meta_description": self._meta_description(pack, центр, конфликт),
            "h1_recommendation": название,
            "body_description": тело,
            "editorial_notes": self._заметки(pack, использованные),
            "faq_items": self._faq(pack),
            "used_fields": sorted(использованные),
        }

    def _структура(self, pack: "_Факты", использованные: set[str],
                   ключ: str = "") -> str:
        части: list[str] = []
        сезонов = pack.v("/season_count")
        if сезонов is not None:
            части.append(счётная(int(сезонов), "сезон"))
            использованные.add("/season_count")
        фактически = pack.v("/actual_episode_count")
        заявлено = pack.v("/declared_episode_count")
        if фактически is not None:
            # Расхождение заявленного и фактического — уточнение к числу
            # серий, а не третий член перечисления: «1 сезон, 100 серий и из
            # заявленных 210» разваливается на полуфразу.
            кусок = счётная(int(фактически), "сери")
            использованные.add("/actual_episode_count")
            if заявлено is not None and int(заявлено) != int(фактически):
                кусок += f" из заявленных {заявлено}"
                использованные.add("/declared_episode_count")
            части.append(кусок)
        elif заявлено is not None:
            части.append(f"заявлено {счётная(int(заявлено), 'сери')}")
            использованные.add("/declared_episode_count")
        статус = СТАТУС_СЛОВО.get(pack.v("/release_status") or "")
        if статус:
            использованные.add("/release_status")
        if not части:
            return f"Статус выхода: {статус}." if статус else ""
        итог = оборот("structure", ключ or "").format(перечислить(части))
        return итог + (f"; {статус}." if статус else ".")

    def _доступность(self, pack: "_Факты", использованные: set[str]) -> str:
        значение = pack.v("/video_availability")
        if значение is None:
            return ""
        использованные.add("/video_availability")
        if значение == VideoAvailability.AVAILABLE.value:
            return "Источник для просмотра на витрине доступен."
        if значение == VideoAvailability.UNAVAILABLE.value:
            return "Источник для просмотра сейчас недоступен."
        return "Доступность просмотра не проверялась."

    def _meta_title(self, pack: "_Факты") -> str | None:
        """Заголовок в ориентире 45–65 символов — из фактов, не из добора.

        Варианты перебираются от более содержательного к более скудному, и
        берётся первый, попавший в ориентир. Если не попал ни один, берётся
        самый содержательный: длина — ориентир, а дописывать ради неё нечего.
        """
        название = pack.v("/canonical_title_ru")
        if not название:
            return None
        год = pack.v("/year")
        тип = ТИП_СЛОВО.get(pack.v("/work_type") or "", "")
        жанры = list(pack.v("/genres") or [])
        страны = list(pack.v("/countries") or [])
        сезонов = pack.v("/season_count")
        основа = f"{название} ({год})" if год else название

        варианты = [
            (f"{основа} — {тип}, {перечислить(жанры[:2])}, "
             f"{перечислить(страны[:1])}" if тип and жанры and страны else None),
            (f"{основа} — {тип}, {перечислить(жанры[:2])}"
             if тип and жанры else None),
            (f"{основа} — {тип}, {счётная(int(сезонов), 'сезон')}"
             if тип and сезонов is not None else None),
            (f"{основа} — {тип}, {перечислить(жанры[:1])}"
             if тип and жанры else None),
            f"{основа} — {тип}: описание и факты" if тип else None,
            f"{основа} — {тип}" if тип else None,
            основа,
            название,
        ]
        живые = [в for в in варианты if в]
        подходящие = [в for в in живые if 45 <= len(в) <= 65]
        if подходящие:
            return подходящие[0]
        короткие = [в for в in живые if len(в) < 45]
        длинные = [в for в in живые if len(в) > 65]
        if длинные:
            обрезанный = _обрезать(min(длинные, key=len), 65)
            if len(обрезанный) >= 45:
                return обрезанный
        return max(короткие, key=len) if короткие else живые[0]

    def _meta_description(self, pack: "_Факты", центр: Any,
                          конфликт: Any) -> str | None:
        """Описание в ориентире 130–170 символов.

        Куски добавляются, пока помещаются, и каждый кусок — факт. Как только
        фактов не осталось, описание кончается, даже если ориентир не
        достигнут: добор пустой фразой запрещён прямо заданием.
        """
        название = pack.v("/canonical_title_ru")
        if not название:
            return None
        тип = ТИП_СЛОВО.get(pack.v("/work_type") or "", "произведение")
        год = pack.v("/year")
        куски: list[str] = [f"{название} — {тип}" + (f" {год} года" if год else "")]
        if центр:
            куски.append(f"в центре — {центр}")
        if конфликт:
            куски.append(str(конфликт))
        жанры = list(pack.v("/genres") or [])
        if жанры:
            куски.append("жанры: " + перечислить(жанры[:3]))
        сезонов = pack.v("/season_count")
        серий = pack.v("/actual_episode_count")
        if сезонов is not None and серий is not None:
            куски.append(f"{счётная(int(сезонов), 'сезон')}, "
                         f"{счётная(int(серий), 'сери')}")
        статус = СТАТУС_СЛОВО.get(pack.v("/release_status") or "")
        if статус:
            куски.append(f"статус: {статус}")

        собранное = куски[:1]
        for кусок in куски[1:]:
            проба = ". ".join(_с_заглавной(к.rstrip(".")) for к in
                              собранное + [кусок]) + "."
            if len(проба) > 170:
                continue
            собранное.append(кусок)
        текст = ". ".join(_с_заглавной(к.rstrip(".")) for к in собранное) + "."
        текст = re.sub(r"\s+", " ", текст).strip()
        return _обрезать(текст, 170) if len(текст) > 170 else текст

    # --- сезон ------------------------------------------------------------

    def _сезон(self, pack: "_Факты", request: WriteRequest) -> dict[str, Any]:
        название = pack.v("/canonical_title_ru")
        номер = pack.v("/season_number")
        if not название or номер is None:
            return {"outcome": "NEEDS_FACTS",
                    "missing": [п for п in ("/canonical_title_ru",
                                            "/season_number") if not pack.v(п)]}
        номер = int(номер)
        использованные = {"/canonical_title_ru", "/season_number"}
        h1 = f"{название}. Сезон {номер}"

        свои_факты = [p for p in ("/season_arc", "/season_position",
                                  "/season_synopsis") if pack.v(p)]
        предложения = [f"Сезон {номер} «{название}»"]
        место = pack.v("/season_position")
        if место:
            предложения[0] += f" — {место}"
            использованные.add("/season_position")
        предложения[0] += "."

        дуга = pack.v("/season_arc")
        if дуга:
            предложения.append(f"Что меняется: {дуга}.")
            использованные.add("/season_arc")
        синопсис = pack.v("/season_synopsis")
        if синопсис and not дуга:
            предложения.append(_с_заглавной(str(синопсис).rstrip(".")) + ".")
            использованные.add("/season_synopsis")

        серий = pack.v("/actual_episode_count")
        заявлено = pack.v("/declared_episode_count")
        if серий is not None:
            фраза = f"В сезоне {счётная(int(серий), 'сери')}"
            использованные.add("/actual_episode_count")
            if заявлено is not None and int(заявлено) != int(серий):
                фраза += f" при заявленных {заявлено}"
                использованные.add("/declared_episode_count")
            предложения.append(фраза + ".")
        статус = СТАТУС_СЛОВО.get(pack.v("/release_status") or "")
        if статус:
            предложения.append(f"Статус сезона: {статус}.")
            использованные.add("/release_status")
        использованные.add("/video_availability")

        тело = " ".join(п for п in предложения if п)
        описание = (f"{название}, сезон {номер}"
                    + (f". {_с_заглавной(str(дуга))}" if дуга else "") + ".")
        return {
            # «1 сезон» читается и как количество, и как номер. Поэтому
            # порядок обратный: «сезон 1» однозначен.
            "meta_title": _обрезать(f"{название}, сезон {номер} — описание "
                                    f"и список серий", 65),
            "meta_description": _обрезать(re.sub(r"\s+", " ", описание), 170),
            "h1_recommendation": h1,
            "body_description": тело,
            "editorial_notes": self._заметки(pack, использованные),
            "faq_items": (),
            "used_fields": sorted(использованные),
            #: Скудный сезон не превращается в развёрнутый текст: честный
            #: короткий текст лучше раздутого.
            "sparse": not свои_факты,
        }

    # --- серия ------------------------------------------------------------

    def _серия(self, pack: "_Факты", request: WriteRequest) -> dict[str, Any]:
        название = pack.v("/canonical_title_ru")
        номер = request.display_number
        if номер is None:
            # Номер не разрешён снаружи — выводить его здесь запрещено.
            return {"outcome": "EPISODE_IDENTITY_CONFLICT",
                    "detail": "отображаемый номер серии не разрешён вызывающим"}
        if not название:
            return {"outcome": "NEEDS_FACTS", "missing": ["/canonical_title_ru"]}

        использованные = {"/canonical_title_ru"}
        сезон = request.season_number if request.season_number is not None \
            else pack.v("/season_number")
        if сезон is not None:
            использованные.add("/season_number")
        заголовок_серии = pack.v("/episode_title")
        h1 = f"{название}" + (f". Сезон {сезон}" if сезон is not None else "") \
            + f". Серия {номер}"
        if заголовок_серии:
            h1 += f" — {заголовок_серии}"
            использованные.add("/episode_title")

        предложения = [
            f"Серия {номер}"
            + (f" {сезон}-го сезона" if сезон is not None else "")
            + f" «{название}»"
            + (f" — «{заголовок_серии}»" if заголовок_серии else "") + "."]

        суть = pack.v("/episode_focus") or pack.v("/episode_synopsis")
        # Ни сути, ни собственного заголовка — описывать нечего. Короткий
        # текст «серия N сериала X» задание допускает, но пятьдесят таких
        # текстов подряд — это пятьдесят одинаковых страниц, и честнее
        # сказать, что фактов нет, чем размножить номер. Заголовок и H1 при
        # этом остаются: они выводятся из личности, а не из содержания.
        if not суть and not заголовок_серии:
            return {"outcome": "NEEDS_FACTS",
                    "missing": ["/episode_focus", "/episode_synopsis",
                                "/episode_title"],
                    "meta_title": _обрезать(
                        f"{название}"
                        + (f", сезон {сезон}" if сезон is not None else "")
                        + f", серия {номер}", 65),
                    "h1_recommendation": h1}
        if суть:
            предложения.append(_с_заглавной(str(суть).rstrip(".")) + ".")
            использованные.add("/episode_focus" if pack.v("/episode_focus")
                               else "/episode_synopsis")
        использованные.add("/video_availability")

        тело = " ".join(п for п in предложения if п)
        мета = (f"{название}"
                + (f", сезон {сезон}" if сезон is not None else "")
                + f", серия {номер}"
                + (f": {заголовок_серии}" if заголовок_серии else ""))
        описание = мета + (f". {_с_заглавной(str(суть))}" if суть else "") + "."
        return {
            "meta_title": _обрезать(мета, 65),
            "meta_description": _обрезать(re.sub(r"\s+", " ", описание), 170),
            "h1_recommendation": h1,
            "body_description": тело,
            "editorial_notes": (),
            "faq_items": (),
            "used_fields": sorted(использованные),
            "sparse": суть is None,
        }

    # --- заметки и FAQ ----------------------------------------------------

    def _заметки(self, pack: "_Факты", использованные: set[str]) -> tuple[dict, ...]:
        """Не более трёх мыслей, каждая — на своих фактах.

        Факт, уже отработавший в основном описании, второй раз мысли не даёт:
        повтор — не новая польза.
        """
        заметки: list[dict] = []
        # Заметка называет произведение. Без этого «возрастное ограничение —
        # 16+» одинаково для сотен страниц, и проверка повторяемости
        # справедливо отвергает её как одну и ту же мысль, размноженную по
        # корпусу.
        имя = pack.v("/canonical_title_ru") or ""
        кавычки = f"«{имя}»" if имя else "произведение"
        имен, род_п, твор, род = LEX.РОДОВОЕ.get(
            pack.v("/work_type") or "", LEX.РОДОВОЕ_ПО_УМОЛЧАНИЮ)
        помечен = {"m": "помечен", "f": "помечена", "n": "помечено"}[род]

        студия = pack.v("/studio")
        создатели = pack.v("/creators") or []
        режиссёры = [c.get("name") for c in создатели
                     if isinstance(c, dict) and c.get("role") == "director"
                     and c.get("name")]
        if (студия or режиссёры) and "/studio" not in использованные:
            части = []
            if студия:
                части.append(f"производством занималась {студия}")
            if режиссёры:
                части.append(f"режиссура — {перечислить(режиссёры)}")
            заметки.append({
                "angle": "production",
                "text": f"Над {твор} {кавычки} работали: "
                        + перечислить(части) + ".",
                "fact_refs": tuple(x for x in (pack.fid("/studio"),
                                               pack.fid("/creators")) if x)})

        источник = pack.v("/source_material")
        if источник:
            заметки.append({
                "angle": "source_material",
                "text": f"У {род_п} {кавычки} есть литературная основа — "
                        f"{источник}.",
                "fact_refs": (pack.fid("/source_material"),)})

        возраст = pack.v("/age_rating")
        if возраст and "/age_rating" not in использованные:
            заметки.append({
                "angle": "audience",
                "text": f"{_с_заглавной(имен)} {кавычки} {помечен} в "
                        f"каталоге как {возраст}: это формальная отметка "
                        f"каталога, а не оценка содержания.",
                "fact_refs": (pack.fid("/age_rating"),)})

        предыдущий = pack.v("/previous_season_ref")
        if предыдущий:
            заметки.append({
                "angle": "continuity",
                "text": f"Связь {род_п} {кавычки} с предыдущим сезоном: "
                        f"{предыдущий}.",
                "fact_refs": (pack.fid("/previous_season_ref"),)})

        заявлено = pack.v("/declared_episode_count")
        фактически = pack.v("/actual_episode_count")
        if заявлено is not None and фактически is not None and \
                int(заявлено) != int(фактически):
            заметки.append({
                "angle": "catalog_state",
                "text": f"У {род_п} {кавычки} каталог заявляет "
                        f"{счётная(int(заявлено), 'сери')}, а доступно "
                        f"{счётная(int(фактически), 'сери')}: часть ещё не "
                        f"выложена.",
                "fact_refs": tuple(x for x in (
                    pack.fid("/declared_episode_count"),
                    pack.fid("/actual_episode_count")) if x)})

        живые = [з for з in заметки if all(з["fact_refs"])and з["fact_refs"]]
        return tuple(живые[:3])

    def _faq(self, pack: "_Факты") -> tuple[dict, ...]:
        """Вопрос появляется только там, где есть подтверждённый ответ."""
        вопросы: list[dict] = []
        название = pack.v("/canonical_title_ru")
        # Название в кавычках не склоняется — склоняется родовое слово перед
        # ним. «Сколько сезонов у Бункера» было бы ошибкой согласования.
        род, род_род, _твор, _г = LEX.РОДОВОЕ.get(
            pack.v("/work_type") or "", LEX.РОДОВОЕ_ПО_УМОЛЧАНИЮ)
        сезонов = pack.v("/season_count")
        if сезонов is not None:
            вопросы.append({
                "question": f"Сколько сезонов у {род_род} «{название}»?",
                "answer": f"{счётная(int(сезонов), 'сезон')}.",
                "fact_refs": (pack.fid("/season_count"),)})
        статус = СТАТУС_СЛОВО.get(pack.v("/release_status") or "")
        if статус:
            вопросы.append({
                "question": f"{_с_заглавной(род)} «{название}» уже вышел "
                            f"полностью?",
                "answer": f"Статус выхода: {статус}.",
                "fact_refs": (pack.fid("/release_status"),)})
        доступность = pack.v("/video_availability")
        if доступность is not None:
            ответ = {"AVAILABLE": "Да, источник на витрине доступен.",
                     "UNAVAILABLE": "Нет, источник сейчас недоступен.",
                     "UNKNOWN": "Доступность не проверялась."}[доступность]
            вопросы.append({
                "question": f"Можно ли посмотреть {род} «{название}» на "
                            f"витрине?",
                "answer": ответ,
                "fact_refs": (pack.fid("/video_availability"),)})
        return tuple(в for в in вопросы if all(в["fact_refs"]))


class _Факты:
    """Доступ к фактам запроса. Ровно то, что попало в ограждённый блок."""

    def __init__(self, значения: Mapping[str, Any],
                 идентификаторы: Mapping[str, str]):
        self._з = dict(значения)
        self._и = dict(идентификаторы)

    def v(self, путь: str) -> Any:
        return self._з.get(путь)

    def fid(self, путь: str) -> str | None:
        return self._и.get(путь) if self._з.get(путь) is not None else None


def _pack_из_запроса(request: WriteRequest) -> _Факты:
    тело = request.data_block.split("\n", 1)[1].rsplit("\n", 1)[0]
    данные = json.loads(тело)
    return _Факты(данные.get("facts") or {}, данные.get("fact_ids") or {})


class RecordedWriter:
    """Воспроизведение записанных ответов. Живых обращений не делает."""

    mode = "RECORDED"

    def __init__(self, записи: Mapping[str, Mapping[str, Any]], *,
                 model_version: str = "qwen2.5-14b-instruct/recorded"):
        self.записи = dict(записи)
        self.model_version = model_version
        self.live_calls = 0
        self.model_downloads = 0
        self.calls = 0
        self.misses = 0

    def write(self, request: WriteRequest) -> dict[str, Any]:
        self.calls += 1
        ответ = self.записи.get(request.digest)
        if ответ is None:
            self.misses += 1
            raise WriterRefused(
                "RECORDING_MISSING",
                f"записанного ответа для запроса {request.digest[:12]} нет; "
                f"подставлять похожий нельзя — это была бы другая проверка")
        reject_model_overreach(ответ)
        return dict(ответ)


class LiveQwenWriter:
    """Живой Qwen. Выключен до отдельного разрешения владельца.

    Отказ происходит ДО обращения и до любых расходов. Проверяются три вещи
    по отдельности, потому что разрешено может быть не всё сразу: сам живой
    режим, платные поставщики и валюта бюджета.
    """

    mode = "LIVE"

    def __init__(self, *, endpoint: str | None = None,
                 model_version: str = "qwen2.5-14b-instruct",
                 budget=None):
        self.endpoint = endpoint or os.environ.get("QWEN_ENDPOINT", "")
        self.model_version = model_version
        self.budget = budget
        self.live_calls = 0
        self.model_downloads = 0
        self.calls = 0

    def write(self, request: WriteRequest) -> dict[str, Any]:
        self.calls += 1
        if os.environ.get("QWEN_LIVE_AUTHORIZED") != "1":
            raise WriterRefused(
                "LIVE_QWEN_NOT_AUTHORIZED",
                "живой вызов Qwen не разрешён владельцем; качество живой "
                "модели остаётся NOT_EVALUATED, а не объявляется по "
                "результатам детерминированной подмены")
        if self.budget is not None:
            self.budget.assert_call_allowed(provider="qwen",
                                            estimated_cost=None)
        if not self.endpoint:
            raise WriterRefused("QWEN_ENDPOINT_MISSING",
                                "адрес локального Qwen не задан")
        raise WriterRefused(
            "LIVE_QWEN_TRANSPORT_ABSENT",
            "транспорт до живого Qwen в этом контуре не реализован намеренно: "
            "включение требует отдельного разрешения и отдельной проверки")


def writer_rights(writer: Writer) -> tuple[str, ...]:
    """Права автора текста. Всегда пустые по отношению к записи и публикации."""
    return tuple(п for п in ЗАПРЕЩЁННЫЕ_ПРАВА if getattr(writer, п, False))
