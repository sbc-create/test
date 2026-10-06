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


# ---------------------------------------------------------------------------
# Формы, на которых инструмент отказывал, хотя точка подключения была
# ---------------------------------------------------------------------------
#
# Все три проверки ниже — регрессии измеренных отказов 2026-10-06, а не
# предположения:
#
#   * `import time as _time` есть у двух монолитов из четырёх. Инструмент
#     искал только его и отказывал словами «нет точки запуска в main()» на
#     zonafilm.space и zonafilm12.site — при том что строка согласования серий
#     стоит там же, где у соседа, и ровно там, где нужно;
#   * форма `_тело_robots` у animego другая (читатель режима уже в `ИНДЕКС`), и
#     отказ «нет точки вставки `_тело_robots`» получали все три витрины
#     семейства;
#   * `мета_роботов_пути` у animego УЖЕ есть, и вторая копия функции сделала бы
#     файл невалидным.

#: Монолит без `import time as _time`: запуск заводится после строки
#: согласования серий. Остальное — тот же стенд.


def _подменить(текст: str, было: str, стало: str) -> str:
    """Подмена, которая НЕ МОЖЕТ пройти впустую.

    Стенды собираются из одного исходного текста подменой кусков, и `replace`
    на несовпавшей подстроке молча отдаёт исходник. Так и вышло: экранирование
    в аргументе ушло на уровень глубже (`\\\\n` вместо `\\n`), подмена не
    применилась, и проверка «форма animego» измеряла вовсе не форму animego.
    """
    if было not in текст:
        raise AssertionError(f"стенд не собран: не нашлось\n{было[:200]}")
    return текст.replace(было, стало, 1)


ВИТРИНА_БЕЗ_ВРЕМЕНИ = _подменить(
    ВИТРИНА_МОНОЛИТ,
    '''def main() -> int:
    import time as _time
    print("стенд поднят", _time.time())
    return 0''',
    '''def main() -> int:
    _согласование = None
    if _согласование is not None and _согласование.запустить(sys.modules[__name__]):
        print("[nova] согласование доступности серий: запущено", flush=True)
    print("стенд поднят")
    return 0''')

#: Форма animego: читатель режима уже импортирован, запрет служебных путей в
#: ответе приложения уже стоит.
ВИТРИНА_АНИМЕГО = _подменить(
    _подменить(ВИТРИНА_БЕЗ_ВРЕМЕНИ, '''def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму."""
    состояние, _ = режим_индексации()
    try:
        import indexing_mode
        return indexing_mode.robots_txt(состояние)
    except Exception:  # noqa: BLE001 — без модуля остаёмся закрытыми
        return "User-agent: *\\nDisallow: /\\n"''',
               '''ИНДЕКС = None


def мета_роботов_пути(путь: str) -> str:
    return мета_роботов()


def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму."""
    состояние, _ = режим_индексации()
    if ИНДЕКС is None:
        return "User-agent: *\\nDisallow: /\\n"
    return ИНДЕКС.robots_txt(состояние)'''),
    '        self.send_header("X-Robots-Tag", мета_роботов())',
    '        self.send_header("X-Robots-Tag",\n'
    '                         мета_роботов_пути(self.path or "/"))')

#: Лаунчер animego: весь набор переменных в одной функции, ни одна не оставлена
#: на умолчание.
ЛАУНЧЕР_ОКРУЖЕНИЕ = '''from pathlib import Path


def окружение(конфиг: dict, данные: Path) -> dict[str, str]:
    среда = {
        "ANIMEGO_CATALOG": str(данные / "catalog.json"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return среда
'''


def _монолит(tmp: pathlib.Path, витрина: str, *, лаунчер: str | None = None,
             пакет_с_окружением: bool = True) -> pathlib.Path:
    репо = tmp / "repo"
    (репо / "src").mkdir(parents=True)
    (репо / "config").mkdir()
    пакет: dict = {"site_id": "t-02", "domain": "t2.example",
                   "entrypoint": "lords-frontend.py"}
    if пакет_с_окружением:
        пакет["environment"] = {"LORDS_CATALOG": "<data>/t-02-catalog.json"}
    (репо / "config" / "site.json").write_text(
        json.dumps(пакет, ensure_ascii=False), encoding="utf-8")
    (репо / "src" / "lords-frontend.py").write_text(витрина, encoding="utf-8")
    (репо / "src" / "seo_layer.py").write_text(
        '"""Прежний общий модуль без сборщика карты."""\n', encoding="utf-8")
    (репо / "run.py").write_text(лаунчер or ЛАУНЧЕР_БЕЗ_ДОПОЛНЕНИЙ, encoding="utf-8")
    return репо


def test_монолит_без_import_time_всё_равно_подключается(tmp_path):
    """Второй якорь запуска: строка согласования серий есть у всех монолитов."""
    репо = _монолит(tmp_path, ВИТРИНА_БЕЗ_ВРЕМЕНИ)
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    витрина = (репо / "src" / "lords-frontend.py").read_text(encoding="utf-8")
    assert "запустить_карту" in витрина
    # Запуск встал ПОСЛЕ согласования и ДО возврата из main().
    место_согл = витрина.index("согласование доступности серий: запущено")
    место_карты = витрина.index("_карта.запустить_карту")
    место_возврата = витрина.rindex("return 0")
    assert место_согл < место_карты < место_возврата, "запуск встал не в main()"
    # Файл остаётся разбираемым: отступ блока закрывает `if` согласования.
    compile(витрина, "lords-frontend.py", "exec")


def test_форма_animego_получает_ссылку_без_второй_копии_функции(tmp_path):
    репо = _монолит(tmp_path, ВИТРИНА_АНИМЕГО, лаунчер=ЛАУНЧЕР_ОКРУЖЕНИЕ,
                    пакет_с_окружением=False)
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    витрина = (репо / "src" / "lords-frontend.py").read_text(encoding="utf-8")
    assert "ИНДЕКС.robots_txt(состояние, sitemap=карта)" in витрина
    assert витрина.count("def мета_роботов_пути") == 1, (
        "вторая копия функции сделала бы файл невалидным")
    assert 'режим_индексации()[0] != "OPEN"' in витрина, "маршрут не fail-closed"
    compile(витрина, "lords-frontend.py", "exec")
    # Третья форма объявления каталога карты: в окружении лаунчера.
    лаунчер = (репо / "run.py").read_text(encoding="utf-8")
    assert '"LORDS_SITEMAP_DIR": str(данные / "sitemap")' in лаунчер
    compile(лаунчер, "run.py", "exec")


ПРОГОН = '''#!/usr/bin/env bash
set -uo pipefail
fail=0
check() { "$@" || fail=1; }
check "site-config-json" python3 -c "print(1)"

exit "$fail"
'''


def test_проверка_карты_доставляется_и_встаёт_в_прогон(tmp_path):
    """Подключение держится проверкой проекта, а не честным словом выпуска.

    Карта отсутствовала на восьми живых доменах, и ни один выпуск этого не
    заметил: терялась она молча. Проверка обязана и доставляться, и
    запускаться — доставленный, но не вызываемый файл не держит ничего.
    """
    репо = _монолит(tmp_path, ВИТРИНА_МОНОЛИТ)
    (репо / "checks").mkdir()
    (репо / "checks" / "run.sh").write_text(ПРОГОН, encoding="utf-8")
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    проверка = репо / "checks" / "sitemap_wired.py"
    эталон = КОРЕНЬ / "automation" / "host" / "sitemap_wired_check.py"
    assert проверка.read_bytes() == эталон.read_bytes(), "доставлена не та проверка"
    прогон = (репо / "checks" / "run.sh").read_text(encoding="utf-8")
    assert "checks/sitemap_wired.py" in прогон, "проверка не вызывается прогоном"
    assert прогон.rstrip().endswith('exit "$fail"'), "строка выхода осталась последней"
    assert прогон.count('exit "$fail"') == 1, "строка выхода удвоилась"
    # Повтор ничего не добавляет: вторая строка вызова означала бы, что
    # инструмент дописывает прогон при каждом применении.
    второй = _запуск(репо)
    assert второй.returncode == 0, второй.stdout + второй.stderr
    assert "ничего не меняю" in второй.stdout, второй.stdout
    assert (репо / "checks" / "run.sh").read_text(encoding="utf-8").count(
        "checks/sitemap_wired.py") == 1


ПРОГОН_АНИМЕГО = '''#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAND="${1:-}"
rc=0
step() { echo "-- $1"; shift; "$@" || rc=1; }
step "рантайм компилируется" python3 -c "print(1)"

if [ -n "$STAND" ]; then
  if ! curl -sf -o /dev/null "$STAND/healthz"; then
    echo "стенд не отвечает" >&2
    exit 1
  fi
  step "браузер" true
fi

echo
if [ $rc -eq 0 ]; then echo "ПРОВЕРКИ ПРОЙДЕНЫ"; else echo "ПРОВЕРКИ ОТКАЗАЛИ"; fi
exit $rc
'''


def test_вторая_форма_прогона_получает_проверку_в_конце(tmp_path):
    """У animego прогон зовёт `step` и выходит `exit $rc` — форма другая.

    Проверка обязана встать в ОБЩУЮ ветвь, а не в ту, что выполняется только
    при переданном стенде: `exit $rc` в этом файле не один, и выбор первого
    вхождения поставил бы проверку в середину.
    """
    репо = _монолит(tmp_path, ВИТРИНА_АНИМЕГО, лаунчер=ЛАУНЧЕР_ОКРУЖЕНИЕ,
                    пакет_с_окружением=False)
    (репо / "checks").mkdir()
    (репо / "checks" / "run.sh").write_text(ПРОГОН_АНИМЕГО, encoding="utf-8")
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    прогон = (репо / "checks" / "run.sh").read_text(encoding="utf-8")
    assert 'checks/sitemap_wired.py' in прогон
    assert прогон.rstrip().endswith("exit $rc"), "строка выхода осталась последней"
    # Проверка стоит ПОСЛЕ ветви стенда, то есть выполняется всегда.
    assert прогон.index("sitemap_wired.py") > прогон.index('if [ -n "$STAND" ]')
    # И ДО вердикта: вставленная между вердиктом и выходом, она исправно меняла
    # код возврата, но отчёт уже сообщал «ПРОВЕРКИ ПРОЙДЕНЫ» — и провал карты
    # оказывался ниже этой строки. Измерено на an1meg0.site.
    assert прогон.index("sitemap_wired.py") < прогон.index("ПРОВЕРКИ ПРОЙДЕНЫ"), (
        "вердикт печатается раньше, чем проверка запущена")
    assert subprocess.run(["bash", "-n", str(репо / "checks" / "run.sh")],
                          capture_output=True).returncode == 0


def test_проверка_карты_доставляется_и_уже_подключённому_сайту(tmp_path):
    """Сайт, подключённый ДО появления проверки, обязан её получить.

    Прежде инструмент выходил по первому признаку «запустить_карту в тексте» и
    до доставки проверки не доходил никогда: lordserials22.info и
    lordserial33.biz остались бы без неё навсегда.
    """
    репо = _монолит(tmp_path, ВИТРИНА_МОНОЛИТ)
    (репо / "checks").mkdir()
    (репо / "checks" / "run.sh").write_text(ПРОГОН, encoding="utf-8")
    assert _запуск(репо).returncode == 0
    витрина_после = (репо / "src" / "lords-frontend.py").read_bytes()
    # Убираем ТОЛЬКО проверку и её вызов — подключение остаётся на месте.
    (репо / "checks" / "sitemap_wired.py").unlink()
    (репо / "checks" / "run.sh").write_text(ПРОГОН, encoding="utf-8")
    итог = _запуск(репо)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    assert "уже на месте" in итог.stdout, итог.stdout
    assert (репо / "checks" / "sitemap_wired.py").is_file(), "проверка не доставлена"
    assert "checks/sitemap_wired.py" in (репо / "checks" / "run.sh").read_text(
        encoding="utf-8")
    assert (репо / "src" / "lords-frontend.py").read_bytes() == витрина_после, (
        "витрина не должна правиться второй раз")


def test_неизвестная_форма_robots_отказывает(tmp_path):
    """Ссылка на карту вслепую не ставится: не совпало — отказ с причиной."""
    чужая = _подменить(ВИТРИНА_МОНОЛИТ, '''def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму."""
    состояние, _ = режим_индексации()
    try:
        import indexing_mode
        return indexing_mode.robots_txt(состояние)
    except Exception:  # noqa: BLE001 — без модуля остаёмся закрытыми
        return "User-agent: *\\nDisallow: /\\n"''',
                       '''def _тело_robots() -> str:
    return "User-agent: *\\nAllow: /\\n"''')
    репо = _монолит(tmp_path, чужая)
    было = (репо / "src" / "lords-frontend.py").read_bytes()
    итог = _запуск(репо)
    assert итог.returncode == 3, итог.stdout + итог.stderr
    assert "_тело_robots" in итог.stderr and "форм" in итог.stderr, итог.stderr
    assert (репо / "src" / "lords-frontend.py").read_bytes() == было
