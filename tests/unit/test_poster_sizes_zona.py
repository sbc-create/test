"""Миниатюры обложек на линии Zona: уменьшение, набор ширин и свой адрес.

Повод измеренный (27.10): у `animedia.icu` обложки идут своим адресом с
закрытым набором ширин и уменьшением на витрине, а линия Zona подставляла
ПРЯМУЮ ссылку на источник — в карточку 148 px уезжал оригинал. Поручение
владельца: подобрать размер миниатюр под показ и плотность экрана, не
растягивать мелкие картинки и не отдавать тяжёлые оригиналы повсеместно.

Проверяется поведение, а не наличие строк: функции вырезаются из рантайма и
исполняются на картинке, созданной здесь же, без сети.
"""
from __future__ import annotations

import ast
import html as _html
import io
import os
import pathlib
from urllib.parse import parse_qs

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РАНТАЙМЫ = (
    КОРЕНЬ / "automation" / "host" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm-space" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm12-site" / "src" / "lords-frontend.py",
)
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-poster-sizes-patch.py"


def _механизм(путь: pathlib.Path) -> dict:
    """Константы и функции миниатюр из рантайма — исполнением, а не копией."""
    текст = путь.read_text(encoding="utf-8")
    дерево = ast.parse(текст)
    строки = текст.splitlines()
    нужны = {"_уменьшить_постер", "_ширина_постера", "_набор_постера",
             "_предел_постера"}
    куски = []
    for узел in дерево.body:
        if isinstance(узел, ast.Assign) and any(
                isinstance(ц, ast.Name) and ц.id.startswith("ПОСТЕР_")
                or isinstance(ц, ast.Name) and ц.id.startswith("ПОКАЗ_")
                for ц in узел.targets):
            куски.append("\n".join(строки[узел.lineno - 1:узел.end_lineno]))
        elif isinstance(узел, ast.FunctionDef) and узел.name in нужны:
            куски.append("\n".join(строки[узел.lineno - 1:узел.end_lineno]))
    область = {"os": os, "html": _html, "parse_qs": parse_qs,
               "__name__": "постеры"}
    exec(compile("\n\n".join(куски), str(путь), "exec"), область)  # noqa: S102
    пропущено = нужны - set(область)
    assert not пропущено, f"в рантайме нет: {пропущено}"
    return область


@pytest.fixture(scope="module", params=РАНТАЙМЫ, ids=lambda п: п.parts[-3])
def м(request):
    return _механизм(request.param)


def _картинка(ширина: int, высота: int, формат: str = "WEBP") -> tuple[bytes, str]:
    PIL = pytest.importorskip("PIL.Image")
    кадр = PIL.new("RGB", (ширина, высота))
    # Шум, иначе однотонный кадр сжимается в сотню байт и сравнение размеров
    # перестаёт что-либо значить.
    for x in range(0, ширина, 7):
        for y in range(0, высота, 11):
            кадр.putpixel((x, y), ((x * 7) % 255, (y * 3) % 255, (x + y) % 255))
    буф = io.BytesIO()
    кадр.save(буф, формат, quality=92)
    return буф.getvalue(), ("image/webp" if формат == "WEBP" else "image/jpeg")


def test_оригинал_уменьшается_до_предела(м):
    данные, тип = _картинка(1000, 1500)
    малые, тип2 = м["_уменьшить_постер"](данные, тип)
    assert тип2 == тип
    assert len(малые) < len(данные), "файл не стал меньше"
    PIL = pytest.importorskip("PIL.Image")
    with PIL.open(io.BytesIO(малые)) as im:
        assert im.size[0] == м["ПОСТЕР_МАКС_ШИРИНА"], im.size


def test_запрошенная_ширина_соблюдается(м):
    данные, тип = _картинка(1000, 1500)
    PIL = pytest.importorskip("PIL.Image")
    for w in (160, 240, 320):
        малые, _ = м["_уменьшить_постер"](данные, тип, w)
        with PIL.open(io.BytesIO(малые)) as im:
            assert im.size[0] == w, (w, im.size)


def test_мелкая_картинка_не_растягивается(м):
    """Увеличения нет никогда: обложку 100 px нельзя «подогнать» под 240."""
    данные, тип = _картинка(100, 150)
    малые, тип2 = м["_уменьшить_постер"](данные, тип, 240)
    assert (малые, тип2) == (данные, тип), "мелкий кадр изменён"


def test_горизонтальный_кадр_обрезается_по_центру(м):
    """Кадр шире порога режется по ширине до цели — высота не меняется."""
    данные, тип = _картинка(900, 600)
    малые, _ = м["_уменьшить_постер"](данные, тип)
    PIL = pytest.importorskip("PIL.Image")
    with PIL.open(io.BytesIO(малые)) as im:
        w, h = im.size
    assert w / h == pytest.approx(м["ПОСТЕР_ЦЕЛЬ_ФОРМЫ"], abs=0.02), (w, h)


def test_чужой_формат_не_трогается(м):
    данные, тип = b"GIF89a" + b"\x00" * 40, "image/gif"
    assert м["_уменьшить_постер"](данные, тип) == (данные, тип)


def test_ширина_только_из_набора(м):
    assert м["_ширина_постера"]("w=240") == 240
    assert м["_ширина_постера"]("w=1000") is None, "предел обойдён"
    assert м["_ширина_постера"]("w=240&w=320") is None, "два значения приняты"
    assert м["_ширина_постера"]("") is None
    assert м["_ширина_постера"]("w=abc") is None


def test_набор_только_для_своего_адреса(м):
    чужой = м["_набор_постера"]("https://poster.cdnvideohub.com/x.webp", 200)
    assert чужой == "", "srcset выдан для чужого адреса"
    свой = м["_набор_постера"]("/poster/x.webp", м["ПОКАЗ_ПОЛКА"])
    assert "srcset=" in свой and "sizes=" in свой
    assert "?w=160 160w" in свой and "?w=240 240w" in свой
    # Кандидат шире предела появляется только там, где показ этого требует:
    # у полки максимум показа 240 px, и при двойной плотности ему хватает
    # базового файла 480. Лишний кандидат 720 заставил бы браузер тянуть
    # полмегабайта в карточку шириной 240.
    assert "?w=720" not in свой, свой
    обложка = м["_набор_постера"]("/poster/x.webp", м["ПОКАЗ_ОБЛОЖКА"])
    assert "?w=720 720w" in обложка, обложка
    узкий = м["_набор_постера"]("/poster/x.webp", 164)
    assert "?w=720" not in узкий, узкий


def test_обложки_идут_своим_адресом_на_zona():
    """Иначе уменьшать нечего: чужой файл витрина не меняет."""
    for путь in РАНТАЙМЫ:
        т = путь.read_text(encoding="utf-8")
        assert 'СЕМЕЙСТВО in ("animedia", "zona")' in т, путь


def test_инструмент_повторно_не_ломает():
    """Повторный прогон на приведённом файле ничего не меняет."""
    import subprocess
    import sys
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check",
                        *[str(п) for п in РАНТАЙМЫ]],
                       capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr


def test_заглушка_постера_не_теряет_режим_загрузки():
    """Регресс 27.10: правка f-строк рантайма задела соседнее место, и в
    разметку уходило голое `eager` вместо `loading="eager" fetchpriority="high"`.
    Поймала это проверка витрины в CI, а не прогон фабрики — значит здесь
    такого теста не хватало."""
    import re
    for путь in РАНТАЙМЫ:
        т = путь.read_text(encoding="utf-8")
        import ast as _ast
        дерево = _ast.parse(т)
        строки = т.splitlines()
        узел = next((у for у in _ast.walk(дерево)
                     if isinstance(у, _ast.FunctionDef)
                     and у.name == "заглушка_постера"), None)
        assert узел is not None, путь
        тело = "\n".join(строки[узел.lineno - 1:узел.end_lineno])
        # Режимы приоритета (T334/MOD-149) есть не у всех витрин линии: на
        # zonafilm12.site и в каноне `заглушка_постера` пока знает только
        # ленивую загрузку. Проверяем не наличие режима, а его ЦЕЛОСТНОСТЬ:
        # где режим есть, он обязан нести имя атрибута.
        assert 'loading="lazy"' in тело, путь
        if "fetchpriority" in тело:
            assert 'loading="eager" fetchpriority="high"' in тело, путь
        # Сломалось именно переприсвоение: `загрузка` теряла имя атрибута и
        # становилась голым «eager»/«lazy». Подстановка `{загрузка}` сама по
        # себе законна — в ней лежит целый `loading="…"`.
        плохо = re.search(r'загрузка = "eager" if срочно else "lazy"', тело)
        assert not плохо, (путь, "режим загрузки потерял имя атрибута")
