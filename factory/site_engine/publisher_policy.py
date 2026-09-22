"""Семейная принадлежность Publisher ID витрины.

Задача модуля — сделать вопрос «вправе ли витрина этого семейства получить это
значение» одним ответом в одном месте, вместо значения, повторённого в операции
подключения плеера, в описании тенанта и в голове оператора.

Почему это оказалось нужно. Операция PLAYER_CONFIGURE читала пару профиля и
писала прочитанное в боковой файл витрины как есть — сверки не было нигде. Пока
у семейства одна пара, дефекта не видно; в день, когда витрине досталась бы пара
другого семейства, витрина ответила бы 200 и показала чужой каталог. Отличить
это от исправной работы было нечем: плеер исправен, страница исправна, каталог
чужой.

Устройство:

* ожидание берётся из config/publisher-ids.yaml и здесь не дублируется;
* семейство витрины берётся из config/site-profiles/<site>.json, поле family;
* семейство, не описанное в файле, не проверяется вовсе — Lords, Yummy и прочие
  проходят с прежним поведением, и операция их не трогает;
* значение из retired отвергается у любого описанного семейства;
* нечисловое значение отвергается: плеер зовёт Number(publisherId), и такое
  значение даёт NaN и 400 у провайдера — проверка здесь дешевле, чем на странице.

Отказ здесь громкий намеренно. Тихая подстановка соседнего значения даёт
витрину, которая отвечает 200 и показывает чужие дорожки, — разбирается это
неделями, а исключение указывает на файл и правило сразу. Автоматического
отката к другому значению нет: отсутствие пригодного — причина отказа, а не
повод взять соседнее.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

POLICY_REF = "config/publisher-ids.yaml"
PROFILES_REF = "config/site-profiles"


class PublisherIdОтклонён(RuntimeError):
    """Значение не вправе попасть витрине этого семейства."""


@dataclass(frozen=True)
class Семейство:
    имя: str
    publisher_id: str
    credential_profile: str | None


@dataclass(frozen=True)
class Политика:
    семейства: dict[str, Семейство]
    снятые: tuple[str, ...]
    онбординг: dict[str, str]


_КЭШ: dict[str, Политика] = {}


def _root(root: Path | str | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parents[2]


def _пригоден(значение: Any) -> bool:
    """Plain digits, без ведущего нуля. Всё прочее плеер превращает в NaN."""
    if not isinstance(значение, str):
        return False
    значение = значение.strip()
    return bool(значение) and значение.isdigit() and not значение.startswith("0")


def загрузить(root: Path | str | None = None) -> Политика:
    """Читает файл ожиданий. Нет файла или он непригоден — отказ, не пустая политика."""
    корень = _root(root)
    ключ = str(корень)
    если_есть = _КЭШ.get(ключ)
    if если_есть is not None:
        return если_есть

    путь = корень / POLICY_REF
    try:
        сырое = yaml.safe_load(путь.read_text(encoding="utf-8"))
    except OSError as ошибка:
        raise PublisherIdОтклонён(f"нет файла {POLICY_REF}: {ошибка}") from ошибка
    except yaml.YAMLError as ошибка:
        raise PublisherIdОтклонён(f"{POLICY_REF} не читается как YAML: {ошибка}") from ошибка
    if not isinstance(сырое, dict):
        raise PublisherIdОтклонён(f"{POLICY_REF} обязан быть отображением")

    описания = сырое.get("families") or {}
    if not isinstance(описания, dict):
        raise PublisherIdОтклонён(f"{POLICY_REF}: families обязан быть отображением")

    семейства: dict[str, Семейство] = {}
    for имя, запись in описания.items():
        if not isinstance(запись, dict):
            raise PublisherIdОтклонён(f"{POLICY_REF}: описание {имя!r} обязано быть отображением")
        значение = запись.get("publisher_id")
        if not _пригоден(значение):
            raise PublisherIdОтклонён(
                f"{POLICY_REF}: у семейства {имя!r} непригодный publisher_id"
            )
        семейства[str(имя)] = Семейство(
            имя=str(имя),
            publisher_id=значение.strip(),
            credential_profile=(str(запись["credential_profile"])
                                if запись.get("credential_profile") else None),
        )

    снятые = tuple(str(з).strip() for з in (сырое.get("retired") or []))

    # Снятое значение не может одновременно быть действующим: такая запись
    # означает, что файл описывает две несовместимые вещи, и молча выбрать из
    # них одну — ровно тот тихий отказ, против которого этот модуль написан.
    for семейство in семейства.values():
        if семейство.publisher_id in снятые:
            raise PublisherIdОтклонён(
                f"{POLICY_REF}: значение семейства {семейство.имя!r} значится снятым"
            )

    онбординг: dict[str, str] = {}
    for запись in (сырое.get("onboarding") or []):
        if not isinstance(запись, dict):
            raise PublisherIdОтклонён(f"{POLICY_REF}: запись onboarding обязана быть отображением")
        домен = str(запись.get("domain") or "").strip().lower()
        семейство = str(запись.get("family") or "").strip()
        if not домен or not семейство:
            raise PublisherIdОтклонён(f"{POLICY_REF}: запись onboarding без domain или family")
        if семейство not in семейства:
            raise PublisherIdОтклонён(
                f"{POLICY_REF}: onboarding {домен} ссылается на неописанное семейство {семейство!r}"
            )
        онбординг[домен] = семейство

    политика = Политика(семейства=семейства, снятые=снятые, онбординг=онбординг)
    _КЭШ[ключ] = политика
    return политика


def семейства(root: Path | str | None = None) -> tuple[str, ...]:
    return tuple(загрузить(root).семейства)


def снятые(root: Path | str | None = None) -> tuple[str, ...]:
    return загрузить(root).снятые


def ожидаемый(семейство: str | None, root: Path | str | None = None) -> str | None:
    """Значение семейства. None — семейство не описано и политикой не ведётся."""
    описание = загрузить(root).семейства.get(str(семейство or ""))
    return описание.publisher_id if описание else None


def семейство_домена(домен: str, root: Path | str | None = None) -> str | None:
    """Семейство, закреплённое за ещё не выложенным доменом."""
    return загрузить(root).онбординг.get(str(домен or "").strip().lower())


def семейство_витрины(site_id: str, root: Path | str | None = None) -> str | None:
    """Семейство тенанта из его профиля. Нет профиля или поля — семейства нет."""
    путь = _root(root) / PROFILES_REF / f"{site_id}.json"
    try:
        профиль = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    семейство = профиль.get("family")
    return str(семейство).strip() if семейство else None


def проверить(
    site_id: str,
    семейство: str | None,
    значение: Any,
    root: Path | str | None = None,
) -> None:
    """Пропускает пригодное значение и отвергает всё прочее.

    Семейство вне файла не проверяется: у операции нет мнения о витринах,
    которых она не ведёт. Возврат без исключения означает «вправе».
    """
    политика = загрузить(root)
    описание = политика.семейства.get(str(семейство or ""))
    if описание is None:
        return

    if not _пригоден(значение):
        # Сообщение не называет ожидаемого значения: отказ читает тот, кто
        # передал непригодное, и подсказывать ему верное незачем.
        raise PublisherIdОтклонён(
            f"{site_id}: непригодный Publisher ID {значение!r} "
            f"для семейства {описание.имя!r} ({POLICY_REF})"
        )

    передано = значение.strip()
    if передано in политика.снятые:
        raise PublisherIdОтклонён(
            f"{site_id}: Publisher ID {передано} снят с обращения и не выдаётся "
            f"витрине семейства {описание.имя!r} ({POLICY_REF})"
        )

    if передано != описание.publisher_id:
        чужое = next(
            (с.имя for с in политика.семейства.values() if с.publisher_id == передано),
            None,
        )
        уточнение = f" — это значение семейства {чужое!r}" if чужое else ""
        raise PublisherIdОтклонён(
            f"{site_id}: Publisher ID {передано} не принадлежит семейству "
            f"{описание.имя!r}{уточнение} ({POLICY_REF})"
        )


def проблемы_профиля(profile: dict, root: Path | str | None = None) -> list[str]:
    """Что в профиле противоречит политике. Пустой список — противоречий нет.

    Вызывается гейтом до сборки: ошибку в заведённом профиле дешевле поймать
    здесь, чем после выкладки. Профиль семейства вне политики не проверяется —
    у неё нет мнения о витринах, которых она не ведёт.
    """
    политика = загрузить(root)
    проблемы: list[str] = []
    сайт = str(profile.get("site_id") or "<без site_id>")
    игрок = profile.get("player") or {}
    семейство = str(profile.get("family") or "").strip()

    # Домен, закреплённый за семейством до выкладки, не заводится под другим:
    # иначе онбординг тихо разойдётся с тем, что закреплено.
    for домен in (profile.get("domains") or []):
        закреплено = политика.онбординг.get(str(домен).strip().lower())
        if закреплено and семейство and закреплено != семейство:
            проблемы.append(
                f"{сайт}: домен {домен} закреплён за семейством {закреплено!r}, "
                f"а профиль объявляет {семейство!r} ({POLICY_REF})"
            )

    описание = политика.семейства.get(семейство)
    if описание is None:
        return проблемы

    значение = игрок.get("publisher_id")
    if значение is not None:
        try:
            проверить(сайт, семейство, значение, root=root)
        except PublisherIdОтклонён as отказ:
            проблемы.append(str(отказ))

    пара = str(игрок.get("credential_profile") or "").strip()
    if пара and описание.credential_profile and пара != описание.credential_profile:
        проблемы.append(
            f"{сайт}: credential_profile {пара!r} не принадлежит семейству "
            f"{описание.имя!r} ({POLICY_REF})"
        )
    return проблемы


def столкновения_доменов(профили: list[dict]) -> list[str]:
    """Один домен — один тенант. Второй профиль с тем же доменом отвергается.

    Два тенанта на одном домене означают два шаблона, спорящих за один сайт:
    чей релиз лёг последним, тот и виден, и разбирается это по журналам выкладки.
    """
    где: dict[str, list[str]] = {}
    for профиль in профили:
        сайт = str(профиль.get("site_id") or "<без site_id>")
        for домен in (профиль.get("domains") or []):
            где.setdefault(str(домен).strip().lower(), []).append(сайт)
    return [
        f"домен {домен} объявлен у нескольких тенантов: {', '.join(sorted(set(сайты)))}"
        for домен, сайты in sorted(где.items())
        if len(set(сайты)) > 1
    ]


def сбросить_кэш() -> None:
    _КЭШ.clear()
