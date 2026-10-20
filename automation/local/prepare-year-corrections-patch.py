#!/usr/bin/env python3
"""Точечный патч поправок года для УСТАНОВЛЕННОГО издателя каталога.

Зачем патч, а не копия файла. Установленный издатель
(`/srv/site-factory/repo/factory/lords/nova_publish.py`, 587 строк) отстаёт от
ветки на три несвязанных правки: признак обогащения (`enrichment`), поле
`updated_at` для `lastmod` карты сайта и коды нехватки оценок. Копия файла
привезла бы их вместе с поправками года — ровно так однажды и уехала правка
постеров вместе с чужим изменением окон подборок. Поэтому патч несёт ТОЛЬКО
поправки года и вида.

Что патч делает:

1. кладёт рядом новый файл `factory/lords/year_corrections.py` (загрузка и
   применение сверенных поправок);
2. в `собрать_сайт` добавляет загрузку набора поправок, применение к `year` и
   `type`, поле `year_source` в карточке и три счётчика в статистику
   (`year_corrected`, `type_corrected`, `year_correction_stale`), а при
   отсутствии файла поправок — `year_corrections_unavailable`.

Чего патч НЕ делает: не меняет порядок записей, не трогает постеры, названия,
описания, сезоны, оценки и карту сайта.

    python3 automation/local/prepare-year-corrections-patch.py            # собрать патч
    python3 automation/local/prepare-year-corrections-patch.py --verify   # проверить применимость
"""
from __future__ import annotations

import argparse
import difflib
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИЗДАТЕЛЬ = Path("/srv/site-factory/repo/factory/lords/nova_publish.py")
ПАТЧ = КОРЕНЬ / "docs" / "handoff" / "year-corrections-nova-publish.patch"
МОДУЛЬ = КОРЕНЬ / "factory" / "lords" / "year_corrections.py"

#: (что искать, на что заменить). Каждый якорь обязан найтись РОВНО один раз:
#: иначе патч собран против другого файла, и это отказ, а не предупреждение.
ПРАВКИ: list[tuple[str, str]] = [
    ("import hashlib\nimport json",
     "import hashlib\nimport importlib.util\nimport json"),
    ("import re\nimport unicodedata",
     "import re\nimport sys\nimport unicodedata"),
    ("""                 читатель=None, только_аниме: bool = False,
                 аниме_видом: bool = False) -> tuple[dict, dict, dict]:""",
     """                 читатель=None, только_аниме: bool = False,
                 аниме_видом: bool = False,
                 поправки_года: dict | None = None) -> tuple[dict, dict, dict]:"""),
    ("""    прежние_подробности = прежние_подробности or {}
    читать = читатель or _прочитать_деталь""",
     """    прежние_подробности = прежние_подробности or {}
    читать = читатель or _прочитать_деталь
    # Поправки года и вида, СВЕРЕННЫЕ с источником по id самой записи.
    # Год приезжает из ответа поставщика и у продолжений несёт дату ПЕРВОЙ
    # части франшизы: у `rukovodstvo-soten-demonov-4` поставщик даёт 2020
    # (`premiere_date` 2020-04-25), источник — `aired_on` 2024-02-23. Снимок
    # витрины приезжает доставкой целиком и правку в себе не удержит, ответ
    # поставщика нам не принадлежит, поэтому поправка живёт в репозитории и
    # применяется здесь. Пустой набор — законное состояние.
    модуль_поправок = _модуль_поправок()
    if поправки_года is not None:
        поправки = поправки_года
    elif модуль_поправок is None:
        поправки = {}
    else:
        поправки = модуль_поправок.загрузить()"""),
    ('''          "kept_previous_poster": 0, "kept_previous_title": 0}''',
     '''          "kept_previous_poster": 0, "kept_previous_title": 0,
          # Сколько значений заменено сверенной поправкой и сколько поправок
          # отступило, потому что поставщик сменил значение после замера.
          # Второе число важнее первого: оно означает «пора перемерить».
          "year_corrected": 0, "type_corrected": 0,
          "year_correction_stale": 0}
    if модуль_поправок is None:
        # Видно в отчёте публикации: механизм поправок не доехал до этого
        # корня, и год остался поставщицким. Тишины здесь быть не должно.
        ст["year_corrections_unavailable"] = str(_ПУТЬ_ПОПРАВОК)'''),
    ("""        название = п.name or запись.get("name") or ""
        слаг = реестр.слаг(ид, название)
        вид = _вид(запись, жанры, страны, аниме_видом=аниме_видом)""",
     """        название = п.name or запись.get("name") or ""
        слаг = реестр.слаг(ид, название)

        if поправки and модуль_поправок is not None:
            год, тип, источник_года = модуль_поправок.применить(
                поправки, д["id"], д.get("year"), д.get("type"))
        else:
            год, тип, источник_года = д.get("year"), д.get("type"), "provider"
        if источник_года == "provider/stale-correction":
            ст["year_correction_stale"] += 1
        elif источник_года != "provider":
            if год != д.get("year"):
                ст["year_corrected"] += 1
            if тип != д.get("type"):
                ст["type_corrected"] += 1
        # Вид витрины считается по ИСПРАВЛЕННОМУ типу: иначе заголовок карточки
        # и её вид в сетке расходились бы между собой.
        запись_для_вида = (запись if тип == запись.get("type")
                           else {**запись, "type": тип})
        вид = _вид(запись_для_вида, жанры, страны, аниме_видом=аниме_видом)"""),
    ('''            "kind": вид,
            "year": д.get("year"),''',
     '''            "kind": вид,
            "year": год,'''),
    ('''            "type": д["type"],
            "year": д["year"],''',
     '''            "type": тип,
            "year": год,
            # Откуда взят год: `provider` — как отдал поставщик;
            # `<адрес источника> (<дата замера>)` — сверенная поправка;
            # `provider/stale-correction` — поправка есть, но поставщик сменил
            # значение после замера, и она отступила. Поле нужно затем, чтобы
            # исправленный год не выглядел подстановкой: у него виден источник.
            "year_source": источник_года,'''),
]

ЗАГРУЗЧИК = '''
#: Модуль сверенных поправок года и вида лежит РЯДОМ с этим файлом.
#: Берётся по пути, а не пакетным импортом: проверка установленного состояния
#: подгружает этот модуль в корне установленного издателя, где пакет
#: `factory.lords` ещё не содержит поправок, и пакетный импорт там падает.
_ПУТЬ_ПОПРАВОК = Path(__file__).resolve().parent / "year_corrections.py"
_ПОПРАВКИ_МОДУЛЬ: Any = None


def _модуль_поправок():
    """Модуль поправок или None, если файла рядом нет.

    None — не «поправок нет», а «механизм не доехал», и этот случай обязан
    быть ВИДЕН: он попадает в статистику публикации как
    `year_corrections_unavailable`.
    """
    global _ПОПРАВКИ_МОДУЛЬ
    if _ПОПРАВКИ_МОДУЛЬ is None:
        if not _ПУТЬ_ПОПРАВОК.exists():
            return None
        спец = importlib.util.spec_from_file_location(
            "factory_lords_year_corrections", _ПУТЬ_ПОПРАВОК)
        модуль = importlib.util.module_from_spec(спец)
        # Модуль обязан лежать в sys.modules ДО исполнения: внутри он
        # объявляет dataclass при отложенных аннотациях, а тот ищет свой
        # модуль по имени.
        sys.modules[спец.name] = модуль
        спец.loader.exec_module(модуль)
        _ПОПРАВКИ_МОДУЛЬ = модуль
    return _ПОПРАВКИ_МОДУЛЬ

'''


def переписать(текст: str) -> str:
    """Применить правки к тексту установленного файла. Якорь обязан быть один."""
    итог = текст
    for искать, заменить in ПРАВКИ:
        сколько = итог.count(искать)
        if сколько != 1:
            строки = искать.splitlines()[0][:70]
            raise SystemExit(
                f"якорь встречается {сколько} раз вместо одного: {строки!r}."
                " Патч собран против другого файла — собирать его заново,"
                " а не подгонять по похожим местам.")
        итог = итог.replace(искать, заменить)
    маркер = "\ndef _вид("
    if итог.count(маркер) != 1:
        raise SystemExit("не найдено место для загрузчика поправок")
    return итог.replace(маркер, ЗАГРУЗЧИК + "\ndef _вид(", 1)


def собрать(исходный: Path) -> tuple[str, str]:
    было = исходный.read_text(encoding="utf-8")
    стало = переписать(было)
    патч = "".join(difflib.unified_diff(
        было.splitlines(keepends=True), стало.splitlines(keepends=True),
        fromfile="a/factory/lords/nova_publish.py",
        tofile="b/factory/lords/nova_publish.py"))
    return стало, патч


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--source", default=str(ИЗДАТЕЛЬ))
    р.add_argument("--verify", action="store_true")
    а = р.parse_args(аргв)

    исходный = Path(а.source)
    if not исходный.is_file():
        print(f"НЕ СОБРАНО: нет установленного файла {исходный}")
        return 2
    стало, патч = собрать(исходный)
    ПАТЧ.parent.mkdir(parents=True, exist_ok=True)
    ПАТЧ.write_text(патч, encoding="utf-8")
    print(f"патч: {ПАТЧ} ({len(патч.splitlines())} строк)")
    print(f"новый файл рядом: factory/lords/year_corrections.py"
          f" ({len(МОДУЛЬ.read_text(encoding='utf-8').splitlines())} строк)")

    if а.verify:
        with tempfile.TemporaryDirectory() as врем:
            к = Path(врем) / "nova_publish.py"
            к.write_text(стало, encoding="utf-8")
            try:
                py_compile.compile(str(к), doraise=True)
            except py_compile.PyCompileError as ош:
                print(f"ПРОВЕРКА НЕ ПРОЙДЕНА: исправленный файл не компилируется:"
                      f" {ош}")
                return 1
            print("исправленный файл компилируется")

            # Патч обязан приклеиваться к установленному файлу тем же `patch`,
            # которым его будут применять, а не только «в уме».
            проба = Path(врем) / "proba"
            проба.mkdir()
            (проба / "factory").mkdir()
            (проба / "factory" / "lords").mkdir()
            shutil.copy(исходный, проба / "factory/lords/nova_publish.py")
            г = subprocess.run(["patch", "-p1", "--dry-run", "-i", str(ПАТЧ)],
                               cwd=проба, capture_output=True, text=True)
            print(г.stdout.strip() or г.stderr.strip())
            if г.returncode != 0:
                print("ПРОВЕРКА НЕ ПРОЙДЕНА: патч не прикладывается")
                return 1
            print("патч прикладывается к установленному файлу (--dry-run)")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
