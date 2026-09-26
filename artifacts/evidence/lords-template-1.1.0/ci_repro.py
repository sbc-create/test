"""Воспроизведение условий CI: у зоны нет наполненного хранилища на хосте.

Тело взято из tests/unit/test_cell_queue_executor.py::
test_грязное_дерево_не_выкладывается без изменений; подменяется ТОЛЬКО то,
чем CI отличается от этой машины — каталог площадки сайта пуст, потому что
никакого /srv/zonafilm-space там нет.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
КОРЕНЬ = Path(sys.argv[1])
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import executor, privileged, queue, registry, runtime  # noqa: E402

КОММИТ = "a" * 40
ДАЙДЖЕСТ = "sha256:" + "b" * 64

tmp = Path(tempfile.mkdtemp())
репо = tmp / "repo"
(репо / "tools").mkdir(parents=True)
(репо / "tools" / "build_release.py").write_text("", encoding="utf-8")

registry.Cell.repo_path = property(lambda self: репо)
runtime.размещение = lambda *a, **k: runtime.Размещение(
    site_id="zona-01", domain="zonafilm.space", data_dir="/srv/x/data",
    unit="u.service", previous_unit="p.service", port=9120,
    account="nobody", reload="mtime", managed_by="cell")
privileged.собрать_без_прав = lambda *a, **k: (
    tmp / "a.tar.gz",
    {"source_commit": КОММИТ, "digest": ДАЙДЖЕСТ, "source_dirty": True,
     "live_build_id": "aaaaaaaaaaaa-zona-01"})

# Вот и вся разница с этой машиной: на бегунке CI /srv/zonafilm-space нет.
пусто = tmp / "srv" / "zonafilm-space"
(пусто / "data").mkdir(parents=True)
настоящая = privileged.Площадка.из_реестра


def _пустая(site_id, **k):
    ж = настоящая(site_id, **k)
    return privileged.Площадка(
        site_id=ж.site_id, account=ж.account, root=пусто,
        app=пусто / "app", data=пусто / "data", unit=ж.unit,
        previous_unit=ж.previous_unit, port=ж.port)


privileged.Площадка.из_реестра = staticmethod(_пустая)
print("площадка подменена:", privileged.Площадка.из_реестра("zona-01").data)

# Второе и последнее отличие бегунка: общего каталога производителя там тоже
# нет — снимков зоны взять неоткуда.
from factory.cell import delivery  # noqa: E402

общий = tmp / "srv" / "producer"
общий.mkdir(parents=True)
delivery.ОБЩИЙ = общий
print("общий каталог подменён:", delivery.ОБЩИЙ)

з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
try:
    executor.активировать(з, файл=tmp / "нет.json", dry_run=True)
except Exception as ош:
    print(f"{type(ош).__name__}: {ош}")
else:
    print("исключения не было")
