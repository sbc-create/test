"""Контур собственного видео: сценарий → раскадровка → сцены → монтаж →
проверка → своё хранилище и плеер.

Подключённого генератора видео и синтеза речи в проекте нет, бюджет на
платную генерацию не выделен. Поэтому:
* сценарии и раскадровка готовы и валидируются схемой;
* задания регистрируются со статусом `queued` и provider=null;
* dispatch отказывает с BLOCKED_INPUT и не пытается ничего «сгенерировать»;
* на странице рецепта видео не появляется, пока у медиа нет status=ready и
  реального файла — пустых кнопок Play нет.
Существенное изменение рецепта (новая версия) переводит готовое видео в review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import jsonschema

from .pipeline import open_store
from .store import SITE_ID, Store, now

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "data" / "video"
SCHEMA = json.loads((ROOT / "schemas" / "video-script.schema.json").read_text())
STATUSES = ("queued", "generating", "failed", "review", "ready")
CONFIG = {
    "provider": None,
    "model": None,
    "max_cost_rub": 0,
    "max_parallel_jobs": 1,
    "max_attempts": 2,
}


class ProviderNotConfigured(RuntimeError):
    """BLOCKED_INPUT: провайдер генерации и лимит расходов не заданы."""


class NullProvider:
    name = None

    def submit(self, scene: dict) -> str:
        raise ProviderNotConfigured("генератор видео не подключён (BLOCKED_INPUT); лимит расходов 0")


def provider():
    if not CONFIG["provider"] or CONFIG["max_cost_rub"] <= 0:
        return NullProvider()
    raise ProviderNotConfigured(f"адаптер для {CONFIG['provider']} не реализован")


def validate_all() -> list[dict]:
    out = []
    for p in sorted(SCRIPTS.glob("*.json")):
        doc = json.loads(p.read_text())
        errs = [e.message for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(doc)]
        total = sum(s["duration_s"] for s in doc["scenes"])
        steps = sorted({s["recipe_step"] for s in doc["scenes"] if s["recipe_step"]})
        out.append(
            {
                "file": p.name,
                "errors": errs,
                "scenes": len(doc["scenes"]),
                "duration_s": total,
                "recipe_steps_covered": steps,
                "status": doc["status"],
            }
        )
    return out


def register(st: Store) -> list[dict]:
    """Медиа-записи по сценариям: сценарий (review) и ролик (queued). Повтор не плодит дублей."""
    res = []
    bad = [v for v in validate_all() if v["errors"]]
    if bad:
        raise ValueError(f"сценарии не проходят схему: {[b['file'] for b in bad]}")
    for p in sorted(SCRIPTS.glob("*.json")):
        doc = json.loads(p.read_text())
        for kind, status in (("video_script", "review"), ("video", "queued")):
            mid = f"{doc['content_id']}:{kind}:v{doc['recipe_version']}"
            if st.db.execute("SELECT 1 FROM media WHERE media_id=?", (mid,)).fetchone():
                res.append({"media_id": mid, "reused": True})
                continue
            rights = (
                doc["rights"] if kind == "video" else {"text": "собственный сценарий по утверждаемой версии рецепта"}
            )
            with st.tx():
                st.db.execute(
                    "INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        mid,
                        SITE_ID,
                        doc["content_id"],
                        doc["recipe_version"],
                        kind,
                        status,
                        None,
                        None,
                        None,
                        json.dumps(rights, ensure_ascii=False),
                        None,
                        str(p.relative_to(ROOT)) if kind == "video_script" else None,
                        now(),
                        now(),
                        "генератор не подключён" if kind == "video" else "сценарий ждёт проверки редактора",
                    ),
                )
                st.audit(
                    "food-daily-video",
                    "media_registered",
                    content_id=doc["content_id"],
                    media_id=mid,
                    status=status,
                )
            res.append({"media_id": mid, "status": status})
    return res


def dispatch(st: Store) -> list[dict]:
    prov = provider()
    out = []
    for m in st.db.execute("SELECT * FROM media WHERE kind='video' AND status='queued'").fetchall():
        try:
            prov.submit({"media_id": m["media_id"]})
        except ProviderNotConfigured as e:
            st.audit(
                "food-daily-video",
                "dispatch_refused",
                content_id=m["content_id"],
                media_id=m["media_id"],
                reason=str(e),
            )
            out.append({"media_id": m["media_id"], "dispatched": False, "reason": str(e)})
    return out


def mark_stale(st: Store) -> int:
    """Видео, снятое по старой версии рецепта, возвращается на проверку."""
    n = 0
    for m in st.db.execute(
        "SELECT m.media_id, m.recipe_version, c.current_version FROM media m JOIN content c "
        "USING(content_id) WHERE m.kind='video' AND m.status='ready'"
    ).fetchall():
        if m["recipe_version"] != m["current_version"]:
            st.db.execute(
                "UPDATE media SET status='review', note='рецепт изменён — ролик требует повторной проверки', "
                "updated_at=? WHERE media_id=?",
                (now(), m["media_id"]),
            )
            n += 1
    return n


def status(st: Store) -> dict:
    rows = st.db.execute("SELECT kind, status, count(*) n FROM media GROUP BY 1, 2").fetchall()
    return {
        "by_kind_status": {f"{r['kind']}:{r['status']}": r["n"] for r in rows},
        "scripts": len(list(SCRIPTS.glob("*.json"))),
        "generated_scenes": 0,
        "ready_files": 0,
        "approved_videos": 0,
        "provider": CONFIG["provider"],
        "budget_rub": CONFIG["max_cost_rub"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily video")
    ap.add_argument("cmd", choices=["validate", "register", "dispatch", "status", "mark-stale"])
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        print(json.dumps(validate_all(), ensure_ascii=False, indent=1))
        return 0
    st = open_store()
    fn = {"register": register, "dispatch": dispatch, "status": status, "mark-stale": mark_stale}[a.cmd]
    print(json.dumps(fn(st), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
