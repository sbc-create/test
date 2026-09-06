"""REQ-LORDS-HEALTH: витрина сообщает то, что выложено, а не что читалось.

После смены имени манифеста релиза `/healthz` полтора часа отдавал номер
релиза, которого уже не было в работе: при пропаже файла прежняя редакция
возвращала последнее прочитанное значение. Проверка по такому ответу
подтверждает не выкладку, а память процесса — и канареечный релиз можно
объявить принятым, глядя на прежний.
"""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from factory.lords.bundle import RUNTIME


@pytest.fixture()
def рантайм(tmp_path, monkeypatch):
    """Рантайм загружается как настоящий модуль: проверяется то, что поедет."""
    релиз = tmp_path / "releases" / "aaaa1111"
    (релиз / "site").mkdir(parents=True)
    (релиз / "site" / "index.html").write_text("<h1>витрина</h1>", encoding="utf-8")
    (tmp_path / "current").symlink_to(релиз)
    файл = релиз / "serve.py"
    файл.write_text(RUNTIME, encoding="utf-8")

    monkeypatch.setenv("LORDS_SITE_ROOT", str(tmp_path / "current"))
    спец = importlib.util.spec_from_file_location("lords_runtime_под_тестом", файл)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["lords_runtime_под_тестом"] = модуль
    спец.loader.exec_module(модуль)
    return модуль, tmp_path, релиз


def _health(модуль):
    собрано = {}

    def начать(status, headers):
        собрано["status"] = status

    тело = модуль.app({"PATH_INFO": "/healthz"}, начать)
    return собрано["status"], json.loads(b"".join(тело).decode("utf-8"))


def test_манифест_релиза_читается(рантайм):
    модуль, корень, релиз = рантайм
    (релиз / "release-manifest.json").write_text(json.dumps({
        "tenant_id": "lords-02", "theme": "lords_dark", "release": "aaaa1111",
        "template_digest": "a" * 64, "renderer_revision": "b" * 40,
        "content_snapshot_id": "snap-1", "content_count": 52533,
        "rollback_target": "zzzz9999",
    }), encoding="utf-8")
    статус, тело = _health(модуль)
    assert статус.startswith("200")
    assert тело["site_id"] == "lords-02"
    assert тело["theme"] == "lords_dark"
    assert тело["template_digest"] == "a" * 64
    assert тело["renderer_revision"] == "b" * 40
    assert тело["content_snapshot_id"] == "snap-1"
    assert тело["rollback_target"] == "zzzz9999"


def test_пропавший_манифест_не_подменяется_прежним(рантайм):
    модуль, корень, релиз = рантайм
    манифест = релиз / "release-manifest.json"
    манифест.write_text(json.dumps({"tenant_id": "lords-02", "release": "aaaa1111",
                                    "template_digest": "a" * 64}), encoding="utf-8")
    _, первый = _health(модуль)
    assert первый["release"] == "aaaa1111"

    манифест.unlink()
    _, второй = _health(модуль)
    assert второй["template_digest"] is None, (
        "отпечаток прежнего манифеста пережил его исчезновение — по такому "
        "ответу канареечный релиз можно объявить принятым, глядя на прежний")
    # Номер релиза при этом всё же известен: он читается по самой ссылке.
    assert второй["release"] == "aaaa1111"


def test_смена_релиза_видна_сразу(рантайм):
    модуль, корень, релиз = рантайм
    (релиз / "release-manifest.json").write_text(
        json.dumps({"release": "aaaa1111", "template_digest": "a" * 64}), encoding="utf-8")
    _, первый = _health(модуль)
    assert первый["template_digest"] == "a" * 64

    новый = корень / "releases" / "bbbb2222"
    (новый / "site").mkdir(parents=True)
    (новый / "site" / "index.html").write_text("<h1>витрина</h1>", encoding="utf-8")
    (новый / "release-manifest.json").write_text(
        json.dumps({"release": "bbbb2222", "template_digest": "c" * 64}), encoding="utf-8")
    (корень / "current").unlink()
    (корень / "current").symlink_to(новый)

    _, второй = _health(модуль)
    assert второй["release"] == "bbbb2222"
    assert второй["template_digest"] == "c" * 64, "healthz отстаёт от переключения"


def test_прежняя_форма_манифеста_ещё_читается(рантайм):
    модуль, корень, релиз = рантайм
    (релиз / "bundle-manifest.json").write_text(
        json.dumps({"site_id": "lords-02", "release": "lords-02-e4f8919e53ef",
                    "profile": "lords-new"}), encoding="utf-8")
    _, тело = _health(модуль)
    assert тело["release"] == "lords-02-e4f8919e53ef"
    assert тело["profile"] == "lords-new"
