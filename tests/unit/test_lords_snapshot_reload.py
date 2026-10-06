"""Перечитывание снимка витрины lords на месте (automation/host/lords_snapshot_reload.py).

Поддельное ядро с тем же интерфейсом, что у lords-frontend.py: `Данные`,
`Подробности`, `построить_индекс`, `Обработчик`, пути файлов. Проверяется:
изменение подхватывается только после того, как файл перестал меняться;
испорченный или пустой файл не подменяет рабочий снимок; проход согласования
серий, шедший во время подмены, переносится на новый объект.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]


def _модуль():
    спец = importlib.util.spec_from_file_location(
        "lords_snapshot_reload", КОРЕНЬ / "automation/host/lords_snapshot_reload.py")
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def _ядро(tmp_path):
    каталог = tmp_path / "catalog.json"
    подробности = tmp_path / "details.json"
    каталог.write_text(json.dumps({"items": [{"slug": "a"}]}))
    подробности.write_text(json.dumps({"details": {"a": {"seasons": [{"n": 1, "avail": 1}]}}}))

    class Данные:
        def __init__(self, путь):
            self.items = json.loads(Path(путь).read_text())["items"]

    class Подробности:
        def __init__(self, путь):
            self.path = str(путь)
            try:
                self.записи = json.loads(Path(путь).read_text()).get("details") or {}
            except ValueError:
                self.записи = {}
            self.покрытие = len(self.записи)

    class Обработчик:
        pass

    ядро = types.SimpleNamespace(
        КАТАЛОГ_ФАЙЛ=str(каталог), ПОДРОБНОСТИ_ФАЙЛ=str(подробности),
        Данные=Данные, Подробности=Подробности, Обработчик=Обработчик,
        построить_индекс=lambda д, п: {"по_slug": {з["slug"]: з for з in д.items}})
    Обработчик.данные = Данные(каталог)
    Обработчик.подробности = Подробности(подробности)
    Обработчик.индекс = ядро.построить_индекс(Обработчик.данные, Обработчик.подробности)
    return ядро, каталог, подробности


def _записать(путь: Path, данные: dict, шаг: int) -> None:
    путь.write_text(json.dumps(данные))
    st = путь.stat()
    os.utime(путь, ns=(st.st_atime_ns, st.st_mtime_ns + шаг * 1_000_000_000))


def test_новые_серии_подхватываются_без_перезапуска(tmp_path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(sys, "argv", ["x"])               # без порта: прогрева нет
    ядро, _, подробности = _ядро(tmp_path)
    п = м.Перечитывание(ядро, пауза=0)
    прежние = ядро.Обработчик.подробности
    assert п.проверить() is False                         # ничего не менялось
    _записать(подробности, {"details": {"a": {"seasons": [{"n": 1, "avail": 2}]}}}, 5)
    assert п.проверить() is False                         # первая встреча: ждём, пока дописан
    assert ядро.Обработчик.подробности is прежние
    assert п.проверить() is True                          # метка устоялась: подменено
    assert ядро.Обработчик.подробности is not прежние
    assert ядро.Обработчик.подробности.записи["a"]["seasons"][0]["avail"] == 2
    assert п.перечитываний == 1 and п.отказов == 0


def test_испорченный_или_пустой_снимок_не_подменяет_рабочий(tmp_path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(sys, "argv", ["x"])
    ядро, каталог, подробности = _ядро(tmp_path)
    п = м.Перечитывание(ядро, пауза=0)
    прежние = ядро.Обработчик.подробности
    подробности.write_text("{обрыв")
    st = подробности.stat()
    os.utime(подробности, ns=(st.st_atime_ns, st.st_mtime_ns + 7_000_000_000))
    п.проверить()
    assert п.проверить() is False
    assert ядро.Обработчик.подробности is прежние         # пустоты вместо данных нет
    assert п.отказов == 1 and "нет записей" in п.последний_отказ
    assert п.проверить() is False and п.отказов == 1      # тот же файл не долбится каждые 10 с
    _записать(каталог, {"items": []}, 9)
    п.проверить()
    assert п.проверить() is False
    assert ядро.Обработчик.данные.items == [{"slug": "a"}]


def test_проход_согласования_переносится_на_новый_снимок(tmp_path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(sys, "argv", ["x"])
    ядро, _, подробности = _ядро(tmp_path)

    def наложить(записи, наложение):
        for слаг, з in наложение.items():
            if слаг in записи:
                записи[слаг]["seasons"][0]["nums"] = з["nums"]
        return len(наложение)

    class Согласование:
        def __init__(self):
            self.наложение = {}

        def _сохранить_наложение(self, ревизия):
            return True

    monkeypatch.setitem(sys.modules, "episode_sync",
                        types.SimpleNamespace(Согласование=Согласование, наложить=наложить))
    п = м.Перечитывание(ядро, пауза=0)
    ядро.ПЕРЕЧИТЫВАНИЕ_СНИМКА = п
    assert м._связать_с_согласованием(ядро, п)
    согл = Согласование()
    _записать(подробности, {"details": {"a": {"seasons": [{"n": 1, "avail": 3}]}}}, 5)
    п.проверить()
    assert п.проверить() is True
    # Проход шёл на прежнем объекте и записал наложение уже после подмены.
    согл.наложение = {"a": {"nums": [1, 2, 3]}}
    согл._сохранить_наложение("rev")
    assert ядро.Обработчик.подробности.записи["a"]["seasons"][0]["nums"] == [1, 2, 3]


def test_ядро_без_нужного_не_трогается():
    м = _модуль()
    assert "не заведено" in м.установить(types.SimpleNamespace())


def test_вставка_в_шаблон_стоит_до_создания_сервера():
    текст = (КОРЕНЬ / "automation/host/lords-frontend.py").read_text(encoding="utf-8")
    i = текст.index("import lords_snapshot_reload as _перечитывание")
    j = текст.index("    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)")
    assert текст.index("def main(") < i < j


@pytest.mark.parametrize("путь", ["automation/host/lords_snapshot_reload.py"])
def test_модуль_компилируется(путь):
    compile((КОРЕНЬ / путь).read_text(encoding="utf-8"), путь, "exec")
