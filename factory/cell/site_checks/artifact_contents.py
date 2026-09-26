"""В артефакте ровно то, что ведёт Git, и ничего сверх того.

Пока сборщик обходил файловую систему, в выпуск уезжало и то, что Git
игнорирует. Два следствия, оба наблюдались:

* digest переставал быть функцией коммита — один коммит давал разные суммы на
  разных машинах, и исполнитель такую заявку отвергает;
* `checks/no_secrets.py` смотрит в ИНДЕКС, а паковался РАБОЧИЙ КАТАЛОГ:
  проверка и артефакт говорили о разном.

Проверяется поведением, а не чтением кода: рядом с проектом кладётся
игнорируемый файл, и он не должен оказаться в архиве.
"""
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_release  # noqa: E402

#: Кладётся в корень проекта намеренно: каталоги вроде var/ сборщик
#: пропускает и без разбора индекса, и подкидыш в них ничего не проверил бы.
ПОДКИДЫШ = ROOT / "podkidysh-proverki.txt"


def состав(куда: Path) -> set:
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_release.py"),
                    "--output", str(куда)], check=True, capture_output=True, cwd=str(ROOT))
    архив = next(куда.glob("*.tar.gz"))
    with tarfile.open(архив, "r:gz") as t:
        return {и.name for и in t.getmembers() if и.isfile()}


ожидалось = set()
вывод = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached"],
                       capture_output=True, text=True, check=True).stdout.split("\n")
for rel in вывод:
    rel = rel.strip()
    if not rel or rel in build_release.SKIP_FILES:
        continue
    if any(часть in build_release.SKIP_DIRS for часть in Path(rel).parts):
        continue
    ожидалось.add(rel)

плохо = []
ПОДКИДЫШ.write_text("этого файла не должно быть в выпуске\n", encoding="utf-8")
try:
    with tempfile.TemporaryDirectory() as tmp:
        собрано = состав(Path(tmp))
finally:
    ПОДКИДЫШ.unlink(missing_ok=True)

лишнее = собрано - ожидалось
нет = ожидалось - собрано
if лишнее:
    плохо.append("в артефакте есть лишнее: " + ", ".join(sorted(лишнее)))
if нет:
    плохо.append("в артефакте нет отслеживаемого: " + ", ".join(sorted(нет)))

if плохо:
    print("состав артефакта не совпал с индексом Git:", *плохо, sep="\n  ", file=sys.stderr)
    sys.exit(1)
