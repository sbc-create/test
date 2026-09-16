"""Витрина не выключает тот вид содержимого, ради которого она заведена.

Профиль объявляет назначение витрины словами, пакет — состав каталога флагами.
Расходиться они не вправе, и расхождение это не теоретическое: пакет
`animedia-preview` объявлял `anime: false` при профиле, чья первая строка —
«Портал аниме». Портал аниме без аниме.

Заметить такое чтением почти невозможно: обе стороны по отдельности выглядят
осмысленно, а расходятся они в разных файлах и разными способами — одна
словами, другая флагами. Видно только на собранной витрине, где в жанрах
стоит «аниме 139» из четырёх тысяч, а в навигации раздела аниме нет вовсе.

Проверка не решает, каким быть каталогу: сколько в нём фильмов и сериалов —
дело владельца. Она запрещает ровно одно — выключить вид содержимого, который
профиль назвал назначением витрины.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

#: Витрины продуктов этапа и их профили. Соответствие снято из пакетов
#: (`tenant.seo_profile`), а не назначено здесь.
PRODUCTS = {
    "zona-cinema-preview": "zona-cinema",
    "animedia-preview": "animedia-portal",
}

#: Слово в назначении профиля → флаг состава каталога. Перечень закрыт: он
#: описывает виды содержимого, которые фабрика различает, и разрастаться от
#: случайных совпадений в тексте не должен.
ВИД_ПО_СЛОВУ = {
    "аниме": "anime",
    "дорам": "dorama",
    "мультфильм": "animation",
    "сериал": "series",
    "кино": "movies",
    "фильм": "movies",
}


def _пакет(site: str) -> dict:
    return yaml.safe_load((ROOT / "sites" / site / "package.yaml").read_text(encoding="utf-8"))


def _профиль(name: str) -> dict:
    path = ROOT / "blueprints" / "lords" / "profiles" / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _назначение(profile: dict) -> str:
    """Первое предложение назначения: там витрина называет, чем она является."""
    purpose = str(profile.get("purpose") or "")
    return purpose.split(".")[0].lower()


@pytest.mark.parametrize("site,profile_name", sorted(PRODUCTS.items()))
class TestНазначениеИСоставСогласованы:
    def test_объявленный_вид_содержимого_не_выключен(self, site, profile_name):
        profile = _профиль(profile_name)
        types = _пакет(site).get("content_types") or {}
        назначение = _назначение(profile)
        нарушения = [
            f"{profile.get('label')} назван «{слово}», а пакет ставит {флаг}: false"
            for слово, флаг in ВИД_ПО_СЛОВУ.items()
            if слово in назначение and types.get(флаг) is False
        ]
        assert нарушения == [], "; ".join(нарушения)

    def test_навигация_не_обещает_выключенного(self, site, profile_name):
        """Раздел в меню, которого нет в каталоге, — тупик для зрителя."""
        package = _пакет(site)
        types = package.get("content_types") or {}
        пути = {
            "/movies/": "movies", "/series/": "series", "/animation/": "animation",
            "/anime/": "anime", "/dorama/": "dorama",
        }
        обещано = [
            item.get("url") for item in ((package.get("navigation") or {}).get("primary") or [])
            if pути_флаг(item.get("url"), пути, types) is False
        ]
        assert obещано_пусто(обещано), f"{site}: меню ведёт в выключённые разделы {обещано}"

    def test_включённый_вид_доступен_из_меню(self, site, profile_name):
        """Включённый вид, до которого нет пути, зритель не найдёт."""
        package = _пакет(site)
        types = package.get("content_types") or {}
        urls = {item.get("url") for item in
                ((package.get("navigation") or {}).get("primary") or [])}
        пути = {"movies": "/movies/", "series": "/series/", "animation": "/animation/",
                "anime": "/anime/", "dorama": "/dorama/"}
        нет_пути = [флаг for флаг, url in пути.items()
                    if types.get(флаг) is True and url not in urls]
        assert нет_пути == [], f"{site}: включены {нет_пути}, а в меню их нет"


def pути_флаг(url, пути, types):
    флаг = пути.get(url)
    return types.get(флаг) if флаг else None


def obещано_пусто(значения) -> bool:
    return not [x for x in значения if x]
