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
    # Импорт стал многострочным, когда к политике добавился помощник
    # копии «до»: проверяется ФАКТ импорта из этого модуля, а не форма
    # строки — иначе проверка падала бы на переносе, а не на подмене.
    assert "from factory.lords.publish_space import" in т
    assert "место_для_публикации" in т
    assert "копия_до" in т
    assert "def место_на_разделе(" not in т
    assert 'отчёт["disk"] = место_для_публикации(' in т
    # Отказ стоит ДО создания каталога копий и до взятия замка.
    отказ = т.index('if not отчёт["disk"].get("ok", True):')
    запись = т.index("копии.mkdir(parents=True, exist_ok=True)\n    ЗАМОК")
    assert отказ < запись


def test_окружение_не_испорчено():
    assert "NOVA_PUBLISH_RESERVE_KB" not in os.environ or os.environ[
        "NOVA_PUBLISH_RESERVE_KB"].isdigit()

# --- копия «до публикации» жёсткой ссылкой ---------------------------------

def test_копия_до_делается_ссылкой(tmp_path):
    """Тот же inode — значит нулевой расход места."""
    и = файл(tmp_path / "details.json", 2048)
    ц = tmp_path / "копии" / "details.json.before.pub-1"
    assert publish_space.копия_до(и, ц) == "link"
    assert ц.stat().st_ino == и.stat().st_ino
    assert ц.read_bytes() == и.read_bytes()


def test_ссылка_держит_состояние_ДО_замены(tmp_path):
    """Главное свойство: публикация заменяет файл целиком, не правит на месте.

    `os.replace` даёт цели НОВЫЙ inode, поэтому ссылка остаётся при прежних
    байтах. Если бы писатель правил файл на месте, «копия» изменилась бы
    вместе с ним — и откат вернул бы не то состояние. Эта проверка и есть
    условие, при котором ссылка допустима.
    """
    и = tmp_path / "details.json"
    и.write_bytes(b"BEFORE")
    ц = tmp_path / "копии" / "details.json.before.pub-1"
    publish_space.копия_до(и, ц)

    врем = tmp_path / "details.json.tmp"
    врем.write_bytes(b"AFTER")
    import os
    os.replace(врем, и)

    assert и.read_bytes() == b"AFTER"
    assert ц.read_bytes() == b"BEFORE", "ссылка изменилась вместе с целью"


def test_правка_на_месте_ломала_бы_копию(tmp_path):
    """Проверка «от обратного»: именно поэтому условие названо в документации.

    Если писатель откроет файл на запись и перезапишет содержимое, ссылка
    покажет новое — то есть копии «до» не станет. Проверка фиксирует это как
    ИЗВЕСТНОЕ ограничение, а не как свойство, на которое можно не смотреть.
    """
    и = tmp_path / "details.json"
    и.write_bytes(b"BEFORE")
    ц = tmp_path / "копии" / "details.json.before.pub-1"
    publish_space.копия_до(и, ц)
    with open(и, "wb") as ф:          # правка НА МЕСТЕ, не через replace
        ф.write(b"INPLACE")
    assert ц.read_bytes() == b"INPLACE"


def test_при_невозможности_ссылки_копируется(tmp_path, monkeypatch):
    """Другое устройство или запрет — не повод остаться без копии."""
    и = файл(tmp_path / "details.json", 1024)
    ц = tmp_path / "копии" / "details.json.before.pub-1"

    def нельзя(*а, **к):
        raise OSError(18, "Invalid cross-device link")

    monkeypatch.setattr(publish_space.os, "link", нельзя)
    assert publish_space.копия_до(и, ц) == "copy"
    assert ц.read_bytes() == и.read_bytes()
    assert ц.stat().st_ino != и.stat().st_ino


def test_публикатор_зовёт_помощника_а_не_copy2():
    from pathlib import Path as П
    т = (П(__file__).resolve().parents[2]
         / "automation/host/nova-catalog-publish.py").read_text(encoding="utf-8")
    assert "способ = копия_до(путь, копия)" in т
    assert "shutil.copy2(путь, копия)" not in т
    # Способ попадает в отчёт: иначе «ссылка» и «копия» неотличимы снаружи.
    assert '"kind": способ' in т

def test_откат_работает_и_до_первой_записи(tmp_path):
    """`cp` без `--remove-destination` отказал бы: копия и цель — один inode.

    Проверяется поведением, а не чтением строки: команда отката должна
    восстанавливать содержимое и в случае, когда публикация ещё ничего не
    писала, то есть копия «до» и цель физически один файл.
    """
    import subprocess
    цель = tmp_path / "lords-01-catalog.json"
    цель.write_bytes(b"BEFORE")
    копия = tmp_path / "копии" / "lords-01-catalog.json.before.pub-1"
    publish_space.копия_до(цель, копия)
    assert цель.stat().st_ino == копия.stat().st_ino

    без_ключа = subprocess.run(["cp", "-p", str(копия), str(цель)],
                               capture_output=True, text=True)
    assert без_ключа.returncode != 0
    assert "same file" in (без_ключа.stderr or "")

    с_ключом = subprocess.run(
        ["cp", "-p", "--remove-destination", str(копия), str(цель)],
        capture_output=True, text=True)
    assert с_ключом.returncode == 0, с_ключом.stderr
    assert цель.read_bytes() == b"BEFORE"


def test_публикатор_печатает_откат_с_ключом():
    from pathlib import Path as П
    т = (П(__file__).resolve().parents[2]
         / "automation/host/nova-catalog-publish.py").read_text(encoding="utf-8")
    assert "cp -p --remove-destination" in т
    assert "are the same file" in т     # причина названа рядом с командой
