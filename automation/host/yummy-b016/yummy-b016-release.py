#!/usr/bin/env python3
"""Yummy: выпуск исправления поверх ЖИВЫХ баз витрин и приёмка (B016/T081 — 15.10; B031 — 16.10).

Текущий выпуск — B031 (решение владельца 16.10): <title> не обрезает название произведения.
Витрины выпуска — yummyani.biz и yummyani.org; yummyani.site — контроль (не выкладывается).
yummyani7.site/.info работают на том же образе, что yummyani.biz (rel-a520a24afb20), но их
compose ведёт Архитектор: после этого выпуска им передаётся тег нового образа biz.

Запуск владельцем (пользователь с доступом к docker и владелец compose.vars — claude):

    python3 /home/claude/wt-portable-site-cell-01/automation/host/yummy-b016/yummy-b016-release.py run

Подкоманды:
    preflight            только проверки, ни одной мутации (код 0 — можно выпускать)
    build                preflight + сборка трёх образов; контейнеры не трогаются
    run --no-accept      ВЫПУСК B031: preflight → сборка → резервная копия БД → выкладка biz → org
                         (каждая — с приёмкой и откатом ТОЛЬКО образа этой витрины при неуспехе;
                         приёмка витрины включает titles: полное название в <title> на компьютере и
                         телефоне, canonical/robots/H1 как до выпуска)
                         → приёмка постоянного исправления (accept); --no-accept — без неё
    accept [--state D]   приёмка постоянного исправления: пауза прогрева, устаревший кеш и
                         холодный старт через публичный домен, полнота карт, T081
    rollback --service web-biz|web-org|web-site [--state D]
                         ручной откат образа одной витрины к записанному в состоянии выпуска

Коды выхода: 0 — успех; 3 — остановка до мутаций (preflight); 4 — сборка; 5 — выкладка
(витрина откачена); 6 — выкладка и откат не удались (нужен человек); 7 — приёмка
постоянного исправления не пройдена (витрины работают, откат — подкоманда rollback);
2 — ошибка вызова.

Чего сценарий не делает никогда: не восстанавливает БД (deploy/staging/rollback.sh не
вызывается), не очищает и не меняет Redis, не правит чужие compose-файлы, не трогает
yummyani7.* (часть B — после фиксации compose Архитектором), не печатает значения
издателя и настроек (сравнение — по sha256).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTORY = Path(os.environ.get("YB_FACTORY", HERE.parents[2]))


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


APP_REPO = Path(_env("YB_APP_REPO", "/srv/sites/yummyani-staging/repo"))
BUILD_ROOT = Path(_env("YB_BUILD_ROOT", "/srv/sites/yummyani-staging/build-b016"))
ENV_FILE = Path(_env("YB_ENV_FILE", "/srv/sites/yummyani-staging/runtime/compose.vars"))
BASE_COMPOSE_DIR = Path(_env("YB_BASE_COMPOSE_DIR", "/home/claude/wt-yummy-mail-biz"))
BASE_COMPOSE_SHA = _env("YB_BASE_COMPOSE_SHA", "4c5796eae24c")
OVERRIDES = [FACTORY / "automation/host/yummy-biz-indexing.override.yaml",
             FACTORY / "automation/host/yummy-overlays.override.yaml"]
PATCH_DIR = Path(_env("YB_PATCH_DIR", str(FACTORY / "var/yummy-patches")))
PATCH_SUMS = Path(_env("YB_PATCH_SUMS", str(HERE / "PATCHES.sha256")))
STATE_ROOT = Path(_env("YB_STATE_ROOT", str(FACTORY / "var/yummy-b016")))
WARM_PAUSE = Path(_env("YB_WARM_PAUSE", str(FACTORY / "var/yummy-sitemap/warm-pause.json")))
DOCKER = _env("YB_DOCKER", "docker")
CHECK = json.loads(_env("YB_CHECK", json.dumps([sys.executable, str(HERE / "yummy-b016-check.py")])))
URL = _env("YB_URL_TEMPLATE", "https://{domain}{path}")
PROJECT = "yummyani-staging"
HEALTH_TIMEOUT = float(_env("YB_HEALTH_TIMEOUT", "240"))
HEALTH_POLL = float(_env("YB_HEALTH_POLL", "3"))
FRESH_TTL = int(_env("YB_FRESH_TTL", "3600"))       # FRESH_TTL_SEC патча SWR
LOCK_TTL = int(_env("YB_LOCK_TTL", "300"))          # LOCK_TTL_SEC патча SWR
SLEEP = time.sleep

B016 = ["b016-sitemap-swr.v2.patch", "b016-sitemap-cap.patch"]
WORDING = "yummy-public-wording.patch"  # тексты для посетителя (15.10)
B031 = "b031-title-no-name-cut.patch"   # <title>: хвост → бренд, название не режется (16.10)
TAG_RE = re.compile(r"^yummyani/web:rel-[0-9a-f]{12}$")
KEPT = re.compile(r"PUBLISHER|CDNVIDEOHUB|^SEO_INDEXING_ENABLED$|^TITLE_OVERLAYS|^SITE_PROFILE$|^REDIS_URL$|^DATABASE_URL$")
PARTS = ("titles", "seasons", "episodes")
# Состояние инвентаря — заголовок x-sitemap-inventory контейнера. Публичный домен
# обслуживает ячейка-прокси (D160), и она этот заголовок не передаёт (замер 15.10
# 16:15Z: у публичного ответа заголовка нет, у 127.0.0.1:3102/3103 — «fresh; age=…»).
# Поэтому код, время и полнота меряются на публичном домене, а состояние кеша
# читается у того же контейнера на его локальном порту — тоже только чтение.
STATE_PORTS = json.loads(_env("YB_STATE_PORTS", json.dumps({"yummyani.site": 3101, "yummyani.org": 3102, "yummyani.biz": 3103})))


@dataclasses.dataclass(frozen=True)
class Tenant:
    service: str
    var: str
    domain: str
    base: str   # 12 знаков живого коммита
    patches: tuple  # патчи поверх ЭТОЙ базы, по порядку

    @property
    def container(self) -> str:
        return f"{PROJECT}-{self.service}-1"


# Порядок выкладки: biz → org → site (самый посещаемый — последним).
# Выпуск 15.10 15:38Z (var/yummy-b016/20261015T153835Z): biz и org приняты с B016/T081
# (их живые базы теперь — коммиты того выпуска), site отклонён проверкой T081 и откачен:
# у базы 054c617 карусель «Актуальное» строится отдельно (actualCards) — для неё свой
# вариант T081. Тексты для посетителя — новым патчем на всех трёх.
#
# Выпуск B031 (16.10): базы — живые ревизии после выпуска 15.10 17:10Z (biz a520a24 =
# 2118480 + WORDING, org 536082c = 8f159f3 + WORDING). yummyani.site (c23018d) — контроль
# на 7 дней (страницы ДжоДжо S7 — 56 % его поисковых входов), в выпуск не входит.
TENANTS = [
    Tenant("web-biz", "WEB_BIZ_IMAGE", "yummyani.biz", "a520a24afb20", (B031,)),
    Tenant("web-org", "WEB_ORG_IMAGE", "yummyani.org", "536082c25e7e", (B031,)),
]
BY_SERVICE = {t.service: t for t in TENANTS}


class Stop(Exception):
    """Остановка выпуска с кодом выхода."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------ вывод и журнал
def log(msg: str) -> None:
    print(f"[b016 {dt.datetime.now(dt.timezone.utc):%H:%M:%SZ}] {msg}", file=sys.stderr, flush=True)


class Journal:
    """Журнал мутаций выпуска (JSON-строки): кто, что, над чем, код выхода."""

    def __init__(self, state: Path):
        self.path = state / "journal.jsonl"

    def write(self, action: str, target: str, rc: int, **extra) -> None:
        rec = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": os.environ.get("USER") or str(os.getuid()),
               "action": action, "target": target, "rc": rc, **extra}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def sh(cmd: list[str], *, code: int, what: str, cwd: Path | None = None, env: dict | None = None,
       timeout: float = 3600) -> str:
    """Команда; stdout возвращается, диагностика — в stderr; ненулевой код — Stop(code)."""
    log("$ " + " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(code, f"{what}: {e}") from e
    if r.stderr.strip():
        print(r.stderr.rstrip()[-4000:], file=sys.stderr)
    if r.returncode != 0:
        if r.stdout.strip():
            print(r.stdout.rstrip()[-2000:], file=sys.stderr)
        raise Stop(code, f"{what}: код {r.returncode}")
    return r.stdout


def docker(*args: str, code: int, what: str, env: dict | None = None, timeout: float = 3600) -> str:
    return sh([DOCKER, *args], code=code, what=what, env=env, timeout=timeout)


def compose_args() -> list[str]:
    args = ["compose", "-p", PROJECT, "--project-directory", str(BASE_COMPOSE_DIR), "-f", str(BASE_COMPOSE_DIR / "compose.staging.yaml")]
    for o in OVERRIDES:
        args += ["-f", str(o)]
    return args + ["--env-file", str(ENV_FILE)]


def h(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:16]


def check(*args: str, code: int) -> int:
    """yummy-b016-check.py; его вывод — в stderr; код возвращается."""
    log("check " + " ".join(args))
    r = subprocess.run([*CHECK, *args], capture_output=True, text=True)
    out = (r.stdout + r.stderr).rstrip()
    if out:
        print(out[-6000:], file=sys.stderr)
    if r.returncode not in (0, 1):
        raise Stop(code, f"проверка {args[0]} не выполнилась: код {r.returncode}")
    return r.returncode


# ------------------------------------------------------------------ compose.vars
def read_env(path: Path | None = None) -> list[tuple[str, str]]:
    # Путь — в момент вызова, не при загрузке модуля: умолчание, связанное при загрузке,
    # однажды увело тестовую запись в боевой compose.vars (15.10 08:45Z).
    path = path or ENV_FILE
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pairs.append((k.strip(), v.strip()))
    return pairs


def pinned(path: Path | None = None) -> dict[str, str]:
    """Три закреплённые переменные образов — ровно по одной и в формате rel-<12 hex>."""
    path = path or ENV_FILE
    pairs = read_env(path)
    out = {}
    for t in TENANTS:
        vals = [v for k, v in pairs if k == t.var]
        if len(vals) != 1:
            raise Stop(3, f"{t.var}: в {path} строк {len(vals)}, ожидается ровно одна")
        if not TAG_RE.match(vals[0]):
            raise Stop(3, f"{t.var}: «{vals[0]}» не в формате yummyani/web:rel-<12 hex>")
        out[t.var] = vals[0]
    return out


def set_pin(var: str, value: str, path: Path | None = None) -> None:
    """Атомарная замена ОДНОЙ строки: временный файл рядом, права и владелец прежние, fsync, rename."""
    path = path or ENV_FILE
    if not TAG_RE.match(value):
        raise Stop(5, f"{var}: отказ закрепить «{value}»")
    st = path.stat()
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    hits = [i for i, l in enumerate(lines) if l.split("=", 1)[0].strip() == var]
    if len(hits) != 1:
        raise Stop(5, f"{var}: строк {len(hits)}, ожидается одна")
    lines[hits[0]] = f"{var}={value}\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("".join(lines))
            f.flush()
            os.fchmod(f.fileno(), st.st_mode & 0o7777)
            if os.geteuid() == 0:
                os.fchown(f.fileno(), st.st_uid, st.st_gid)
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    st2 = path.stat()
    if pinned(path).get(var) != value or (st2.st_mode & 0o7777) != (st.st_mode & 0o7777) or (st2.st_uid, st2.st_gid) != (st.st_uid, st.st_gid):
        raise Stop(5, f"{var}: после замены значение или права не те")


# ------------------------------------------------------------------ docker-чтение
def inspect_container(name: str, code: int) -> dict:
    return json.loads(docker("inspect", name, code=code, what=f"inspect {name}"))[0]


def image_id(ref: str, code: int) -> str:
    return docker("image", "inspect", "-f", "{{.Id}}", ref, code=code, what=f"образ {ref}").strip()


def image_revision(ref: str, code: int) -> str:
    return docker("image", "inspect", "-f", '{{index .Config.Labels "org.opencontainers.image.revision"}}', ref,
                  code=code, what=f"метка образа {ref}").strip()


def health(name: str) -> str:
    try:
        d = inspect_container(name, 5)
    except Stop:
        return "missing"
    return ((d.get("State") or {}).get("Health") or {}).get("Status") or "none"


def wait_healthy(name: str) -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT
    while True:
        st = health(name)
        if st == "healthy":
            log(f"{name}: healthy")
            return
        if time.monotonic() > deadline:
            raise Stop(5, f"{name}: {st} — нет здоровья за {HEALTH_TIMEOUT:.0f} с")
        SLEEP(HEALTH_POLL)


# ------------------------------------------------------------------ preflight
def check_patches() -> None:
    for line in PATCH_SUMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        want, rel = line.split(None, 1)
        p = PATCH_DIR / Path(rel.strip()).name
        if not p.is_file():
            raise Stop(3, f"нет патча {p}")
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want:
            raise Stop(3, f"{p.name}: sha256 {got[:12]}… ≠ {want[:12]}…")
    names = {Path(l.split(None, 1)[1].strip()).name for l in PATCH_SUMS.read_text().splitlines() if l.strip()}
    for need in sorted({p for t in TENANTS for p in t.patches}):
        if need not in names:
            raise Stop(3, f"{need} не перечислен в {PATCH_SUMS}")


def config_kept(svc_cfg: dict) -> dict[str, str]:
    env = svc_cfg.get("environment") or {}
    if isinstance(env, list):
        env = dict(x.split("=", 1) for x in env if "=" in x)
    return {k: h(str(v)) for k, v in env.items() if KEPT.search(k) and v is not None}


def config_targets(svc_cfg: dict) -> set[str]:
    targets = {v.get("target") for v in svc_cfg.get("volumes") or [] if isinstance(v, dict)}
    for s in svc_cfg.get("secrets") or []:
        targets.add(s.get("target") or f"/run/secrets/{s.get('source')}")
    return {t if t.startswith("/") else f"/run/secrets/{t}" for t in targets if t}


def preflight(state: Path | None = None) -> dict:
    """Все условия — обязательные. Любое несоответствие — Stop(3) до первой мутации."""
    log("preflight: хеши патчей")
    check_patches()
    log("preflight: базовый compose-файл")
    head = sh(["git", "-C", str(BASE_COMPOSE_DIR), "rev-parse", "HEAD"], code=3, what="HEAD базового compose").strip()
    if not head.startswith(BASE_COMPOSE_SHA):
        raise Stop(3, f"{BASE_COMPOSE_DIR}: HEAD {head[:12]}, ожидается {BASE_COMPOSE_SHA}")
    if sh(["git", "-C", str(BASE_COMPOSE_DIR), "status", "--porcelain"], code=3, what="status базового compose").strip():
        raise Stop(3, f"{BASE_COMPOSE_DIR}: в дереве незакоммиченные правки")
    for o in OVERRIDES:
        if not o.is_file():
            raise Stop(3, f"нет наложения {o}")
    log("preflight: закреплённые образы")
    pins = pinned()
    log("preflight: итоговая конфигурация compose (три файла)")
    cfg = json.loads(docker(*compose_args(), "config", "--format", "json", code=3, what="compose config"))
    info = {}
    for t in TENANTS:
        c = inspect_container(t.container, 3)
        st = ((c.get("State") or {}).get("Health") or {}).get("Status")
        if st != "healthy":
            raise Stop(3, f"{t.container}: {st}")
        if c["Config"]["Image"] != pins[t.var]:
            raise Stop(3, f"{t.container}: работает {c['Config']['Image']}, закреплено {pins[t.var]}")
        rev = (c["Config"].get("Labels") or {}).get("org.opencontainers.image.revision") or ""
        if not rev.startswith(t.base):
            raise Stop(3, f"{t.container}: ревизия {rev[:12]}, ожидается база {t.base} — базы сменились, сборку перепроверить")
        sc = (cfg.get("services") or {}).get(t.service)
        if not sc:
            raise Stop(3, f"compose config: нет службы {t.service}")
        if sc.get("image") != pins[t.var]:
            raise Stop(3, f"compose config {t.service}: image {sc.get('image')} ≠ {pins[t.var]}")
        run_env = dict(x.split("=", 1) for x in c["Config"]["Env"])
        img_env = dict(x.split("=", 1) for x in json.loads(docker("image", "inspect", c["Image"], code=3, what="образ контейнера"))[0]["Config"].get("Env") or [])
        want = config_kept(sc)
        have = {k: h(v) for k, v in run_env.items() if KEPT.search(k)}
        for k in sorted(set(want) | set(have)):
            if k in want and want[k] != have.get(k):
                raise Stop(3, f"{t.service}: {k} в итоговой конфигурации отличается от работающего (пересоздание изменило бы его)")
            if k not in want and not (k in img_env and h(img_env[k]) == have[k]):
                raise Stop(3, f"{t.service}: {k} есть в работающем, но не в итоговой конфигурации — пересоздание снимет")
        mounts = {m.get("Destination") for m in c.get("Mounts") or []}
        if config_targets(sc) != mounts:
            raise Stop(3, f"{t.service}: монтирования конфигурации {sorted(config_targets(sc))} ≠ работающие {sorted(mounts)}")
        info[t.service] = {"image_ref": pins[t.var], "image_id": c["Image"], "revision": rev}
    if config_kept(cfg["services"]["web-biz"]).get("SEO_INDEXING_ENABLED") != h("true"):
        raise Stop(3, "web-biz: SEO_INDEXING_ENABLED в итоговой конфигурации не true (наложение не применено)")
    if state is not None:
        log("preflight: снимок до выпуска")
        if check("snapshot", str(state / "before.json"), code=3) != 0:
            raise Stop(3, "снимок до выпуска с отклонениями (издатель на странице не найден или контейнер недоступен)")
        if check("titles", "--save", str(state / "titles-before.json"), *[t.domain for t in TENANTS], code=3) != 0:
            raise Stop(3, "снимок страниц B031 до выпуска: страница не ответила 200")
    log("preflight: OK")
    return info


# ------------------------------------------------------------------ сборка
def build_one(t: Tenant, state: Path) -> dict:
    """Рабочая копия живой базы + патчи + коммит + сборка + неизменяемый тег. Только тег наружу."""
    # Своя папка на каждый выпуск: рабочие копии прошлого выпуска не мешают новому.
    wt = BUILD_ROOT / state.name / t.base
    if wt.exists():
        raise Stop(4, f"{wt} уже есть — удалите: git -C {APP_REPO} worktree remove {wt}")
    wt.parent.mkdir(parents=True, exist_ok=True)
    sh(["git", "-C", str(APP_REPO), "worktree", "add", "--detach", str(wt), t.base], code=4, what=f"worktree {t.base}")
    for p in t.patches:
        sh(["patch", "-d", str(wt), "-p1", "--forward", "--batch", "--no-backup-if-mismatch", "-i", str(PATCH_DIR / p)],
           code=4, what=f"патч {p} на {t.base}")
    if sh(["git", "-C", str(wt), "status", "--porcelain"], code=4, what="status").strip() == "":
        raise Stop(4, f"{t.base}: патчи ничего не изменили")
    sh(["git", "-C", str(wt), "add", "-A"], code=4, what="git add")
    sh(["git", "-C", str(wt), "-c", "user.name=yummy-b016", "-c", "user.email=yummy-b016@localhost", "commit", "-q",
        "-m", f"поверх {t.base}: " + ", ".join(t.patches)],
       code=4, what=f"коммит {t.base}")
    sha = sh(["git", "-C", str(wt), "rev-parse", "HEAD"], code=4, what="rev-parse").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise Stop(4, f"{t.base}: коммит «{sha}»")
    docker("compose", "-p", PROJECT, "--project-directory", str(wt), "-f", str(wt / "compose.staging.yaml"),
           "--env-file", str(ENV_FILE), "--profile", "build", "build", "web-build",
           code=4, what=f"сборка {t.base}", env={"GIT_REVISION": sha}, timeout=5400)
    label = image_revision("yummyani/web:staging", 4)
    if label != sha:
        raise Stop(4, f"{t.base}: метка собранного образа «{label}», ожидается {sha}")
    tag = f"yummyani/web:rel-{sha[:12]}"
    if not TAG_RE.match(tag):
        raise Stop(4, f"тег «{tag}» не в формате")
    docker("tag", "yummyani/web:staging", tag, code=4, what=f"тег {tag}")
    if image_revision(tag, 4) != sha:
        raise Stop(4, f"{tag}: метка не совпала после тегирования")
    Journal(state).write("build", t.service, 0, base=t.base, commit=sha, image=tag)
    return {"service": t.service, "base": t.base, "commit": sha, "image": tag, "image_id": image_id(tag, 4)}


def build_all(state: Path) -> dict[str, dict]:
    built = {}
    for t in TENANTS:
        log(f"сборка {t.service} поверх {t.base}")
        built[t.service] = build_one(t, state)
    (state / "images.json").write_text(json.dumps(built, ensure_ascii=False, indent=1), encoding="utf-8")
    return built


# ------------------------------------------------------------------ выкладка и откат одной витрины
def recreate(t: Tenant) -> None:
    docker(*compose_args(), "up", "-d", "--no-deps", "--force-recreate", t.service, code=5, what=f"пересоздание {t.service}")


def accept_tenant(t: Tenant, new: dict, deployed: list[str], state: Path) -> None:
    c = inspect_container(t.container, 5)
    if c["Image"] != new["image_id"]:
        raise Stop(5, f"{t.container}: работает не новый образ")
    if (c["Config"].get("Labels") or {}).get("org.opencontainers.image.revision") != new["commit"]:
        raise Stop(5, f"{t.container}: ревизия не новая")
    after = state / f"after-{t.service}.json"
    if check("snapshot", str(after), code=5) != 0:
        raise Stop(5, "снимок после выкладки с отклонениями")
    if check("compare", str(state / "before.json"), str(after), "--changed", *deployed, code=5) != 0:
        raise Stop(5, "сравнение до/после: издатель, индексация, наложения, монтирования или образы соседей изменились")
    if check("links", t.domain, code=5) != 0:
        raise Stop(5, f"{t.domain}: на главной остались ссылки --uuid (T081)")
    if check("titles", "--against", str(state / "titles-before.json"), t.domain, code=5) != 0:
        raise Stop(5, f"{t.domain}: <title> обрезает название, либо canonical/robots/H1 изменились (B031)")
    # Прогретый кеш (таймер прогрева работает): сначала проход с пределом 90 с — на случай
    # истёкшего ключа, затем рабочий предел 5 с.
    if check("sitemaps", "--max-seconds", "90", t.domain, code=5) != 0 or check("sitemaps", "--max-seconds", "5", t.domain, code=5) != 0:
        raise Stop(5, f"{t.domain}: карты не 200 или дольше предела")


def rollback_tenant(t: Tenant, prev: dict, still_changed: list[str], state: Path, journal: Journal) -> None:
    """Откат ТОЛЬКО образа: прежняя строка закрепления → пересоздание → проверка. БД не трогается."""
    log(f"ОТКАТ {t.service} → {prev['image_ref']}")
    set_pin(t.var, prev["image_ref"])
    journal.write("pin", t.var, 0, image=prev["image_ref"], reason="rollback")
    try:
        recreate(t)
        journal.write("recreate", t.service, 0, reason="rollback")
        wait_healthy(t.container)
    except Stop as e:
        journal.write("recreate", t.service, e.code, reason="rollback", error=str(e))
        raise Stop(6, f"{t.service}: откат не поднялся: {e}") from e
    c = inspect_container(t.container, 6)
    if c["Image"] != prev["image_id"]:
        raise Stop(6, f"{t.service}: после отката работает не прежний образ")
    rb = state / f"rollback-{t.service}.json"
    check("snapshot", str(rb), code=6)
    if check("compare", str(state / "before.json"), str(rb), "--changed", *still_changed, code=6) != 0:
        raise Stop(6, f"{t.service}: после отката состояние отличается от исходного")
    journal.write("rollback", t.service, 0, image=prev["image_ref"])
    log(f"{t.service}: откат выполнен и проверен")


def deploy_one(t: Tenant, new: dict, prev: dict, deployed: list[str], state: Path, journal: Journal) -> None:
    backup = state / f"compose.vars.before-{t.service}"
    shutil.copy2(ENV_FILE, backup)
    if hashlib.sha256(backup.read_bytes()).digest() != hashlib.sha256(ENV_FILE.read_bytes()).digest():
        raise Stop(5, "копия compose.vars не совпала с оригиналом")
    docker("tag", prev["image_id"], f"yummyani/web:rollback-b016-{t.service}-{state.name.lower()}", code=5, what="тег отката")
    set_pin(t.var, new["image"])
    journal.write("pin", t.var, 0, image=new["image"])
    try:
        recreate(t)
        journal.write("recreate", t.service, 0, image=new["image"])
        wait_healthy(t.container)
        accept_tenant(t, new, deployed + [t.service], state)
    except Stop as e:
        journal.write("deploy", t.service, e.code, error=str(e))
        log(f"{t.service}: {e} — откат образа этой витрины")
        rollback_tenant(t, prev, deployed, state, journal)
        raise Stop(5, f"{t.service}: выкладка не принята ({e}); образ откачен, следующие витрины не выкладывались") from e
    journal.write("deploy", t.service, 0, image=new["image"])


# ------------------------------------------------------------------ приёмка постоянного исправления
def fetch(domain: str, path: str, timeout: float = 120) -> dict:
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(URL.format(domain=domain, path=path), headers={"User-Agent": "yummy-b016-accept"}),
                                    timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return {"code": r.status, "t": time.monotonic() - t0, "loc": body.count("<loc>"), "body": body,
                    "inventory": r.headers.get("x-sitemap-inventory") or ""}
    except urllib.error.HTTPError as e:
        return {"code": e.code, "t": time.monotonic() - t0, "loc": 0, "body": "", "inventory": ""}
    except Exception as e:  # noqa: BLE001 — сеть и тайм-аут — код -1
        return {"code": -1, "t": time.monotonic() - t0, "loc": 0, "body": "", "inventory": "", "error": str(e)[:120]}


def inv_state(header: str) -> tuple[str, int | None]:
    m = re.match(r"\s*(fresh|stale|cold|unavailable)\s*;\s*age=(\d+|unknown)", header or "")
    if not m:
        return "", None
    return m.group(1), (int(m.group(2)) if m.group(2).isdigit() else None)


def container_state(domain: str, part: str) -> str:
    port = STATE_PORTS.get(domain)
    if not port:
        return ""
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/sitemap/{part}.xml",
                                                           headers={"User-Agent": "yummy-b016-accept"}), timeout=120) as r:
            return r.headers.get("x-sitemap-inventory") or ""
    except Exception:  # noqa: BLE001
        return ""


def sweep(domains: list[str]) -> list[dict]:
    jobs = [(d, p) for d in domains for p in PARTS]

    def one(dp):
        r = {"domain": dp[0], "part": dp[1], **fetch(dp[0], f"/sitemap/{dp[1]}.xml")}
        if not r["inventory"]:
            r["inventory"] = container_state(dp[0], dp[1])
        return r
    with ThreadPoolExecutor(len(jobs)) as ex:
        res = list(ex.map(one, jobs))
    for r in res:
        log(f"  {r['domain']} {r['part']}.xml {r['code']} {r['t']:.2f}s loc={r['loc']} [{r['inventory']}]")
    return res


def pause_warm(seconds: int) -> None:
    """Управляемая пауза прогрева: файл с крайним сроком; прогрев сам его соблюдает и сам возобновится."""
    WARM_PAUSE.parent.mkdir(parents=True, exist_ok=True)
    until = int(time.time()) + seconds
    tmp = WARM_PAUSE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"until": until, "by": "yummy-b016-release accept"}), encoding="utf-8")
    os.replace(tmp, WARM_PAUSE)
    log(f"прогрев на паузе до {dt.datetime.fromtimestamp(until, dt.timezone.utc):%H:%M:%SZ}")


def resume_warm() -> None:
    try:
        WARM_PAUSE.unlink()
        log("прогрев возобновлён")
    except FileNotFoundError:
        pass


def accept(state: Path, domains: list[str] | None = None) -> dict:
    """Приёмка постоянного исправления. Redis не читается и не меняется: состояние — из заголовка."""
    domains = domains or [t.domain for t in TENANTS]
    report: dict = {"domains": domains, "checks": {}}
    ok = True
    pause_warm(2 * FRESH_TTL + 2 * LOCK_TTL + 900)
    try:
        log("приёмка 1/5: текущее состояние инвентаря")
        first = sweep(domains)
        states = {inv_state(r["inventory"]) for r in first}
        report["first"] = [{k: r[k] for k in ("domain", "part", "code", "t", "loc", "inventory")} for r in first]
        if any(not s for s, _ in states):
            raise Stop(7, "нет заголовка x-sitemap-inventory — на витринах не новый код")
        cold_seen = any(s == "cold" for s, _ in states)
        report["checks"]["cold_start"] = (
            {"observed": True, "all_200": all(r["code"] == 200 for r in first if inv_state(r["inventory"])[0] == "cold")}
            if cold_seen else {"observed": False, "why": "инвентарь уже был в кеше; общий Redis не очищается — холодный старт покрыт тестом sitemap-inventory-cache.test.ts"})
        # Инвентарь общий у трёх витрин: его может обновить и обходчик. Тогда «устаревшее»
        # состояние не застанем — ждём следующего устаревания (не больше двух раз).
        stale: list[dict] = []
        cur = states
        for attempt in range(2):
            ages = [a for s, a in cur if s == "fresh" and a is not None]
            wait = max(0, FRESH_TTL - min(ages) + 30) if ages else 0
            if wait:
                log(f"приёмка 2/5: ждём устаревания инвентаря {wait} с (прогрев на паузе)")
                SLEEP(wait)
            log("приёмка 3/5: устаревший кеш — ответ сразу, перестройка в фоне")
            stale = sweep(domains)
            cur = {inv_state(r["inventory"]) for r in stale}
            if any(s == "stale" for s, _ in cur):
                break
        report["stale"] = [{k: r[k] for k in ("domain", "part", "code", "t", "loc", "inventory")} for r in stale]
        stale_states = [inv_state(r["inventory"])[0] for r in stale]
        report["checks"]["stale_observed"] = "stale" in stale_states
        report["checks"]["stale_fast_200"] = all(r["code"] == 200 and r["t"] <= 5 for r in stale)
        log("приёмка 4/5: перестройка завершается без участия прогрева")
        deadline = time.monotonic() + LOCK_TTL + 120
        refreshed = False
        while time.monotonic() < deadline:
            SLEEP(20)
            r = fetch(domains[0], "/sitemap/titles.xml")
            s, a = inv_state(r["inventory"] or container_state(domains[0], "titles"))
            if r["code"] == 200 and s == "fresh" and a is not None and a < LOCK_TTL + 180:
                refreshed = True
                break
        report["checks"]["background_refresh"] = refreshed
        log("приёмка 5/5: полнота карт и ссылки T081")
        final = sweep(domains)
        report["final"] = [{k: r[k] for k in ("domain", "part", "code", "t", "loc", "inventory")} for r in final]
        allr = first + stale + final
        report["checks"]["no_504"] = all(r["code"] != 504 for r in allr)
        report["checks"]["all_200"] = all(r["code"] == 200 for r in allr)
        titles = {r["domain"]: r["loc"] for r in final if r["part"] == "titles"}
        report["checks"]["titles_over_8000"] = {d: n for d, n in titles.items()}
        cap_ok = all(n > 8000 for n in titles.values())
        report["checks"]["links_t081"] = check("links", *domains, code=7) == 0
        ok = all([report["checks"]["stale_observed"], report["checks"]["stale_fast_200"], refreshed,
                  report["checks"]["no_504"], report["checks"]["all_200"], cap_ok, report["checks"]["links_t081"]])
        report["ok"] = ok
    finally:
        resume_warm()
        (state / "accept.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if not ok:
        raise Stop(7, f"приёмка постоянного исправления не пройдена: {json.dumps(report['checks'], ensure_ascii=False)}")
    return report


# ------------------------------------------------------------------ команды
def new_state() -> Path:
    state = STATE_ROOT / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    state.mkdir(parents=True, exist_ok=False)
    return state


def latest_state() -> Path:
    states = sorted(p for p in STATE_ROOT.glob("2*") if (p / "release.json").is_file())
    if not states:
        raise Stop(2, f"в {STATE_ROOT} нет состояния выпуска")
    return states[-1]


def backup_databases(state: Path, journal: Journal) -> None:
    """Резервная копия трёх БД официальным backup.sh (дамп + репетиция восстановления во временную БД).

    Копия — условие выпуска (правила фабрики), а не средство отката: откат БД не делается.
    """
    cmd = json.loads(os.environ["YB_BACKUP_CMD"]) if os.environ.get("YB_BACKUP_CMD") else [
        "bash", str(BUILD_ROOT / state.name / TENANTS[0].base / "deploy/staging/backup.sh")]
    sh(cmd, code=5, what="резервная копия БД", timeout=3600)
    journal.write("backup", "yummyani-staging databases", 0)


def cmd_run(args) -> int:
    state = new_state()
    journal = Journal(state)
    log(f"состояние выпуска: {state}")
    info = preflight(state)
    built = build_all(state)
    for t in TENANTS:
        tag = built[t.service]["image"]
        if not TAG_RE.match(tag):
            raise Stop(4, f"{t.service}: тег «{tag}»")
    release = {"previous": info, "built": built, "deployed": []}
    (state / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=1), encoding="utf-8")
    backup_databases(state, journal)
    deployed: list[str] = []
    for t in TENANTS:
        log(f"выкладка {t.service} ({t.domain}) → {built[t.service]['image']}")
        deploy_one(t, built[t.service], info[t.service], deployed, state, journal)
        deployed.append(t.service)
        release["deployed"] = deployed
        (state / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{t.service}: принято")
    if not args.no_accept:
        accept(state)
    log("готово")
    print(str(state))
    return 0


def cmd_rollback(args) -> int:
    state = Path(args.state) if args.state else latest_state()
    release = json.loads((state / "release.json").read_text(encoding="utf-8"))
    t = BY_SERVICE[args.service]
    if args.service not in release.get("deployed", []):
        raise Stop(2, f"{args.service} в этом выпуске не выкладывался")
    still = [s for s in release["deployed"] if s != args.service]
    rollback_tenant(t, release["previous"][t.service], still, state, Journal(state))
    release["deployed"] = still
    (state / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preflight")
    sub.add_parser("build")
    r = sub.add_parser("run")
    r.add_argument("--no-accept", action="store_true")
    a = sub.add_parser("accept")
    a.add_argument("--state")
    rb = sub.add_parser("rollback")
    rb.add_argument("--service", required=True, choices=sorted(BY_SERVICE))
    rb.add_argument("--state")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "preflight":
            preflight()
            return 0
        if args.cmd == "build":
            state = new_state()
            preflight(state)
            for b in build_all(state).values():
                print(b["image"])
            return 0
        if args.cmd == "run":
            return cmd_run(args)
        if args.cmd == "accept":
            accept(Path(args.state) if args.state else latest_state())
            return 0
        if args.cmd == "rollback":
            return cmd_rollback(args)
    except Stop as e:
        log(f"СТОП ({e.code}): {e}")
        return e.code
    return 2


if __name__ == "__main__":
    sys.exit(main())
