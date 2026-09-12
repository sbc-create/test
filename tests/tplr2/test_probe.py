"""Разовая проба: выдаётся ли разрешение аудитории templates-executor."""
from factory.site_engine.changeset import store as S
from ._путь import довести_до_approved, запросить_grant, собрать_цель


def test_проба_аудитории(стенд):
    цель = собрать_цель(стенд)
    cid, _ = довести_до_approved(стенд, цель)
    аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
    м = аренда["fencing_token"]
    для_templates = запросить_grant(стенд, cid, audience="templates-executor",
                                    fencing_token=м)
    для_worker = запросить_grant(стенд, cid, audience="changeset-worker",
                                 fencing_token=м)
    print("\nаудитория templates-executor ->", для_templates)
    print("аудитория changeset-worker   ->", для_worker[0],
          list(для_worker[1].get("grant", {}))[:6])
