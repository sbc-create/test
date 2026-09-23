"""Выделение действующего сайта в собственный репозиторий.

Отличие от `siterepo.generate`, который заводит проект для НОВОГО сайта: здесь
исходной точкой служит уже работающий экземпляр. Ничего не придумывается —
всё берётся из наблюдаемого состояния хоста:

* порт, юнит и ссылка на релиз — из реестра рантайма;
* переменные окружения — из самого юнита systemd, потому что именно он сегодня
  определяет, какие файлы читает сайт;
* исполняемые файлы — из каталога релиза, на который указывает `current`;
* происхождение — из `RELEASE.json` рядом с ними, а где его нет, честно
  записывается «снято с исполняемого релиза».

Почему переменные берутся из юнита, а не из профиля. Профиль описывает
намерение, юнит — действительность. Они расходились: у animedia-02 профиль нёс
счётчик и canonical соседнего сайта, а юнит — правильные пути. Переносить надо
то, что работает.

Главная ловушка, от которой защищает результат. У рантайма этих семейств
**каждое** умолчание указывает на соседний сайт: каталог, манифест шаблона,
старый корень. Пока юнит задавал все пути явно, это было безопасно. В отдельном
развёртывании одна незаданная переменная означала бы, что сайт молча отдаёт
каталог соседа и пишет в его хранилище. Поэтому сгенерированный `run.py`
выставляет всё явно и отказывается стартовать, если путь ведёт к соседу.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FRONTEND = Path("/srv/lords/.frontend")
RUNTIME_REGISTRY = FRONTEND / "lords-runtime-registry.json"
UNIT_DIR = Path("/etc/systemd/system")

#: Отозванные поставщиком идентификаторы издателя. В активную настройку не
#: попадают ни при каких условиях: плеер с ними не заработает.
RETIRED_PUBLISHER_IDS = frozenset({"10331", "10332", "10333"})


class ExtractError(RuntimeError):
    pass


@dataclass
class LiveSite:
    """Наблюдаемое состояние действующего сайта."""

    site_id: str
    port: int
    unit: str
    domain: str | None
    release_dir: Path
    environment: dict[str, str]
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_commit: str | None = None
    build_id: str | None = None
    family: str = ""
    #: Для витрин, чей релиз — один файл рядом с общими модулями.
    single_file: str | None = None

    @property
    def catalog(self) -> str | None:
        return self.environment.get("LORDS_CATALOG") or self.environment.get("ANIMEDIA_CATALOG")

    @property
    def legacy_root(self) -> str | None:
        return (self.environment.get("LORDS_LEGACY_ROOT")
                or self.environment.get("ANIMEDIA_LEGACY_ROOT"))

    @property
    def data_root(self) -> Path | None:
        """Каталог данных сайта: `/srv/lords/<site>/data` рядом с релизом."""
        root = self.environment.get("LORDS_LEGACY_ROOT") or self.environment.get(
            "ANIMEDIA_LEGACY_ROOT")
        if not root:
            return None
        # `/srv/lords/<site>/current/site` → `/srv/lords/<site>/data`
        p = Path(root)
        for parent in p.parents:
            if (parent / "data").is_dir():
                return parent / "data"
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_unit(unit: str) -> dict[str, str]:
    """Переменные окружения из юнита systemd.

    Читается файл, а не вывод `systemctl show`: показывать состояние службы
    может быть нечем, а файл юнита доступен на чтение и является источником,
    из которого служба и стартует.
    """
    path = UNIT_DIR / unit
    if not path.is_file():
        raise ExtractError(f"юнита нет: {path}")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*Environment=([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    return env


def observe_from_unit(site_id: str, unit: str) -> LiveSite:
    """Состояние сайта, которого нет в реестре рантайма.

    Реестр охватывает семейства lords/animedia/zona. Витрины Yummy в него не
    внесены, но юнит у них есть и он так же полон: порт в ExecStart, пути в
    Environment. Источником служит то, что реально запускает службу.
    """
    path = UNIT_DIR / unit
    if not path.is_file():
        raise ExtractError(f"{site_id}: юнита нет: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"ExecStart=.*?--port[= ](\d+)", text)
    if not m:
        raise ExtractError(f"{site_id}: в {unit} не нашёл --port")
    exec_m = re.search(r"ExecStart=\S+\s+(\S+)", text)
    артефакт = Path(exec_m.group(1)) if exec_m else None
    if not артефакт or not артефакт.is_file():
        raise ExtractError(f"{site_id}: исполняемый файл из ExecStart не найден")
    return LiveSite(
        site_id=site_id, port=int(m.group(1)), unit=unit, domain=None,
        release_dir=артефакт.parent, environment=read_unit(unit),
        files={}, source_commit=None, build_id=None, family="yummy",
        single_file=артефакт.name,
    )


def observe(site_id: str) -> LiveSite:
    """Снять фактическое состояние сайта с хоста."""
    registry = json.loads(RUNTIME_REGISTRY.read_text(encoding="utf-8"))
    entry = (registry.get("sites") or {}).get(site_id)
    if not entry:
        raise ExtractError(f"{site_id}: записи нет в реестре рантайма")

    link = Path(entry["release_link"])
    if not link.exists():
        raise ExtractError(
            f"{site_id}: ссылка на релиз {link} никуда не ведёт — сайт не развёрнут"
        )
    release_dir = link.resolve()

    files: dict[str, Any] = {}
    source_commit = build_id = None
    rj = release_dir / "RELEASE.json"
    if rj.is_file():
        data = json.loads(rj.read_text(encoding="utf-8"))
        files = data.get("files") or {}
        source_commit = data.get("source_commit")
        build_id = data.get("build_id")

    return LiveSite(
        site_id=site_id,
        port=int(entry["port"]),
        unit=entry["unit"],
        domain=entry.get("exact_domain"),
        release_dir=release_dir,
        environment=read_unit(entry["unit"]),
        files=files,
        source_commit=source_commit,
        build_id=build_id,
        family=entry.get("family", ""),
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(live: LiveSite, repo_root: Path) -> dict[str, Any]:
    """Происхождение каждого исполняемого файла.

    Три исхода, и смешивать их нельзя: подтверждено гитом, подтверждено только
    манифестом релиза, не подтверждено ничем. Последнее — законное состояние
    для сайтов, чей релиз собран без метаданных, но называть его проверенным
    нельзя.
    """
    out: dict[str, Any] = {}
    for path in sorted(live.release_dir.glob("*.py")):
        digest = sha256_file(path)
        meta = live.files.get(path.name) or {}
        запись = {"sha256": digest, "bytes": path.stat().st_size,
                  "verified_against": "ничего"}
        if meta.get("sha256"):
            запись["verified_against"] = (
                "release-manifest" if meta["sha256"] == digest else "РАСХОЖДЕНИЕ")
        repo_path = meta.get("repo_path")
        if not repo_path and live.source_commit:
            # Релиз собран без метаданных о путях. Происхождение всё равно
            # можно доказать: ищем в исходном коммите файл с таким же именем и
            # сверяем байты. Совпадение имени само по себе ничего не значит —
            # решает только sha256.
            found = subprocess.run(
                ["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only",
                 live.source_commit],
                capture_output=True, text=True, check=False)
            if found.returncode == 0:
                кандидаты = [c for c in found.stdout.split()
                             if c.rsplit("/", 1)[-1] == path.name]
                for кандидат in кандидаты:
                    blob = subprocess.run(
                        ["git", "-C", str(repo_root), "show",
                         f"{live.source_commit}:{кандидат}"],
                        capture_output=True, check=False)
                    if (blob.returncode == 0
                            and hashlib.sha256(blob.stdout).hexdigest() == digest):
                        repo_path = кандидат
                        break
        if repo_path and live.source_commit:
            blob = subprocess.run(
                ["git", "-C", str(repo_root), "show", f"{live.source_commit}:{repo_path}"],
                capture_output=True, check=False)
            if blob.returncode == 0:
                совпало = hashlib.sha256(blob.stdout).hexdigest() == digest
                запись["repo_path"] = repo_path
                запись["verified_against"] = "git" if совпало else "РАСХОЖДЕНИЕ С GIT"
        out[path.name] = запись
    return out


def player_config(live: LiveSite) -> dict[str, Any]:
    """Настройка плеера сайта: путь и проверка идентификатора издателя."""
    путь = live.environment.get("LORDS_PLAYER_CONFIG")
    if not путь:
        # Соглашение рантайма: player-<site>.json рядом со снимком каталога.
        каталог = live.catalog
        if каталог and каталог.endswith("-catalog.json"):
            имя = Path(каталог).name[: -len("-catalog.json")]
            путь = str(Path(каталог).with_name(f"player-{имя}.json"))
    if not путь or not Path(путь).is_file():
        return {"path": путь, "publisher_id": None,
                "note": "настройка плеера не найдена — воспроизведение не подтверждено"}
    данные = json.loads(Path(путь).read_text(encoding="utf-8"))
    pid = str(данные.get("publisher_id", "")).strip()
    if pid in RETIRED_PUBLISHER_IDS:
        raise ExtractError(
            f"{live.site_id}: в активной настройке отозванный publisher_id {pid}")
    return {"path": путь, "publisher_id": pid or None}


def neighbours(site_id: str) -> list[str]:
    """Соседние сайты, к которым ведут умолчания рантайма."""
    registry = json.loads(RUNTIME_REGISTRY.read_text(encoding="utf-8"))
    return sorted(s for s in (registry.get("sites") or {}) if s != site_id)


def copy_runtime(live: LiveSite, destination: Path) -> list[str]:
    """Скопировать исполняемые файлы релиза в проект сайта."""
    src = destination / "src"
    src.mkdir(parents=True, exist_ok=True)
    имена = []
    for path in sorted(live.release_dir.glob("*.py")):
        shutil.copy2(path, src / path.name)
        имена.append(path.name)
    if not имена:
        raise ExtractError(f"{live.site_id}: в релизе {live.release_dir} нет .py файлов")
    return имена


LAUNCHER = '''#!/usr/bin/env python3
"""Запуск {domain} из этого репозитория и только из него.

Рантайм этого семейства собран так, что его умолчания указывают на СОСЕДНИЙ
сайт: каталог, манифест шаблона, старый корень. Пока юнит задавал все пути
явно и лежал рядом с соседями, это было безопасно. В отдельном развёртывании
одна незаданная переменная означала бы, что {domain} молча отдаёт каталог
соседа и пишет в его хранилище — и заметили бы это не сразу.

Поэтому здесь fail-closed: все переменные выставляются явно из
`config/site.json`, а затем проверяется, что ни один путь не ведёт к соседу.
Несовпадение — отказ до первого запроса, а не после.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "site.json"


class StartupError(RuntimeError):
    pass


def load_config() -> dict:
    if not CONFIG.is_file():
        raise StartupError(f"нет {{CONFIG}}: запускать нечего")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def data_dir(args, config: dict) -> Path:
    value = args.data_dir or os.environ.get("SITE_DATA_DIR")
    if not value:
        raise StartupError(
            "каталог данных не задан: укажите --data-dir или SITE_DATA_DIR. "
            "Пустое значение — не повод взять чужой: умолчания рантайма ведут "
            f"к {{config['neighbour_site_ids']}}"
        )
    return Path(value).resolve()


def environment(config: dict, data: Path) -> dict:
    """Полный набор переменных. Ни одна не оставляется на умолчание."""
    site_id = config["site_id"]
    env = {{}}
    for name, template in config["environment"].items():
        env[name] = template.replace("<data>", str(data)).replace("<app>", str(ROOT))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def foreign_paths(env: dict, config: dict) -> list:
    """Ни один путь не должен вести к соседнему сайту."""
    mine = config["site_id"]
    bad = []
    for neighbour in config.get("neighbour_site_ids", []):
        for name, value in env.items():
            if neighbour in value and mine not in value:
                bad.append(f"{{name}}={{value}} ведёт к соседнему сайту {{neighbour}}")
    return bad


def check_player(config: dict, env: dict) -> list:
    """Publisher ID обязан быть на месте и быть тем самым.

    Проверка применяется там, где плеер вообще настраивается. У витрин Yummy
    воспроизведением занимается верхний поток Next.js, своего player.json у них
    нет и не должно быть — требовать его значило бы заваливать корректную
    конфигурацию. Но если сайт объявил ожидаемый publisher_id, файл обязан быть
    и обязан совпасть: тут послабления нет.
    """
    path = env.get("LORDS_PLAYER_CONFIG")
    expected = str(config.get("publisher_id_expected") or "").strip()
    retired = {{"10331", "10332", "10333"}}
    if not path and not expected:
        return []
    if not path:
        return [f"сайт объявляет publisher_id {{expected}}, но LORDS_PLAYER_CONFIG "
                "не задан: плеер не настроен"]
    p = Path(path)
    if not p.is_file():
        return [f"нет {{p}}: плеер без publisher_id не заработает"]
    try:
        actual = str(json.loads(p.read_text(encoding="utf-8")).get("publisher_id", "")).strip()
    except ValueError as exc:
        return [f"{{p}} не читается как JSON: {{exc}}"]
    if not actual:
        return [f"{{p}}: publisher_id пуст — это BLOCKED_INPUT, а не умолчание"]
    if actual in retired:
        return [f"{{p}}: publisher_id {{actual}} отозван поставщиком"]
    if expected and actual != expected:
        return [f"{{p}}: publisher_id {{actual}}, а сайт объявляет {{expected}}"]
    return []


def check_data(env: dict) -> list:
    bad = []
    catalog = env.get("LORDS_CATALOG") or env.get("ANIMEDIA_CATALOG")
    if catalog and not Path(catalog).is_file():
        bad.append(f"нет снимка каталога {{catalog}}: витрине нечего показывать")
    return bad


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="запуск {domain}")
    parser.add_argument("--port", type=int)
    parser.add_argument("--data-dir")
    parser.add_argument("--check", action="store_true",
                        help="только проверить конфигурацию и выйти")
    args = parser.parse_args(argv)

    config = load_config()
    data = data_dir(args, config)
    port = args.port or int(config["port"])
    env = environment(config, data)

    problems = foreign_paths(env, config) + check_player(config, env) + check_data(env)
    if problems:
        print(f"запуск {{config['domain']}} остановлен до первого запроса:", file=sys.stderr)
        for p in problems:
            print(f"  — {{p}}", file=sys.stderr)
        return 78

    if args.check:
        print(f"{{config['domain']}} ({{config['site_id']}}): конфигурация полна")
        for name in sorted(env):
            print(f"  {{name}}={{env[name]}}")
        return 0

    os.environ.update(env)
    artifact = ROOT / "src" / config["entrypoint"]
    if not artifact.is_file():
        print(f"нет артефакта {{artifact}}", file=sys.stderr)
        return 70
    os.execv(sys.executable, [sys.executable, str(artifact), "--port", str(port)])
    return 72


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StartupError as error:
        print(f"{{error}}", file=sys.stderr)
        raise SystemExit(78) from None
'''


def environment_template(live: LiveSite) -> dict[str, str]:
    """Переменные сайта с подстановочными метками вместо машинных путей.

    `<data>` заменяется каталогом данных при запуске. Так репозиторий не несёт
    в себе путь конкретной машины и остаётся переносимым.
    """
    данные = live.data_root
    шаблон: dict[str, str] = {}
    for имя, значение in live.environment.items():
        if имя == "PYTHONDONTWRITEBYTECODE":
            continue
        новое = значение
        if данные and str(данные) in значение:
            новое = значение.replace(str(данные), "<data>")
        # Снимки каталога и подробностей переезжают в каталог данных сайта.
        новое = новое.replace(str(FRONTEND), "<data>")
        # Дерево страниц прежнего релиза тоже становится данными.
        новое = re.sub(r"/srv/lords/[a-z0-9-]+/current/site", "<data>/site", новое)
        шаблон[имя] = новое
    plc = player_config(live)
    if plc.get("path"):
        шаблон["LORDS_PLAYER_CONFIG"] = "<app>/config/player.json"
    return шаблон


def entrypoint_for(live: LiveSite, names: list[str]) -> str:
    """Какой файл релиза запускается.

    У Animedia рядом лежит совместимая заглушка `lords-frontend.py`, которая
    лишь передаёт управление своему артефакту. Запускать надо артефакт, иначе
    `__file__` укажет на заглушку и витрина объявит не то, что исполняет.
    """
    if "animedia-frontend.py" in names:
        return "animedia-frontend.py"
    if "lords-frontend.py" in names:
        return "lords-frontend.py"
    raise ExtractError(f"{live.site_id}: не нашёл точку входа среди {names}")


def build_repo(site_id: str, *, domain: str, destination: Path, repo_root: Path,
               template_id: str, force: bool = False) -> dict[str, Any]:
    """Собрать репозиторий сайта из его действующего релиза."""
    live = observe(site_id)
    if destination.exists():
        if not force:
            raise ExtractError(f"{destination} уже существует; нужен force")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    names = copy_runtime(live, destination)
    prov = provenance(live, repo_root)
    plc = player_config(live)
    entry = entrypoint_for(live, names)
    env_template = environment_template(live)

    config = {
        "schema_version": 1,
        "site_id": site_id,
        "domain": domain,
        "family": live.family or "lords",
        "port": live.port,
        "entrypoint": entry,
        "template": {"template_id": template_id},
        "publisher_id_ref": "secret://cdnvideohub/<профиль>/publisher-id",
        "publisher_id_expected": plc.get("publisher_id"),
        "environment": env_template,
        "neighbour_site_ids": neighbours(site_id),
        "neighbour_note": (
            "Умолчания рантайма ведут к этим сайтам. Запуск отказывает, если "
            "хоть один путь указывает на соседа."),
        "indexing_note": (
            "Режим индексации задан владельцем и этой задачей не меняется."),
    }
    (destination / "config").mkdir()
    (destination / "config" / "site.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "config" / "player.json.example").write_text(
        json.dumps({"_note": "Образец. Настоящий player.json в git не попадает.",
                    "publisher_id": "<из Secret Hub>",
                    "source_mode": "provider-id"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    manifest_src = live.environment.get("LORDS_TEMPLATE_MANIFEST")
    if manifest_src and Path(manifest_src).is_file():
        shutil.copy2(manifest_src, destination / "config" / "template-manifest.json")

    pins = {
        "schema_version": 1,
        "site_id": site_id,
        "note": ("Закреплённые версии. Плавающих значений здесь не бывает: "
                 "latest/main/HEAD сделали бы завтрашнюю сборку другой."),
        "pins": {
            "source_commit": live.source_commit,
            "build_id": live.build_id,
            "template": template_id,
            "entrypoint": entry,
            "python": "3.10",
        },
        "files": prov,
        "provenance_note": (
            "verified_against: git — байты совпали с исходным коммитом; "
            "release-manifest — совпали с манифестом релиза, но коммита нет; "
            "ничего — релиз собран без метаданных, происхождение не доказано."),
    }
    (destination / "pins.lock.json").write_text(
        json.dumps(pins, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (destination / "run.py").write_text(
        LAUNCHER.format(domain=domain), encoding="utf-8")
    (destination / "run.py").chmod(0o755)

    (destination / ".gitignore").write_text(
        "# Данные и секреты сайта в Git не хранятся.\n"
        "config/player.json\ndata/\nvar/\ndist/\n*-catalog.json\n*-details.json\n"
        "*community*.json\n__pycache__/\n*.pyc\n", encoding="utf-8")

    (destination / "README.md").write_text(
        f"# {domain}\n\nСамостоятельный сайт `{site_id}`, выделенный из фабрики.\n\n"
        f"Исполняемый код снят с действующего релиза `{live.release_dir.name}`.\n"
        f"Происхождение каждого файла — в `pins.lock.json`.\n\n"
        "## Запуск с чистого клона\n\n```bash\n"
        "cp config/player.json.example config/player.json   # значение из Secret Hub\n"
        f"python3 run.py --check --data-dir /srv/{site_id}/data\n"
        f"python3 run.py --port {live.port} --data-dir /srv/{site_id}/data\n```\n\n"
        "`--check` отказывает, если путь ведёт к соседнему сайту или нет "
        "publisher_id. Не подняться лучше, чем подняться на чужих данных.\n\n"
        "## Чего здесь нет\n\nСнимков каталога, страниц, комментариев, голосов и "
        "секретов: это данные, они доставляются отдельно.\n", encoding="utf-8")

    (destination / "AGENTS.md").write_text(
        f"# AGENTS.md — проект сайта {site_id}\n\n"
        f"Этот репозиторий — один сайт: **{domain}**.\n\n"
        f"Соседи: {', '.join(neighbours(site_id))} — они правятся не отсюда никогда.\n\n"
        "1. Только этот сайт. Задача не переходит в соседний проект.\n"
        "2. Массовая замена по всей фабрике запрещена.\n"
        "3. Общее ядро меняется отдельной задачей и приезжает сюда отдельным "
        "коммитом, поднимающим версию в `pins.lock.json`.\n"
        "4. Плавающих версий не бывает.\n"
        "5. Данные и секреты не коммитятся.\n"
        "6. Живой код по SSH не правится.\n", encoding="utf-8")

    return {"site_id": site_id, "domain": domain, "path": str(destination),
            "port": live.port, "unit": live.unit, "entrypoint": entry,
            "release_dir": str(live.release_dir), "source_commit": live.source_commit,
            "publisher_id": plc.get("publisher_id"),
            "files": len(names), "provenance": {
                v["verified_against"]: sum(1 for x in prov.values()
                                           if x["verified_against"] == v["verified_against"])
                for v in prov.values()}}


CHECKS_RUN = '''#!/usr/bin/env bash
# Проверки проекта сайта. Падение любой — причина не выпускать релиз.
# Имена переменных только ASCII: bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*,
# и строка вида `СУХОЙ=0` для него не присваивание, а вызов команды. `bash -n`
# такую строку пропускает.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
say() { printf '%-30s %s\\n' "$1" "$2"; }
check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then say "$name" "PASS"; else say "$name" "FAIL"; fail=1; fi
}

check "site-config-json"   python3 -c "import json;json.load(open('config/site.json'))"
check "pins-json"          python3 -c "import json;json.load(open('pins.lock.json'))"
check "entrypoint-present" python3 checks/entrypoint_present.py
check "runtime-compiles"   python3 checks/compiles.py
check "pins-match-sources" python3 checks/verify_pins.py
check "no-secrets-in-git"  python3 checks/no_secrets.py
check "shell-ascii-names"  python3 checks/ascii_shell_identifiers.py
check "launcher-refuses"   python3 checks/fails_closed.py
check "shell-syntax"       bash -n deploy/activate.sh
# Сценарии именно выполняются: `bash -n` пропустил ошибку, валившую скрипт на
# третьей строке, и обнаружилась она только на боевой активации.
check "activate-scenarios" python3 checks/activate_scenarios.py

exit "$fail"
'''

CHECK_ENTRYPOINT = '''"""Точка входа существует и названа в конфигурации."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
entry = ROOT / "src" / cfg["entrypoint"]
if not entry.is_file():
    print(f"нет точки входа {entry}", file=sys.stderr)
    sys.exit(1)
'''

CHECK_COMPILES = '''"""Весь перенесённый рантайм компилируется.

Артефакт снят с работающего сайта, но это не освобождает от проверки: файл мог
не доехать целиком.
"""
import py_compile
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []
# cfile во временный файл: py_compile отказывается писать в /dev/null, а без
# cfile он засорил бы проект каталогами __pycache__.
with tempfile.TemporaryDirectory() as tmp:
    for i, p in enumerate(sorted((ROOT / "src").glob("*.py"))):
        try:
            py_compile.compile(str(p), doraise=True, cfile=f"{tmp}/{i}.pyc")
        except py_compile.PyCompileError as exc:
            bad.append(f"{p.name}: {exc}")
if bad:
    print("не компилируется:", *bad, sep="\\n  ", file=sys.stderr)
    sys.exit(1)
'''

CHECK_VERIFY_PINS = '''"""Файлы совпадают с тем, что закреплено в pins.lock.json.

Без этого закрепление — запись о намерении, а не о факте.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
pins = json.loads((ROOT / "pins.lock.json").read_text(encoding="utf-8"))
bad = []
for name, meta in pins["files"].items():
    p = ROOT / "src" / name
    if not p.is_file():
        bad.append(f"{name}: файла нет")
        continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != meta["sha256"]:
        bad.append(f"{name}: sha256 {actual[:12]} вместо {meta['sha256'][:12]}")
if bad:
    print("исходники разошлись с замком:", *bad, sep="\\n  ", file=sys.stderr)
    sys.exit(1)
'''

CHECK_NO_SECRETS = '''"""Ни данных, ни секретов среди файлов, которые Git действительно хранит.

Проверяется индекс, а не рабочий каталог: `config/player.json` обязан лежать
рядом с работающим сайтом и обязан отсутствовать в Git. Отдельно сверяется, что
git отвечает про ЭТОТ проект, иначе распакованное дерево опросило бы
объемлющий репозиторий и прошло проверку, ничего не проверив.
"""
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("*.sqlite3", "*.db", "*.dump", "*.sql", ".env", "*.pem", "*.key",
             "player.json", "*-catalog.json", "*-details.json", "*community*.json")

top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                     text=True, check=False, cwd=ROOT)
if top.returncode != 0 or Path(top.stdout.strip()).resolve() != ROOT:
    print("git отвечает не про этот проект: проверка прошла бы впустую",
          file=sys.stderr)
    sys.exit(1)

tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         check=False, cwd=ROOT).stdout.split()
bad = [p for p in tracked
       if not p.endswith(".example")
       and any(fnmatch.fnmatch(p.rsplit("/", 1)[-1], pat) for pat in FORBIDDEN)]
if bad:
    print("эти файлы не должны быть в Git:", ", ".join(sorted(bad)), file=sys.stderr)
    sys.exit(1)
'''

CHECK_FAILS_CLOSED = '''"""Запуск отказывает, а не подставляет чужое."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

r = subprocess.run([sys.executable, str(ROOT / "run.py"), "--check"],
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode == 0:
    print("запуск без --data-dir не отказал", file=sys.stderr)
    sys.exit(1)

cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
if not cfg.get("neighbour_site_ids"):
    print("в config/site.json не перечислены соседние site_id", file=sys.stderr)
    sys.exit(1)
'''

CHECK_ASCII = '''"""Имена переменных и функций в shell — только ASCII.

Bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*. `СУХОЙ=0` для него не
присваивание, а вызов команды; падает только при запуске. `bash -n` пропускает.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSIGN = re.compile(r"^\\s*(?:export\\s+|local\\s+)?([^\\s=]*[^\\x00-\\x7F][^\\s=]*)=")
REF = re.compile(r"\\$\\{?([A-Za-z_]*[^\\x00-\\x7F][^\\s}/:\\-]*)")
FUNC = re.compile(r"^\\s*(?:function\\s+)?([^\\s()]*[^\\x00-\\x7F][^\\s()]*)\\s*\\(\\s*\\)")

bad = []
for path in sorted(ROOT.rglob("*.sh")):
    if ".git" in path.parts:
        continue
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#", 1)[0]
        for rule, what in ((ASSIGN, "присваивание"), (REF, "обращение"), (FUNC, "функция")):
            for name in rule.findall(code):
                bad.append(f"{path.relative_to(ROOT)}:{n}: {what} к не-ASCII имени {name!r}")
if bad:
    print("не-ASCII имена в shell:", *bad, sep="\\n  ", file=sys.stderr)
    sys.exit(1)
'''

CI_WORKFLOW = '''# Выпуск {domain}. Меняет только этот сайт.
name: release

on:
  push:
    # Ветка по умолчанию у этого проекта — рабочая, а не пустая main.
    # Триггер только на main означал бы, что CI не запускается никогда.
    branches: ['main', 'claude/**']
  pull_request:
  workflow_dispatch:

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
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Проверки проекта
        run: ./checks/run.sh
      - name: Репозиторий описывает именно свой сайт
        run: |
          set -euo pipefail
          declared=$(python3 -c "import json;print(json.load(open('config/site.json'))['site_id'])")
          if [ "$declared" != "{site_id}" ]; then
            echo "конфигурация описывает $declared: чужой сайт не выпускается" >&2
            exit 1
          fi
      - name: Сборка артефакта с digest
        run: |
          set -euo pipefail
          python3 tools/build_release.py --output dist
          cat dist/release-manifest.json
      - uses: actions/upload-artifact@v4
        with:
          name: {site_id}-release
          path: dist/
          retention-days: 30
'''


BUILD_RELEASE = '''#!/usr/bin/env python3
"""Сборка установочного пакета с воспроизводимым digest.

В архив не попадает ничего переменного: порядок файлов задан, времена обнулены,
владелец обезличен, режим канонизирован. Git хранит у файла ровно один бит прав;
остальное берётся из umask сборщика, и без нормализации один коммит давал разный
digest у разработчика и на раннере CI — digest отвечал бы на вопрос «кто
собирал», а не «то же ли это самое».
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

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "dist", "data", "var"}
SKIP_FILES = {"config/player.json"}


def files() -> list:
    out = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if str(rel) in SKIP_FILES:
            continue
        if p.is_file():
            out.append(p)
    return sorted(out, key=lambda p: str(p.relative_to(ROOT)))


def anonymise(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.mode & 0o111 else 0o644
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist")
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)

    cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                           capture_output=True, text=True, check=True).stdout.strip()

    # Манифест штампуется коммитом ЭТОЙ репы: иначе живой сайт объявлял бы
    # build_id чужой сборки, и связь commit → CI → digest → живой сайт
    # обрывалась бы на последнем звене. Отметки времени нет намеренно — она
    # сделала бы digest невоспроизводимым.
    manifest_path = "config/template-manifest.json"
    stamped = None
    if (ROOT / manifest_path).is_file():
        stamped = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
        stamped["site_repo_commit"] = commit
        stamped["build_id"] = f"{commit[:12]}-{cfg['site_id']}"
        stamped_bytes = (json.dumps(stamped, ensure_ascii=False, indent=1) + "\\n").encode()

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for p in files():
            arc = str(p.relative_to(ROOT))
            if stamped is not None and arc == manifest_path:
                info = tarfile.TarInfo(arc)
                info.size = len(stamped_bytes)
                info.mode = 0o644
                tar.addfile(anonymise(info), io.BytesIO(stamped_bytes))
                continue
            tar.add(p, arcname=arc, filter=anonymise)
    artifact = out / f"{cfg['site_id']}-{commit[:12]}.tar.gz"
    with artifact.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())

    digest = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "site_id": cfg["site_id"],
        "domain": cfg["domain"],
        "artifact": artifact.name,
        "digest": digest,
        "size_bytes": artifact.stat().st_size,
        "source_commit": commit,
        "source_dirty": bool(dirty),
        "pins": json.loads((ROOT / "pins.lock.json").read_text(encoding="utf-8"))["pins"],
        "built_at": datetime.now(timezone.utc).isoformat(),
        "live_build_id": stamped["build_id"] if stamped else None,
        "contains": {"code": True, "config": True, "database": False,
                     "media": False, "secrets": False, "catalog_snapshot": False},
    }
    (out / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(f"артефакт: {artifact}")
    print(f"digest:   {digest}")
    print(f"коммит:   {commit}")
    if dirty:
        print("ВНИМАНИЕ: дерево грязное, артефакт не воспроизводим из коммита")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def add_tooling(destination: Path, site_id: str, domain: str) -> None:
    """Проверки, CI и сборщик релиза — одинаковые у всех сайтов."""
    checks = destination / "checks"
    checks.mkdir(exist_ok=True)
    run = checks / "run.sh"
    run.write_text(CHECKS_RUN, encoding="utf-8")
    run.chmod(0o755)
    # Сценарный тест активации лежит файлом рядом с генератором: встроенный в
    # строку, он однажды уже приехал в репозиторий сайта с разъехавшимися
    # escape-последовательностями и не компилировался.
    сценарии = Path(__file__).resolve().parent / "site_checks" / "activate_scenarios.py"
    (checks / "activate_scenarios.py").write_text(
        сценарии.read_text(encoding="utf-8"), encoding="utf-8")

    for имя, текст in (("entrypoint_present.py", CHECK_ENTRYPOINT),
                       ("compiles.py", CHECK_COMPILES),
                       ("verify_pins.py", CHECK_VERIFY_PINS),
                       ("no_secrets.py", CHECK_NO_SECRETS),
                       ("fails_closed.py", CHECK_FAILS_CLOSED),
                       ("ascii_shell_identifiers.py", CHECK_ASCII)):
        (checks / имя).write_text(текст, encoding="utf-8")

    tools = destination / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "build_release.py").write_text(BUILD_RELEASE, encoding="utf-8")

    wf = destination / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "release.yml").write_text(
        CI_WORKFLOW.format(domain=domain, site_id=site_id), encoding="utf-8")


ACTIVATE = '''#!/usr/bin/env bash
# Активация {domain} на текущем хосте. Одна команда, один сайт.
#
# Делает только то, что нельзя без root: учётная запись, каталоги, перенос
# данных, юнит и переключение службы. Всё остальное уже проверено в репозитории.
#
#   sudo .../deploy/activate.sh --dry-run   # показать план, ничего не менять
#   sudo .../deploy/activate.sh             # выполнить
#
# Откат: sudo .../deploy/rollback.sh
#
# ВАЖНО об именах: только ASCII. Bash считает именем лишь
# [A-Za-z_][A-Za-z0-9_]*, и строка вида `СУХОЙ=0` для него не присваивание, а
# вызов команды. `bash -n` такую строку пропускает, падает она при запуске.
set -euo pipefail

dry_run=0
artifact=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --artifact) artifact="${{2:-}}"; shift ;;
    --artifact=*) artifact="${{1#*=}}" ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done

project="$(cd "$(dirname "$0")/.." && pwd)"
site_id="{site_id}"
account="${{SITE_ACCOUNT:-{account}}}"
root_dir="${{SITE_ROOT:-/srv/{account}}}"
app_dir="$root_dir/app"
data_dir="$root_dir/data"
unit="${{SITE_UNIT:-nova-{account}.service}}"
old_unit="${{SITE_OLD_UNIT:-{old_unit}}}"
port="${{SITE_PORT:-{port}}}"

shared_dir="${{SITE_SHARED:-/srv/lords/.frontend}}"
old_root="${{SITE_OLD_ROOT:-{old_root}}}"

# Крючки изолированной репетиции: без них скрипт нельзя выполнить ни разу до
# боевого запуска — а именно этого и не хватило в прошлый раз.
require_root="${{SITE_REQUIRE_ROOT:-1}}"
systemctl_cmd="${{SITE_SYSTEMCTL:-systemctl}}"
useradd_cmd="${{SITE_USERADD:-useradd}}"
unit_dir="${{SITE_UNIT_DIR:-/etc/systemd/system}}"
install_owner="${{SITE_INSTALL_OWNER:-1}}"
# Двоеточия нет намеренно: `${{X:-...}}` подставил бы умолчание и для пустого
# значения, то есть явная попытка отключить префикс молча вернула бы sudo.
run_as="${{SITE_RUN_AS-sudo -u $account}}"
# Ожидание готовности. 40 секунд (прежнее умолчание) оказалось втрое короче
# реальной загрузки витрины: боевая активация zonafilm.space 2026-09-23
# откатилась не из-за поломки, а не успев, — прежняя служба после отката
# поднималась 252 секунды. Короткий предел не ускоряет проверку, он превращает
# нормальный запуск в ложный отказ, и сайт лежит дольше.
health_timeout="${{SITE_HEALTH_TIMEOUT:-600}}"
health_interval="${{SITE_HEALTH_INTERVAL:-3}}"
# Без --max-time одно зависшее соединение съедает весь бюджет ожидания.
http_timeout="${{SITE_HTTP_TIMEOUT:-5}}"
journalctl_cmd="${{SITE_JOURNALCTL:-journalctl}}"

step() {{ printf '\\n== %s\\n' "$1"; }}
run_step() {{
  if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\\n' "$*"; else "$@"; fi
}}
own() {{ if [ "$install_owner" = 1 ]; then printf '%s' "-o $account -g $account"; fi; }}

diagnose() {{
  local unit_name="$1"
  echo "--- диагностика $unit_name ---" >&2
  "$systemctl_cmd" status "$unit_name" --no-pager 2>&1 | head -12 >&2 || true
  if command -v "$journalctl_cmd" >/dev/null 2>&1; then
    "$journalctl_cmd" -u "$unit_name" -n 40 --no-pager 2>&1 | tail -40 >&2 || true
  fi
}}

# Три различимых исхода: 0 отвечает, 1 не успел при живом процессе,
# 2 процесс не работает. `systemctl is-active` готовностью не считается:
# служба типа simple активна с первой миллисекунды, задолго до первого ответа.
wait_ready() {{
  local unit_name="$1" limit="$2" what="$3"
  local start now elapsed
  start=$(date +%s)
  while :; do
    if curl -fsS --max-time "$http_timeout" -o /dev/null "http://127.0.0.1:$port/healthz"; then
      now=$(date +%s); elapsed=$(( now - start ))
      echo "   $what: healthz ответил через ${{elapsed}} с"
      return 0
    fi
    now=$(date +%s); elapsed=$(( now - start ))
    if ! "$systemctl_cmd" is-active --quiet "$unit_name"; then
      echo "   $what: служба $unit_name не работает (через ${{elapsed}} с)" >&2
      diagnose "$unit_name"
      return 2
    fi
    if [ "$elapsed" -ge "$limit" ]; then
      echo "   $what: healthz не ответил за ${{elapsed}} с при пределе ${{limit}} с" >&2
      diagnose "$unit_name"
      return 1
    fi
    printf '   %s: загружается, %s с из %s\\n' "$what" "$elapsed" "$limit"
    sleep "$health_interval"
  done
}}

step "проверка предусловий"
if [ "$require_root" = 1 ] && [ "$(id -u)" != 0 ]; then
  echo "нужен root" >&2; exit 1
fi

# Рядом работают другие сессии: они перезапускают витрины направления.
lock_file="$shared_dir/.deploy.lock"
if [ -e "$lock_file" ]; then
  lock_age=$(( $(date +%s) - $(stat -c %Y "$lock_file") ))
  # Возраст замка НЕ доказывает смерть владельца: долгая миграция живёт часами.
  lock_pid=$(python3 -c "import json,sys
try: print(json.load(open(sys.argv[1])).get('pid') or '')
except Exception: print('')" "$lock_file")
  if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
    echo "выкладку держит живой процесс $lock_pid (замок $lock_file)" >&2
    exit 1
  fi
  if [ -z "$lock_pid" ]; then
    echo "в замке $lock_file нет pid владельца — снимать его автоматически нельзя" >&2
    exit 1
  fi
  echo "   владелец замка (pid $lock_pid) не существует — замок брошен"
fi

# Замок направления ненадёжен (наблюдался возраст 72 ч при активной работе
# соседей), поэтому отдельно смотрим на то, что подделать нечем.
if [ -d "$old_root" ]; then
  restarted=$(( $(date +%s) - $(stat -c %Y "$old_root" 2>/dev/null || date +%s) ))
  if [ "$restarted" -lt 600 ]; then
    echo "   ВНИМАНИЕ: каталог сайта менялся $restarted с назад — возможна чужая работа."
  fi
fi

own_lock="$root_dir/.activate.lock"
if [ "$dry_run" = 0 ]; then
  mkdir -p "$root_dir"
  if mkdir "$own_lock" 2>/dev/null; then
    printf '{{"pid": %d, "site": "%s", "at": "%s"}}\\n' "$$" "$site_id" "$(date -Is)" \\
      > "$own_lock/owner.json"
  else
    echo "активация $site_id уже идёт ($own_lock); второй запуск отклонён" >&2
    exit 1
  fi
  trap 'rm -rf "$own_lock" 2>/dev/null || true' EXIT
fi

if "$systemctl_cmd" is-active --quiet "$unit"; then
  echo "$unit уже активна: сайт, похоже, уже переключён." >&2
  exit 1
fi

if [ "${{SITE_SKIP_CHECKS:-0}}" != 1 ]; then
  "$project/checks/run.sh"
else
  echo "   проверки пропущены: запуск изнутри checks/run.sh"
fi

step "учётная запись и каталоги"
id -u "$account" >/dev/null 2>&1 || run_step "$useradd_cmd" --system --home "$root_dir" --shell /usr/sbin/nologin "$account"
# shellcheck disable=SC2046
run_step install -d $(own) -m 0755 "$root_dir" "$app_dir" "$data_dir"
# shellcheck disable=SC2046
run_step install -d $(own) -m 0700 "$data_dir/site-data"

step "код из проверенного артефакта"
# rsync рабочего каталога ставил то, что лежит на диске, а не то, что прошло
# CI: успешный прогон не доказывал, что в production попали именно его байты.
if [ -z "${{artifact:-}}" ]; then
  echo "не задан --artifact: установка из рабочего каталога запрещена" >&2
  exit 2
fi
[ -r "$artifact" ] || {{ echo "артефакт не читается: $artifact" >&2; exit 2; }}
manifest="${{artifact%.tar.gz}}.release-manifest.json"
[ -r "$manifest" ] || manifest="$(dirname "$artifact")/release-manifest.json"
[ -r "$manifest" ] || {{ echo "нет release-manifest рядом с артефактом" >&2; exit 2; }}
expected=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['digest'])" "$manifest")
actual="sha256:$(sha256sum "$artifact" | cut -d' ' -f1)"
if [ "$expected" != "$actual" ]; then
  echo "digest артефакта $actual не совпал с манифестом $expected" >&2
  exit 2
fi
echo "   digest подтверждён: $actual"
run_step rm -rf "$app_dir.new"
run_step mkdir -p "$app_dir.new"
run_step tar -xzf "$artifact" -C "$app_dir.new"
run_step rm -rf "$app_dir.prev"
[ -d "$app_dir" ] && run_step mv "$app_dir" "$app_dir.prev"
run_step mv "$app_dir.new" "$app_dir"

step "секрет плеера (вне Git)"
if [ -r "$shared_dir/player-$site_id.json" ]; then
  # shellcheck disable=SC2046
  run_step install $(own) -m 0600 "$shared_dir/player-$site_id.json" "$app_dir/config/player.json"
fi

step "данные сайта"
for f in "$site_id-catalog.json" "$site_id-details.json" \\
         "$site_id-ratings-top.json" "template-manifest-$site_id.json"; do
  if [ -r "$shared_dir/$f" ]; then
    # shellcheck disable=SC2046
    run_step install $(own) -m 0644 "$shared_dir/$f" "$data_dir/$f"
  fi
done
if [ -d "$old_root/current/site" ]; then
  run_step cp -a "$old_root/current/site" "$data_dir/site"
fi

step "проверка конфигурации до запуска"
# shellcheck disable=SC2086
run_step $run_as python3 "$app_dir/run.py" --check --data-dir "$data_dir"

step "короткая пауза записи и перенос последней дельты"
# Старая служба останавливается ДО копирования пользовательских записей:
# иначе два экземпляра писали бы одновременно и дельта потерялась бы.
run_step "$systemctl_cmd" stop "$old_unit"
# Отключение автозапуска входит в миграцию: иначе перезагрузка вернула бы
# прежний экземпляр на занятый порт.
run_step "$systemctl_cmd" disable "$old_unit"
if [ -r "$old_root/data/animedia-community.json" ]; then
  # shellcheck disable=SC2046
  run_step install $(own) -m 0600 \\
      "$old_root/data/animedia-community.json" "$data_dir/site-data/animedia-community.json"
fi

step "установка и запуск службы"
run_step cp "$project/deploy/$unit" "$unit_dir/"
run_step "$systemctl_cmd" daemon-reload
run_step "$systemctl_cmd" enable --now "$unit"

step "проверка здоровья"
if [ "$dry_run" = 1 ]; then
  echo
  echo "сухой прогон завершён: ничего не менялось"
  exit 0
fi

echo "   жду готовности до $health_timeout с; загрузка снимков каталога занимает минуты"
if wait_ready "$unit" "$health_timeout" "новая служба"; then
  "$systemctl_cmd" is-active "$unit" || true
  echo
  echo "ГОТОВО. Проверьте публично и, если что-то не так:"
  echo "  sudo $project/deploy/rollback.sh"
  exit 0
fi

echo "новая служба не вышла на готовность — откатываюсь" >&2
"$systemctl_cmd" disable --now "$unit" || true
"$systemctl_cmd" enable --now "$old_unit"

# Возврат проверяется тем же ожиданием: объявить восстановление по `enable --now`
# значило бы сказать «сайт работает», пока он ещё читает снимки каталога.
if wait_ready "$old_unit" "$health_timeout" "прежняя служба"; then
  echo "откат завершён: прежняя служба отвечает; данные в $data_dir не трогались" >&2
  exit 1
fi

# Отдельный код: «откатились, но сайт не отвечает» — требует человека немедленно.
echo "ВНИМАНИЕ: после отката прежняя служба не отвечает — сайт недоступен" >&2
exit 3
'''

ROLLBACK = '''#!/usr/bin/env bash
# Откат {domain} на прежнюю службу. Данные сохраняются.
#
# Возвращает КОД и маршрутизацию. Записи, принятые после переключения, остаются
# на месте: каталог данных не трогается вовсе. Восстановление вчерашней базы
# откатом не является.
set -euo pipefail

account="${{SITE_ACCOUNT:-{account}}}"
unit="${{SITE_UNIT:-nova-{account}.service}}"
old_unit="${{SITE_OLD_UNIT:-{old_unit}}}"
port="${{SITE_PORT:-{port}}}"
systemctl_cmd="${{SITE_SYSTEMCTL:-systemctl}}"
data_dir="${{SITE_ROOT:-/srv/{account}}}/data"

echo "== остановка новой службы"
"$systemctl_cmd" disable --now "$unit" || true

echo "== возврат прежней службы"
"$systemctl_cmd" enable --now "$old_unit"

echo "== здоровье прежней службы"
for _ in $(seq 1 15); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$port/healthz"; then
    echo "healthz отвечает; данные в $data_dir не изменялись"
    exit 0
  fi
  sleep 2
done
echo "healthz не ответил за 30 с" >&2
exit 1
'''


UNIT_TEMPLATE = '''# Служба {domain} ({site_id}). Ставится владельцем под root.
#
# Отличие от прежнего юнита: рабочий каталог и ExecStart указывают на ЭТОТ
# проект, а не на общий /srv/lords/.frontend. Пути данных задаёт run.py из
# config/site.json — забыть переменную и уехать на каталог соседа больше нечем.
[Unit]
Description={domain} ({site_id}), собственное развёртывание
After=network-online.target

[Service]
Type=simple
User={account}
Group={account}
WorkingDirectory=/srv/{account}/app
ExecStart=/usr/bin/python3 /srv/{account}/app/run.py --port {port} --data-dir /srv/{account}/data
Restart=on-failure
RestartSec=2

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/{account}/data
ProtectKernelTunables=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
'''


def account_for(slug: str) -> str:
    """Имя системной учётной записи сайта по его слагу.

    Соглашение об именах пользователей — `^[a-z][-a-z0-9_]*$` (см. NAME_REGEX в
    `/etc/adduser.conf`). Домен `1lordserials1.online` даёт слаг, начинающийся с
    цифры, и такое имя создать нельзя. Обнаружить это на активации боевого
    сайта — значит обнаружить в самый дорогой момент, поэтому правило
    детерминированное и применяется при сборке репозитория.

    Префикс, а не удаление цифры: имя обязано оставаться узнаваемым и
    однозначно обратимым к домену.
    """
    очищенный = slug.lower().replace(".", "-")
    return очищенный if очищенный[:1].isalpha() else f"site-{очищенный}"


def add_deploy(destination: Path, *, site_id: str, domain: str, account: str,
               old_unit: str, port: int, old_root: str) -> None:
    """Скрипты активации и отката плюс юнит — одинаковой формы у всех сайтов."""
    deploy = destination / "deploy"
    deploy.mkdir(exist_ok=True)
    поля = {"site_id": site_id, "domain": domain, "account": account,
            "old_unit": old_unit, "port": port, "old_root": old_root}
    for имя, шаблон in (("activate.sh", ACTIVATE), ("rollback.sh", ROLLBACK)):
        путь = deploy / имя
        путь.write_text(шаблон.format(**поля), encoding="utf-8")
        путь.chmod(0o755)
    (deploy / f"nova-{account}.service").write_text(
        UNIT_TEMPLATE.format(**поля), encoding="utf-8")
