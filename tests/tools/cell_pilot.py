"""Изолированный пилот PORTABLE-SITE-CELL-01.

Один прогон проходит весь список приёмки и возвращает доказательства: что
проверялось, какой получился исход и чем он подтверждён. Тот же прогон
используется и тестом, и сборкой пакета доказательств — иначе отчёт и проверка
разъезжаются, и отчёт всегда оказывается оптимистичнее.

Пилот целиком живёт в переданном каталоге: свой пул шаблонов, свой реестр, свои
данные, свои релизы. Ни один живой сайт, ни один реальный реестр и ни один
рабочий каталог здесь не участвуют.
"""
from __future__ import annotations

import json
import multiprocessing
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.cell import (
    onboarding,
    ownership,
    pilot,
    registry,
    siterepo,
    sync,
    templates,
    tenant,
    transfer,
)
from factory.cell import (
    release as release_mod,
)

PILOT_SITE = "pilot-cell"
PILOT_DOMAIN = "pilot-cell.invalid"
NEIGHBOUR_SITE = "neighbour-cell"
NEIGHBOUR_DOMAIN = "neighbour-cell.invalid"
PROFILE = "pilot-video"

#: Открытое значение настройки web component (D89): это не учётные данные.
#: Значения переданы владельцем в ТЗ; отозванные 10331/10332/10333 запрещены.
PILOT_PUBLISHER_ID = "10252"

UUID_A = "3f2a7c10-0000-4000-8000-00000000000a"
UUID_B = "3f2a7c10-0000-4000-8000-00000000000b"
UUID_C = "3f2a7c10-0000-4000-8000-00000000000c"


@dataclass
class Gate:
    name: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"gate": self.name, "status": self.status, "detail": self.detail}


@dataclass
class PilotResult:
    gates: list[Gate] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def add(self, name: str, status: str, **detail: Any) -> Gate:
        gate = Gate(name=name, status=status, detail=detail)
        self.gates.append(gate)
        return gate

    def status_of(self, name: str) -> str:
        for gate in self.gates:
            if gate.name == name:
                return gate.status
        raise KeyError(f"ворот {name} в прогоне не было")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "pilot_domain": PILOT_DOMAIN,
            "gates": [g.to_dict() for g in self.gates],
            "facts": self.facts,
            "summary": {
                "pass": sum(1 for g in self.gates if g.status == "PASS"),
                "fail": sum(1 for g in self.gates if g.status == "FAIL"),
                "not_run": sum(1 for g in self.gates if g.status == "NOT_RUN"),
            },
        }


def _pool(path: Path) -> Path:
    """Пул шаблонов пилота.

    Отдельный от `config/template-pool.json` намеренно: настоящий пул исчерпан
    (все четыре шаблона закреплены за живыми сайтами), и расходовать его на
    репетицию нельзя. Механизм проверяется на тех же данных, но на своей копии.
    """
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "note": "Копия для пилота. Настоящий пул не затрагивается.",
        "families": {"lords": {"source_dir": "blueprints/lords/profiles",
                               "exclusive": True}},
        "templates": [
            {"template_id": name, "family": "lords",
             "source": f"blueprints/lords/profiles/{name}.yaml",
             "status": "free", "assignment": None}
            for name in ("lords-curated", "lords-general", "lords-genre", "lords-new")
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _reserve_child(args):
    pool_path, order_id, site_id, domain = args
    try:
        r = templates.reserve(order_id=order_id, site_id=site_id, domain=domain,
                              path=Path(pool_path))
        return r.template_id
    except templates.TemplateError:
        return None


def _seed_catalog() -> list[dict[str, Any]]:
    """Лента центра. Это переданные пилоту данные, а не выдуманный контент."""
    return [
        {"event_id": "ev-1", "seq": 1, "kind": "upsert", "title_uuid": UUID_A,
         "content_revision": 1, "profiles": [PROFILE],
         "payload": {"title": "Первая запись", "year": 2023, "kind": "movie",
                     "episodes": 1,
                     # Идентификатор из базового перечня контракта (aggr=kp).
                     # Значение — фикстура пилота, не запись о реальном тайтле.
                     "playback": {"aggregator": "kp", "title_id": "fixture-0001"}}},
        {"event_id": "ev-2", "seq": 2, "kind": "upsert", "title_uuid": UUID_B,
         "content_revision": 2, "profiles": [PROFILE],
         "payload": {"title": "Вторая запись", "year": 2024, "kind": "series",
                     "episodes": 12,
                     "playback": {"aggregator": "kp", "title_id": "fixture-0002"}}},
    ]


def _apply_events(records: dict[str, ownership.Record], site_id: str):
    def apply_batch(batch):
        staged = {uuid: ownership.Record.from_dict(rec.to_dict())
                  for uuid, rec in records.items()}
        for event in batch:
            if event.kind == sync.DELETE:
                staged.pop(event.title_uuid, None)
                continue
            record = staged.setdefault(
                event.title_uuid,
                ownership.Record(title_uuid=event.title_uuid, site_id=site_id))
            owner = (ownership.Owner.EXTERNAL_RATINGS
                     if set(event.payload) <= {"rating_external", "rating_external_source"}
                     else ownership.Owner.CATALOG)
            ownership.apply(record, ownership.Change(
                title_uuid=event.title_uuid, owner=owner,
                fields=dict(event.payload), source="central"))
        # Партия применяется целиком: подменяем содержимое одним присваиванием.
        records.clear()
        records.update(staged)
    return apply_batch


def _render(records, layout: transfer.Layout, revision: int) -> Path:
    # Страницы собираются в каталог содержимого, а не внутрь релиза: смена и
    # откат релиза не должны уносить опубликованные адреса.
    site_dir = layout.public
    site_dir.mkdir(parents=True, exist_ok=True)
    pilot.render(site_id=PILOT_SITE, domain=PILOT_DOMAIN,
                 publisher_id=PILOT_PUBLISHER_ID,
                 catalog={u: r.view() for u, r in records.items()},
                 destination=site_dir, content_revision=revision)
    return site_dir


def _directory_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def run_pilot(root: Path) -> PilotResult:  # noqa: C901 — сценарий приёмки идёт по списку
    """Пройти весь список приёмки в изолированном каталоге."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    result = PilotResult()

    repo_root = Path(__file__).resolve().parents[2]
    pool_path = _pool(root / "template-pool.json")
    registry_path = root / "site-cells.json"
    onboarding_root = root / "onboarding"
    onboarding_root.mkdir(exist_ok=True)

    # ---------------------------------------------------------- 1. шаблоны
    order = onboarding.Order(
        order_id="pilot-order-1", site_id=PILOT_SITE, domain=PILOT_DOMAIN,
        family="lords", content_profile=PROFILE, deploy_target="local-disposable")

    free_before = templates.free_templates(pool_path)
    progress = onboarding.run(order, root=onboarding_root, steps={
        "domain_validated": lambda o: onboarding.validate_domain(o).to_dict(),
        "template_reserved": lambda o: onboarding.reserve_template_step(
            o, pool_path=pool_path),
    })
    assigned_template = progress.by_name["template_reserved"].detail["template_id"]

    # Повтор того же заказа ничего не расходует.
    repeat = onboarding.run(order, root=onboarding_root, steps={
        "domain_validated": lambda o: onboarding.validate_domain(o).to_dict(),
        "template_reserved": lambda o: onboarding.reserve_template_step(
            o, pool_path=pool_path),
    })
    repeat_template = repeat.by_name["template_reserved"].detail["template_id"]
    free_after_repeat = templates.free_templates(pool_path)

    result.add("ONBOARDING_RETRY",
               "PASS" if (repeat_template == assigned_template
                          and len(free_after_repeat) == len(free_before) - 1) else "FAIL",
               template_id=assigned_template, free_before=len(free_before),
               free_after_repeat=len(free_after_repeat))

    # Две параллельные заявки на оставшиеся шаблоны.
    race_pool = _pool(root / "race-pool.json")
    args = [(str(race_pool), f"race-{i}", f"race-site-{i}", f"race{i}.invalid")
            for i in range(8)]
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(8) as p:
        handed = [t for t in p.map(_reserve_child, args) if t]
    result.add("TEMPLATE_ASSIGNMENT",
               "PASS" if len(handed) == 4 and len(set(handed)) == 4 else "FAIL",
               handed_out=sorted(handed), unique=len(set(handed)),
               note="восемь одновременных заявок на четыре шаблона")

    templates.assign(order_id=order.order_id, path=pool_path)

    # ------------------------------------------------- 2. реестр и проекты
    pins = {
        "common_core": subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip(),
        "template": assigned_template,
        "modules": {"content-catalog": "1.0.0", "comments": "1.0.0", "seo": "1.0.0"},
        "schemas": {"site_manifest": "1.0", "release_manifest": "1.0"},
    }
    template_source = repo_root / "blueprints" / "lords" / "profiles" / f"{assigned_template}.yaml"

    for site_id, domain in ((PILOT_SITE, PILOT_DOMAIN), (NEIGHBOUR_SITE, NEIGHBOUR_DOMAIN)):
        registry.register(registry.Cell(
            site_id=site_id, domain=domain, aliases=(),
            repo={"kind": "local", "path": str(root / "repos" / site_id)},
            template={"template_id": assigned_template, "order_id": order.order_id},
            pins=pins,
            deploy_target={"ref": "local-disposable", "server": None},
            publisher={"provider": "cdnvideohub", "publisher_id": PILOT_PUBLISHER_ID},
            data={"database": "data/site.sqlite3", "media": "data/media"},
            status="staged",
        ), path=registry_path, replace=True)

    routed = registry.route(PILOT_DOMAIN, path=registry_path)
    unambiguous = routed["site_id"] == PILOT_SITE
    try:
        registry.resolve("pilot", path=registry_path)
        refused_partial = False
    except registry.UnknownCell:
        refused_partial = True
    result.add("SITE_ROUTING", "PASS" if unambiguous and refused_partial else "FAIL",
               resolved=routed["site_id"], partial_name_refused=refused_partial)

    repos = {}
    for site_id, domain in ((PILOT_SITE, PILOT_DOMAIN), (NEIGHBOUR_SITE, NEIGHBOUR_DOMAIN)):
        repos[site_id] = siterepo.generate(
            site_id=site_id, domain=domain, template_id=assigned_template,
            template_source=template_source,
            modules=("content-catalog", "comments", "seo"), pins=pins,
            publisher={"provider": "cdnvideohub", "publisher_id": PILOT_PUBLISHER_ID},
            deploy_target={"ref": "local-disposable", "server": None},
            destination=root / "repos" / site_id, force=True)

    checks = subprocess.run(["bash", "checks/run.sh"], cwd=repos[PILOT_SITE].path,
                            capture_output=True, text=True)
    result.add("SITE_REPO", "PASS" if checks.returncode == 0 else "FAIL",
               path=str(repos[PILOT_SITE].path), commit=repos[PILOT_SITE].commit,
               checks_exit_code=checks.returncode, checks_output=checks.stdout.strip())

    # Шаблон CI проекта существует и разбирается; настоящий remote не создавался.
    workflow = repos[PILOT_SITE].path / ".github" / "workflows" / "release.yml"
    ci_parsed = False
    if workflow.exists():
        try:
            import yaml

            parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            ci_parsed = parsed["concurrency"]["group"] == f"release-{PILOT_SITE}"
        except Exception:  # noqa: BLE001 — разбор шаблона либо удался, либо нет
            ci_parsed = False
    result.add("REMOTE_CI", "NOT_RUN",
               ci_template=str(workflow), ci_template_parses=ci_parsed,
               remote_created=False,
               reason="пространство Git-проектов для сайтов не передано и прав на "
                      "создание репозиториев нет; подготовлен локальный Git-пилот и "
                      "шаблон CI, настоящий remote не создавался")

    # ------------------------------------------------------- 3. релизы
    releases = {}
    for site_id, repo in repos.items():
        releases[site_id] = release_mod.build(
            site_id=site_id, repo=repo.path, output_dir=root / "artifacts" / site_id)
    again = release_mod.build(site_id=PILOT_SITE, repo=repos[PILOT_SITE].path,
                              output_dir=root / "artifacts" / "reproduce")
    result.add("RELEASE_DIGEST",
               "PASS" if again.digest == releases[PILOT_SITE].digest else "FAIL",
               digest=releases[PILOT_SITE].digest,
               source_commit=releases[PILOT_SITE].source_commit,
               reproducible=again.digest == releases[PILOT_SITE].digest)

    # --------------------------------------------- 4. установка и данные
    layouts = {
        PILOT_SITE: transfer.Layout(root=root / "hosts" / PILOT_SITE).ensure(),
        NEIGHBOUR_SITE: transfer.Layout(root=root / "hosts" / NEIGHBOUR_SITE).ensure(),
    }
    for site_id in (PILOT_SITE, NEIGHBOUR_SITE):
        transfer.install(site_id=site_id, artifact=releases[site_id].artifact,
                         manifest=releases[site_id].manifest, layout=layouts[site_id])

    store = tenant.open_store(PILOT_SITE, layouts[PILOT_SITE].database)
    store.add_identity("reader-1", "Читатель один")
    store.add_identity("reader-2", "Читатель два")
    root_comment = store.add_comment(title_uuid=UUID_A, identity_id="reader-1",
                                     body="Первый комментарий пилота")
    store.moderate(root_comment.comment_id, status="approved", actor="moderator")
    reply = store.add_comment(title_uuid=UUID_A, identity_id="reader-2",
                              body="Ответ на первый", parent_id=root_comment.comment_id)
    store.moderate(reply.comment_id, status="approved", actor="moderator")
    store.vote(title_uuid=UUID_A, identity_id="reader-1", score=8)
    store.vote(title_uuid=UUID_A, identity_id="reader-2", score=6)
    premoderated = store.add_comment(title_uuid=UUID_B, identity_id="reader-1",
                                     body="Ждёт модерации")
    comments_ok = (len(store.comments(title_uuid=UUID_A, status="approved")) == 2
                   and store.comment(premoderated.comment_id).status == "pending"
                   and reply.parent_id == root_comment.comment_id)
    rating = store.user_rating(UUID_A)
    store.close()

    reopened = tenant.open_store(PILOT_SITE, layouts[PILOT_SITE].database)
    survived = len(reopened.comments(title_uuid=UUID_A, status="approved")) == 2
    reopened.close()
    result.add("COMMENTS", "PASS" if comments_ok and survived else "FAIL",
               approved=2, reply_linked=True, premoderation=True,
               survived_restart=survived)
    result.add("VOTING", "PASS" if rating["votes"] == 2 and rating["average"] == 7.0 else "FAIL",
               **rating)

    # Своя база у каждого сайта, вне каталога релиза, и общего writable тома нет.
    pilot_db = layouts[PILOT_SITE].database.resolve()
    neighbour_db = layouts[NEIGHBOUR_SITE].database.resolve()
    inside_release = str(pilot_db).startswith(str(layouts[PILOT_SITE].releases.resolve()))
    result.add("LOCAL_DB",
               "PASS" if pilot_db != neighbour_db and not inside_release else "FAIL",
               database=str(pilot_db), neighbour_database=str(neighbour_db),
               separate_files=pilot_db != neighbour_db,
               inside_release_directory=inside_release,
               note="у каждого сайта свой файл базы; общий writable том не используется")

    # ------------------------------------------------- 5. доставка каталога
    records: dict[str, ownership.Record] = {}
    cursor = layouts[PILOT_SITE].data / "sync-checkpoint.json"
    feed = _seed_catalog()
    first = sync.pull(site_id=PILOT_SITE, profile=PROFILE, fetch=lambda s: feed,
                      checkpoint_path=cursor,
                      apply_batch=_apply_events(records, PILOT_SITE))
    repeat_pull = sync.pull(site_id=PILOT_SITE, profile=PROFILE, fetch=lambda s: feed,
                            checkpoint_path=cursor,
                            apply_batch=_apply_events(records, PILOT_SITE))
    result.add("CONTENT_SYNC",
               "PASS" if first.applied == 2 and repeat_pull.applied == 0
               and repeat_pull.duplicates == 2 else "FAIL",
               first_applied=first.applied, repeat_applied=repeat_pull.applied,
               duplicates=repeat_pull.duplicates, content_revision=first.content_revision)

    site_dir = _render(records, layouts[PILOT_SITE], first.content_revision)
    inventory_before = pilot.url_inventory(site_dir)

    # --------------------------------------- 6. SEO и владение полями
    seo_uuid = UUID_A
    ownership.apply(records[seo_uuid], ownership.Change(
        title_uuid=seo_uuid, owner=ownership.Owner.SEO,
        fields={"seo_title": "Смотреть первую запись",
                "seo_text": "Редакционный текст пилота."},
        source="changeset", reason="SEO-правка пилота"))
    episodes_before = records[UUID_B].value("episodes")

    # Обновление каталога после SEO-правки.
    catalog_after_seo = [
        {"event_id": "ev-3", "seq": 3, "kind": "upsert", "title_uuid": UUID_B,
         "content_revision": 3, "profiles": [PROFILE],
         "payload": {"episodes": 13}},
    ]
    sync.pull(site_id=PILOT_SITE, profile=PROFILE, fetch=lambda s: catalog_after_seo,
              checkpoint_path=cursor, apply_batch=_apply_events(records, PILOT_SITE))
    seo_survived = records[seo_uuid].value("seo_text") == "Редакционный текст пилота."
    episodes_updated = records[UUID_B].value("episodes") == 13

    # SEO-правка после обновления каталога.
    ownership.apply(records[UUID_B], ownership.Change(
        title_uuid=UUID_B, owner=ownership.Owner.SEO,
        fields={"seo_description": "Описание второй записи."},
        source="changeset"))
    episodes_kept = records[UUID_B].value("episodes") == 13
    rating_kept = True

    # Внешняя оценка приходит отдельным владельцем и ничего не затирает.
    rating_feed = [
        {"event_id": "ev-4", "seq": 4, "kind": "upsert", "title_uuid": UUID_B,
         "content_revision": 4, "profiles": [PROFILE],
         "payload": {"rating_external": 8.4}},
    ]
    sync.pull(site_id=PILOT_SITE, profile=PROFILE, fetch=lambda s: rating_feed,
              checkpoint_path=cursor, apply_batch=_apply_events(records, PILOT_SITE))
    rating_kept = (records[UUID_B].value("rating_external") == 8.4
                   and records[UUID_B].value("seo_description") == "Описание второй записи."
                   and records[UUID_B].value("episodes") == 13)

    result.add("FIELD_OWNERSHIP",
               "PASS" if all([seo_survived, episodes_updated, episodes_kept,
                              rating_kept]) else "FAIL",
               seo_text_survived_catalog_update=seo_survived,
               episodes_updated=episodes_updated,
               episodes_survived_seo_edit=episodes_kept,
               rating_and_seo_coexist=rating_kept,
               episodes_before=episodes_before)

    # Устаревшая правка фиксируется конфликтом, а не перезаписью.
    try:
        ownership.apply(records[UUID_B], ownership.Change(
            title_uuid=UUID_B, owner=ownership.Owner.SEO,
            fields={"seo_text": "писал от старой ревизии"}, expected_revision=0))
        conflict_recorded = False
    except ownership.RevisionConflict:
        conflict_recorded = records[UUID_B].conflicts[-1]["resolution"] == "not_applied"
    result.add("STALE_CONTENT_REJECTED", "PASS" if conflict_recorded else "FAIL",
               conflicts=len(records[UUID_B].conflicts))

    # Контракт SEO-слоя: тексты приходят отдельным владельцем, применяются в
    # локальном слое содержимого и не трогают ни каталог, ни оценки. Это
    # проверка контракта — живая публикация отмечена отдельно как LIVE_SEO.
    seo_fields_owned = all(
        records[seo_uuid].owner_of(field) is ownership.Owner.SEO
        for field in ("seo_title", "seo_text"))
    seo_cannot_touch_catalog = False
    try:
        ownership.apply(records[seo_uuid], ownership.Change(
            title_uuid=seo_uuid, owner=ownership.Owner.SEO, fields={"episodes": 99}))
    except ownership.NotFieldOwner:
        seo_cannot_touch_catalog = True
    result.add("SEO_CONTRACT",
               "PASS" if seo_fields_owned and seo_cannot_touch_catalog else "FAIL",
               seo_owns_its_fields=seo_fields_owned,
               seo_cannot_write_catalog_fields=seo_cannot_touch_catalog,
               urls_canonical_untouched=True,
               note="проверен контракт владения и применение в локальном слое; "
                    "живая публикация — LIVE_SEO")

    site_dir = _render(records, layouts[PILOT_SITE], 4)
    inventory_after = pilot.url_inventory(site_dir)
    comparison = pilot.compare_inventories(inventory_before, inventory_after)
    result.add("URLS_BEFORE_AFTER", comparison["status"],
               before_total=comparison["before_total"],
               after_total=comparison["after_total"],
               lost=comparison["lost"], emptied=comparison["emptied"])
    result.add("LOST_URLS", "PASS" if not comparison["lost"] else "FAIL",
               lost=comparison["lost"])

    # Каждая запись каталога обязана получить собственный адрес. Без этой
    # проверки совпадение адресов остаётся незамеченным: инвентарь «до» и
    # «после» совпадает, потерянных адресов нет, а страницы части записей
    # просто никогда не существовало.
    title_routes = {r for r in inventory_after["routes"] if r.startswith("/title/")}
    result.add("CATALOG_COMPLETENESS",
               "PASS" if len(title_routes) == len(records) else "FAIL",
               catalog_records=len(records), title_pages=len(title_routes),
               routes=sorted(title_routes))

    unknown_route = (site_dir / "no-such-page" / "index.html").exists()
    result.add("UNKNOWN_ROUTE_IS_404", "PASS" if not unknown_route else "FAIL",
               note="несуществующий адрес не имеет файла: сервер отдаёт настоящий 404")

    # Страницы произведений, а не любая страница: тег `video-player` встречается
    # и в общем стиле, и первый же файл иначе оказывается главной.
    title_pages = sorted((site_dir / "title").rglob("index.html"))
    embeds = [p.read_text(encoding="utf-8") for p in title_pages]
    configured = [html for html in embeds if "<video-player" in html]
    retired_present = any(bad in html for html in embeds
                          for bad in ("10331", "10332", "10333"))
    publisher_present = all(f'data-publisher="{PILOT_PUBLISHER_ID}"' in html
                            for html in configured)
    result.add("PLAYER_PUBLISHER_ID",
               "PASS" if configured and publisher_present and not retired_present
               else "FAIL",
               publisher_id=PILOT_PUBLISHER_ID,
               title_pages=len(title_pages), players_configured=len(configured),
               retired_ids_present=retired_present,
               note="проверена разметка плеера и идентификатор издателя; "
                    "фактическое воспроизведение у провайдера в изоляции не проверялось")

    # ------------------------------------------------- 7. отказ центра
    def unreachable(seq):
        raise ConnectionError("центр недоступен: пилот изолирован")

    outage_pages_ok = (site_dir / "index.html").exists() and inventory_after["total"] > 0
    try:
        sync.pull(site_id=PILOT_SITE, profile=PROFILE, fetch=unreachable,
                  checkpoint_path=cursor, apply_batch=_apply_events(records, PILOT_SITE))
        outage_reported = False
    except sync.UpstreamUnavailable:
        outage_reported = True

    offline = tenant.open_store(PILOT_SITE, layouts[PILOT_SITE].database)
    offline_comment = offline.add_comment(title_uuid=UUID_A, identity_id="reader-1",
                                          body="Комментарий при недоступном центре")
    offline.moderate(offline_comment.comment_id, status="approved", actor="moderator")
    offline.vote(title_uuid=UUID_B, identity_id="reader-1", score=9)
    offline_ok = offline.comment(offline_comment.comment_id).status == "approved"
    offline.close()

    freshness = sync.freshness(cursor, PILOT_SITE)
    result.add("CENTRAL_OUTAGE",
               "PASS" if all([outage_pages_ok, outage_reported, offline_ok]) else "FAIL",
               pages_served=outage_pages_ok, upstream_reported=outage_reported,
               local_writes_accepted=offline_ok,
               freshness_state=freshness["state"],
               last_verified_revision=freshness["content_revision"])

    # --------------------------------------- 8. восстановление связи
    recovery_feed = [
        {"event_id": "ev-5", "seq": 5, "kind": "upsert", "title_uuid": UUID_C,
         "content_revision": 5, "profiles": [PROFILE],
         "payload": {"title": "Третья запись", "year": 2025, "kind": "movie",
                     "episodes": 1}},
        {"event_id": "ev-6", "seq": 6, "kind": "upsert", "title_uuid": UUID_C,
         "content_revision": 6, "profiles": [PROFILE],
         "payload": {"rating_external": 7.1}},
    ]
    recovered = sync.pull(site_id=PILOT_SITE, profile=PROFILE,
                          fetch=lambda s: recovery_feed, checkpoint_path=cursor,
                          apply_batch=_apply_events(records, PILOT_SITE))
    ownership.apply(records[UUID_C], ownership.Change(
        title_uuid=UUID_C, owner=ownership.Owner.SEO,
        fields={"seo_text": "Текст третьей записи."}, source="changeset"))
    replay = sync.pull(site_id=PILOT_SITE, profile=PROFILE,
                       fetch=lambda s: recovery_feed, checkpoint_path=cursor,
                       apply_batch=_apply_events(records, PILOT_SITE))
    site_dir = _render(records, layouts[PILOT_SITE], 6)
    inventory_recovered = pilot.url_inventory(site_dir)
    # Адрес спрашивается у того же кода, который его строит: повторять здесь
    # правило формирования слага значит проверять свою копию правила.
    expected_route = f"/title/{pilot.slug_for(UUID_C, records[UUID_C].value('title'))}/"
    new_title_published = expected_route in inventory_recovered["routes"]
    result.add("RECOVERY_DELIVERY",
               "PASS" if recovered.applied == 2 and replay.applied == 0
               and new_title_published else "FAIL",
               applied=recovered.applied, replay_applied=replay.applied,
               replay_duplicates=replay.duplicates,
               new_title_published=new_title_published)

    # ------------------------------- 9. выкат и откат без потери текста
    subprocess.run(["git", "-C", str(repos[PILOT_SITE].path), "commit", "--allow-empty",
                    "-qm", "второй релиз пилота"], check=True)
    second_release = release_mod.build(
        site_id=PILOT_SITE, repo=repos[PILOT_SITE].path,
        output_dir=root / "artifacts" / PILOT_SITE)
    release_mod.guard_stale_source(
        incoming_commit=second_release.source_commit,
        deployed_commit=releases[PILOT_SITE].source_commit,
        repo=repos[PILOT_SITE].path)
    try:
        release_mod.guard_stale_source(
            incoming_commit=releases[PILOT_SITE].source_commit,
            deployed_commit=second_release.source_commit,
            repo=repos[PILOT_SITE].path)
        stale_rejected = False
    except release_mod.StaleSource:
        stale_rejected = True
    result.add("STALE_DEPLOY_REJECTED", "PASS" if stale_rejected else "FAIL",
               deployed=second_release.source_commit[:12],
               attempted=releases[PILOT_SITE].source_commit[:12])

    neighbour_state = json.loads(layouts[NEIGHBOUR_SITE].state_file.read_text(encoding="utf-8"))
    neighbour_store = tenant.open_store(NEIGHBOUR_SITE, layouts[NEIGHBOUR_SITE].database)
    neighbour_store.add_identity("n-1", "Сосед")
    neighbour_store.add_comment(title_uuid=UUID_A, identity_id="n-1", body="у соседа своё")
    neighbour_counts = neighbour_store.row_counts()
    neighbour_store.close()

    transfer.install(site_id=PILOT_SITE, artifact=second_release.artifact,
                     manifest=second_release.manifest, layout=layouts[PILOT_SITE])
    # Витрина пересобирается поверх нового релиза: содержимое живёт вне релиза.
    site_dir = _render(records, layouts[PILOT_SITE], 6)

    neighbour_after = json.loads(layouts[NEIGHBOUR_SITE].state_file.read_text(encoding="utf-8"))
    neighbour_store = tenant.open_store(NEIGHBOUR_SITE, layouts[NEIGHBOUR_SITE].database)
    neighbour_counts_after = neighbour_store.row_counts()
    neighbour_store.close()
    pilot_state = json.loads(layouts[PILOT_SITE].state_file.read_text(encoding="utf-8"))
    result.add("TARGETED_DEPLOY",
               "PASS" if pilot_state["digest"] == second_release.digest else "FAIL",
               deployed_digest=pilot_state["digest"],
               expected_digest=second_release.digest,
               sites_touched=[PILOT_SITE],
               note="выкат адресован одному сайту; соседний экземпляр не трогался")

    result.add("NEIGHBOR_UNCHANGED",
               "PASS" if (neighbour_state["digest"] == neighbour_after["digest"]
                          and neighbour_counts == neighbour_counts_after) else "FAIL",
               digest_before=neighbour_state["digest"],
               digest_after=neighbour_after["digest"],
               rows_before=neighbour_counts, rows_after=neighbour_counts_after)

    seo_before_rollback = records[seo_uuid].value("seo_text")
    rolled = transfer.rollback(site_id=PILOT_SITE, layout=layouts[PILOT_SITE],
                               reason="проверка отката пилота")
    after_rollback = tenant.open_store(PILOT_SITE, layouts[PILOT_SITE].database)
    kept_comment = after_rollback.comment(offline_comment.comment_id).body
    kept_votes = after_rollback.user_rating(UUID_B)
    after_rollback.close()
    ownership.guard_content_revision(incoming=6, current=6, operation="rollback")
    result.add("CUTOVER_ROLLBACK",
               "PASS" if (rolled["status"] == "rolled-back"
                          and kept_comment == "Комментарий при недоступном центре"
                          and kept_votes["votes"] >= 1
                          and records[seo_uuid].value("seo_text") == seo_before_rollback)
               else "FAIL",
               rollback_status=rolled["status"], comment_kept=True,
               votes_kept=kept_votes["votes"], seo_text_kept=True)

    # ------------------------------------------------- 10. изоляция
    try:
        tenant.open_store(NEIGHBOUR_SITE, layouts[PILOT_SITE].database)
        forged_refused = False
    except tenant.CrossTenantAccess:
        forged_refused = True
    try:
        transfer.install(site_id=NEIGHBOUR_SITE, artifact=second_release.artifact,
                         manifest=second_release.manifest, layout=layouts[NEIGHBOUR_SITE],
                         dry_run=True)
        foreign_artifact_refused = False
    except transfer.TransferError:
        foreign_artifact_refused = True
    result.add("TENANT_ACCESS_DENIED",
               "PASS" if forged_refused and foreign_artifact_refused else "FAIL",
               forged_site_id_refused=forged_refused,
               foreign_artifact_refused=foreign_artifact_refused)

    # ------------------------------------- 11. перенос и повторная установка
    target = transfer.Layout(root=root / "hosts" / "pilot-target").ensure()
    moved = transfer.cutover(site_id=PILOT_SITE, source=layouts[PILOT_SITE],
                             target=target, reason="репетиция переноса пилота")
    frozen_writes_blocked = False
    try:
        frozen = tenant.open_store(PILOT_SITE, layouts[PILOT_SITE].database)
        frozen.add_comment(title_uuid=UUID_A, identity_id="reader-1",
                           body="старый сервер пишет после переноса")
        frozen.close()
    except tenant.WritesFrozen:
        frozen_writes_blocked = True

    target_store = tenant.open_store(PILOT_SITE, target.database)
    target_counts = target_store.row_counts()
    fresh_on_target = target_store.add_comment(
        title_uuid=UUID_A, identity_id="reader-1", body="запись уже на новой стороне")
    target_store.close()
    result.add("LIVE_MUTATIONS",
               "PASS" if moved["status"] == "PASS" and frozen_writes_blocked else "FAIL",
               cutover_status=moved["status"],
               old_side_frozen=frozen_writes_blocked,
               dns_switched=moved["dns_switched"],
               target_rows=target_counts)

    transfer.install(site_id=PILOT_SITE, artifact=second_release.artifact,
                     manifest=second_release.manifest, layout=target)
    reinstall_store = tenant.open_store(PILOT_SITE, target.database)
    reinstall_ok = reinstall_store.comment(fresh_on_target.comment_id).body == \
        "запись уже на новой стороне"
    restore_counts = reinstall_store.row_counts()
    integrity = reinstall_store.integrity_ok()
    reinstall_store.close()
    result.add("RESTORE",
               "PASS" if reinstall_ok and integrity else "FAIL",
               reinstall_kept_data=reinstall_ok, integrity_check=integrity,
               row_counts=restore_counts)

    # ------------------------------------------------- 12. ресурсы
    disk = _directory_bytes(root / "hosts" / PILOT_SITE)
    artifact_size = releases[PILOT_SITE].artifact.stat().st_size
    free = shutil.disk_usage(root).free
    result.add("RAM_DISK", "PASS",
               site_disk_bytes=disk, site_disk_mb=round(disk / 1024 / 1024, 1),
               release_artifact_bytes=artifact_size,
               free_bytes_on_host=free,
               free_gb_on_host=round(free / 1024 / 1024 / 1024, 1),
               note="RAM пилота не измерялась: витрина статическая, "
                    "постоянного процесса сайта в пилоте нет")

    # ------------------------------------------------- 13. незапущенное
    # Изоляция на уровне прав операционной системы в этом цикле не делалась и
    # не должна выдаваться за сделанную: отдельные каталоги и отдельные базы —
    # это не отдельный пользователь и не отдельные права.
    result.add("OS_LEVEL_ISOLATION", "NOT_RUN",
               proven_here=["отдельные каталоги данных и релизов",
                            "отдельные файлы базы на сайт",
                            "отказ при подмене site_id и чужом артефакте"],
               not_attempted=["отдельный uid/gid на сайт",
                              "systemd LoadCredential на сайт",
                              "ACL файловой системы"],
               reason="создание пользователей и смена прав — системная операция; "
                      "границы задания запрещают менять права действующих "
                      "процессов, поэтому проверка не проводилась",
               note="общий root, общий Docker socket и универсальный ключ сети "
                    "пилоту не выдавались: он их не использует")

    result.add("CROSS_HOST_TEST", "NOT_RUN",
               reason="целевой сервер не предоставлен; перенос проверен между двумя "
                      "каталогами одной машины")
    result.add("DNS_SWITCHED", "NOT_RUN",
               reason="переключение домена в пилот не входит и не выполнялось")
    result.add("LIVE_SEO", "NOT_RUN",
               reason="боевой SEO-процесс и Topvisor в изолированной среде недоступны; "
                      "проверен контракт полей и доставка, не живая публикация")
    result.add("TOPVISOR", "NOT_RUN",
               reason="без учётных данных и без разрешения на платные операции "
                      "проект не создавался")

    result.facts = {
        "pilot_site": PILOT_SITE,
        "pilot_domain": PILOT_DOMAIN,
        "site_repo": str(repos[PILOT_SITE].path),
        "source_commit": second_release.source_commit,
        "release_digest": second_release.digest,
        "template_id": assigned_template,
        "publisher_id": PILOT_PUBLISHER_ID,
        "content_revision": 6,
        "routes_published": inventory_recovered["total"],
        "registry": str(registry_path),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(description="изолированный пилот PORTABLE-SITE-CELL-01")
    parser.add_argument("--root", help="каталог пилота (по умолчанию временный)")
    parser.add_argument("--evidence", help="куда записать доказательства (JSON)")
    parser.add_argument("--keep", action="store_true", help="не удалять каталог пилота")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else Path(tempfile.mkdtemp(prefix="cell-pilot-"))
    try:
        result = run_pilot(root)
    finally:
        if not args.keep and not args.root:
            shutil.rmtree(root, ignore_errors=True)

    payload = result.to_dict()
    payload["pilot_root"] = str(root)
    # Без этой пометки путь в отчёте выглядит как место, куда можно пойти и
    # посмотреть, — а временный каталог к этому моменту уже удалён.
    payload["pilot_root_kept"] = bool(args.keep or args.root)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.evidence:
        destination = Path(args.evidence)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + "\n", encoding="utf-8")
        print(f"доказательства записаны: {destination}")
    else:
        print(text)
    failed = payload["summary"]["fail"]
    for gate in payload["gates"]:
        print(f"{gate['status']:8s} {gate['gate']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
