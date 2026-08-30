"""Редакционный слой: правки поверх поставщика, а не вместо него."""
from datetime import datetime, timedelta, timezone

import pytest

from factory.site_engine.contracts import ContractError, Title
from factory.site_engine.editorial import (
    BulkOperation,
    ChangeSet,
    EditorialOverride,
    EditorialService,
    InvalidOverride,
    Permission,
    PermissionDenied,
    PreviewToken,
    Principal,
    PublicationTarget,
    RevisionConflict,
    Role,
)

MOMENT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def тайтл(name: str = "Имя от поставщика") -> Title:
    return Title(canonical_id="p:1", provider="p", provider_id="1", name=name,
                 observed_at=MOMENT)


@pytest.fixture
def сервис() -> EditorialService:
    return EditorialService()


@pytest.fixture
def редактор() -> Principal:
    return Principal("редактор", Role.EDITOR, frozenset({"lords-01"}))


@pytest.fixture
def выпускающий() -> Principal:
    return Principal("выпускающий", Role.PUBLISHER, frozenset({"lords-01"}))


class TestДанныеПоставщикаТолькоДляЧтения:
    def test_правка_не_меняет_исходную_запись(self, сервис, редактор, выпускающий):
        исходный = тайтл()
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "Исправленное"}, reason="опечатка")
        сервис.publish(выпускающий, черновик.draft_id,
                       target=PublicationTarget(("lords-01",)), reason="выпуск")
        assert исходный.name == "Имя от поставщика"
        assert сервис.apply_overrides("lords-01", исходный).name == "Исправленное"

    def test_поля_вне_списка_править_нельзя(self, сервис, редактор):
        with pytest.raises(InvalidOverride, match="принадлежат поставщику"):
            сервис.create_draft(редактор, site_id="lords-01", canonical_title_id="p:1",
                                fields={"seasons": []}, reason="почему бы нет")

    def test_правка_без_причины_не_принимается(self):
        with pytest.raises(InvalidOverride, match="без причины"):
            EditorialOverride(site_id="s", canonical_title_id="p:1", fields={"name": "x"},
                              author="кто-то", reason="  ", created_at=MOMENT)


class TestПраваИОбластьСайтов:
    def test_редактор_не_публикует(self, редактор):
        with pytest.raises(PermissionDenied):
            редактор.require(Permission.PUBLISH, "lords-01")

    def test_право_не_распространяется_на_чужой_сайт(self, выпускающий):
        """Иначе редактор одного сайта однажды опубликует на всех шести."""
        with pytest.raises(PermissionDenied, match="lords-02"):
            выпускающий.require(Permission.PUBLISH, "lords-02")

    def test_читатель_ничего_не_меняет(self, сервис):
        читатель = Principal("гость", Role.VIEWER, frozenset({"lords-01"}))
        with pytest.raises(PermissionDenied):
            сервис.create_draft(читатель, site_id="lords-01", canonical_title_id="p:1",
                                fields={"name": "x"}, reason="просто так")


class TestПредпросмотр:
    def test_предпросмотр_не_влияет_на_живое(self, сервис, редактор):
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "Черновое"}, reason="проба")
        предпросмотр = сервис.preview(редактор, черновик.draft_id, тайтл())
        assert предпросмотр.name == "Черновое"
        assert сервис.apply_overrides("lords-01", тайтл()).name == "Имя от поставщика"

    def test_чужой_токен_не_подходит(self, сервис, редактор):
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "x"}, reason="проба")
        чужой = PreviewToken(token="t", draft_id="другой",
                             expires_at=MOMENT + timedelta(hours=1))
        with pytest.raises(PermissionDenied):
            сервис.preview(редактор, черновик.draft_id, тайтл(), token=чужой)


class TestВерсииИОткат:
    def test_одновременная_правка_не_теряется_молча(self, сервис, редактор):
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "первое"}, reason="раз")
        сервис.update_draft(редактор, черновик.draft_id, fields={"name": "второе"},
                            reason="два", expected_version=1)
        with pytest.raises(RevisionConflict, match="версии"):
            сервис.update_draft(редактор, черновик.draft_id, fields={"name": "третье"},
                                reason="три", expected_version=1)

    def test_откат_возвращает_конкретную_ревизию(self, сервис, редактор):
        публикатор = Principal("выпускающий", Role.PUBLISHER, frozenset({"lords-01"}))
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "первое"}, reason="раз")
        сервис.update_draft(редактор, черновик.draft_id, fields={"name": "второе"},
                            reason="два", expected_version=1)
        сервис.rollback(публикатор, черновик.draft_id, revision=1, reason="вернуть как было")
        assert черновик.fields["name"] == "первое"

    def test_откат_к_несуществующей_ревизии_отклоняется(self, сервис, редактор):
        публикатор = Principal("выпускающий", Role.PUBLISHER, frozenset({"lords-01"}))
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "первое"}, reason="раз")
        with pytest.raises(ContractError, match="ревизии"):
            сервис.rollback(публикатор, черновик.draft_id, revision=99, reason="наугад")


class TestПубликация:
    def test_публикация_требует_явного_списка_сайтов(self):
        with pytest.raises(ContractError, match="без списка сайтов"):
            PublicationTarget(())

    def test_снятие_с_публикации_возвращает_данные_поставщика(self, сервис, редактор,
                                                              выпускающий):
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "Исправленное"}, reason="опечатка")
        сервис.publish(выпускающий, черновик.draft_id,
                       target=PublicationTarget(("lords-01",)), reason="выпуск")
        сервис.unpublish(выпускающий, черновик.draft_id, reason="передумали")
        assert сервис.apply_overrides("lords-01", тайтл()).name == "Имя от поставщика"


class TestИдемпотентность:
    def test_повтор_той_же_просьбы_не_создаёт_второй_черновик(self, сервис, редактор):
        первый = сервис.create_draft(редактор, site_id="lords-01", canonical_title_id="p:1",
                                     fields={"name": "x"}, reason="раз",
                                     idempotency_key="ключ")
        второй = сервис.create_draft(редактор, site_id="lords-01", canonical_title_id="p:1",
                                     fields={"name": "x"}, reason="раз",
                                     idempotency_key="ключ")
        assert первый.draft_id == второй.draft_id


class TestМассовыеОперации:
    def test_без_сухого_прогона_применить_нельзя(self, сервис):
        админ = Principal("админ", Role.ADMIN, frozenset({"*"}))
        операция = BulkOperation(operation_id="op1", site_ids=("lords-01",),
                                 changes=(ChangeSet("lords-01", "p:1", {"name": "a"},
                                                    {"name": "b"}),),
                                 dry_run=False)
        with pytest.raises(ContractError, match="сухой прогон"):
            сервис.apply_bulk(админ, операция, reason="сразу")

    def test_сухой_прогон_считает_действительные_изменения(self, сервис):
        админ = Principal("админ", Role.ADMIN, frozenset({"*"}))
        операция = BulkOperation(
            operation_id="op2",
            site_ids=("lords-01",),
            changes=(
                ChangeSet("lords-01", "p:1", {"name": "a"}, {"name": "b"}),
                ChangeSet("lords-01", "p:2", {"name": "c"}, {"name": "c"}),
            ),
        )
        план = сервис.plan_bulk(админ, операция)
        assert план["changes_total"] == 2
        assert план["changes_effective"] == 1
        assert план["no_op"] == 1


class TestАудит:
    def test_каждое_изменение_записано(self, сервис, редактор, выпускающий):
        черновик = сервис.create_draft(редактор, site_id="lords-01",
                                       canonical_title_id="p:1",
                                       fields={"name": "x"}, reason="раз")
        сервис.update_draft(редактор, черновик.draft_id, fields={"name": "y"},
                            reason="два", expected_version=1)
        сервис.publish(выпускающий, черновик.draft_id,
                       target=PublicationTarget(("lords-01",)), reason="выпуск")
        действия = [e.action for e in сервис.audit]
        assert действия == ["draft.create", "draft.update", "draft.publish"]
        assert all(e.reason for e in сервис.audit), "запись без причины бесполезна"

    def test_запись_аудита_имеет_отпечаток(self, сервис, редактор):
        сервис.create_draft(редактор, site_id="lords-01", canonical_title_id="p:1",
                            fields={"name": "x"}, reason="раз")
        запись = next(iter(сервис.audit))
        assert len(запись.digest()) == 16
