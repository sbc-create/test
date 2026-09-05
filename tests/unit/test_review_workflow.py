"""REQ-REVIEW-WORKFLOW: решение редактора обязано доходить до каталога.

Очередь разбора умела записать решение и отменить его. Но записанное решение
никуда не применялось: вид записи в каталоге оставался прежним, и редактор,
разобрав конфликт, не менял ничего, кроме строки в очереди.

Здесь решение проходит путь до витрины: черновик → сверка «было/стало» →
утверждение → публикация → проверка → точечный откат. Публикация пишет в
наложение, а не в каталог поставщика: каталог перезаписывается обновлением, и
запись прямо в него терялась бы при следующем прогоне.
"""

from __future__ import annotations

import pytest

from factory.site_engine.content_kind import ContentKind
from factory.site_engine.kind_overlay import KindOverlay
from factory.site_engine.review_queue import (
    Claim,
    ReviewError,
    ReviewItem,
    ReviewQueue,
    ReviewState,
    item_id_for,
)

SITE = "wf-site"


def очередь(tmp_path, сколько=3) -> ReviewQueue:
    q = ReviewQueue(tmp_path)
    for n in range(сколько):
        eid = f"{SITE}:e{n}"
        q.upsert(
            ReviewItem(
                item_id=item_id_for(eid, "contentKind"),
                internal_entity_id=eid,
                site_id=SITE,
                conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
                field="contentKind",
                claims=(
                    Claim("MOVIE", "поле type поставщика", "type='movie'"),
                    Claim("OVA", "тег вида у поставщика", "tags=['ova']"),
                ),
                title=f"Спорный {n}",
            )
        )
    return q


class TestНаложение:
    def test_пустое_наложение_ничего_не_меняет(self, tmp_path):
        assert KindOverlay(tmp_path).kind_for(f"{SITE}:e0") is None

    def test_решение_попадает_в_наложение(self, tmp_path):
        н = KindOverlay(tmp_path)
        н.set(f"{SITE}:e0", kind="OVA", actor="editor", note="по тегу", batch="b1")
        assert н.kind_for(f"{SITE}:e0") == "OVA"

    def test_наложение_переживает_перечитывание(self, tmp_path):
        KindOverlay(tmp_path).set(f"{SITE}:e0", kind="OVA", actor="e")
        assert KindOverlay(tmp_path).kind_for(f"{SITE}:e0") == "OVA"

    def test_чужое_значение_не_принимается(self, tmp_path):
        """Наложение хранит вид из контракта, а не любую строку."""
        with pytest.raises(ValueError):
            KindOverlay(tmp_path).set(f"{SITE}:e0", kind="ПОДКАСТ", actor="e")

    def test_снятие_возвращает_исходное(self, tmp_path):
        н = KindOverlay(tmp_path)
        н.set(f"{SITE}:e0", kind="OVA", actor="e")
        assert н.unset(f"{SITE}:e0", actor="e")
        assert н.kind_for(f"{SITE}:e0") is None

    def test_наложение_видно_сборщику_каталога(self, tmp_path, monkeypatch):
        """Иначе решение остаётся строкой в очереди и ни на что не влияет."""
        from factory.paths import PATHS
        from factory.site_engine import catalog_identity

        monkeypatch.setattr(PATHS, "root", tmp_path)
        конфликт = catalog_identity.decide(provider_type="movie", tags=["ova"])
        assert конфликт.kind is ContentKind.UNKNOWN and конфликт.conflicted

        KindOverlay(tmp_path).set(f"{SITE}:e0", kind="OVA", actor="editor")
        решено = catalog_identity.decide(
            provider_type="movie", tags=["ova"], entity_id=f"{SITE}:e0", root=tmp_path
        )
        assert решено.kind is ContentKind.OVA
        assert not решено.conflicted
        assert решено.decided_by_editor is True


class TestРабочийПоток:
    def test_решение_не_публикуется_само(self, tmp_path):
        """Записанное решение — ещё не изменение витрины."""
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="e", expected_version=1)
        assert KindOverlay(tmp_path).kind_for(f"{SITE}:e0") is None
        assert q.get(iid).state is ReviewState.RESOLVED

    def test_сверка_показывает_было_и_стало(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="e", expected_version=1)
        сверка = q.preview(iid)
        assert сверка["before"] == "UNKNOWN" and сверка["after"] == "OVA"
        assert сверка["published"] is False

    def test_публикация_требует_утверждения(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="e", expected_version=1)
        with pytest.raises(ReviewError, match="утвержд"):
            q.publish(iid, actor="e", expected_version=q.get(iid).version)

    def test_утверждает_не_тот_кто_решил(self, tmp_path):
        """Иначе утверждение — это второе нажатие того же человека."""
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="editor@x", expected_version=1)
        with pytest.raises(ReviewError, match="сам"):
            q.approve(iid, actor="editor@x", expected_version=q.get(iid).version)
        одобрено = q.approve(iid, actor="lead@x", expected_version=q.get(iid).version)
        assert одобрено.state is ReviewState.APPROVED

    def test_полный_путь_до_витрины(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="editor@x", expected_version=1)
        q.approve(iid, actor="lead@x", expected_version=q.get(iid).version)
        итог = q.publish(iid, actor="lead@x", expected_version=q.get(iid).version)
        assert итог.state is ReviewState.PUBLISHED
        assert KindOverlay(tmp_path).kind_for(f"{SITE}:e0") == "OVA"
        assert q.preview(iid)["published"] is True

    def test_точечный_откат_снимает_наложение(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="editor@x", expected_version=1)
        q.approve(iid, actor="lead@x", expected_version=q.get(iid).version)
        q.publish(iid, actor="lead@x", expected_version=q.get(iid).version)
        откат = q.unpublish(iid, actor="lead@x", note="ошиблись")
        assert откат.state is ReviewState.APPROVED
        assert KindOverlay(tmp_path).kind_for(f"{SITE}:e0") is None

    def test_история_хранит_каждый_шаг(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="editor@x", expected_version=1)
        q.approve(iid, actor="lead@x", expected_version=q.get(iid).version)
        q.publish(iid, actor="lead@x", expected_version=q.get(iid).version)
        q.unpublish(iid, actor="lead@x")
        assert [h["action"] for h in q.get(iid).history] == [
            "decide",
            "approve",
            "publish",
            "unpublish",
        ]

    def test_отмена_решения_снимает_публикацию(self, tmp_path):
        """Иначе отменённое решение продолжает действовать на витрине."""
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="editor@x", expected_version=1)
        q.approve(iid, actor="lead@x", expected_version=q.get(iid).version)
        q.publish(iid, actor="lead@x", expected_version=q.get(iid).version)
        q.revert(iid, actor="lead@x", note="передумали")
        assert KindOverlay(tmp_path).kind_for(f"{SITE}:e0") is None
        assert q.get(iid).state is ReviewState.OPEN


class TestКонкурентность:
    def test_двое_не_перезаписывают_друг_друга(self, tmp_path):
        """Второй обязан получить отказ, а не тихо победить."""
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        версия = q.get(iid).version
        q.decide(iid, value="OVA", actor="first@x", expected_version=версия)
        with pytest.raises(ReviewError, match="изменилась"):
            q.decide(iid, value="MOVIE", actor="second@x", expected_version=версия)
        assert q.get(iid).decided_value == "OVA"

    def test_утверждение_по_устаревшей_версии_отклонено(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="e@x", expected_version=1)
        устаревшая = 1
        with pytest.raises(ReviewError, match="изменилась"):
            q.approve(iid, actor="lead@x", expected_version=устаревшая)

    def test_публикация_по_устаревшей_версии_отклонена(self, tmp_path):
        q = очередь(tmp_path, 1)
        iid = q.list()["items"][0]["itemId"]
        q.decide(iid, value="OVA", actor="e@x", expected_version=1)
        q.approve(iid, actor="lead@x", expected_version=q.get(iid).version)
        with pytest.raises(ReviewError, match="изменилась"):
            q.publish(iid, actor="lead@x", expected_version=1)


class TestГрупповаяПубликация:
    def test_публикация_партии_после_сухого_прогона(self, tmp_path):
        q = очередь(tmp_path, 3)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        r = q.batch_apply(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
            from_value="MOVIE",
            to_value="OVA",
            actor="e@x",
            expected_fingerprint=p["versionFingerprint"],
        )
        итог = q.batch_publish(batch_id=r["batchId"], actor="lead@x")
        assert итог["published"] == 3
        н = KindOverlay(tmp_path)
        assert all(н.kind_for(f"{SITE}:e{n}") == "OVA" for n in range(3))

    def test_откат_партии_снимает_наложения(self, tmp_path):
        q = очередь(tmp_path, 3)
        p = q.batch_preview(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG", from_value="MOVIE", to_value="OVA"
        )
        r = q.batch_apply(
            conflict_code="PROVIDER_TYPE_VS_KIND_TAG",
            from_value="MOVIE",
            to_value="OVA",
            actor="e@x",
            expected_fingerprint=p["versionFingerprint"],
        )
        q.batch_publish(batch_id=r["batchId"], actor="lead@x")
        q.batch_revert(batch_id=r["batchId"], actor="lead@x")
        н = KindOverlay(tmp_path)
        assert all(н.kind_for(f"{SITE}:e{n}") is None for n in range(3))
