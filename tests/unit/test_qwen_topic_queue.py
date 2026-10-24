"""Очередь тем для Qwen: запас, раскладка 24 + 16, без опубликованного и без повторов, переделки — первыми."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("queue", ROOT / "tools" / "qwen_topic_queue.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def test_queue_has_stock_split_and_no_published_or_repeats():
    published = {"bestreciept.site": [("s", q.intake.title_key("Борщ"), "x")], "myfood.mobi": []}
    res = q.build((24, 16), existing=published)
    br, mf = res["queue"]["bestreciept.site"], res["queue"]["myfood.mobi"]
    assert len(br) + len(mf) >= 80 and len(mf) >= 16 and len(br) >= 24
    assert br[0]["kind"] == "redo" and mf[0]["kind"] == "redo"
    assert [x["day"] for x in br[:25]] == [1] * 24 + [2] and [x["day"] for x in mf[:17]] == [1] * 16 + [2]
    titles = [x["title"] for x in br + mf]
    assert len(titles) == len(set(titles))
    assert not any("Борщ" in t for t in titles)  # опубликованный «Борщ» исключает и «Борщ с говядиной»
