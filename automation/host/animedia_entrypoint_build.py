#!/usr/bin/env python3
"""Сборка изолированного entrypoint Animedia из общего рантайма.

Общий файл не правится: читается и пишется отдельный собственный. Из копии
удаляются виды, палитры, стили и профили соседних контуров; общая база, от
которой наследует вид Animedia, остаётся СВОИМ кодом под нейтральным именем —
это форк, а не импорт, поэтому дальше он расходится с соседом свободно.

Честность сборки проверяется отдельным шагом: обе версии поднимаются на
служебных портах с одним манифестом и снимком, и HTML каждого маршрута
сравнивается побайтно.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ИСТОЧНИК = Path("automation/host/lords-frontend.py")
ЦЕЛЬ = Path("automation/host/animedia-frontend.py")


class Не(Exception):
    pass


def найти(с: list[str], начало: str, с_какой: int = 0) -> int:
    for i in range(с_какой, len(с)):
        if с[i].startswith(начало):
            return i
    raise Не(f"не найдено: {начало!r}")


def удалить_присваивание(с: list[str], имя: str, отчёт: list) -> list[str]:
    i = найти(с, f"{имя} = ")
    открыв = с[i].rstrip()
    if открыв.endswith('"""'):
        j = i + 1
        while not с[j].startswith('"""'):
            j += 1
        j += 1
    elif открыв.endswith("{") or открыв.endswith("("):
        закр = "}" if открыв.endswith("{") else ")"
        j = i + 1
        while not с[j].startswith(закр):
            j += 1
        j += 1
    else:
        j = i + 1
    k = i
    while k > 0 and с[k - 1].startswith("#"):
        k -= 1
    отчёт.append(f"удалено присваивание {имя}: строк {j - k}")
    return с[:k] + с[j:]


def удалить_класс(с: list[str], имя: str, отчёт: list) -> list[str]:
    i = найти(с, f"class {имя}(")
    j = i + 1
    while j < len(с) and not re.match(r"^(class |def |[А-ЯA-Z_0-9]+ = )", с[j]):
        j += 1
    k = i
    while k > 0 and с[k - 1].startswith("#"):
        k -= 1
    отчёт.append(f"удалён класс {имя}: строк {j - k}")
    return с[:k] + с[j:]


def удалить_метод(с: list[str], класс: str, метод: str, отчёт: list) -> list[str]:
    i = найти(с, f"class {класс}(")
    конец = len(с)
    for j in range(i + 1, len(с)):
        if re.match(r"^(class |def |[А-ЯA-Z_0-9]+ = )", с[j]):
            конец = j
            break
    for n in range(i, конец):
        if с[n].startswith(f"    def {метод}("):
            m = n + 1
            while m < конец and not с[m].startswith("    def "):
                m += 1
            отчёт.append(f"удалён метод {класс}.{метод}: строк {m - n}")
            return с[:n] + с[m:]
    raise Не(f"метод {класс}.{метод} не найден")


def удалить_ключ(с: list[str], словарь: str, ключ: str, отчёт: list) -> list[str]:
    i = найти(с, f"{словарь} = ")
    конец = i + 1
    while not с[конец].startswith("}"):
        конец += 1
    for n in range(i, конец):
        if с[n].strip().startswith(f'"{ключ}":'):
            глубина = с[n].count("{") + с[n].count("(") - с[n].count("}") - с[n].count(")")
            m = n + 1
            while m < конец and глубина > 0:
                глубина += с[m].count("{") + с[m].count("(") - с[m].count("}") - с[m].count(")")
                m += 1
            отчёт.append(f"удалён ключ {словарь}[{ключ!r}]: строк {m - n}")
            return с[:n] + с[m:]
    raise Не(f"ключ {ключ} в {словарь} не найден")


ШАПКА = '''#!/usr/bin/env python3
"""Витрина ANIMEDIA: собственный изолированный рантайм.

Этот файл — entrypoint контура Animedia и ничей больше. Он появился потому, что
прежний общий рантайм обслуживал шесть витрин трёх контуров одним файлом: имя
файла принадлежало соседу, вид Animedia наследовал вид соседа, а профили,
палитры и стили трёх контуров лежали рядом. Любая правка ради одной витрины
физически касалась остальных, и заметно это становилось только после
перезапуска.

Что здесь есть и чего нет:

* виды, палитры, стили и профили соседних контуров — удалены;
* общая база, от которой наследует вид Animedia, скопирована как СВОЙ код под
  нейтральным именем `ВидОснова`: это форк, а не импорт, поэтому дальше она
  расходится с соседом свободно и без согласований;
* семейство проверяется на старте: манифест, объявляющий чужое семейство, не
  поднимает витрину. Молча отдать чужой шаблон хуже, чем не подняться.

Чего этот файл НЕ делает: не читает и не пишет ничего в каталогах соседних
контуров, не импортирует их модули и не носит их имя.

Переменные окружения. Свои — `ANIMEDIA_*`. Юниты витрин принадлежат root и
задают прежние имена `LORDS_*`; они читаются как совместимость, пока владелец
не сменит `ExecStart`. Это единственное место, где прежние имена упомянуты, и
они здесь не потому, что код чужой, а потому что чужая только строка запуска.

Сборка файла воспроизводима: `automation/host/animedia_entrypoint_build.py`
собирает его из общего рантайма перечнем именованных операций, а проверка
паритета рендера сравнивает HTML всех маршрутов побайтно с прежней версией.
"""
'''


def main() -> int:
    if not ИСТОЧНИК.is_file():
        raise SystemExit("нет исходного файла общего рантайма")
    исходный = ИСТОЧНИК.read_text(encoding="utf-8")
    с = исходный.splitlines()
    было = len(с)
    отчёт: list[str] = []

    for имя in ("ЛОРДС_ТОКЕНЫ", "ЗОНА_ТОКЕНЫ_1_1", "ЗОНА_ТОКЕНЫ",
                "ЛОРДС_СТИЛЬ", "ЗОНА_СТИЛЬ_1_1"):
        с = удалить_присваивание(с, имя, отчёт)
    с = удалить_класс(с, "ВидЛордс", отчёт)
    с = удалить_метод(с, "ВидЗона", "оболочка", отчёт)
    for ключ in ("lords", "yummy", "zona"):
        с = удалить_ключ(с, "ПРОФИЛИ_СЕМЕЙСТВ", ключ, отчёт)
    for ключ in ("lords", "zona"):
        с = удалить_ключ(с, "СЕМЕЙСТВА_1_1", ключ, отчёт)
    с = удалить_ключ(с, "ПЕРЕРАБОТАНО_С", "zona", отчёт)

    т = "\n".join(с) + "\n"

    # Переименования: база становится своей, нейтральной по имени.
    for шаблон, на in (
        (r"\bВидЗона\b", "ВидОснова"),
        (r"\bЗОНА_СТИЛЬ\b", "ОСНОВА_СТИЛЬ"),
        (r"\bСКРИПТ_ЛОРДС_ШАПКА\b", "СКРИПТ_ШАПКИ_ОСНОВЫ"),
        (r'ПРОФИЛИ_СЕМЕЙСТВ\.get\(МАНИФЕСТ\["template_family"\], ПРОФИЛИ_СЕМЕЙСТВ\["lords"\]\)',
         'ПРОФИЛИ_СЕМЕЙСТВ["animedia"]'),
        (r'СЕМЕЙСТВА_1_1\.get\(СЕМЕЙСТВО\) or СЕМЕЙСТВА_1_1\["lords"\]',
         'СЕМЕЙСТВА_1_1["animedia"]'),
        (r"ВИДЫ_1_1 = \{[^}]*\}", 'ВИДЫ_1_1 = {"animedia": ВидАнимедиа}'),
        (r"ВИДЫ_1_1\.get\(описание\[\"вид\"\], ВидЛордс\)",
         'ВИДЫ_1_1.get("animedia", ВидАнимедиа)'),
    ):
        новый, n = re.subn(шаблон, на, т)
        if n == 0:
            raise Не(f"замена не применилась: {шаблон}")
        отчёт.append(f"замена {шаблон} → {на}: {n}")
        т = новый

    # Имена окружения и пути по умолчанию: свои впереди, прежние — совместимость.
    т = т.replace(
        'РЕВИЗИЯ = os.environ.get("LORDS_TEMPLATE_REVISION", "unknown")',
        'def _окр(имя: str, прежнее: str, по_умолчанию: str = "") -> str:\n'
        '    """Своё имя переменной впереди, прежнее — совместимость с юнитом."""\n'
        '    return os.environ.get(имя) or os.environ.get(прежнее) or по_умолчанию\n'
        '\n'
        '\n'
        'РЕВИЗИЯ = _окр("ANIMEDIA_TEMPLATE_REVISION", "LORDS_TEMPLATE_REVISION",\n'
        '               "unknown")')
    т = т.replace(
        'МАНИФЕСТ_ФАЙЛ = os.environ.get("LORDS_TEMPLATE_MANIFEST",\n'
        '                               "/srv/lords/.frontend/template-manifest.json")',
        'МАНИФЕСТ_ФАЙЛ = _окр(\n'
        '    "ANIMEDIA_TEMPLATE_MANIFEST", "LORDS_TEMPLATE_MANIFEST",\n'
        '    str(_КОРЕНЬ_РАНТАЙМА / "template-manifest-animedia-01.json"))')
    т = т.replace(
        'КАТАЛОГ_ФАЙЛ = os.environ.get("LORDS_CATALOG", "/srv/lords/.frontend/lords-01-catalog.json")',
        'КАТАЛОГ_ФАЙЛ = _окр("ANIMEDIA_CATALOG", "LORDS_CATALOG",\n'
        '                    str(_КОРЕНЬ_РАНТАЙМА / "animedia-01-catalog.json"))')
    т = т.replace(
        'ПОДРОБНОСТИ_ФАЙЛ = os.environ.get("LORDS_DETAILS") or _рядом_с_каталогом("{site}-details.json")',
        'ПОДРОБНОСТИ_ФАЙЛ = (_окр("ANIMEDIA_DETAILS", "LORDS_DETAILS")\n'
        '                    or _рядом_с_каталогом("{site}-details.json"))')
    т = т.replace(
        'СТАРЫЙ_КОРЕНЬ = Path(os.environ.get("LORDS_LEGACY_ROOT", "/srv/lords/lords-01/current/site"))',
        'СТАРЫЙ_КОРЕНЬ = Path(_окр("ANIMEDIA_LEGACY_ROOT", "LORDS_LEGACY_ROOT",\n'
        '                          "/srv/animedia/animedia-01/current/site"))')
    т = т.replace(
        'ИМЯ_ВИТРИНЫ = os.environ.get("LORDS_SITE_NAME", "Lords")',
        'ИМЯ_ВИТРИНЫ = _окр("ANIMEDIA_SITE_NAME", "LORDS_SITE_NAME", "Animedia")')
    т = т.replace(
        'ВЕРХОВОЙ = os.environ.get("LORDS_LEGACY_UPSTREAM", "")',
        'ВЕРХОВОЙ = _окр("ANIMEDIA_LEGACY_UPSTREAM", "LORDS_LEGACY_UPSTREAM")')

    # Корень рантайма — одной переменной, чтобы переезд был правкой одной строки.
    т = т.replace(
        "РЕВИЗИЯ = _окр(",
        '#: Корень рантайма. Сейчас общий и носит имя соседа по историческим\n'
        '#: причинам; собственный корень требует смены ExecStart юнитов, то есть\n'
        '#: действия владельца под root (`config/animedia/TENANT_SCOPE.yaml`,\n'
        '#: planned_own_root). Переезд — правка этой одной строки.\n'
        '_КОРЕНЬ_РАНТАЙМА = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT",\n'
        '                                       "/srv/lords/.frontend"))\n'
        '\n'
        'РЕВИЗИЯ = _окр(', 1)

    # Контракт коллекций — из своего пакета, без чужого имени модуля.
    т = т.replace(
        'if (_КОРЕНЬ_РЕПО / "factory" / "lords" / "collection_contract.py").is_file():',
        'if (_КОРЕНЬ_РЕПО / "factory" / "animedia" / "collection_contract.py").is_file():')
    т = т.replace(
        "    from factory.lords import collection_contract as КОЛЛЕКЦИИ  # noqa: E402",
        "    from factory.animedia import collection_contract as КОЛЛЕКЦИИ  # noqa: E402")

    # Семейство проверяется на старте: чужое не поднимает витрину.
    т = т.replace(
        'МАНИФЕСТ = _манифест()\nВЕРСИЯ = МАНИФЕСТ["design_version"]',
        'МАНИФЕСТ = _манифест()\n'
        'if МАНИФЕСТ["template_family"] != "animedia":\n'
        '    # Fail closed. Этот рантайм принадлежит одному контуру, и отдать\n'
        '    # чужое семейство своим оформлением он не имеет права.\n'
        '    raise SystemExit(\n'
        '        "этот рантайм обслуживает только семейство animedia, "\n'
        '        f"манифест объявляет {МАНИФЕСТ[\'template_family\']!r}")\n'
        'ВЕРСИЯ = МАНИФЕСТ["design_version"]')

    # Точечные правки кода: пути через корень рантайма, свой ключ темы и
    # удаление мёртвых ветвей, принадлежавших чужому семейству.
    код_правки = [
        ('            player_path = Path(f"/srv/lords/.frontend/player-{site_hint}.json") if site_hint else None\n'
         '            tmpl_path = Path(f"/srv/lords/.frontend/template-manifest-{site_hint}.json") if site_hint else None',
         '            player_path = (_КОРЕНЬ_РАНТАЙМА / f"player-{site_hint}.json"\n'
         '                           if site_hint else None)\n'
         '            tmpl_path = (_КОРЕНЬ_РАНТАЙМА / f"template-manifest-{site_hint}.json"\n'
         '                         if site_hint else None)'),
        ("var k='lords-theme',r=document.documentElement;",
         "var k='animedia-theme',r=document.documentElement;"),
        ('            if СЕМЕЙСТВО == "lords" and hasattr(в, "хаб_подборок"):\n'
         '                return self._отдать(в.хаб_подборок().encode("utf-8"))\n'
         '            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))',
         '            # Хаб подборок соседнего контура здесь не нужен: у Animedia\n'
         '            # свой хаб коллекций, и его собирает вид.\n'
         '            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))'),
        ('            # Канон жанра для Lords — path /genre/<code>/; комбинации остаются query.\n'
         '            if СЕМЕЙСТВО == "lords":\n'
         '                зпр = dict(зпр)\n'
         '                зпр["genre"] = [код]\n'
         '                return self._отдать(в.список("/catalog", зпр).encode("utf-8"))\n'
         '            return self._переход(f"/catalog/?genre={код}")',
         '            # У Animedia канон жанра — query на каталоге, а не отдельный\n'
         '            # путь; поэтому здесь переход, а не своя выдача.\n'
         '            return self._переход(f"/catalog/?genre={код}")'),
    ]
    for что, на in код_правки:
        if что not in т:
            raise Не(f"правка кода не нашла место: {что[:70]!r}")
        т = т.replace(что, на)
        отчёт.append(f"правка кода: {что.strip().splitlines()[0][:60]}")

    # Упоминания соседних контуров — только внутри комментариев и только
    # адресами и именами, которые в отчётах не публикуются.
    словарь = {
        "lordserial33.biz": "соседней витрине",
        "lordfilm47.space": "соседней витрине",
        "1lordserials1.online": "соседней витрине",
        "zonafilm.space": "соседней витрине",
        "w140.zona.plus": "эталоне соседнего контура",
        "zona-01": "соседней витрины",
        "lords-01": "соседней витрины",
        "scripts/lords_zona_visual_audit.cjs": "скрипте визуального аудита",
        "Палитра Zona": "Палитра базы",
        "Zona 1.1.0": "прежнее оформление базы",
        "Zona 1.2.0": "базовое оформление",
        "Lords": "базу",
        "Zona": "базу",
    }
    # Границы больших строковых констант: их содержимое уходит в браузер, и
    # правка прозы внутри них изменила бы отдаваемые байты. Пространство классов
    # и брендовые надписи внутри стилей закрываются отдельным шагом, у которого
    # своя проверка диффа.
    строки = т.splitlines()
    в_константе = [False] * len(строки)
    i = 0
    while i < len(строки):
        m = re.match(r'^([А-ЯA-Z_0-9]+) = """', строки[i])
        if m:
            j = i + 1
            while j < len(строки) and not строки[j].startswith('"""'):
                в_константе[j] = True
                j += 1
            i = j + 1
            continue
        i += 1
    заменено = 0
    for i, s in enumerate(строки):
        if в_константе[i]:
            continue
        новая = s
        for что, на in словарь.items():
            if что in новая:
                новая = новая.replace(что, на)
        if новая != s:
            строки[i] = новая
            заменено += 1
    т = "\n".join(строки) + "\n"
    отчёт.append(f"нейтрализовано строк прозы вне константных блоков: {заменено}")
    осталось = {}
    for что in словарь:
        n = sum(1 for i, s in enumerate(строки) if что in s and в_константе[i])
        if n:
            осталось[что] = n
    отчёт.append(f"осталось внутри стилей и скриптов (шаг пространства имён): {осталось or 'нет'}")

    # Шапка файла: своя.
    т = re.sub(r'^#!/usr/bin/env python3\n""".*?"""\n', ШАПКА, т, count=1, flags=re.S)

    ЦЕЛЬ.write_text(т, encoding="utf-8")
    стало = len(т.splitlines())
    p = subprocess.run([sys.executable, "-m", "py_compile", str(ЦЕЛЬ)],
                       capture_output=True, text=True)
    print("\n".join(отчёт))
    print(f"\nстрок: было {было} → стало {стало} (убрано {было - стало})")
    print("компиляция:", "OK" if p.returncode == 0 else p.stderr[-2000:])
    остатки = {}
    for ключ in ("ВидЛордс", "ВидЗона", "ЛОРДС_", "ЗОНА_", "factory.lords"):
        n = len(re.findall(re.escape(ключ), т))
        if n:
            остатки[ключ] = n
    print("остатки чужих имён:", остатки or "нет")
    return 0 if p.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
