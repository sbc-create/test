"""Подключение карты сайта не правит вслепую и различает устройство витрин.

Измерено 2026-10-04 по шести репозиториям семейства, и это не деталь, а
причина существования инструмента:

* МОНОЛИТЫ — точка входа и есть рантайм: lordserials22.info (8339 строк),
  1lordserials1.online (7101), zonafilm.space (9763), zonafilm12.site (9637);
* АДАПТЕРЫ над общим ядром — lordfilm47.space (731 строка поверх ядра в 7103)
  и lordserial33.biz (66 строк). Их ядро совпадает с ядром соседа байт в байт,
  закреплено в `pins.lock.json` с происхождением `verified_against: git`, и
  `AGENTS.md` этих репозиториев требует менять ядро отдельной задачей.

Ещё одно расхождение, которое пришлось учесть: у части лаунчеров есть функция
дополнений (236 строк), и каталог карты выводится из `--data-dir`; у остальных
(193 строки) переменные объявляет `config/site.json: environment`, а `<data>`
подставляет сам лаунчер. Это две законные формы, и подменять одну другой
незачем.

Наконец, перечень разделов у сайтов РАЗНЫЙ: у lordserials22.info есть
`/anime/` и `/dorama/`, а у lordfilm47.space те же адреса отвечают 404.
Поэтому разделы передаются явно и не выдумываются по аналогии.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "wire-sitemap.py"

ВИТРИНА_МОНОЛИТ = '''"""Монолитная витрина стенда."""
import os
import re
import sys
from pathlib import Path


def режим_индексации():
    return ("CLOSED", "стенд")


def мета_роботов() -> str:
    return "noindex, nofollow"


def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму."""
    состояние, _ = режим_индексации()
    try:
        import indexing_mode
        return indexing_mode.robots_txt(состояние)
    except Exception:  # noqa: BLE001 — без модуля остаёмся закрытыми
        return "User-agent: *\\nDisallow: /\\n"


SITEMAP_DIR = os.environ.get("LORDS_SITEMAP_DIR", "").strip()


class Обработчик:
    def _отдать(self, тело, тип, код=200):
        return (код, тип, тело)

    def маршрут(self, путь):
        if путь == "/sitemap.xml" or re.fullmatch(r"/sitemap-\\d+\\.xml", путь):
            if not SITEMAP_DIR:
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            return self._отдать(b"<x/>", "application/xml")
        self.send_header("X-Robots-Tag", мета_роботов())
        return None

    def send_header(self, *а):
        pass


def main() -> int:
    import time as _time
    print("стенд поднят", _time.time())
    return 0
'''

#: Лаунчер-АДАПТЕР по образцу живых витрин: загружает общее ядро по пути,
#: ставит слои и отдаёт управление `ядро.main()`.
АДАПТЕР_ЛАУНЧЕР = '''"""Адаптер над общим ядром."""
import importlib.util
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent


def загрузить_ядро():
    спец = importlib.util.spec_from_file_location(
        "lords_frontend_core", КОРЕНЬ / "lords-frontend.py")
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["lords_frontend_core"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


def main() -> int:
    ядро = загрузить_ядро()
    return ядро.main()


if __name__ == "__main__":
    raise SystemExit(main())
'''

ЛАУНЧЕР_БЕЗ_ДОПОЛНЕНИЙ = '''import json
from pathlib import Path


def environment(config: dict, data: Path) -> dict:
    env = {}
    for имя, шаблон in config["environment"].items():
        env[имя] = шаблон.replace("<data>", str(data))
    return env
'''


def _репозиторий(tmp: pathlib.Path, *, адаптер: bool) -> pathlib.Path:
    репо = tmp / "repo"
    (репо / "src").mkdir(parents=True)
    (репо / "config").mkdir()
    точка = "site01-frontend.py" if адаптер else "lords-frontend.py"
    (репо / "config" / "site.json").write_text(json.dumps({
        "site_id": "t-01", "domain": "t.example", "entrypoint": точка,
        "environment": {"LORDS_CATALOG": "<data>/t-01-catalog.json"},
    }, ensure_ascii=False), encoding="utf-8")
    (репо / "src" / "lords-frontend.py").write_text(ВИТРИНА_МОНОЛИТ, encoding="utf-8")
    # Прежняя версия общего модуля: доставка из шаблона должна быть видна.
    (репо / "src" / "seo_layer.py").write_text(
        '"""Прежний общий модуль без сборщика карты."""\n', encoding="utf-8")
    if адаптер:
        (репо / "src" / точка).write_text(АДАПТЕР_ЛАУНЧЕР, encoding="utf-8")
    (репо / "run.py").write_text(ЛАУНЧЕР_БЕЗ_ДОПОЛНЕНИЙ, encoding="utf-8")
    return репо


def _запуск(репо: pathlib.Path, *аргументы: str):
    return subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--repo", str(репо),
                           "--sections", "/", "/movies/", *аргументы],
                          capture_output=True, text=True, cwd=str(КОРЕНЬ))


def test_адаптер_подключается_не_трогая_ядро(tmp_path):
    """У витрины на общем ядре карта подключается слоем, а ядро не правится.

    Прежде инструмент отказывал адаптеру ЦЕЛИКОМ. Отказ был слишком широким:
    ядро уже умеет ОТДАВАТЬ карту (маршрут и `SITEMAP_DIR` в нём есть), а не
    хватало ровно того, что лежит в файлах САМОГО САЙТА — сборщика, перечня
    разделов, переменной каталога и ссылки в robots.txt. Измерено 2026-10-04
    на выложенном lordserial33.biz: `/sitemap.xml` отдавал 404 молча.
    """
    репо = _репозиторий(tmp_path, адаптер=True)
    ядро = репо / "src" / "lords-frontend.py"
    было = ядро.read_bytes()
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    assert "АДАПТЕР над общим ядром" in итог.stdout, итог.stdout
    # ЯДРО НЕ ТРОНУТО — байт в байт.
    assert ядро.read_bytes() == было, "правка общего ядра запрещена п. 3 AGENTS.md"
    # Подключение — в файлах сайта.
    лаунчер = (репо / "src" / "site01-frontend.py").read_text(encoding="utf-8")
    assert "lords_sitemap_layer.подключить(ядро, РАЗДЕЛЫ_КАРТЫ)" in лаунчер
    assert 'РАЗДЕЛЫ_КАРТЫ = ("/", "/movies/",)' in лаунчер
    # Запуск сборщика — ДО `ядро.main()`: сервер стартует в нём.
    assert лаунчер.index("lords_sitemap_layer.подключить") < лаунчер.index(
        "return ядро.main()")
    слой = репо / "src" / "lords_sitemap_layer.py"
    assert слой.is_file(), "общий слой семейства обязан быть доставлен"
    assert слой.read_bytes() == (
        КОРЕНЬ / "automation" / "host" / "lords_sitemap_layer.py").read_bytes()
    # И сборщик: прежняя версия общего модуля заменена шаблонной.
    assert "запустить_карту" in (репо / "src" / "seo_layer.py").read_text(
        encoding="utf-8")


def test_адаптер_без_точки_подключения_отказывает(tmp_path):
    """Нет `main()` — нет места для слоя, и инструмент не правит вслепую."""
    репо = _репозиторий(tmp_path, адаптер=True)
    (репо / "src" / "site01-frontend.py").write_text(
        '"""Адаптер без main()."""\nimport lords_frontend  # noqa\n',
        encoding="utf-8")
    ядро = репо / "src" / "lords-frontend.py"
    было = ядро.read_bytes()
    итог = _запуск(репо)
    assert итог.returncode == 4, итог.stdout + итог.stderr
    assert "нет main()" in итог.stderr, итог.stderr
    assert ядро.read_bytes() == было


def test_копия_общего_модуля_только_для_чтения_не_правится_наполовину(tmp_path):
    """Отказ на последнем файле не вправе оставить репозиторий в половине правок.

    Измерено 2026-10-04 на lordserial33.biz: копии общих модулей помечены
    `-r--r--r--`, доставка `seo_layer.py` шла отдельной строкой ПОСЛЕ правок
    лаунчера, и `PermissionError` на ней оставил витрину звать слой, которого
    в модуле нет.
    """
    репо = _репозиторий(tmp_path, адаптер=True)
    модуль = репо / "src" / "seo_layer.py"
    модуль.chmod(0o444)
    лаунчер = репо / "src" / "site01-frontend.py"
    было = лаунчер.read_bytes()
    итог = _запуск(репо)
    assert итог.returncode == 5, итог.stdout + итог.stderr
    assert "только для чтения" in итог.stderr, итог.stderr
    assert "chmod u+w" in итог.stderr, "что делать — обязано быть сказано"
    assert лаунчер.read_bytes() == было, "ни одной правки не применено"


def test_монолит_подключается_целиком(tmp_path):
    репо = _репозиторий(tmp_path, адаптер=False)
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    витрина = (репо / "src" / "lords-frontend.py").read_text(encoding="utf-8")
    assert "РАЗДЕЛЫ_КАРТЫ = (\"/\", \"/movies/\",)" in витрина, витрина[:400]
    assert "запустить_карту" in витрина
    assert "мета_роботов_пути(self.path" in витрина
    assert 'режим_индексации()[0] != "OPEN"' in витрина, (
        "маршрут карты не стал fail-closed")
    assert "sitemap=карта" in витрина
    # Вторая форма лаунчера: переменная объявлена в пакете.
    пакет = json.loads((репо / "config" / "site.json").read_text(encoding="utf-8"))
    assert пакет["environment"]["LORDS_SITEMAP_DIR"] == "<data>/sitemap"
    # Общий модуль доставлен из шаблона.
    общий = (КОРЕНЬ / "automation" / "host" / "seo_layer.py").read_bytes()
    assert (репо / "src" / "seo_layer.py").read_bytes() == общий


def test_повтор_ничего_не_меняет(tmp_path):
    репо = _репозиторий(tmp_path, адаптер=False)
    assert _запуск(репо).returncode == 0
    было = (репо / "src" / "lords-frontend.py").read_bytes()
    итог = _запуск(репо)
    assert итог.returncode == 0
    assert "уже подключена" in итог.stdout
    assert (репо / "src" / "lords-frontend.py").read_bytes() == было


def test_сухой_прогон_ничего_не_пишет(tmp_path):
    репо = _репозиторий(tmp_path, адаптер=False)
    было = (репо / "src" / "lords-frontend.py").read_bytes()
    итог = _запуск(репо, "--dry-run")
    assert итог.returncode == 0
    assert "сухой прогон" in итог.stdout
    assert (репо / "src" / "lords-frontend.py").read_bytes() == было


def test_разделы_обязательны():
    """Перечень разделов не выдумывается: у сайтов он разный."""
    итог = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--repo", "."],
                          capture_output=True, text=True, cwd=str(КОРЕНЬ))
    assert итог.returncode != 0
    assert "--sections" in итог.stderr or "sections" in итог.stderr
