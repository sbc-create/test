"""Выкладка одной витрины Lords: canary без массового выката.

Зачем понадобился отдельный режим. Существующий
`automation/host/lords-staging-apply.sh` применяет конфигурацию всем трём
витринам разом — в нём стоит `[[ ${#SITES[@]} -eq 3 ]] || die`, отбора по
сайту нет ни флагом, ни переменной, — и попутно переставляет nginx, выпускает
сертификаты и перезапускает юниты. «Одна витрина, наблюдение, затем
следующая» этим сценарием не выражается: он меняет всё или ничего.

Здесь делается ровно одно действие и ничего сверх него: разложить релиз в
`<root>/<site>/releases/<отпечаток>` и переключить на него ссылку `current`.
Ни nginx, ни сертификатов, ни systemd, ни соседних витрин.

Переключение видно немедленно и без перезапуска: рантайм витрины разрешает
ссылку `current` при каждом обращении к файлу — это записано в самом
`serve.py` вместе с историей о 243 перезапусках в сутки и 502 у живого
посетителя, ради которой так сделано.

## Что модуль отказывается делать

Отказ всегда наступает **до первой записи**, а не на середине:

* отпечаток шаблона не совпал с ожидаемым — выкатывать «текущее дерево»
  вместо названного артефакта есть самый тихий способ выложить не то;
* каталог витрины недоступен на запись — сообщается точное, чего не хватает;
* витрины с таким именем нет;
* откат без записи о предыдущем релизе — молчаливый успех здесь опаснее
  отказа, потому что оператор решит, что откатился.

## Здоровье и атомарность

Новый релиз проверяется **до** подмены ссылки. Проверка идёт по разложенному
каталогу, а не по исходнику: трафик пойдёт именно в него, и расхождение между
ними — ровно то, что проверка обязана заметить.

Подмена атомарна: ссылка создаётся под временным именем и переносится на
место `os.replace`. Состояния «ссылки нет» не возникает, поэтому одновременный
запрос не может застать витрину без релиза.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

#: Каталог рантайма витрин по умолчанию. Совпадает с `runtime_root` в
#: `config/directions/lords.json`; в тестах подменяется аргументом, а не
#: глобальной правкой.
DEFAULT_ROOT = Path("/srv/lords")

#: Файл записи о выкладке. Лежит рядом с витриной, а не в общем каталоге:
#: запись о canary принадлежит витрине, которую выкатывали.
RECORD_NAME = "canary.json"

HealthCheck = Callable[[Path], "tuple[bool, str]"]


class CanaryRefused(Exception):
    """Отказ до мутации. Причина обязана называть, чего именно не хватает."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _release_id(payload: Path) -> str:
    """Идентификатор релиза — отпечаток его содержимого.

    Не время и не номер: одинаковое содержимое обязано давать одинаковый
    идентификатор, иначе повторная выкладка того же артефакта создаёт второй
    каталог и вопрос «а это тот же релиз?» остаётся без ответа.
    """
    digest = hashlib.sha256()
    for path in sorted(payload.rglob("*")):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(payload)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


@dataclass(frozen=True)
class CanaryPlan:
    """Что будет сделано. Собирается без единой мутации."""

    site_id: str
    root: Path
    site_dir: Path
    release_dir: Path
    new_release: str
    current_release: str | None
    template_digest: str
    payload: Path
    refusals: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return not self.refusals

    def describe(self) -> dict:
        return {
            "site_id": self.site_id,
            "site_dir": str(self.site_dir),
            "switch_from": self.current_release,
            "switch_to": self.new_release,
            "template_digest": self.template_digest,
            "allowed": self.allowed,
            "refusals": list(self.refusals),
        }


@dataclass
class CanaryResult:
    site_id: str
    new_release: str
    previous_release: str | None
    switched: bool
    dry_run: bool = False
    detail: str = ""
    would: dict = field(default_factory=dict)


def plan(
    site_id: str,
    *,
    payload: Path,
    template_digest: str,
    expect_template_digest: str | None = None,
    root: Path | None = None,
) -> CanaryPlan:
    """План выкладки одной витрины. Ничего не пишет и не переключает.

    `expect_template_digest` — не украшение подписи. Без сверки команда
    выкатила бы то, что оказалось в дереве на момент запуска, и подмена
    артефакта прошла бы незамеченной.
    """
    base = Path(root) if root is not None else DEFAULT_ROOT
    site_dir = base / site_id
    refusals: list[str] = []

    if expect_template_digest and template_digest != expect_template_digest:
        refusals.append(
            f"отпечаток шаблона не совпал: ожидался {expect_template_digest[:16]}, "
            f"в дереве {template_digest[:16]}"
        )

    if not site_dir.is_dir():
        refusals.append(f"нет каталога витрины {site_dir}")
        return CanaryPlan(site_id, base, site_dir, site_dir, "", None,
                          template_digest, payload, tuple(refusals))

    releases = site_dir / "releases"
    link = site_dir / "current"
    current = os.path.basename(os.readlink(link)) if link.is_symlink() else None

    # Права проверяются пробой намерения, а не чтением битов: режим доступа
    # не учитывает ни владельца процесса, ни ACL, ни только-чтение файловой
    # системы, и «drwxr-xr-x» ничего не говорит о том, сможем ли мы писать.
    for target, what in ((releases, "каталог релизов"), (site_dir, "каталог витрины")):
        if not os.access(target, os.W_OK | os.X_OK):
            refusals.append(
                f"нет права записи в {what} {target}: "
                f"процесс работает как uid {os.getuid()}"
            )

    new_release = _release_id(payload) if payload.is_dir() else ""
    if not new_release:
        refusals.append(f"нечего выкладывать: {payload} не каталог")

    return CanaryPlan(
        site_id=site_id, root=base, site_dir=site_dir,
        release_dir=releases / new_release if new_release else releases,
        new_release=new_release, current_release=current,
        template_digest=template_digest, payload=payload,
        refusals=tuple(refusals),
    )


def _switch(link: Path, target: Path) -> None:
    """Атомарная подмена ссылки. Состояния «ссылки нет» не возникает.

    Цель приводится к абсолютному пути намеренно. Относительная ссылка
    разрешается относительно каталога самой ссылки, то есть `lords-01/`, а
    релиз лежит в `lords-01/releases/<id>` — ссылка указывала бы в никуда, и
    витрина отвечала бы 404 на все адреса сразу, включая главную. Дефект
    нашёлся сквозным прогоном на песочном рантайме: модульные тесты его не
    видели, потому что `tmp_path` абсолютен всегда.
    """
    target = Path(os.path.abspath(target))
    temporary = link.with_name(link.name + ".new")
    if temporary.is_symlink() or temporary.exists():
        temporary.unlink()
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, link)
    # Проверка после подмены: ссылка обязана вести в существующий каталог.
    # Стоит она один системный вызов, а ловит целый класс отказов, при
    # котором витрина «переключена» и при этом пуста.
    if not link.is_dir():
        raise CanaryRefused(
            f"ссылка {link} после подмены не ведёт в каталог: цель {target}"
        )


def apply(
    plan: CanaryPlan,
    *,
    health: HealthCheck,
    dry_run: bool = False,
) -> CanaryResult:
    """Раскладывает релиз и переключает ссылку. Одна витрина, ничего сверх."""
    if not plan.allowed:
        raise CanaryRefused("; ".join(plan.refusals))

    if dry_run:
        return CanaryResult(
            site_id=plan.site_id, new_release=plan.new_release,
            previous_release=plan.current_release, switched=False, dry_run=True,
            detail="сухой прогон: ни одной записи не сделано",
            would=plan.describe(),
        )

    release_dir = plan.release_dir
    if not release_dir.exists():
        # Сначала во временный каталог, потом переименование: наполовину
        # скопированный релиз не должен выглядеть готовым, если процесс
        # прервут между файлами.
        staging = release_dir.with_name(release_dir.name + ".incomplete")
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(plan.payload, staging)
        os.replace(staging, release_dir)

    ok, detail = health(release_dir)
    if not ok:
        # Каталог остаётся на месте: он пригодится для разбора, а места
        # занимает столько же, сколько занял бы после успешной выкладки.
        return CanaryResult(
            site_id=plan.site_id, new_release=plan.new_release,
            previous_release=plan.current_release, switched=False,
            detail=f"проверка здоровья не пройдена, ссылка не переключена: {detail}",
        )

    _switch(plan.site_dir / "current", release_dir)

    (plan.site_dir / RECORD_NAME).write_text(
        json.dumps({
            "site_id": plan.site_id,
            "release": plan.new_release,
            "previous_release": plan.current_release,
            "template_digest": plan.template_digest,
            "switched_at_utc": _now(),
            "health": detail,
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return CanaryResult(
        site_id=plan.site_id, new_release=plan.new_release,
        previous_release=plan.current_release, switched=True,
        detail=f"переключено на {plan.new_release}: {detail}",
    )


def rollback(
    site_id: str,
    *,
    health: HealthCheck,
    root: Path | None = None,
) -> CanaryResult:
    """Возврат витрины на релиз, который был до выкладки.

    Источник истины — запись `canary.json`, а не «предпоследний каталог по
    сортировке»: сортировка вернула бы произвольный релиз, если каталогов
    больше двух, и сделала бы это молча.
    """
    base = Path(root) if root is not None else DEFAULT_ROOT
    site_dir = base / site_id
    record_path = site_dir / RECORD_NAME
    if not record_path.exists():
        raise CanaryRefused(
            f"нет записи о выкладке {record_path}: предыдущего релиза не известно"
        )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    previous = record.get("previous_release")
    if not previous:
        raise CanaryRefused("в записи не указан предыдущий релиз: возвращаться некуда")

    target = site_dir / "releases" / previous
    if not target.is_dir():
        raise CanaryRefused(f"предыдущий релиз {target} не найден на диске")

    ok, detail = health(target)
    if not ok:
        return CanaryResult(
            site_id=site_id, new_release=previous,
            previous_release=record.get("release"), switched=False,
            detail=f"прежний релиз не прошёл проверку, откат не выполнен: {detail}",
        )

    _switch(site_dir / "current", target)
    record_path.write_text(
        json.dumps({**record, "rolled_back_to": previous, "rolled_back_at_utc": _now()},
                   ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return CanaryResult(
        site_id=site_id, new_release=previous,
        previous_release=record.get("release"), switched=True,
        detail=f"откат на {previous}: {detail}",
    )


#: Маршруты, по которым релиз признаётся живым. Список короткий намеренно:
#: проверка идёт до переключения и обязана быть быстрой, а её задача —
#: отличить «релиз поднялся и отдаёт страницы» от «релиз пуст или падает»,
#: а не заменить приёмку.
HEALTH_ROUTES: tuple[str, ...] = ("/", "/catalog/", "/nonexistent-canary-probe/")


def serve_health(directory: Path, *, timeout: float = 25.0) -> tuple[bool, str]:
    """Поднимает релиз его же рантаймом на временном порту и опрашивает маршруты.

    Проверяется именно разложенный каталог, а не исходник сборки: трафик
    пойдёт в него, и расхождение между ними — ровно то, что эта проверка
    обязана заметить.

    Порт занимается на петле и только на время проверки. Наружу ничего не
    открывается: инцидент 001 этой программы случился ровно из-за умолчания,
    при котором сервер слушал все интерфейсы.
    """
    import socket
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request

    runtime = directory / "serve.py"
    if not runtime.exists():
        return False, f"в релизе нет рантайма {runtime.name}"

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    env = {**os.environ, "LORDS_SITE_ROOT": str(directory), "PORT": str(port),
           "LORDS_PORT": str(port), "HOST": "127.0.0.1"}
    process = subprocess.Popen(
        [sys.executable, str(runtime)], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + timeout
        statuses: dict[str, object] = {}
        alive = False
        while time.monotonic() < deadline:
            if process.poll() is not None:
                out = (process.stdout.read() or "")[-300:] if process.stdout else ""
                return False, f"рантайм завершился с кодом {process.returncode}: {out.strip()}"
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                    response.read(64)
                alive = True
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        if not alive:
            return False, f"релиз не ответил на петле за {timeout:.0f} с"

        for route in HEALTH_ROUTES:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=5) as r:
                    statuses[route] = (r.status, len(r.read()))
            except urllib.error.HTTPError as exc:
                statuses[route] = (exc.code, len(exc.read()))
            except Exception as exc:  # noqa: BLE001 — недоступность маршрута тоже факт
                return False, f"{route}: {type(exc).__name__}"

        home = statuses.get("/")
        catalog = statuses.get("/catalog/")
        missing = statuses.get("/nonexistent-canary-probe/")
        if not (isinstance(home, tuple) and home[0] == 200 and home[1] > 1000):
            return False, f"главная отвечает {home}, ожидалось 200 и непустое тело"
        if not (isinstance(catalog, tuple) and catalog[0] == 200):
            return False, f"каталог отвечает {catalog}, ожидалось 200"
        # 404 на несуществующем адресе — не придирка: релиз, отвечающий 200 на
        # что угодно, ломает и индексацию, и обход ссылок.
        if not (isinstance(missing, tuple) and missing[0] == 404):
            return False, f"несуществующий адрес отвечает {missing}, ожидалось 404"
        return True, "; ".join(f"{k} {v[0]}/{v[1]}б" for k, v in statuses.items())
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
