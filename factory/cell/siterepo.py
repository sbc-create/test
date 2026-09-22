"""Отдельный Git-проект сайта.

В проект попадает то, что принадлежит этому сайту: выбранный шаблон, его
настройки, закреплённые версии общих зависимостей, миграции, проверки и
инструкция запуска. Не попадает: код фабрики, чужие сайты, базы, медиа и
секреты.

Почему не ветка монорепозитория. Ветка не даёт того, ради чего проект заводится:
у неё нет собственной истории сайта, собственных прав на выкладку и собственного
артефакта, который можно поставить, не имея доступа к фабрике. Ветка — это
удобство для того, кто уже внутри; проект — это граница.

Что здесь намеренно не делается: сюда не кладётся бизнес-логика. Обновился общий
модуль — сайт продолжает работать на своей закреплённой версии, пока её не
продвинут отдельно. Форк логики на домен был бы ровно тем, чего задание требует
избежать.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.paths import PATHS

SCHEMA_VERSION = "1.0"

#: Файлы, которых в проекте сайта не бывает никогда. Проверяется при сборке
#: релиза, а не только обещается в AGENTS.md: обещание не останавливает коммит.
FORBIDDEN_IN_REPO = (
    "*.sqlite3", "*.sqlite", "*.db", "*.dump", "*.sql",
    ".env", "*.pem", "*.key", "id_rsa", "id_ed25519",
)


class SiteRepoError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


AGENTS_TEMPLATE = """# AGENTS.md — проект сайта {site_id}

Этот репозиторий — один сайт: **{domain}**. Всё, что здесь меняется, меняет
только его.

## Область

| Что | Значение |
| --- | --- |
| site_id | `{site_id}` |
| Домен | `{domain}` |
| Шаблон | `{template_id}` (закреплён за этим сайтом) |
| Общее ядро | закреплено в `pins.lock.json`, версия `{core_pin}` |

## Правила, которые здесь не обсуждаются

1. **Только этот сайт.** Задача, начатая здесь, не переходит в соседний проект.
   Нет причины, по которой правка {site_id} требует открыть репозиторий другого
   сайта: если такая причина появилась — это задача на общее ядро, и она
   оформляется отдельно.
2. **Массовая замена по всей фабрике запрещена.** `sed -i` по всем сайтам, общий
   рефакторинг шаблонов, «заодно поправил у всех» — не здесь. Один выпуск
   меняет один сайт.
3. **Общее ядро меняется не отсюда.** Нужна правка общего модуля — заводится
   отдельная задача в репозитории фабрики, версия продвигается в `pins.lock.json`
   этого сайта отдельным выпуском. Обновление общего модуля не обновляет сеть:
   каждый сайт остаётся на своей закреплённой версии до явного продвижения.
4. **Ничего плавающего.** `latest`, `main`, `HEAD` в качестве версии зависимости
   не принимаются. Версия закреплена — иначе сборка невоспроизводима.
5. **Данные и секреты не коммитятся.** Базы, медиа, дампы, `.env`, ключи. Они
   доставляются отдельным защищённым каналом; собранный пакет не является
   резервной копией базы.
6. **Живой код по SSH не правится.** SSH допустим для диагностики и штатных
   install/deploy/rollback. Правка файла на работающем сервере не оставляет ни
   истории, ни отката и теряется при следующем выкате.

## Один выпуск — одна причина

Не смешивать в одном выпуске редизайн, миграцию данных и включение новой
возможности. Когда что-то из этого сломается, откатывать придётся всё сразу.

## Как выпускается изменение

```
задача (domain/site_id) → ветка в ЭТОМ репозитории → целевые тесты
  → сборка чистого commit → неизменяемый артефакт → подтверждение → деплой {site_id}
```

## Проверки перед выпуском

```bash
./checks/run.sh
```
"""

README_TEMPLATE = """# {site_id} — {domain}

Проект одного сайта. Общий код не здесь: в проекте лежат выбранный шаблон,
настройки сайта, закреплённые версии и проверки.

## Состав

| Путь | Что это |
| --- | --- |
| `site-manifest.json` | паспорт сайта: домен, шаблон, модули, владельцы полей |
| `pins.lock.json` | закреплённые версии общего ядра, шаблона, модулей и схем |
| `template/` | копия закреплённого шаблона |
| `config/` | настройки этого сайта |
| `migrations/` | миграции данных сайта, по порядку |
| `checks/` | проверки, которые обязаны пройти до выпуска |
| `AGENTS.md` | правила работы в этом репозитории |

## Чего здесь нет и не будет

Базы, медиа, дампы, секреты. Они переносятся отдельным защищённым экспортом.
Готовый пакет — это код и настройки, а не резервная копия данных.

## Запуск

```bash
./checks/run.sh                 # проверки
python3 -m factory cell release --site {site_id}   # сборка артефакта (из фабрики)
```

Установка готового артефакта на сервер описана в `docs/INSTALL.md`.
"""

INSTALL_TEMPLATE = """# Установка {site_id}

Ставится **готовый проверенный артефакт**. Сборка на целевом сервере не
выполняется: собранное там не совпадает с тем, что проверяли.

## Что нужно

| Вход | Откуда |
| --- | --- |
| артефакт `{site_id}-<digest>.tar.gz` | релизы этого проекта |
| `release-manifest.json` | рядом с артефактом |
| данные сайта | отдельный защищённый экспорт |
| секреты | отдельный канал, не из этого репозитория |

## Порядок

```bash
python3 -m factory cell install --site {site_id} --artifact <путь> --dry-run
python3 -m factory cell install --site {site_id} --artifact <путь>
python3 -m factory cell verify  --site {site_id}
```

`--dry-run` проверяет digest, манифест и совместимость версий, ничего не меняя.
Установка без совпадения digest не начинается.

## Откат

```bash
python3 -m factory cell rollback --site {site_id}
```

Откат возвращает код и маршрутизацию. Данные, принятые после переключения,
он сохраняет: комментарии и голоса не откатываются вместе с кодом.
"""

CHECKS_TEMPLATE = """#!/usr/bin/env bash
# Проверки проекта сайта. Падение любой из них — причина не выпускать релиз.
set -euo pipefail

cd "$(dirname "$0")/.."

fail=0
say() { printf '%-34s %s\\n' "$1" "$2"; }

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
check "template-present"     test -d template
check "no-floating-pins"     python3 checks/no_floating_pins.py
check "no-data-or-secrets"   python3 checks/no_data_or_secrets.py

exit "$fail"
"""

NO_FLOATING_PINS = '''"""Плавающих версий в проекте сайта не бывает.

`latest`, `main`, `HEAD` и пустая версия означают, что завтра сборка даст другой
результат, а сегодняшняя проверка ничего не доказывает.
"""
import json
import sys

FLOATING = {"latest", "main", "master", "HEAD", "head", "*", ""}

pins = json.load(open("pins.lock.json", encoding="utf-8"))
bad = []


def walk(prefix, value):
    if isinstance(value, dict):
        for key, item in value.items():
            walk(f"{prefix}.{key}" if prefix else key, item)
    elif isinstance(value, str) and value.strip() in FLOATING:
        bad.append(prefix)


walk("", pins.get("pins", pins))
if bad:
    print("плавающие версии:", ", ".join(sorted(bad)), file=sys.stderr)
    sys.exit(1)
'''

NO_DATA_OR_SECRETS = '''"""Данных и секретов в проекте сайта быть не может."""
import fnmatch
import pathlib
import sys

FORBIDDEN = {forbidden!r}

bad = []
for path in pathlib.Path(".").rglob("*"):
    if ".git" in path.parts or not path.is_file():
        continue
    for pattern in FORBIDDEN:
        if fnmatch.fnmatch(path.name, pattern):
            bad.append(str(path))
            break

if bad:
    print("в проекте сайта не место этим файлам:", ", ".join(sorted(bad)), file=sys.stderr)
    sys.exit(1)
'''

#: Шаблон CI проекта сайта.
#:
#: Написан под GitHub Actions, потому что именно он настроен у фабрики
#: (`.github/workflows/`). Механизмы, а не синтаксис, переносимы: у любого CI
#: есть группа параллелизма и шаг проверки — при смене провайдера меняется
#: запись, а не смысл.
#:
#: Три вещи, которые он обязан делать, и каждая куплена отдельным случаем:
#:  * `concurrency` с группой по сайту — два выката одного сайта одновременно
#:    перетирают друг друга, и виноватым оказывается тот, кто выкатил раньше;
#:  * проверка `site_id` — чужой артефакт, поставленный по ошибке, обнаруживается
#:    на живом домене;
#:  * сверка ожидаемой исходной ревизии — вчерашняя сессия иначе молча
#:    перезапишет сегодняшний релиз.
CI_TEMPLATE = """# Выпуск сайта {site_id}. Меняет только его.
name: release

on:
  push:
    branches: [main]
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
          # отвечает 0 (предок), 1 (не предок) и иначе — «не смог ответить»,
          # например когда коммита нет в истории. Считать «не смог» за «не
          # устарел» значит пропустить ровно тот выкат, ради которого шаг и
          # написан.
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
        run: |
          echo "Артефакт собирается фабрикой:"
          echo "  python3 -m factory cell release --site {site_id}"
          echo "Сборка на целевом сервере не выполняется: собранное там — другая сборка."

# Чего здесь нет намеренно: шага, который трогает соседние сайты, и шага,
# который переключает домен. Переключение маршрутизации — отдельное решение
# с подтверждением владельца, а не побочный эффект зелёной сборки.
"""

GITIGNORE = """# Данные сайта живут не в Git.
*.sqlite3
*.sqlite
*.db
*.dump
*.sql
.env
*.pem
*.key
media/
var/
data/
__pycache__/
"""


@dataclass(frozen=True)
class SiteRepo:
    site_id: str
    path: Path
    commit: str
    manifest: dict[str, Any]

    @property
    def manifest_path(self) -> Path:
        return self.path / "site-manifest.json"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )
    if check and result.returncode != 0:
        raise SiteRepoError(
            f"git {' '.join(args)} в {repo}: код {result.returncode}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def build_manifest(*, site_id: str, domain: str, template_id: str,
                   modules: tuple[str, ...], pins: dict[str, Any],
                   publisher: dict[str, Any], deploy_target: dict[str, Any],
                   aliases: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "site_id": site_id,
        "domain": domain,
        "aliases": list(aliases),
        "template": {"template_id": template_id},
        "modules": list(modules),
        "publisher": dict(publisher),
        "deploy_target": dict(deploy_target),
        # Владение полями объявлено в манифесте, потому что спор за поле решается
        # до записи, а не после: см. factory.cell.ownership.
        "field_ownership": {
            "catalog": ["title", "original_name", "year", "kind", "seasons",
                        "episodes", "availability", "poster_url"],
            "external_ratings": ["rating_external"],
            "seo": ["seo_title", "seo_description", "seo_text", "meta_keywords"],
            "manual": ["*"],
            "rule": "Владелец пишет только свои поля. Приоритет ручной правки выше "
                    "обоих источников. «Последний записавший победил» не применяется.",
        },
        "data": {
            "location": "вне каталога релиза",
            "note": "Каталог, SEO-тексты и пользовательские данные не лежат внутри "
                    "сменяемой папки релиза: смена релиза не должна их касаться.",
        },
        "generated_at": utc_now(),
        "pins_ref": "pins.lock.json",
    }


def generate(*, site_id: str, domain: str, template_id: str, template_source: Path,
             modules: tuple[str, ...], pins: dict[str, Any], publisher: dict[str, Any],
             deploy_target: dict[str, Any], destination: Path,
             aliases: tuple[str, ...] = (), force: bool = False) -> SiteRepo:
    """Создать проект сайта и сделать первый коммит."""
    if destination.exists():
        if not force:
            raise SiteRepoError(
                f"каталог {destination} уже существует; "
                "перезапись проекта сайта требует --force"
            )
        shutil.rmtree(destination)
    if not template_source.exists():
        raise SiteRepoError(f"исходника шаблона нет: {template_source}")

    destination.mkdir(parents=True)
    manifest = build_manifest(
        site_id=site_id, domain=domain, template_id=template_id, modules=modules,
        pins=pins, publisher=publisher, deploy_target=deploy_target, aliases=aliases,
    )

    (destination / "site-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "pins.lock.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "site_id": site_id,
                    "pins": pins, "generated_at": utc_now()},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    template_dir = destination / "template"
    template_dir.mkdir()
    if template_source.is_dir():
        shutil.copytree(template_source, template_dir / template_source.name)
    else:
        shutil.copy2(template_source, template_dir / template_source.name)

    (destination / "config").mkdir()
    (destination / "config" / "site.json").write_text(
        json.dumps({"site_id": site_id, "domain": domain,
                    "template_id": template_id, "modules": list(modules)},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    migrations = destination / "migrations"
    migrations.mkdir()
    (migrations / "README.md").write_text(
        "# Миграции\n\nПо одной на выпуск, по возрастанию номера. Первый пилот "
        "формат данных не меняет: расширение схемы — совместимое, удаление старых "
        "полей — отдельным выпуском после закрытия окна отката.\n", encoding="utf-8")

    checks = destination / "checks"
    checks.mkdir()
    run_sh = checks / "run.sh"
    run_sh.write_text(CHECKS_TEMPLATE, encoding="utf-8")
    run_sh.chmod(0o755)
    (checks / "no_floating_pins.py").write_text(NO_FLOATING_PINS, encoding="utf-8")
    (checks / "no_data_or_secrets.py").write_text(
        NO_DATA_OR_SECRETS.replace("{forbidden!r}", repr(list(FORBIDDEN_IN_REPO))),
        encoding="utf-8")

    docs = destination / "docs"
    docs.mkdir()
    (docs / "INSTALL.md").write_text(
        INSTALL_TEMPLATE.format(site_id=site_id), encoding="utf-8")

    workflows = destination / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "release.yml").write_text(
        CI_TEMPLATE.format(site_id=site_id), encoding="utf-8")

    (destination / "AGENTS.md").write_text(AGENTS_TEMPLATE.format(
        site_id=site_id, domain=domain, template_id=template_id,
        core_pin=pins.get("common_core", "—")), encoding="utf-8")
    (destination / "README.md").write_text(
        README_TEMPLATE.format(site_id=site_id, domain=domain), encoding="utf-8")
    (destination / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

    _git(destination, "init", "-q", "-b", "main")
    _git(destination, "config", "user.name", "site-factory")
    _git(destination, "config", "user.email", "site-factory@localhost")
    _git(destination, "add", "-A")
    _git(destination, "commit", "-q", "-m",
         f"{site_id}: проект сайта на шаблоне {template_id}")
    commit = _git(destination, "rev-parse", "HEAD")
    return SiteRepo(site_id=site_id, path=destination, commit=commit, manifest=manifest)


def head_commit(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def is_clean(repo: Path) -> bool:
    return _git(repo, "status", "--porcelain") == ""


def source_dir_for_template(template_id: str, pool_entry: dict[str, Any] | None = None) -> Path:
    if pool_entry and pool_entry.get("source"):
        return PATHS.root / pool_entry["source"]
    raise SiteRepoError(
        f"не знаю, где исходник шаблона {template_id}: в пуле не указан source"
    )
