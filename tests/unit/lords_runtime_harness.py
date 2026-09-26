"""Поднять рантайм Lords в процессе теста, на своём каталоге и своём манифесте.

Зачем отдельная оснастка. `automation/host/lords-frontend.py` читает манифест
шаблона НА ИМПОРТЕ и без него отказывается подниматься (`SystemExit`). Это
правильно для витрины и неудобно для теста, поэтому подготовка окружения
собрана здесь один раз: иначе каждый файл проверок завёл бы свою копию, и
копии разошлись бы — ровно та беда, из-за которой эта работа и началась.

Ничего общего с машиной оснастка не трогает: каталог, подробности, манифест и
настройка плеера создаются во временном каталоге теста. Путь к соседнему сайту
здесь появиться не может.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЯДРО = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"
КОНТРАКТ = КОРЕНЬ / "automation" / "host" / "collection_contract.py"


def манифест(**переопределения: Any) -> dict:
    """Минимальный валидный манифест шаблона.

    Поля выпуска пусты намеренно: заполненное в репозитории значение пережило
    бы свой выпуск и продолжило бы называть его цифры (разбор lords-01,
    `docs/STATE.md`, раздел 3).
    """
    м = {
        "schema_version": 1,
        "template_family": "lords",
        "design_version": "1.0.2",
        "source_commit": "0" * 40,
        "build_id": "test-build",
        "artifact_sha256": "",
        "profile": "lords-general",
        "built_at": "2026-09-26T00:00:00+00:00",
        "runtime_commit": "",
        "site_repo_commit": "",
        "release_dir": "",
        "bound_release_link": "",
    }
    м.update(переопределения)
    return м


def запись(slug: str, *, title: str, kind: str = "Фильм", year: int = 2024,
           rating: float | None = 8.0, published_at: str = "2026-09-20",
           poster: str | None = None, playable: bool = True) -> dict:
    з = {
        "slug": slug,
        "url": f"/title/{slug}/",
        "title": title,
        "kind": kind,
        "year": year,
        "published_at": published_at,
        "playable": playable,
    }
    if rating is not None:
        з["rating"] = rating
    з["poster"] = poster if poster is not None else f"/posters/{slug}.jpg"
    return з


def подробность(slug: str, *, genres: tuple[str, ...] = (), type_: str = "movie",
                seasons: tuple[dict, ...] = (), country: str = "",
                ident: str = "", источник: bool = True) -> dict:
    """Запись бокового файла.

    `external_ids.kp` проставляется по умолчанию: без идентификатора
    агрегатора рантайм считает запись `nosource` и не пускает её на главную —
    это правильное поведение витрины и мешающее умолчание для проверки
    отбора. Отсутствие источника проверяется отдельно, флагом.
    """
    д = {
        "id": ident or slug,
        "slug": slug,
        "genres": list(genres),
        "type": type_,
        "seasons": [dict(с) for с in seasons],
        "country": country,
    }
    if источник:
        д["external_ids"] = {"kp": f"kp-{slug}"}
    return д


class Стенд:
    """Каталог, подробности, манифест и настройка плеера одного теста."""

    def __init__(self, корень: Path, *, профиль: str = "lords-general",
                 site_id: str = "lords-test") -> None:
        self.корень = корень
        self.site_id = site_id
        self.каталог = корень / f"{site_id}-catalog.json"
        self.подробности = корень / f"{site_id}-details.json"
        self.манифест = корень / "config" / "template-manifest.json"
        self.плеер = корень / "config" / "player.json"
        self.манифест.parent.mkdir(parents=True, exist_ok=True)
        self.манифест.write_text(
            json.dumps(манифест(profile=профиль), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")

    def записать_каталог(self, записи: list[dict], *, revision: str = "rev-1") -> None:
        self.каталог.write_text(json.dumps({
            "revision": revision,
            "built_at": "2026-09-26T03:30:00+00:00",
            "items": записи,
        }, ensure_ascii=False), encoding="utf-8")

    def записать_подробности(self, подробности: list[dict], *,
                             revision: str = "rev-1") -> None:
        # Ключ `details`, как в живом боковом файле: `items` рантайм молча
        # проигнорировал бы, и проверка классификации ничего бы не проверяла.
        self.подробности.write_text(json.dumps({
            "catalog_revision": revision,
            "catalog_built_at": "2026-09-26T03:30:00+00:00",
            "source": "test",
            "details_total": len(подробности),
            "details": {д["slug"]: д for д in подробности},
        }, ensure_ascii=False), encoding="utf-8")

    def записать_плеер(self, publisher_id: str = "10555") -> None:
        self.плеер.write_text(
            json.dumps({"publisher_id": publisher_id}, ensure_ascii=False) + "\n",
            encoding="utf-8")

    @property
    def окружение(self) -> dict[str, str]:
        return {
            "LORDS_TEMPLATE_MANIFEST": str(self.манифест),
            "LORDS_CATALOG": str(self.каталог),
            "LORDS_DETAILS": str(self.подробности),
            "LORDS_PLAYER_CONFIG": str(self.плеер),
            "LORDS_LEGACY_ROOT": str(self.корень / "legacy"),
            "LORDS_SITE_NAME": "Тестовая витрина",
            "LORDS_SITE_ID": self.site_id,
        }


def загрузить(стенд: Стенд, monkeypatch) -> Any:
    """Импортировать рантайм на окружении стенда.

    Модуль импортируется под уникальным именем: он читает манифест на импорте,
    и кэш `sys.modules` отдал бы второму тесту настройки первого.
    """
    for имя, значение in стенд.окружение.items():
        monkeypatch.setenv(имя, значение)
    # Контракт коллекций рантайм импортирует по имени — путь до него должен
    # быть в sys.path, иначе КОЛЛЕКЦИИ молча станут None и половина проверок
    # перестанет что-либо проверять.
    monkeypatch.syspath_prepend(str(КОРЕНЬ / "automation" / "host"))
    имя_модуля = f"_lords_runtime_{abs(hash(str(стенд.корень)))}"
    spec = importlib.util.spec_from_file_location(имя_модуля, ЯДРО)
    модуль = importlib.util.module_from_spec(spec)
    sys.modules[имя_модуля] = модуль
    try:
        spec.loader.exec_module(модуль)
    except BaseException:
        sys.modules.pop(имя_модуля, None)
        raise
    monkeypatch.setattr(sys, "modules", sys.modules)  # держим ссылку на время теста
    return модуль


def вид(модуль: Any) -> Any:
    """Вид семейства на данных стенда — тот же, что собирает обработчик."""
    данные = модуль.Данные(модуль.КАТАЛОГ_ФАЙЛ)
    подробности = модуль.Подробности(модуль.ПОДРОБНОСТИ_ФАЙЛ)
    индекс = модуль.построить_индекс(данные, подробности)
    описание = модуль.СЕМЕЙСТВА_1_1.get(модуль.СЕМЕЙСТВО) or модуль.СЕМЕЙСТВА_1_1["lords"]
    класс = модуль.ВИДЫ_1_1.get(описание["вид"], модуль.ВидЛордс)
    return класс(описание, данные, подробности, индекс, модуль.ИМЯ_ВИТРИНЫ)


def выгрузить(модуль: Any) -> None:
    sys.modules.pop(модуль.__name__, None)


__all__ = ["КОРЕНЬ", "ЯДРО", "КОНТРАКТ", "Стенд", "загрузить", "выгрузить", "вид",
           "манифест", "запись", "подробность"]
