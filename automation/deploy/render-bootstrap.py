#!/usr/bin/env python3
"""Рендер установщика: подставляет отпечатки в шаблон `lords-deploy-bootstrap.py`.

Зачем отдельный инструмент
--------------------------

Шаблон установщика содержит `@@MANIFEST@@` и `@@REQUEST@@` и сам по себе не
исполняется. Раньше его подставляли руками, и это дважды стоило ночи: 9 сентября
установленная копия помощника осталась на ревизии `31014bb4`, потому что
перерендерить забыли, и выкладка полтора часа падала на `TypeError` в коде,
исправленном тремя коммитами выше. Рукописный манифест — это отпечаток,
скопированный не оттуда, и файл, забытый в списке.

Здесь ни одно поле не вводится: список файлов задан составом установки,
отпечатки считаются по тем самым файлам, которые будут установлены, а результат
проверяется компиляцией до того, как попадёт на исполняемый раздел.

Запуск:
    python3 automation/deploy/render-bootstrap.py --out var/bootstrap/<имя>.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import py_compile
import subprocess
import sys
from pathlib import Path

ИСТОЧНИК = Path(__file__).resolve().parent
ШАБЛОН = ИСТОЧНИК / "lords-deploy-bootstrap.py"

#: Состав установки. Ключ — путь назначения относительно раздела установки:
#: `units/` уходит в /etc/systemd/system, остальное — в LIBEXEC рядом друг с
#: другом. `lords_fence.py` обязателен: помощник и приёмщик ищут барьер в
#: собственном каталоге, и установка без него молча возвращает выкладку без
#: барьера — ровно дефект `LORDS-FENCE-FAIL-OPEN-37`.
СОСТАВ = (
    "lords-deploy-broker",
    "lords-deployctl",
    "lords_fence.py",
    "lords-public-check.py",
    "units/lords-deploy-broker.path",
    "units/lords-deploy-broker.service",
    "units/lords-site-render@.service",
)


def отпечаток(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def собрать_манифест() -> dict[str, str]:
    манифест: dict[str, str] = {}
    for имя in СОСТАВ:
        путь = ИСТОЧНИК / имя
        if not путь.is_file():
            raise SystemExit(f"нет файла состава: {путь}")
        манифест[имя] = отпечаток(путь)
    return манифест


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", required=True, help="куда положить готовый установщик")
    р.add_argument("--request", default=None,
                   help="JSON-файл заявки; без него установщик умеет только "
                        "--install-only и --cancel-stuck")
    args = р.parse_args()

    манифест = собрать_манифест()
    заявка = json.loads(Path(args.request).read_text(encoding="utf-8")) if args.request else None

    текст = ШАБЛОН.read_text(encoding="utf-8")
    for метка, значение in (("@@MANIFEST@@", манифест), ("@@REQUEST@@", заявка)):
        if метка not in текст:
            raise SystemExit(f"в шаблоне нет метки {метка}")
        # Python-литерал, а не JSON. `json.dumps(None)` даёт `null`, и это
        # синтаксически годный Python — имя, — поэтому py_compile молчит, а
        # установка падает от root на `NameError: name 'null' is not defined`.
        # `pprint.pformat` не выдаёт ни null, ни true, ни false.
        текст = текст.replace(
            метка, pprint.pformat(значение, indent=4, width=100, sort_dicts=False), 1)

    цель = Path(args.out)
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(текст, encoding="utf-8")

    # Компиляция до установки: подставленный шаблон обязан быть Python, а не
    # почти-Python. Дефект здесь стоил бы отказа уже от root.
    py_compile.compile(str(цель), doraise=True)

    # Компиляции мало: `null` компилируется и падает только при запуске.
    # Исполняем модуль в отдельном интерпретаторе с `--help`, который ничего не
    # устанавливает, но исполняет все определения верхнего уровня.
    проба = subprocess.run([sys.executable, str(цель), "--help"],
                           capture_output=True, text=True, timeout=120)
    if проба.returncode != 0:
        raise SystemExit(f"собранный установщик не запускается:\n{проба.stderr.strip()}")

    print(f"установщик собран: {цель}")
    print(f"состав: {len(манифест)} файлов")
    for имя, сумма in манифест.items():
        print(f"  {сумма[:12]}… {имя}")
    print(f"заявка: {'нет (только --install-only)' if заявка is None else заявка['deployment_id']}")
    print(f"sha256 установщика: {отпечаток(цель)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
