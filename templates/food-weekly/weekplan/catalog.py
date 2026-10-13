"""Снимок каталога соседних сайтов сети (контракт recipe-catalog/1).

Снимок хранится в data/catalog/<site_id>.json вместе с временем получения и
статусом интеграции. Публичное чтение меню работает от снимка, даже если
сосед недоступен. Тексты рецептов сюда не попадают — только адреса и факты.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from .net import network_feed

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "catalog"


def refresh(site_id: str) -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "network.yaml").read_text())["sites"][site_id]
    feed = network_feed(site_id)
    snap = {
        "site_id": site_id,
        "schema": feed["schema"],
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_generated_at": feed["generated_at"],
        "integration_status": cfg["integration_status"],
        "items": feed["items"],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"{site_id}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
    return {"site_id": site_id, "items": len(snap["items"]), "status": snap["integration_status"]}


if __name__ == "__main__":
    print(json.dumps(refresh("food-daily"), ensure_ascii=False))
