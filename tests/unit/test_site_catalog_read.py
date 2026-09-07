"""Characterization: чтение каталога витрины — до переноса и после.

Функция `_каталог_витрины` читает файл каталога и его возраст. Живёт она в
управляющем контуре (`api/overview.py`), а пользуется ею домен каталога
(`rating_feed`), причём по приватному имени. Направление перевёрнуто: контур
управления обязан зависеть от доменов, а не они от него.

Перенос без этого теста был бы переносом вслепую: поведение здесь состоит из
мелочей, каждая из которых уже была причиной отказа — абсолютный путь
поставщика, отсутствующий файл, битый JSON, возраст в секундах.

Проверки написаны до переноса и обязаны пройти и после него без единой правки.
Если после переноса их пришлось бы менять — это не перенос, а изменение
поведения под видом переноса.
"""

from __future__ import annotations

import json
import time

import pytest

# Импортируется публичный вход, а не приватное имя: тест не должен закреплять
# то, что мы как раз собираемся перестать делать.
from factory.site_engine.api import overview as контур


@pytest.fixture
def чтение():
    """Читатель каталога в его нынешнем месте."""
    return контур._каталог_витрины


def каталог(tmp_path, site_id: str, данные) -> tuple:
    место = tmp_path / "catalog-cache"
    место.mkdir(parents=True, exist_ok=True)
    (место / f"{site_id}.json").write_text(
        json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return место


class TestЧитаетТоЧтоЕсть:
    def test_читает_каталог_витрины(self, tmp_path, чтение):
        место = каталог(tmp_path, "s-1", {"items": [{"external_id": "a"}]})
        данные, возраст = чтение(tmp_path, {"SITE_ENGINE_CATALOG_DIR": str(место)}, "s-1")
        assert данные == {"items": [{"external_id": "a"}]}
        assert isinstance(возраст, int) and возраст >= 0

    def test_возраст_считается_в_секундах_от_времени_файла(self, tmp_path, чтение):
        место = каталог(tmp_path, "s-1", {"items": []})
        путь = место / "s-1.json"
        старое = time.time() - 3600
        import os

        os.utime(путь, (старое, старое))
        _, возраст = чтение(tmp_path, {"SITE_ENGINE_CATALOG_DIR": str(место)}, "s-1")
        assert 3500 <= возраст <= 3700, f"возраст {возраст} не похож на час"

    def test_возраст_никогда_не_отрицателен(self, tmp_path, чтение):
        """Файл из будущего бывает при рассинхронизации часов."""
        место = каталог(tmp_path, "s-1", {"items": []})
        путь = место / "s-1.json"
        import os

        будущее = time.time() + 600
        os.utime(путь, (будущее, будущее))
        _, возраст = чтение(tmp_path, {"SITE_ENGINE_CATALOG_DIR": str(место)}, "s-1")
        assert возраст == 0, "отрицательный возраст читался бы как свежесть из будущего"


class TestОтсутствиеОтличаетсяОтПустоты:
    def test_подкаталог_не_задан_источник_недоступен(self, tmp_path, чтение):
        assert чтение(tmp_path, {}, "s-1") == (None, None)

    def test_пустая_строка_подкаталога_это_не_задан(self, tmp_path, чтение):
        assert чтение(tmp_path, {"SITE_ENGINE_CATALOG_DIR": "   "}, "s-1") == (None, None)

    def test_файла_нет_источник_недоступен(self, tmp_path, чтение):
        место = tmp_path / "пусто"
        место.mkdir()
        assert чтение(tmp_path, {"SITE_ENGINE_CATALOG_DIR": str(место)}, "s-1") == (None, None)

    def test_битый_json_не_роняет_чтение(self, tmp_path, чтение):
        место = tmp_path / "catalog-cache"
        место.mkdir()
        (место / "s-1.json").write_text("{не json", encoding="utf-8")
        assert чтение(tmp_path, {"SITE_ENGINE_CATALOG_DIR": str(место)}, "s-1") == (None, None)


class TestПутьПоставщикаМожетБытьВнеРепозитория:
    def test_абсолютный_путь_не_приклеивается_к_корню(self, tmp_path, чтение):
        """Каталог поставщика законно живёт вне дерева — /srv/..., не var/..."""
        снаружи = каталог(tmp_path / "снаружи", "s-1", {"items": [1]})
        (tmp_path / "репо").mkdir()
        данные, _ = чтение(tmp_path / "репо",
                           {"SITE_ENGINE_CATALOG_DIR": str(снаружи)}, "s-1")
        assert данные == {"items": [1]}, (
            "абсолютный путь склеили с корнем — искали бы var/... внутри /srv/...")

    def test_относительный_путь_отсчитывается_от_корня(self, tmp_path, чтение):
        репо = tmp_path / "репо"
        репо.mkdir()
        каталог(репо, "s-1", {"items": [2]})
        данные, _ = чтение(репо, {"SITE_ENGINE_CATALOG_DIR": "catalog-cache"}, "s-1")
        assert данные == {"items": [2]}
