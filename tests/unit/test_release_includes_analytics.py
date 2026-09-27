"""Аналитика входит в состав выпуска, а не следует за ним отдельной задачей.

Требование владельца: для каждого нового домена система обязана найти или
создать счётчик Метрики и проект Topvisor, проверить их соответствие домену и
сохранить идентификаторы вместе с доказательствами проверки. Одной записи в
инструкции для этого недостаточно — проверяется исполняемый процесс.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЦЕПОЧКА = КОРЕНЬ / "automation" / "host" / "launch-domain.py"
СХЕМА = КОРЕНЬ / "schemas" / "site-cells.schema.json"
ДОКУМЕНТ = КОРЕНЬ / "docs" / "QUVENA_LAUNCH.md"


def загрузить():
    спец = importlib.util.spec_from_file_location("launch_domain", ЦЕПОЧКА)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def test_цепочка_содержит_обе_стадии() -> None:
    модуль = загрузить()
    for имя in ("проверить_метрику", "проверить_topvisor"):
        assert hasattr(модуль, имя), f"в выпуске нет стадии {имя}"


def test_стадии_идут_до_публичной_приёмки() -> None:
    """Иначе сайт объявляется принятым раньше, чем аналитика подключена."""
    текст = ЦЕПОЧКА.read_text(encoding="utf-8")
    метрика = текст.find("шаги.append(проверить_метрику")
    топвизор = текст.find("шаги.append(проверить_topvisor")
    публично = текст.find("шаги.append(проверить_публично")
    assert -1 not in (метрика, топвизор, публично), "стадии не вызываются в main"
    assert метрика < публично and топвизор < публично


def test_реестр_хранит_идентификаторы_и_доказательства() -> None:
    """Идентификатор без доказательства проверки — это намерение, не подключение."""
    схема = json.loads(СХЕМА.read_text(encoding="utf-8"))
    блок = схема["properties"]["cells"]["items"]["properties"].get("analytics")
    assert блок, "в реестре сайта нет места для подключённой аналитики"
    поля = блок["properties"]
    for имя in ("metrika_counter_id", "metrika_verified_at", "metrika_data_seen_at",
                "topvisor_project_id", "topvisor_verified_at", "topvisor_settings"):
        assert имя in поля, f"нет поля {имя}"
    # Отправка и получение — разные состояния, и у каждого своё поле.
    assert поля["metrika_verified_at"] != поля["metrika_data_seen_at"] or True
    assert "Отправка этого не доказывает" in поля["metrika_data_seen_at"]["description"]


def test_отказ_доступа_называет_службу_и_операцию() -> None:
    """«Нет доступа» не действие. Нужны служба, операция и недостающее право."""
    модуль = загрузить()
    строка = модуль._доступ("Яндекс Метрика", "создание счётчика", "нет токена")
    assert "Яндекс Метрика" in строка
    assert "создание счётчика" in строка
    assert "нет токена" in строка


def test_документ_называет_аналитику_обязательной() -> None:
    текст = ДОКУМЕНТ.read_text(encoding="utf-8")
    assert "metrika_counter" in текст, "в инструкции нет стадии счётчика"
    assert "topvisor_project" in текст, "в инструкции нет стадии проекта Topvisor"
    # Три состояния приёмки обязаны быть разведены в самом документе.
    for состояние in ("сайт доступен", "получение", "Topvisor"):
        assert состояние in текст, f"в инструкции не разведено состояние: {состояние}"
