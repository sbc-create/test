"""Контракты v1: обещания, которые должны падать при нарушении."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.site_engine.contracts import ContractError
from factory.site_engine.contracts_v1 import (
    REGISTRY,
    CacheTagContract,
    Deployment,
    EditorialOverride,
    HealthSnapshot,
    MediaAsset,
    PublishJob,
    SchedulerJob,
    SeoDocument,
    Timestamps,
    TimeSemantics,
    User,
)


def сейчас():
    return datetime.now(timezone.utc)


class TestВремя:
    def test_отсутствующая_отметка_остаётся_пустой(self):
        """Подставить «сегодня» вместо неизвестной даты — выдумать факт."""
        t = Timestamps(observed_at=сейчас())
        assert t.as_dict()["releaseAt"] is None
        assert t.as_dict()["updatedAt"] is None

    def test_наивное_время_отклоняется(self):
        with pytest.raises(ContractError):
            Timestamps(observed_at=datetime(2026, 1, 1))

    def test_releaseAt_и_observedAt_разные_понятия(self):
        """Смысл отметок различается явно, а не подразумевается."""
        assert TimeSemantics.RELEASE_AT.value == "releaseAt"
        assert TimeSemantics.OBSERVED_AT.value == "observedAt"
        assert TimeSemantics.RELEASE_AT is not TimeSemantics.OBSERVED_AT

    def test_все_отметки_приводятся_к_осведомлённым(self):
        t = Timestamps(observed_at=сейчас(), release_at=сейчас() + timedelta(days=1))
        assert t.release_at.tzinfo is not None


class TestSeoDocument:
    def test_canonical_обязан_быть_https(self):
        with pytest.raises(ContractError, match="HTTPS"):
            SeoDocument(document_id="1", site_id="s", path="/", title="t",
                        description="d", canonical="http://x", robots="index, follow")

    def test_неизвестная_директива_robots_отклоняется(self):
        with pytest.raises(ContractError, match="robots"):
            SeoDocument(document_id="1", site_id="s", path="/", title="t",
                        description="d", canonical="https://x", robots="как-нибудь")

    def test_годный_документ_принимается(self):
        d = SeoDocument(document_id="1", site_id="s", path="/", title="t",
                        description="d", canonical="https://x", robots="noindex, follow")
        assert d.version == 1


class TestКэшТеги:
    def test_полная_очистка_запрещена_контрактом(self):
        """Она превращает переживаемый сбой в поломку всех витрин сразу."""
        with pytest.raises(ContractError, match="полная очистка"):
            CacheTagContract(tag="media", covers=("poster",), owner="Media Engine",
                             global_purge_allowed=True)

    def test_обычный_тег_создаётся(self):
        t = CacheTagContract(tag="title", covers=("page",), owner="Site Engine",
                             invalidated_by=("TITLE_UPDATED",))
        assert t.global_purge_allowed is False


class TestВыкладка:
    def test_ревизия_неправдоподобной_длины_отклоняется(self):
        """В 02E «SHA» из 42 символов существовал только в постановке."""
        with pytest.raises(ContractError, match="42"):
            Deployment(deployment_id="d", site_id="s",
                       revision="5a70fa843c9a0d6c4a28a9f2127a867e659fea0da5")

    def test_сорока_символьная_ревизия_принимается(self):
        d = Deployment(deployment_id="d", site_id="s",
                       revision="93ba4d1554a620c58c76445079e75a2e35fb0a6b")
        assert len(d.revision) == 40

    def test_короткая_ревизия_релиза_принимается(self):
        assert Deployment(deployment_id="d", site_id="s", revision="d853747e6413").revision


class TestПубликация:
    def test_счётчики_не_могут_противоречить(self):
        with pytest.raises(ContractError, match="несогласованы"):
            PublishJob(publish_id="p", site_id="s", release_id="r",
                       rendered_pages=10, changed_pages=11)

    def test_ноль_изменений_законен(self):
        """Неизменившийся цикл — обычное состояние, а не ошибка."""
        j = PublishJob(publish_id="p", site_id="s", release_id="r",
                       rendered_pages=9364, changed_pages=0)
        assert j.changed_pages == 0


class TestПрочее:
    def test_правка_без_витрин_отклоняется(self):
        with pytest.raises(ContractError, match="витрин"):
            EditorialOverride(override_id="o", site_ids=(), subject_id="t",
                              fields={"title": "x"}, author="editor")

    def test_черновик_не_опубликован_по_умолчанию(self):
        o = EditorialOverride(override_id="o", site_ids=("s",), subject_id="t",
                              fields={"title": "x"}, author="editor")
        assert o.published is False

    def test_медиа_не_изображение_отклоняется(self):
        with pytest.raises(ContractError, match="не изображение"):
            MediaAsset(asset_id="a", source_url="https://x/y.webp", local_path=None,
                       content_type="text/html", bytes_size=10)

    def test_лицо_без_ролей_отклоняется(self):
        with pytest.raises(ContractError, match="без ролей"):
            User(user_id="u", roles=())

    def test_неизвестный_итог_задания_отклоняется(self):
        with pytest.raises(ContractError, match="итог"):
            SchedulerJob(job_id="j", name="n", schedule="5min", last_result="наверное")

    def test_здоровье_считается_по_всем_признакам(self):
        assert HealthSnapshot(site_id="s", http_status=200).healthy
        assert not HealthSnapshot(site_id="s", http_status=200, broken_images=1).healthy
        assert not HealthSnapshot(site_id="s", http_status=500).healthy
        assert not HealthSnapshot(site_id="s", http_status=200, problems=("индекс стар",)).healthy


class TestРеестр:
    def test_все_пятнадцать_контрактов_названы(self):
        ожидаемые = {
            "NormalizedContentDocument", "SiteProfile", "EditorialOverride", "SeoDocument",
            "MediaAsset", "ContentEvent", "SchedulerJob", "PublishJob", "Deployment",
            "HealthSnapshot", "Tenant", "User", "Role", "AuditEvent", "CacheTagContract",
        }
        assert set(REGISTRY) == ожидаемые

    def test_у_каждого_контракта_есть_владелец_и_потребители(self):
        for имя, запись in REGISTRY.items():
            assert запись["owner"], имя
            assert запись["consumers"], имя
            assert запись["version"] == "1.0", имя
