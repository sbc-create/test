"""REQ-SITE-ADMIN-CONTRACT: договор админки сайта и принадлежность оператора.

Центральная админка одна на весь массив: вход в одну точку, витрина выбирается
параметром запроса, а каталог операторов не знает слова «сайт» вовсе — в нём
нет ни `site_id`, ни `tenant_id`. Любой вошедший оператор видит все витрины.

Для флота этого мало, и мало не «строго», а по существу: местный администратор
одного сайта обязан не видеть соседний. Пока принадлежности нет, изоляции нет
тоже — её нечем выразить.

Три правила, каждое написано на конкретный способ соврать.

**Принадлежность есть у каждого оператора.** Либо он привязан к сайту, либо он
super-admin — и второе объявляется отдельным полем, а не отсутствием первого.
Пустая принадлежность, означающая «видит всё», превращает забытое поле в
раздачу прав.

**Тенант нельзя сменить снаружи.** Ни адресом, ни полем формы, ни телом
запроса. Проверенная принадлежность берётся из сессии, а параметр запроса может
только сузить видимое до уже разрешённого.

**Super-admin переключается явно и под запись.** Переключение — действие, а не
побочный эффект открытия страницы.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.operators import OperatorDirectory, OperatorError

REPO = Path(__file__).resolve().parents[2]
САЙТ_A = "lords-01"
САЙТ_B = "lords-02"


@pytest.fixture
def каталог(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    # Профили витрин настоящие: принадлежность проверяется по ним, и
    # песочница без профилей проверяла бы не то, что работает в жизни.
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    for сайт in (САЙТ_A, САЙТ_B):
        (профили / f"{сайт}.json").write_text(
            json.dumps({"site_id": сайт, "domains": [f"{сайт}.test"]}, ensure_ascii=False),
            encoding="utf-8",
        )
    return OperatorDirectory(tmp_path)


def _завести(каталог, email: str, роли, **kw):
    приглашение, секрет = каталог.invite(email=email, roles=list(роли), created_by="владелец", **kw)
    каталог.accept_invite(secret=секрет, password="длинный-пароль-для-проверки-1")
    return каталог.by_email(email)


class TestПринадлежность:
    def test_оператор_привязан_к_сайту(self, каталог):
        оператор = _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        assert оператор.site_id == САЙТ_A
        assert оператор.is_super_admin is False

    def test_супер_админ_объявляется_явно(self, каталог):
        оператор = _завести(каталог, "s@test", ["admin"], super_admin=True)
        assert оператор.is_super_admin is True
        assert оператор.site_id == ""

    def test_без_сайта_и_без_флага_приглашение_отклоняется(self, каталог):
        """Пустая принадлежность не может означать «видит всё».

        Забытое поле тогда раздаёт права на весь массив, и заметить это можно
        только по последствиям.
        """
        with pytest.raises(OperatorError):
            каталог.invite(email="x@test", roles=["editor"], created_by="владелец")

    def test_нельзя_быть_и_супер_админом_и_привязанным(self, каталог):
        with pytest.raises(OperatorError):
            каталог.invite(
                email="y@test", roles=["admin"], created_by="владелец",
                site_id=САЙТ_A, super_admin=True,
            )

    def test_неизвестный_сайт_отклоняется(self, каталог):
        with pytest.raises(OperatorError):
            каталог.invite(
                email="z@test", roles=["editor"], created_by="владелец", site_id="нет такого",
            )


class TestВидимость:
    def test_список_ограничен_своим_сайтом(self, каталог):
        _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        _завести(каталог, "b@test", ["admin"], site_id=САЙТ_B)
        итог = каталог.list(scope_site_id=САЙТ_A)
        адреса = {о["email"] for о in итог["items"]}
        assert адреса == {"a@test"}
        assert итог["total"] == 1

    def test_супер_админ_видит_всех(self, каталог):
        _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        _завести(каталог, "b@test", ["admin"], site_id=САЙТ_B)
        итог = каталог.list(scope_site_id="")
        assert {о["email"] for о in итог["items"]} == {"a@test", "b@test"}

    def test_чужого_оператора_не_прочитать(self, каталог):
        чужой = _завести(каталог, "b@test", ["admin"], site_id=САЙТ_B)
        with pytest.raises(OperatorError):
            каталог.get(чужой.operator_id, scope_site_id=САЙТ_A)

    def test_чужого_оператора_не_изменить(self, каталог):
        свой = _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        чужой = _завести(каталог, "b@test", ["editor"], site_id=САЙТ_B)
        with pytest.raises(OperatorError):
            каталог.set_roles(
                чужой.operator_id, ["viewer"],
                actor_id=свой.operator_id, actor_roles=свой.roles,
                scope_site_id=САЙТ_A,
            )

    def test_чужие_сессии_не_отзываются(self, каталог):
        свой = _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        чужой = _завести(каталог, "b@test", ["editor"], site_id=САЙТ_B)
        with pytest.raises(OperatorError):
            каталог.revoke_all_sessions(
                чужой.operator_id, actor=свой.email, scope_site_id=САЙТ_A
            )


class TestПоследнийАдминистраторПоСайту:
    def test_последний_админ_сайта_защищён_отдельно_от_соседа(self, каталог):
        """Соседний администратор не заменяет своего.

        Пока защита считала администраторов по всему массиву, единственного
        админа сайта можно было разжаловать: в массиве оставались другие, и
        проверка не возражала — а сайт оставался без хозяина.
        """
        свой = _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        _завести(каталог, "b@test", ["admin"], site_id=САЙТ_B)
        with pytest.raises(OperatorError):
            каталог.set_roles(
                свой.operator_id, ["viewer"],
                actor_id="другой", actor_roles=["admin"], scope_site_id=САЙТ_A,
            )

    def test_второй_админ_того_же_сайта_снимает_запрет(self, каталог):
        первый = _завести(каталог, "a@test", ["admin"], site_id=САЙТ_A)
        _завести(каталог, "a2@test", ["admin"], site_id=САЙТ_A)
        итог = каталог.set_roles(
            первый.operator_id, ["viewer"],
            actor_id="другой", actor_roles=["admin"], scope_site_id=САЙТ_A,
        )
        assert итог.roles == ("viewer",)


class TestДоговор:
    def test_версия_договора_объявлена(self):
        from factory.site_engine import site_admin_contract as договор

        assert договор.VERSION.startswith("site-admin/")

    def test_обязательные_возможности_перечислены(self):
        from factory.site_engine import site_admin_contract as договор

        обязательные = {
            "auth", "users", "content", "layout", "seo", "public-registration",
            "settings", "publish", "jobs", "audit",
        }
        assert обязательные <= set(договор.CAPABILITIES)

    def test_у_каждой_возможности_есть_область_права(self):
        from factory.site_engine import site_admin_contract as договор

        for имя, описание in договор.CAPABILITIES.items():
            assert описание["scope"], f"{имя}: возможность без области права"
            assert описание["summary"], f"{имя}: возможность без объяснения"

    def test_семейства_шаблонов_совпадают_со_схемой(self):
        from factory.site_engine import site_admin_contract as договор

        схема = json.loads(
            (REPO / "schemas" / "site-package.schema.json").read_text(encoding="utf-8")
        )
        перечень = схема["properties"]["tenant"]["properties"]["theme"]["enum"]
        assert list(договор.TEMPLATE_FAMILIES) == list(перечень), (
            "перечень семейств в договоре обязан совпадать со схемой пакета, "
            "иначе адаптер найдётся для семейства, которого схема не знает"
        )

    def test_адаптер_объявлен_для_каждого_семейства(self):
        from factory.site_engine import site_admin_contract as договор

        for семья in договор.TEMPLATE_FAMILIES:
            адаптер = договор.adapter_for(семья)
            assert адаптер["family"] == семья
            assert адаптер["contractVersion"] == договор.VERSION
            assert адаптер["capabilities"], f"{семья}: адаптер без возможностей"

    def test_чужое_семейство_отклоняется(self):
        from factory.site_engine import site_admin_contract as договор

        with pytest.raises(договор.ContractError):
            договор.adapter_for("нет-такого-семейства")
