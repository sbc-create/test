"""Политика свободного места для публикации каталога.

Отказ, который нельзя проверить, опаснее отсутствующего: он может остановить
публикацию зря. Поэтому проверяется и то, что политика ОТКАЗЫВАЕТ, когда
сайтам осталось бы меньше резерва, и то, что она НЕ отказывает, когда места
хватает, и что недоступность статистики раздела разрешением писать не
становится.
"""
import os
from pathlib import Path

from factory.lords import publish_space


def файл(путь: Path, байт: int) -> Path:
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_bytes(b"0" * байт)
    return путь


def test_резерв_по_умолчанию_пять_гибибайт():
    assert publish_space.РЕЗЕРВ_САЙТАМ_КБ == 5 * 1024 * 1024


def test_места_хватает_отказа_нет(tmp_path):
    итог = publish_space.место_для_публикации(tmp_path, {}, резерв_кб=1)
    assert итог["ok"] is True
    assert итог["free_kb"] > 0
    assert "reason" not in итог


def test_нехватка_называет_числа(tmp_path):
    """Резерв выставлен заведомо больше раздела — отказ обязателен."""
    итог = publish_space.место_для_публикации(
        tmp_path, {}, резерв_кб=10 ** 12)
    assert итог["ok"] is False
    assert "резерве" in итог["reason"]
    assert "свободно" in итог["reason"]


def test_пик_и_остаток_считаются_отдельно(tmp_path):
    """Пик прогона и остаток ПОСЛЕ него — разные числа, и названы оба.

    Встречный счёт соседней сессии дал другой ответ ровно потому, что считал
    остаток: переименование временного файла освобождает прежний, и прирастают
    только копии «до». Отчёт, называющий одно число без имени, выглядит
    произвольным рядом с честным подсчётом другого.
    """
    большой = файл(tmp_path / "src" / "details.json", 4 * 1024 * 1024)
    малый = файл(tmp_path / "src" / "catalog.json", 1024 * 1024)
    итог = publish_space.место_для_публикации(
        tmp_path, {"lords-01": {"details": str(большой), "catalog": str(малый)}},
        резерв_кб=1)
    # Состав взят по коду публикатора: площадка сборки ВСЕХ витрин + копии
    # «до» ВСЕХ витрин + ОДИН временный файл атомарной записи (os.replace
    # идёт сразу после fsync, такие файлы не копятся).
    assert итог["peak_parts_kb"] == {"staging_area": 5 * 1024,
                                     "before_copies": 5 * 1024,
                                     "atomic_temp": 4 * 1024}
    assert итог["write_peak_kb"] == 14 * 1024
    assert итог["write_net_kb"] == 5 * 1024
    assert итог["write_kb"] == итог["write_peak_kb"]
    assert итог["left_after_run_kb"] - итог["left_to_sites_kb"] == 9 * 1024


def test_отказ_идёт_по_пику_и_говорит_об_этом(tmp_path):
    и = файл(tmp_path / "src" / "catalog.json", 1024)
    итог = publish_space.место_для_публикации(
        tmp_path, {"lords-01": {"catalog": str(и)}}, резерв_кб=10 ** 12)
    assert итог["ok"] is False
    assert "пик прогона" in итог["reason"]
    assert "После прогона осталось бы" in итог["reason"]
    assert "отказ именно по пику" in итог["reason"]


def test_накопленные_копии_измеряются_но_не_трогаются(tmp_path):
    копии = tmp_path / "publish-backups"
    файл(копии / "lords-01-details.json.before.pub-aaa", 2 * 1024 * 1024)
    файл(копии / "lords-02-details.json.before.pub-bbb", 1024 * 1024)
    файл(копии / "посторонний.json", 1024 * 1024)      # не копия «до»
    итог = publish_space.место_для_публикации(tmp_path, {}, копии=копии,
                                              резерв_кб=1)
    assert итог["kept_backups_files"] == 2
    assert итог["kept_backups_kb"] == 3 * 1024
    # Самое важное: ни один файл не исчез. Уборка этой функции запрещена.
    assert len(list(копии.iterdir())) == 3


def test_нехватка_называет_владельца_срока_хранения(tmp_path):
    копии = tmp_path / "publish-backups"
    файл(копии / "lords-01-details.json.before.pub-aaa", 1024)
    итог = publish_space.место_для_публикации(tmp_path, {}, копии=копии,
                                              резерв_кб=10 ** 12)
    assert "владелец" in итог["reason"]
    assert "удалять их публикация не вправе" in итог["reason"]


def test_непрочитанное_место_не_разрешение_писать(tmp_path):
    итог = publish_space.место_для_публикации(tmp_path / "нет-такого")
    assert итог["ok"] is False
    assert "не прочитано" in итог["reason"]
    assert "не разрешение писать" in итог["reason"]


def test_резерв_настраивается_переменной(monkeypatch):
    """Владелец может понизить резерв для одного прогона — осознанно."""
    monkeypatch.setenv("NOVA_PUBLISH_RESERVE_KB", "12345")
    import importlib
    заново = importlib.reload(publish_space)
    try:
        assert заново.РЕЗЕРВ_САЙТАМ_КБ == 12345
    finally:
        monkeypatch.delenv("NOVA_PUBLISH_RESERVE_KB", raising=False)
        importlib.reload(publish_space)


def test_скрипт_узла_зовёт_эту_политику():
    """Второй реализации того же решения в скрипте узла быть не должно."""
    т = (Path(__file__).resolve().parents[2]
         / "automation/host/nova-catalog-publish.py").read_text(encoding="utf-8")
    assert "from factory.lords.publish_space import место_для_публикации" in т
    assert "def место_на_разделе(" not in т
    assert 'отчёт["disk"] = место_для_публикации(' in т
    # Отказ стоит ДО создания каталога копий и до взятия замка.
    отказ = т.index('if not отчёт["disk"].get("ok", True):')
    запись = т.index("копии.mkdir(parents=True, exist_ok=True)\n    ЗАМОК")
    assert отказ < запись


def test_окружение_не_испорчено():
    assert "NOVA_PUBLISH_RESERVE_KB" not in os.environ or os.environ[
        "NOVA_PUBLISH_RESERVE_KB"].isdigit()
