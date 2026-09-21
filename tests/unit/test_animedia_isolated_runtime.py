"""Изолированный рантайм ANIMEDIA: в нём нет чужого и он не отдаёт чужое.

Изоляция ценна только пока её держит проверка. Без этих тестов первая же
правка вернёт в файл чужой вид, чужой профиль или импорт из пакета с чужим
именем — и заметно это станет после выкладки, как уже было.

Проверяется три свойства:

1. в файле нет кода, имён и импортов соседних контуров;
2. манифест чужого семейства не поднимает витрину (fail closed);
3. форк честен: рендер всех маршрутов побайтно совпал с прежним рантаймом —
   запись проверки лежит в доказательствах и читается здесь, а не
   пересказывается.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
РАНТАЙМ = ROOT / "automation/host/animedia-frontend.py"
КОНТРАКТ = ROOT / "config/animedia/TENANT_SCOPE.yaml"
ЭКВИВАЛЕНТ = (ROOT / "artifacts/evidence/animedia-original-parity-01"
              / "01-isolation" / "RENDER_EQUIVALENCE.json")
#: Коммит переноса: именно к нему относится доказательство побайтового
#: совпадения рендера. Позднейшие правки под оригинал — уже другая история.
ИЗОЛЯЦИЯ = "9f204b2"

#: Префиксы соседних контуров. Единственное место, где они перечислены, — так
#: же, как в контракте изоляции: машинный список, а не текст отчёта.
ЧУЖИЕ_ПРЕФИКСЫ = ("lordfilm", "lordserial", "zonafilm", "yummyani")


@pytest.fixture(scope="module")
def текст() -> str:
    assert РАНТАЙМ.is_file(), "нет изолированного рантайма Animedia"
    return РАНТАЙМ.read_text(encoding="utf-8")


def test_рантайм_компилируется():
    p = subprocess.run([sys.executable, "-m", "py_compile", str(РАНТАЙМ)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_нет_видов_и_палитр_соседних_контуров(текст):
    for имя in ("ВидЛордс", "ВидЗона", "ЛОРДС_СТИЛЬ", "ЗОНА_СТИЛЬ",
                "ЛОРДС_ТОКЕНЫ", "ЗОНА_ТОКЕНЫ"):
        assert имя not in текст, имя


def test_база_переименована_в_нейтральную(текст):
    # База осталась своим кодом под нейтральным именем: это форк, а не импорт.
    assert "class ВидОснова(Вид):" in текст
    assert "class ВидАнимедиа(ВидОснова):" in текст
    # Базовый лист стилей удалён: витрина собирает оформление только своим,
    # и держать рядом неиспользуемые 318 строк чужого вида незачем.
    assert "ОСНОВА_СТИЛЬ" not in текст


def test_реестр_видов_только_свой(текст):
    assert 'ВИДЫ_1_1 = {"animedia": ВидАнимедиа}' in текст
    профили = re.search(r"ПРОФИЛИ_СЕМЕЙСТВ = \{(.*?)\n\}", текст, re.S).group(1)
    assert set(re.findall(r'^\s{4}"([a-z]+)":', профили, re.M)) == {"animedia"}
    семейства = re.search(r"СЕМЕЙСТВА_1_1 = \{(.*?)\n\}", текст, re.S).group(1)
    assert set(re.findall(r'^\s{4}"([a-z]+)":', семейства, re.M)) == {"animedia"}


def test_нет_импортов_из_пакета_с_чужим_именем(текст):
    assert "factory.lords" not in текст
    assert "from factory.animedia import collection_contract" in текст
    assert (ROOT / "factory/animedia/collection_contract.py").is_file()


def test_нет_адресов_соседних_витрин(текст):
    for префикс in ЧУЖИЕ_ПРЕФИКСЫ:
        assert префикс not in текст, префикс


def test_брендовых_надписей_соседа_не_осталось(текст):
    """Долг изоляции закрыт: вместе с мёртвым базовым стилем ушли и они."""
    долг = [n for n, s in enumerate(текст.splitlines(), 1)
            if "Zona" in s or "Lords" in s]
    assert долг == [], f"вернулись брендовые надписи соседа: строки {долг}"


def test_корень_рантайма_вынесен_одной_строкой(текст):
    """Переезд на собственный корень обязан быть правкой одной строки."""
    assert 'os.environ.get("ANIMEDIA_RUNTIME_ROOT"' in текст
    # Путей в общий корень, набранных вручную, быть не должно.
    руками = [s for s in re.findall(r'"/srv/[^"]+"', текст)
              if "/srv/lords" in s and "ANIMEDIA_RUNTIME_ROOT" not in s]
    assert руками == ['"/srv/lords/.frontend"'], руками


def test_свои_имена_переменных_окружения_впереди(текст):
    assert 'def _окр(' in текст
    for своё in ("ANIMEDIA_TEMPLATE_MANIFEST", "ANIMEDIA_CATALOG",
                 "ANIMEDIA_SITE_NAME", "ANIMEDIA_TEMPLATE_REVISION"):
        assert своё in текст, своё


def test_чужое_семейство_не_поднимает_витрину(tmp_path):
    """Fail closed: отдать чужое семейство своим оформлением нельзя."""
    манифест = tmp_path / "m.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "neighbour",
        "design_version": "1.2.4", "source_commit": "0" * 40,
        "build_id": "x", "artifact_sha256": "0" * 64, "profile": "p",
        "built_at": "2026-09-21T00:00:00Z"}), encoding="utf-8")
    p = subprocess.run([sys.executable, str(РАНТАЙМ), "--port", "0"],
                       capture_output=True, text=True, cwd=str(ROOT),
                       env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                            "ANIMEDIA_TEMPLATE_MANIFEST": str(манифест)},
                       timeout=120)
    assert p.returncode != 0
    assert "только семейство animedia" in (p.stdout + p.stderr)


def test_запись_проверки_рендера_доказывает_честность_переноса():
    """Перенос был байт-в-байт — это доказательство заморожено на своём коммите.

    Позже витрину сознательно меняли под оригинал, поэтому сверять запись с
    сегодняшним файлом бессмысленно: она относится к моменту переноса и
    доказывает, что изоляция ничего не сломала. За сегодняшнюю геометрию
    отвечают тесты паритета.
    """
    assert ЭКВИВАЛЕНТ.is_file(), "нет записи проверки эквивалентности рендера"
    з = json.loads(ЭКВИВАЛЕНТ.read_text(encoding="utf-8"))
    assert з["all_identical"] is True
    assert з["all_codes_match"] is True
    assert len(з["routes"]) >= 15
    сверка = subprocess.run(
        ["git", "show", f"{ИЗОЛЯЦИЯ}:automation/host/animedia-frontend.py"],
        cwd=str(ROOT), capture_output=True)
    assert сверка.returncode == 0, "коммит переноса не найден"
    import hashlib
    assert з["isolated_sha256"] == hashlib.sha256(сверка.stdout).hexdigest(), (
        "запись эквивалентности не относится к коммиту переноса")


def test_контракт_изоляции_называет_свой_entrypoint():
    т = КОНТРАКТ.read_text(encoding="utf-8")
    assert "automation/host/animedia-*" in т
    assert "factory/animedia/**" in т
    assert "cross_tenant_imports: true" in т


def test_сборщик_рантайма_лежит_рядом_и_воспроизводим():
    сборщик = ROOT / "automation/host/animedia_entrypoint_build.py"
    assert сборщик.is_file(), "сборка изолированного рантайма должна быть воспроизводимой"
    т = сборщик.read_text(encoding="utf-8")
    assert "animedia-frontend.py" in т
