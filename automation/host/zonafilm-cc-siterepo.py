#!/usr/bin/env python3
"""Наполнение проекта сайта zonafilm.cc: запуск, сборка, выкладка, откат, CI.

Скелет проекта делает `factory.cell.siterepo.generate` — второго генератора
здесь нет. Этот файл добавляет ровно то, чего у общего скелета быть не может,
потому что оно про конкретный рантайм этой витрины:

* `run.py` — запуск релиза с явными путями. Все умолчания рантайма ведут на
  соседнюю витрину (`lords-01`), и одна незаданная переменная означала бы
  чужой каталог и чужие комментарии. Поэтому запуск не полагается на
  умолчания и отказывается стартовать, увидев чужой путь;
* `build/build.py` — воспроизводимый артефакт без доступа к фабрике;
* `deploy/install.sh`, `deploy/rollback.sh` — атомарная смена релиза;
* CI, который действительно собирает и сверяет digest двух сборок.

Скрипт идемпотентен: повторный запуск переписывает те же файлы тем же
содержимым и не создаёт второй проект.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

РЕПО = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(РЕПО))

from factory.cell import registry, siterepo  # noqa: E402

SITE_ID = "zona-02"
DOMAIN = "zonafilm.cc"
ПОРТ = 9123
РЕЛИЗ_ИСТОЧНИК = Path("/srv/lords/.frontend/releases/zona-02-1015c650d8be")
ИМЯ_ШАБЛОНА = РЕЛИЗ_ИСТОЧНИК.name
ДАННЫЕ_ПО_УМОЛЧАНИЮ = "/srv/lords/.frontend/sites/zona-02/data"

СОСЕДИ = (
    "lords-01", "lords-02", "lords-03", "lords-04",
    "zona-01", "animedia-01", "animedia-02",
    "yummyani-site", "yummyani-org", "yummyani-biz",
)

RUN_PY = '''#!/usr/bin/env python3
"""Запуск витрины {domain} ({site_id}) из её собственного релиза.

Почему запуск не прямой. Рантайм витрины читает окружение, и **все** его
умолчания ведут на соседнюю витрину: каталог соседа, его корень старого
релиза и имя `Lords`. Одна незаданная переменная —
и {domain} отдал бы каталог соседа и писал бы комментарии в его хранилище.
Поэтому здесь задаётся всё, и ничего не остаётся на умолчание.

Второе свойство: процесс отказывается стартовать, если любой итоговый путь
ведёт к чужой витрине. Отказ громкий и до первого запроса — тихий старт на
чужих данных обнаруживается уже на живом домене.

Данные лежат вне каталога релиза. Смена релиза их не касается, откат кода не
возвращает вчерашние комментарии.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent
SITE_ID = {site_id!r}
DOMAIN = {domain!r}
ЧУЖИЕ = {neighbours!r}


def настройки() -> dict:
    файл = КОРЕНЬ / "config" / "runtime.json"
    return json.loads(файл.read_text(encoding="utf-8"))


def данные(cfg: dict) -> Path:
    """Каталог данных. Внешнее значение сильнее записанного в релизе."""
    путь = os.environ.get("ZONA02_DATA") or cfg["data_root"]
    return Path(путь).resolve()


def проверить_чужое(окружение: dict) -> None:
    """Ни один путь не ведёт к соседней витрине.

    Проверяются итоговые значения, а не намерения: ошибиться можно и в
    конфигурации, и в переменной окружения, а последствие одно.
    """
    плохие = []
    for ключ, значение in sorted(окружение.items()):
        if not isinstance(значение, str) or "/" not in значение:
            continue
        for чужой in ЧУЖИЕ:
            if чужой in значение:
                плохие.append(f"{{ключ}}={{значение}} содержит {{чужой}}")
    if плохие:
        raise SystemExit(
            f"{{SITE_ID}}: отказ запуска — путь ведёт к чужой витрине:\\n  "
            + "\\n  ".join(плохие)
        )


def обязательные(пути: dict) -> None:
    нет = [f"{{k}}={{v}}" for k, v in sorted(пути.items()) if not Path(v).exists()]
    if нет:
        raise SystemExit(
            f"{{SITE_ID}}: отказ запуска — нет обязательных файлов:\\n  " + "\\n  ".join(нет))


def main() -> int:
    cfg = настройки()
    корень_данных = данные(cfg)
    релиз = КОРЕНЬ / "template" / cfg["release_dir"]

    окружение = {{
        "LORDS_TEMPLATE_MANIFEST": str(КОРЕНЬ / "template-manifest.json"),
        "LORDS_CATALOG": str(корень_данных / f"{{SITE_ID}}-catalog.json"),
        "LORDS_DETAILS": str(корень_данных / f"{{SITE_ID}}-details.json"),
        "LORDS_PLAYER_CONFIG": str(корень_данных / f"player-{{SITE_ID}}.json"),
        "LORDS_LEGACY_ROOT": str(корень_данных / "legacy"),
        "LORDS_SITE_NAME": cfg["site_name"],
        "LORDS_TEMPLATE_REVISION": cfg["template_revision"],
        "LORDS_SITEMAP_DIR": str(корень_данных / "sitemap"),
        "LORDS_POPULAR_WEEKLY": str(корень_данных / f"{{SITE_ID}}-popular-weekly.json"),
        "ZONA_FOOTER_CONFIG": str(корень_данных / f"footer-{{SITE_ID}}.json"),
        "ZONA_AD_SLOTS": "1" if cfg.get("ad_slots_enabled") else "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }}
    # Счётчик Метрики подставляется, только если он выдан этому домену.
    # Пустая строка означает «счётчика нет», а не «возьми соседний».
    счётчик = str(cfg.get("metrika_counter") or "").strip()
    if счётчик:
        окружение["LORDS_METRIKA_COUNTER"] = счётчик

    проверить_чужое(окружение)
    обязательные({{
        "LORDS_TEMPLATE_MANIFEST": окружение["LORDS_TEMPLATE_MANIFEST"],
        "LORDS_CATALOG": окружение["LORDS_CATALOG"],
        "release": str(релиз / "lords-frontend.py"),
    }})

    os.environ.update(окружение)
    точка = str(релиз / "lords-frontend.py")
    аргументы = sys.argv[1:] or ["--port", str(cfg["port"])]
    # execv, а не import: `__file__` работающего процесса становится путём
    # неизменяемого релиза, и вопрос «какой релиз исполняется» перестаёт быть
    # вопросом доверия — на него отвечает /proc.
    os.execv(sys.executable, [sys.executable, точка, *аргументы])


if __name__ == "__main__":
    raise SystemExit(main())
'''

BUILD_PY = '''#!/usr/bin/env python3
"""Воспроизводимый артефакт релиза — без доступа к фабрике.

Алгоритм повторяет `factory.cell.release.pack` и закреплён тестом равенства
digest: сборка здесь и сборка фабрикой обязаны давать одно значение, иначе
digest не отвечал бы на вопрос «то же ли это самое».

Переменного в архив не попадает ничего: порядок файлов задан, времена
обнулены, владелец обезличен, штамп gzip нулевой. Один и тот же коммит даёт
один и тот же digest.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
ИСКЛЮЧЕНО = (".git", "__pycache__", "node_modules", "var", "data", "media")


def sha256_file(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as fh:
        for кусок in iter(lambda: fh.read(1 << 20), b""):
            h.update(кусок)
    return f"sha256:{h.hexdigest()}"


def _обезличить(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Времена, владелец, группа и права — к канону.

    Права обезличиваются потому, что полный режим зависит от umask того, кто
    раскладывал дерево: чистый clone при umask 022 даёт 644, рабочий каталог
    при umask 002 — 664. Значащим остаётся один бит: исполняемый или нет.
    """
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.mode & 0o100 else 0o644
    return info


def файлы(корень: Path) -> list[Path]:
    итог = [
        p for p in корень.rglob("*")
        if p.is_file() and not any(ч in ИСКЛЮЧЕНО for ч in p.relative_to(корень).parts)
    ]
    return sorted(итог, key=lambda p: str(p.relative_to(корень)))


def упаковать(источник: Path, цель: Path) -> str:
    цель.parent.mkdir(parents=True, exist_ok=True)
    сырьё = io.BytesIO()
    with tarfile.open(fileobj=сырьё, mode="w") as tar:
        for путь in файлы(источник):
            tar.add(путь, arcname=str(путь.relative_to(источник)), filter=_обезличить)
    данные = сырьё.getvalue()
    with цель.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(данные)
    return sha256_file(цель)


def коммит() -> str:
    out = subprocess.run(["git", "-C", str(КОРЕНЬ), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def чисто() -> bool:
    out = subprocess.run(["git", "-C", str(КОРЕНЬ), "status", "--porcelain"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip() == ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default=str(КОРЕНЬ / "var" / "release"))
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()

    if not args.allow_dirty and not чисто():
        raise SystemExit("в проекте есть незакоммиченные изменения: "
                         "релиз собирается из чистого коммита")

    манифест_сайта = json.loads((КОРЕНЬ / "site-manifest.json").read_text(encoding="utf-8"))
    site_id = манифест_сайта["site_id"]
    sha = коммит()
    выход = Path(args.output)
    артефакт = выход / f"{site_id}-{sha[:12]}.tar.gz"
    digest = упаковать(КОРЕНЬ, артефакт)

    манифест = {
        "schema_version": "1.0",
        "site_id": site_id,
        "domain": манифест_сайта.get("domain"),
        "artifact": артефакт.name,
        "digest": digest,
        "size_bytes": артефакт.stat().st_size,
        "source_commit": sha,
        "template": манифест_сайта.get("template", {}),
        "modules": манифест_сайта.get("modules", []),
        "pins": json.loads((КОРЕНЬ / "pins.lock.json").read_text(encoding="utf-8"))["pins"],
        "built_at": datetime.now(timezone.utc).isoformat(),
        "builder": "build/build.py",
    }
    путь_манифеста = выход / f"{site_id}-{sha[:12]}.release-manifest.json"
    путь_манифеста.write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"artifact": str(артефакт), "manifest": str(путь_манифеста),
                      "digest": digest, "source_commit": sha},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

INSTALL_SH = '''#!/usr/bin/env bash
# Установка релиза {site_id}. Атомарная: витрина либо на прежнем релизе, либо
# на новом, промежуточного состояния снаружи не видно.
#
# Данные не трогаются. Каталог данных живёт вне каталога релиза именно затем,
# чтобы смена релиза не касалась комментариев и оценок, а откат кода не
# возвращал вчерашние.
#
# Имена переменных латиницей не по стилю, а по необходимости: bash принимает
# в имени только [A-Za-z_0-9], и кириллическое имя — ошибка времени
# исполнения, которую `bash -n` не показывает. Комментарии остаются русскими.
set -euo pipefail

artifact="${{1:?укажите путь к артефакту .tar.gz}}"
manifest="${{2:-${{artifact%.tar.gz}}.release-manifest.json}}"
root="${{SITE_ROOT:?SITE_ROOT не задан: корень размещения витрины обязателен}}"

command -v python3 >/dev/null || {{ echo "python3 не найден" >&2; exit 1; }}
[ -f "$artifact" ] || {{ echo "нет артефакта: $artifact" >&2; exit 1; }}
[ -f "$manifest" ] || {{ echo "нет манифеста релиза: $manifest" >&2; exit 1; }}

expected=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['digest'])" "$manifest")
actual="sha256:$(sha256sum "$artifact" | cut -d' ' -f1)"
if [ "$expected" != "$actual" ]; then
  echo "digest артефакта $actual не совпал с манифестом $expected: установка не начата" >&2
  exit 1
fi

site_id=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['site_id'])" "$manifest")
if [ "$site_id" != "{site_id}" ]; then
  echo "артефакт описывает $site_id, а ставят в {site_id}: чужой артефакт не ставится" >&2
  exit 1
fi

commit=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['source_commit'])" "$manifest")
release_dir="$root/releases/${{commit:0:12}}"

mkdir -p "$root/releases" "$root/data"
if [ -d "$release_dir" ]; then
  echo "релиз ${{commit:0:12}} уже установлен: повтор ничего не меняет"
else
  staging="$release_dir.tmp.$$"
  rm -rf "$staging"
  mkdir -p "$staging"
  tar -xzf "$artifact" -C "$staging"
  mv "$staging" "$release_dir"
fi

# Прежний релиз запоминается до переключения: без него откатывать некуда.
if [ -L "$root/current" ]; then
  previous=$(readlink -f "$root/current")
  if [ "$previous" != "$release_dir" ]; then
    ln -sfn "$previous" "$root/previous.new"
    mv -Tf "$root/previous.new" "$root/previous"
  fi
fi

ln -sfn "$release_dir" "$root/current.new"
mv -Tf "$root/current.new" "$root/current"

echo "установлен ${{commit:0:12}} в $root/current"
'''


ROLLBACK_SH = '''#!/usr/bin/env bash
# Откат {site_id} на предыдущий релиз. Данные не трогаются.
#
# Откат без сохранённого previous не выполняется: молча остаться на текущем
# релизе значило бы отчитаться об откате, которого не было.
set -euo pipefail

root="${{SITE_ROOT:?SITE_ROOT не задан}}"

[ -L "$root/previous" ] || {{ echo "previous не задан: откатывать не на что" >&2; exit 1; }}
target=$(readlink -f "$root/previous")
[ -d "$target" ] || {{ echo "previous ведёт в несуществующий каталог $target" >&2; exit 1; }}

current=$(readlink -f "$root/current" 2>/dev/null || echo "")
if [ "$current" = "$target" ]; then
  echo "current и previous указывают на один релиз: откатывать некуда" >&2
  exit 1
fi

ln -sfn "$target" "$root/current.new"
mv -Tf "$root/current.new" "$root/current"
if [ -n "$current" ]; then
  ln -sfn "$current" "$root/previous.new"
  mv -Tf "$root/previous.new" "$root/previous"
fi

echo "откат выполнен: current -> $target"
'''


UNIT_TEMPLATE = '''# Витрина {site_id} ({domain}), семейство zona.
#
# ExecStart ведёт в собственный релиз витрины, а не в общий загрузчик
# /srv/lords/.frontend. Так и задумано: у сайта свой репозиторий, свой
# артефакт и свой откат, и работать он обязан из того, что выпущено им.
# `run.py` задаёт окружение целиком и отказывается стартовать, если любой
# итоговый путь ведёт к соседней витрине.
#
# Порт и имя юнита выданы аллокатором по четырём реестрам, а не выбраны:
#   automation/host/zonafilm-cc-allocate.py --family zona --domain {domain} \
#     --service-name-source runtime_registry
#
# TimeoutStartSec намеренно не задан: старт читает снимок каталога (16 МиБ) и
# боковой файл подробностей (73 МиБ) и строит указатели. Измерено на этом
# стенде — от 105 до 290 с. Дефолтные 90 с убивали бы витрину на старте.

[Unit]
Description=nova frontend: {site_id} ({domain}) [zona]
After=network-online.target

[Service]
Type=simple
User=lords
WorkingDirectory={site_root}
Environment=SITE_ROOT={site_root}
Environment=ZONA02_DATA={data_root}
Environment=PYTHONDONTWRITEBYTECODE=1
# Интерпретатор задан явно, а не через PATH: системный приносит тот набор
# пакетов, который окажется в образе, а не тот, на котором витрина проверена.
ExecStart={python} {site_root}/current/run.py --port {port}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
'''

OPERATIONS_MD = '''# Эксплуатация {site_id} ({domain})

Один домен, один арендатор, один закреплённый шаблон, один Git-проект.
Всё, что здесь описано, меняет только этот сайт.

## Что где лежит

| Что | Где | Меняется |
| --- | --- | --- |
| Код релиза | `<корень>/current/` (символическая ссылка на `releases/<коммит>`) | при каждом выкате |
| Прежний релиз | `<корень>/previous/` | при каждом выкате |
| Данные | `{data_root}` | независимо от релизов |
| Секреты | вне Git и вне релиза, по `secret_ref` | вне этого проекта |

Данные вне каталога релиза — не стилистика. Смена релиза не должна касаться
комментариев и оценок, а откат кода не должен возвращать вчерашние.

## Запуск

```bash
SITE_ROOT=<корень> <корень>/current/run.py --port {port}
```

`run.py` задаёт окружение целиком и **отказывается стартовать**, если любой
итоговый путь ведёт к соседней витрине. Умолчания рантайма ведут на соседа —
именно поэтому ни одно из них не остаётся незаданным.

Первый ответ появляется не сразу: старт читает снимок каталога и боковой файл
подробностей и строит указатели. На стенде — от 105 до 290 с.

## Сборка

```bash
python3 build/build.py --output var/release
```

Собирается из чистого коммита. На целевом сервере ничего не собирается:
собранное там — другая сборка, и проверяли не её. Две сборки одного коммита
обязаны дать один digest; это проверяет CI, а не обещает документация.

## Выкладка

```bash
SITE_ROOT=<корень> ./deploy/install.sh var/release/{site_id}-<коммит>.tar.gz
```

Установка сверяет digest артефакта с манифестом и `site_id` с целью, затем
атомарно переставляет `current`, запомнив прежний релиз в `previous`.

## Откат

```bash
SITE_ROOT=<корень> ./deploy/rollback.sh
```

Откат без сохранённого `previous` не выполняется: молча остаться на текущем
релизе значило бы отчитаться об откате, которого не было.

## Чего здесь не делается

* не переключается DNS и не выпускается сертификат;
* не открывается индексация — витрина закрыта на двух уровнях, открытие
  отдельная команда владельца после визуальной приёмки;
* не перезапускаются соседние витрины;
* не правится живой код по SSH: правка на работающем сервере не оставляет ни
  истории, ни отката и теряется при следующем выкате.
'''

CI_TEMPLATE = '''# Выпуск сайта {site_id} ({domain}). Меняет только его.
name: release

on:
  push:
    branches: [main, "claude/**"]
  pull_request:
  workflow_dispatch:

# Один выкат на сайт одновременно. cancel-in-progress выключен намеренно:
# прерванный посередине выкат оставляет сайт в состоянии, которого нет ни в
# одном релизе.
concurrency:
  group: release-{site_id}
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          # Полная история обязательна: по умолчанию checkout берёт один
          # коммит, и `git merge-base` ниже не смог бы ответить на вопрос о
          # родстве — а неответ выглядел бы как «не устарел».
          fetch-depth: 0

      - name: Проверки проекта
        run: ./checks/run.sh

      - name: Этот репозиторий описывает именно свой сайт
        run: |
          set -euo pipefail
          declared=$(python3 -c "import json;print(json.load(open('site-manifest.json'))['site_id'])")
          if [ "$declared" != "{site_id}" ]; then
            echo "манифест описывает $declared, а проект — {site_id}: чужой сайт не выпускается" >&2
            exit 1
          fi

      - name: Исходник не устарел
        run: |
          set -euo pipefail
          # Выкат, основанный на предке уже развёрнутого коммита, — это
          # перезапись более свежего релиза. Ожидаемая ревизия приходит
          # снаружи; без неё шаг честно сообщает, что не проверял.
          if [ -z "${{DEPLOYED_COMMIT:-}}" ]; then
            echo "DEPLOYED_COMMIT не передан: сверка с развёрнутым релизом НЕ ВЫПОЛНЯЛАСЬ"
            exit 0
          fi
          # Три исхода, и их нельзя сводить к двум. `merge-base --is-ancestor`
          # отвечает 0 (предок), 1 (не предок) и иначе — «не смог ответить».
          # Считать «не смог» за «не устарел» значит пропустить ровно тот
          # выкат, ради которого шаг и написан.
          set +e
          git merge-base --is-ancestor "$GITHUB_SHA" "${{DEPLOYED_COMMIT}}"
          verdict=$?
          set -e
          case "$verdict" in
            0) echo "развёрнут потомок ${{DEPLOYED_COMMIT}}: устаревший выкат отклонён" >&2
               exit 1 ;;
            1) echo "исходник не устарел" ;;
            *) echo "родство с ${{DEPLOYED_COMMIT}} установить не удалось: выкат остановлен" >&2
               exit 1 ;;
          esac

      - name: Сборка артефакта
        id: build
        run: |
          set -euo pipefail
          # var/ нет в чистом clone: он в .gitignore, и это правильно —
          # выходы сборки не коммитятся. Создать его обязан тот, кто в него пишет.
          mkdir -p var
          python3 build/build.py --output var/release-1 | tee var/build-1.json
          digest=$(python3 -c "import json;print(json.load(open('var/build-1.json'))['digest'])")
          echo "digest=$digest" >> "$GITHUB_OUTPUT"

      - name: Сборка воспроизводима
        run: |
          set -euo pipefail
          mkdir -p var
          # Digest, полученный один раз, подтверждает только момент упаковки.
          # Полезен он ровно тогда, когда две независимые сборки одного
          # коммита дают одно значение.
          python3 build/build.py --output var/release-2 > var/build-2.json
          a=$(python3 -c "import json;print(json.load(open('var/build-1.json'))['digest'])")
          b=$(python3 -c "import json;print(json.load(open('var/build-2.json'))['digest'])")
          if [ "$a" != "$b" ]; then
            echo "две сборки одного коммита дали разные digest: $a и $b" >&2
            exit 1
          fi
          echo "воспроизводимость подтверждена: $a"

      - name: Артефакт не несёт данных и секретов
        run: |
          set -euo pipefail
          # Проверяется собранный архив, а не рабочее дерево: в релиз попадает
          # то, что упаковано, и запрет обязан проверяться там же.
          archive=$(ls var/release-1/*.tar.gz)
          if tar -tzf "$archive" | grep -E '(^|/)(data|media|var)/|\.(sqlite3?|db|dump|sql|pem|key)$|(^|/)\.env$'; then
            echo "в артефакте есть данные или секреты" >&2
            exit 1
          fi
          echo "в артефакте только код и конфигурация"

      - uses: actions/upload-artifact@v4
        with:
          name: {site_id}-release
          path: |
            var/release-1/*.tar.gz
            var/release-1/*.release-manifest.json
          retention-days: 14

# Чего здесь нет намеренно: шага, который трогает соседние сайты, и шага,
# который переключает домен. Переключение маршрутизации — отдельное решение
# с подтверждением владельца, а не побочный эффект зелёной сборки.
'''

NO_NEIGHBOUR_PY = '''"""Ни один путь проекта не ведёт к соседней витрине.

Проверка исполняемая, а не обещанная. Все умолчания рантайма ведут на
`lords-01`, и путь соседа, попавший в конфигурацию этого проекта, означал бы
чужой каталог и чужие комментарии на живом домене.

Ищется ровно то, что вредит: **абсолютный путь файловой системы**, внутри
которого стоит имя чужой витрины. Упоминание соседа в тексте — объяснение,
почему так сделано, и запрещать его значило бы запрещать объяснения.
Ссылка вида `secret://cdnvideohub/lords/lords-01/publisher-id` тоже не путь:
это имя пары учётных данных семейства, одной на всё семейство, и подменять её
нечем — у витрины нет собственной пары.

Каталог `template/` исключён намеренно: это закреплённый байт в байт артефакт
общего рантайма, его умолчания перекрываются в `run.py`, и правка артефакта
сломала бы сверку sha256 с закреплённым шаблоном.
"""
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
ЧУЖИЕ = {neighbours!r}
ПРОПУСК = ("template", ".git", "var", "data", "checks")

#: Абсолютный путь файловой системы: начинается со слэша и не является схемой
#: URI (`secret://`, `https://` — перед слэшами стоит двоеточие).
ПУТЬ = re.compile(r"(?<![:/\w])(/[\w./-]+)")

плохие = []
for путь in sorted(КОРЕНЬ.rglob("*")):
    if not путь.is_file():
        continue
    части = путь.relative_to(КОРЕНЬ).parts
    if части[0] in ПРОПУСК:
        continue
    if путь.suffix not in (".json", ".py", ".sh", ".yml", ".yaml"):
        continue
    текст = путь.read_text(encoding="utf-8", errors="replace")
    for номер, строка in enumerate(текст.splitlines(), 1):
        for найденный in ПУТЬ.findall(строка):
            for чужой in ЧУЖИЕ:
                if чужой in найденный:
                    плохие.append(f"{{путь.relative_to(КОРЕНЬ)}}:{{номер}}: {{найденный}}")

if плохие:
    print("пути ведут к чужим витринам:", file=sys.stderr)
    for строка in плохие:
        print("  " + строка, file=sys.stderr)
    sys.exit(1)
print("путей к чужим витринам не найдено")
'''

DEPLOY_SMOKE_PY = '''"""Выкладка и откат проверяются исполнением, а не чтением.

Почему появилась эта проверка. `bash -n` разбирает синтаксис и молчит про
присваивание в переменную с кириллическим именем — bash принимает в имени
только [A-Za-z_0-9], и падение случается при первом реальном запуске, то есть
на выкладке. Синтаксической проверки для такого класса дефектов не
существует: скрипт нужно выполнить.

Всё происходит во временном каталоге на поддельных артефактах: настоящий
корень витрины, настоящие релизы и настоящие данные не участвуют.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
SITE_ID = json.loads((КОРЕНЬ / "site-manifest.json").read_text(encoding="utf-8"))["site_id"]


def артефакт(каталог: Path, коммит: str, метка: str) -> tuple[Path, Path]:
    дерево = каталог / f"tree-{метка}"
    (дерево / "config").mkdir(parents=True)
    (дерево / "marker.txt").write_text(метка, encoding="utf-8")
    (дерево / "config" / "site.json").write_text(
        json.dumps({"site_id": SITE_ID}), encoding="utf-8")
    путь = каталог / f"{SITE_ID}-{коммит[:12]}.tar.gz"
    with tarfile.open(путь, "w:gz") as tar:
        for файл in sorted(дерево.rglob("*")):
            if файл.is_file():
                tar.add(файл, arcname=str(файл.relative_to(дерево)))
    h = hashlib.sha256(путь.read_bytes()).hexdigest()
    манифест = каталог / f"{SITE_ID}-{коммит[:12]}.release-manifest.json"
    манифест.write_text(json.dumps({
        "site_id": SITE_ID, "digest": f"sha256:{h}", "source_commit": коммит,
    }), encoding="utf-8")
    return путь, манифест


def запустить(скрипт: str, корень: Path, *аргументы: str) -> subprocess.CompletedProcess:
    среда = dict(os.environ, SITE_ROOT=str(корень))
    return subprocess.run([str(КОРЕНЬ / "deploy" / скрипт), *аргументы],
                          capture_output=True, text=True, env=среда)


def провал(сообщение: str, результат: subprocess.CompletedProcess) -> None:
    print(f"{сообщение}\\n  rc={результат.returncode}\\n  out={результат.stdout.strip()}"
          f"\\n  err={результат.stderr.strip()}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zona02-deploy-smoke-") as tmp:
        каталог = Path(tmp)
        корень = каталог / "site-root"
        корень.mkdir()
        (корень / "data").mkdir()
        (корень / "data" / "keep.txt").write_text("данные переживают выкат", encoding="utf-8")

        a_арт, a_ман = артефакт(каталог, "a" * 40, "первый")
        b_арт, b_ман = артефакт(каталог, "b" * 40, "второй")

        # 1. Первая установка.
        r = запустить("install.sh", корень, str(a_арт), str(a_ман))
        if r.returncode != 0:
            провал("install.sh не установил первый релиз", r)
        if (корень / "current" / "marker.txt").read_text(encoding="utf-8") != "первый":
            провал("current не указывает на первый релиз", r)

        # 2. Повтор ничего не меняет.
        до = os.readlink(корень / "current")
        r = запустить("install.sh", корень, str(a_арт), str(a_ман))
        if r.returncode != 0 or os.readlink(корень / "current") != до:
            провал("повторная установка того же релиза изменила current", r)

        # 3. Второй релиз: current переезжает, previous запоминает прежний.
        r = запустить("install.sh", корень, str(b_арт), str(b_ман))
        if r.returncode != 0:
            провал("install.sh не установил второй релиз", r)
        if (корень / "current" / "marker.txt").read_text(encoding="utf-8") != "второй":
            провал("current не переехал на второй релиз", r)
        if (корень / "previous" / "marker.txt").read_text(encoding="utf-8") != "первый":
            провал("previous не запомнил первый релиз", r)

        # 4. Откат возвращает первый и запоминает второй.
        r = запустить("rollback.sh", корень)
        if r.returncode != 0:
            провал("rollback.sh не выполнил откат", r)
        if (корень / "current" / "marker.txt").read_text(encoding="utf-8") != "первый":
            провал("откат не вернул первый релиз", r)
        if (корень / "previous" / "marker.txt").read_text(encoding="utf-8") != "второй":
            провал("previous не запомнил второй релиз", r)

        # 5. Данные не тронуты ни выкладкой, ни откатом.
        if (корень / "data" / "keep.txt").read_text(encoding="utf-8") != "данные переживают выкат":
            print("данные изменились при смене релиза", file=sys.stderr)
            return 1

        # 6. Подменённый digest не ставится.
        порченый = каталог / "broken.release-manifest.json"
        данные = json.loads(a_ман.read_text(encoding="utf-8"))
        данные["digest"] = "sha256:" + "0" * 64
        порченый.write_text(json.dumps(данные), encoding="utf-8")
        r = запустить("install.sh", корень, str(a_арт), str(порченый))
        if r.returncode == 0:
            провал("артефакт с несовпавшим digest был установлен", r)

        # 7. Чужой site_id не ставится.
        чужой = каталог / "alien.release-manifest.json"
        данные = json.loads(a_ман.read_text(encoding="utf-8"))
        данные["site_id"] = "lords-01"
        чужой.write_text(json.dumps(данные), encoding="utf-8")
        r = запустить("install.sh", корень, str(a_арт), str(чужой))
        if r.returncode == 0:
            провал("артефакт чужого сайта был установлен", r)

    print("выкладка и откат: установка, повтор, смена, откат, digest, чужой site_id — PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

CHECKS_SH = '''#!/usr/bin/env bash
# Проверки проекта сайта. Падение любой из них — причина не выпускать релиз.
set -euo pipefail

cd "$(dirname "$0")/.."

fail=0
say() { printf '%-34s %s\n' "$1" "$2"; }

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    say "$name" "PASS"
  else
    say "$name" "FAIL"
    fail=1
  fi
}

check "manifest-is-json"     python3 -c "import json;json.load(open('site-manifest.json'))"
check "pins-are-json"        python3 -c "import json;json.load(open('pins.lock.json'))"
check "runtime-is-json"      python3 -c "import json;json.load(open('config/runtime.json'))"
check "template-present"     test -d template
check "no-floating-pins"     python3 checks/no_floating_pins.py
check "no-data-or-secrets"   python3 checks/no_data_or_secrets.py
check "no-neighbour-paths"   python3 checks/no_neighbour_paths.py
check "pinned-template-sha"  python3 checks/pinned_template_sha.py
check "run-py-compiles"      python3 -m py_compile run.py
check "build-py-compiles"    python3 -m py_compile build/build.py
check "install-sh-syntax"    bash -n deploy/install.sh
check "rollback-sh-syntax"   bash -n deploy/rollback.sh
check "activate-sh-syntax"   bash -n deploy/activate.sh
check "deactivate-sh-syntax" bash -n deploy/deactivate.sh
check "deploy-rollback-smoke" python3 checks/deploy_smoke.py

exit "$fail"
'''

PINNED_SHA_PY = '''"""Закреплённый шаблон не подменён.

sha256 исполняемого файла релиза сверяется с тем, что записано в
`pins.lock.json`. Без этой проверки «закреплённая версия» была бы обещанием:
файл в `template/` правится так же легко, как любой другой.
"""
import hashlib
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
pins = json.loads((КОРЕНЬ / "pins.lock.json").read_text(encoding="utf-8"))["pins"]
ожидаемый = pins["template_sha256"]
релиз = КОРЕНЬ / "template" / pins["modules"]["runtime"] / "lords-frontend.py"

if not релиз.exists():
    print(f"нет файла релиза: {релиз}", file=sys.stderr)
    sys.exit(1)

h = hashlib.sha256()
with релиз.open("rb") as fh:
    for кусок in iter(lambda: fh.read(1 << 20), b""):
        h.update(кусок)
факт = h.hexdigest()

if факт != ожидаемый:
    print(f"sha256 релиза {факт} не совпал с закреплённым {ожидаемый}", file=sys.stderr)
    sys.exit(1)
print(f"закреплённый шаблон совпал: {факт}")
'''


def прочитать(путь: Path) -> str:
    return путь.read_text(encoding="utf-8") if путь.exists() else ""


def записать(путь: Path, содержимое: str, режим: int = 0o644) -> bool:
    путь.parent.mkdir(parents=True, exist_ok=True)
    изменилось = прочитать(путь) != содержимое
    if изменилось:
        путь.write_text(содержимое, encoding="utf-8")
    путь.chmod(режим)
    return изменилось


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None, help="путь к проекту сайта")
    args = ap.parse_args()

    cell = registry.resolve(SITE_ID)
    корень = Path(args.repo) if args.repo else (РЕПО / cell.repo["path"])
    if not (корень / ".git").exists():
        raise SystemExit(f"{корень} не Git-проект: сначала factory.cell.siterepo.generate")

    манифест_рантайма = json.loads(
        Path("/srv/lords/.frontend/template-manifest-zona-02.json").read_text(encoding="utf-8"))

    изменения = []

    # 1. Запуск.
    изменения.append(("run.py", записать(
        корень / "run.py",
        RUN_PY.format(site_id=SITE_ID, domain=DOMAIN, neighbours=СОСЕДИ),
        0o755)))

    # 2. Сборка.
    изменения.append(("build/build.py", записать(корень / "build" / "build.py", BUILD_PY, 0o755)))

    # 3. Выкладка и откат.
    изменения.append(("deploy/install.sh", записать(
        корень / "deploy" / "install.sh", INSTALL_SH.format(site_id=SITE_ID), 0o755)))
    изменения.append(("deploy/rollback.sh", записать(
        корень / "deploy" / "rollback.sh", ROLLBACK_SH.format(site_id=SITE_ID), 0o755)))

    # 4. Проверки.
    изменения.append(("checks/no_neighbour_paths.py", записать(
        корень / "checks" / "no_neighbour_paths.py",
        NO_NEIGHBOUR_PY.format(neighbours=СОСЕДИ))))
    изменения.append(("checks/pinned_template_sha.py", записать(
        корень / "checks" / "pinned_template_sha.py", PINNED_SHA_PY)))
    изменения.append(("checks/deploy_smoke.py", записать(
        корень / "checks" / "deploy_smoke.py", DEPLOY_SMOKE_PY)))
    изменения.append(("checks/run.sh", записать(
        корень / "checks" / "run.sh", CHECKS_SH, 0o755)))

    # 5. Конфигурация рантайма. Секретов здесь нет и быть не может: Publisher ID
    #    — открытое значение web component, счётчик Метрики пуст до выдачи.
    runtime = {
        "schema_version": "1.0",
        "site_id": SITE_ID,
        "domain": DOMAIN,
        "canonical_host": DOMAIN,
        "port": ПОРТ,
        "site_name": "Zona",
        "release_dir": ИМЯ_ШАБЛОНА,
        "template_revision": манифест_рантайма["build_id"],
        "data_root": ДАННЫЕ_ПО_УМОЛЧАНИЮ,
        "ad_slots_enabled": False,
        "metrika_counter": None,
        "metrika_note": (
            "BLOCKED_SECRET: собственный счётчик zonafilm.cc ещё не создан — токен "
            "Метрики читает сервисная учётная запись, не сессия агента. Домен "
            "заведён в реестре аналитики фабрики (config/analytics.json, состояние "
            "planned), поэтому создание счётчика — одна команда, и она не заведёт "
            "второй: провайдер сначала ищет счётчик этого домена и переиспользует "
            "найденный. Пустое значение здесь означает «счётчика нет», а не «возьми "
            "соседний»: витрина при нём не отдаёт тег вовсе — ни скрипта, ни "
            "noscript-пикселя. Проверено исполнением, см. "
            "artifacts/evidence/zona-02-launch-01/04-metrika/."),
        "indexing_enabled": False,
        "indexing_note": (
            "Витрина закрыта от индексации на двух уровнях: заголовок "
            "X-Robots-Tag и разметка страницы. Открытие — отдельная команда "
            "владельца после визуальной приёмки."),
        "comments": {
            "module": "site-factory/comments-platform",
            "module_version": "0.1.0-mvp",
            "tenant_id": "zona",
            "read_enabled": 0,
            "write_enabled": 0,
            "publication_enabled": 0,
            "seo_mode": "user_initiated",
            "note": (
                "Значения задвижек — контракт общей платформы комментариев "
                "(docs/comments_platform/INTEGRATION.md). Открывает их терминал "
                "платформы, а не этот проект: общая служба меняется одним "
                "владельцем за раз."),
        },
    }
    изменения.append(("config/runtime.json", записать(
        корень / "config" / "runtime.json",
        json.dumps(runtime, ensure_ascii=False, indent=2) + "\n")))

    # 6. Манифест шаблона внутри релиза: витрина обязана отвечать, какой релиз
    #    исполняет, не заглядывая в общий каталог соседей.
    свой = dict(манифест_рантайма)
    свой["artifact_path"] = f"template/{ИМЯ_ШАБЛОНА}/lords-frontend.py"
    свой["release_dir"] = f"template/{ИМЯ_ШАБЛОНА}"
    свой["note"] = (
        "Манифест витрины zonafilm.cc внутри её собственного релиза. Пути "
        "относительны корню релиза: витрина не зависит от общего каталога.")
    изменения.append(("template-manifest.json", записать(
        корень / "template-manifest.json",
        json.dumps(свой, ensure_ascii=False, indent=2, sort_keys=True) + "\n")))

    # 7. pins: sha закреплённого шаблона проверяется, а не описывается.
    pins_файл = корень / "pins.lock.json"
    pins = json.loads(pins_файл.read_text(encoding="utf-8"))
    pins["pins"]["template_sha256"] = манифест_рантайма["code_file_sha256"]
    pins["pins"]["modules"]["runtime"] = ИМЯ_ШАБЛОНА
    изменения.append(("pins.lock.json", записать(
        pins_файл, json.dumps(pins, ensure_ascii=False, indent=2) + "\n")))

    # 8. CI, который действительно собирает и сверяет две сборки.
    изменения.append((".github/workflows/release.yml", записать(
        корень / ".github" / "workflows" / "release.yml",
        CI_TEMPLATE.format(site_id=SITE_ID, domain=DOMAIN))))

    # 9. Юнит и vhost: витрина самодостаточна и не зависит от каталога фабрики
    #    в вопросе «чем меня поднимают и кто ко мне проксирует».
    изменения.append(("deploy/systemd/nova-zona-02.service", записать(
        корень / "deploy" / "systemd" / "nova-zona-02.service",
        UNIT_TEMPLATE.format(
            site_id=SITE_ID, domain=DOMAIN, port=ПОРТ,
            site_root="/srv/lords/.frontend/sites/zona-02",
            data_root=ДАННЫЕ_ПО_УМОЛЧАНИЮ,
            python="/srv/site-factory/repo/.venv/bin/python3"))))
    vhost = (РЕПО / "automation" / "host" / "nginx" / "zona-02.conf").read_text(encoding="utf-8")
    изменения.append(("deploy/nginx/zona-02.conf", записать(
        корень / "deploy" / "nginx" / "zona-02.conf", vhost)))
    # Активация и её откат едут вместе с сайтом: ячейка обязана ставиться без
    # доступа к фабрике. Источник один — файл в фабрике, чтобы копии не
    # разошлись; сюда он копируется, а не переписывается.
    for имя in ("activate", "deactivate"):
        текст = (РЕПО / "automation" / "host" / f"zonafilm-cc-{имя}.sh").read_text(
            encoding="utf-8")
        изменения.append((f"deploy/{имя}.sh", записать(
            корень / "deploy" / f"{имя}.sh", текст, 0o755)))

    # 10. Заявка на подключение к общему модулю комментариев. Именно заявка:
    #     реестр платформы принадлежит другому терминалу, и правка общей службы
    #     одновременно с тем, кто её готовит, даёт не подключение, а конфликт.
    заявка = {
        "schema_version": "COMMENTS_PLATFORM_SITE_BINDING_REQUEST_V1",
        "status": "REQUESTED",
        "note": (
            "Заявка на строку в config/comments-platform/sites.json платформы. "
            "Отправлена как docs/zona-02/COMMENTS_RATINGS_HANDOFF.md. Сам реестр "
            "этой заявкой не меняется."),
        "binding": {
            "tenant_id": "zona",
            "site_id": SITE_ID,
            "hosts": [DOMAIN],
            "allowed_origins": [f"https://{DOMAIN}"],
            "module_version": "0.1.0-mvp",
            "artifact_checksum": None,
            "theme": "auto",
            "language": "ru",
            "moderation_mode": "pre",
            "read_enabled": 0,
            "write_enabled": 0,
            "publication_enabled": 0,
            "seo_mode": "user_initiated",
            "rollout_percent": 0,
            "max_depth": 3,
            "max_length": 4000,
            "max_links": 2,
        },
        "artifact_checksum_note": (
            "null намеренно: сумма обязана совпадать с фактически выложенным "
            "артефактом виджета и считается на стороне платформы. Скопировать "
            "значение из чужой строки реестра значило бы объявить проверенной "
            "сумму, которую этот проект не считал."),
        "discussion_key": "tenant_id · site_id · resource_type · canonical_content_id",
        "content_id_note": (
            "canonical_content_id — постоянный идентификатор записи (detail.id), "
            "не slug и не адрес: slug меняется при пересборке снимка, и ветка "
            "обсуждения, привязанная к нему, заводилась бы заново каждую пересборку."),
        "isolation_from_neighbour": (
            "Изоляция от zona-01 обеспечивается парой tenant_id · site_id: у соседа "
            "site_id = zona-01, и записи не пересекаются даже при одинаковом "
            "canonical_content_id."),
        "blockers": [
            "в закреплённом шаблоне витрины нет точки монтирования виджета "
            "(0 вхождений data-cp-comments / SiteFactoryComments / comments-widget)",
            "витрина не принимает запись: POST/PUT/DELETE отвечают 501",
            "Stage 1 платформы авторизует один домен: SECOND_DOMAIN_DEPLOY_ALLOWED=false",
        ],
    }
    изменения.append(("config/comments-binding.request.json", записать(
        корень / "config" / "comments-binding.request.json",
        json.dumps(заявка, ensure_ascii=False, indent=2) + "\n")))

    # 11. Эксплуатация: запуск, выкладка, откат, границы.
    изменения.append(("docs/OPERATIONS.md", записать(
        корень / "docs" / "OPERATIONS.md", OPERATIONS_MD.format(
            site_id=SITE_ID, domain=DOMAIN, port=ПОРТ,
            data_root=ДАННЫЕ_ПО_УМОЛЧАНИЮ))))

    print(json.dumps({
        "repo": str(корень),
        "changed": [имя for имя, было in изменения if было],
        "unchanged": [имя for имя, было in изменения if not было],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
