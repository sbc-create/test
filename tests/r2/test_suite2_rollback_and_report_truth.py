"""SUITE_2 — откат, монотонность защиты и соответствие отчёта доказательствам.

Отчёт — тоже интерфейс. Утверждение «адаптер готов» читают как «остался один
шаг», и если шагов не сделано ни одного, это не стилистика, а неверные
данные для решения. Здесь проверяется, что машинные поля выводятся из
доказательств, а не из намерений.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.site_engine.credentials import generation as G
from factory.site_engine.provisioner import capabilities as CAP
from factory.site_engine.provisioner import readiness as R
from factory.site_engine.provisioner.mapping import Связь
from factory.site_engine.provisioner.providers import fake as F

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


# =============================================================================
# A. Соответствие отчёта доказательствам
# =============================================================================

class TestПравдивостьМатрицы:
    def test_ни_один_адаптер_не_живой(self):
        for в in CAP.МАТРИЦА:
            assert в.adapter_mode == CAP.FAKE_SHADOW_ONLY, (
                f"{в.provider_type}: адаптер не обращался к живому провайдеру")
        assert CAP.живые() == []
        assert CAP.production_onboarding_готов() is False

    def test_api_без_credential_не_объявляется_подтверждённым(self):
        for в in CAP.МАТРИЦА:
            if в.api_status == CAP.PRESENT:
                assert в.credential_present, (
                    f"{в.provider_type}: API объявлен подтверждённым без "
                    f"выданного credential")

    def test_tls_не_выдаётся_за_api_провайдера(self):
        assert CAP.TLS.api_status == CAP.UNVERIFIED
        assert CAP.TLS_АВТОМАТИЗАЦИЯ == "LOCAL_ACME_CLIENT_PRESENT"
        свидетельства = " ".join(CAP.TLS.evidence)
        assert "certbot" in свидетельства and "сертификат" in свидетельства
        assert "обращений контура к ACME не выполнялось" in свидетельства

    def test_метрика_endpoint_отдельно_от_возможностей(self):
        assert CAP.METRIKA.endpoint_state == CAP.OBSERVED_UNAUTHENTICATED
        assert CAP.METRIKA.authenticated_capability == CAP.UNVERIFIED
        assert CAP.METRIKA.api_status == CAP.UNVERIFIED
        assert "401" in " ".join(CAP.METRIKA.evidence)

    @pytest.mark.parametrize("возможности", [CAP.DNS, CAP.TOPVISOR])
    def test_непроверенное_остаётся_непроверенным(self, возможности):
        assert возможности.api_status == CAP.UNVERIFIED
        assert возможности.operations == ()
        assert возможности.credential_present is False

    def test_значений_секретов_в_матрице_нет(self):
        """Описание схемы — не секрет; секрет — это значение.

        Строка «Authorization: OAuth {token}» описывает, КАК передаётся токен,
        и её отсутствие ничего бы не улучшило. Искать надо непрозрачные
        длинные строки и абсолютные пути к хранилищу секретов.
        """
        import re
        сырое = json.dumps(CAP.матрица(), ensure_ascii=False)
        for путь in ("/etc/site-factory/secrets", "/etc/site-factory/credentials"):
            assert путь not in сырое, f"в матрице абсолютный путь {путь}"
        assert "PRIVATE KEY" not in сырое
        # Непрозрачная строка длиной 24+ из алфавита токенов.
        подозрения = [s for s in re.findall(r"[A-Za-z0-9_\-]{24,}", сырое)
                      if not s.startswith(("list_", "create_", "get_"))
                      and "_" not in s.strip("_")]
        assert подозрения == [], f"похоже на значения: {подозрения[:3]}"


# =============================================================================
# B. Монотонность защиты и упаковка отката
# =============================================================================

class TestПолБезопасности:
    def test_пол_не_понижается(self, tmp_path):
        ф = tmp_path / "floor.json"
        ф.write_text(json.dumps({"generation": 99}), encoding="utf-8")
        итог = G.поднять_пол(ф)
        assert итог["current"] == 99, "пол обязан быть монотонным"
        assert json.loads(ф.read_text())["generation"] == 99

    def test_пол_поднимается_до_поколения(self, tmp_path):
        ф = tmp_path / "floor.json"
        ф.write_text(json.dumps({"generation": 1}), encoding="utf-8")
        итог = G.поднять_пол(ф)
        assert итог["previous"] == 1 and итог["current"] == G.ПОКОЛЕНИЕ

    def test_нечитаемый_пол_не_означает_отсутствие_пола(self, tmp_path,
                                                        monkeypatch):
        ф = tmp_path / "floor.json"
        ф.write_text("не json", encoding="utf-8")
        with pytest.raises(G.ПолНедоступен):
            G.пол(ф)

    def test_релиз_без_модуля_считается_первым_поколением(self, tmp_path):
        (tmp_path / "factory/site_engine/credentials").mkdir(parents=True)
        assert G.поколение_релиза(tmp_path) == 1

    def test_поколение_читается_из_файла_а_не_импортом(self, tmp_path):
        """Импорт взял бы то, что первым в sys.path, — и однажды это не релиз."""
        каталог = tmp_path / "factory/site_engine/credentials"
        каталог.mkdir(parents=True)
        (каталог / "generation.py").write_text("ПОКОЛЕНИЕ = 7\n", encoding="utf-8")
        assert G.поколение_релиза(tmp_path) == 7
        assert G.ПОКОЛЕНИЕ != 7, "прочитано из чужого каталога, а не из своего"

    @pytest.mark.parametrize("поколение,пол_,разрешено,ожидается", [
        (1, 2, False, False), (2, 2, False, True), (3, 2, False, True),
        (1, 2, True, True), (1, 0, False, True)])
    def test_правило_допуска(self, поколение, пол_, разрешено, ожидается):
        можно, _ = G.допустимо_ли(поколение, пол_,
                                  разрешено_понижение=разрешено)
        assert можно is ожидается

    def test_текущее_поколение_описывает_свойства(self):
        assert G.ПОКОЛЕНИЕ >= 2
        assert "no-raw-payload-signing" in G.СВОЙСТВА
        assert "split-publisher-identities" in G.СВОЙСТВА
        assert "per-identity-credentials" in G.СВОЙСТВА


class TestОснасткаОтката:
    """Предохранитель обязан стоять на пути отката, а не только выкладки."""

    @pytest.fixture(scope="class")
    def скрипт(self) -> str:
        return (КОРЕНЬ / "automation/host/deploy-control-api.sh").read_text("utf-8")

    def test_откат_проверяет_поколение(self, скрипт):
        откат = скрипт[скрипт.index("cmd_rollback()"):]
        assert "assert_generation_allowed" in откат

    def test_понижение_называется_прямо(self, скрипт):
        assert "--force-security-downgrade" in скрипт
        # Общий --force не должен молча разрешать понижение защиты.
        assert "--force)" not in скрипт

    def test_поколение_измеряется_из_каталога_релиза(self, скрипт):
        """cd в каталог релиза — иначе измеряется рабочее дерево."""
        assert 'cd "$CURRENT_REAL"' in скрипт
        assert "generation check" in скрипт or "generation \\\n      check" in скрипт


# =============================================================================
# C. Закрепление исправлений R1
# =============================================================================

class TestИсправленияR1:
    def test_пространства_провайдеров_не_пересекаются(self):
        """Topvisor не должен находить счётчик Метрики по совпадению поля."""
        мир = F.Мир()
        мир.поместить("analytics", "counter-1",
                      {"site": "shop.test", "public_counter_id": 1})
        tv = F.ФейковыйTopvisor(мир)
        свои = tv._свои()
        assert свои == {}, "чужой объект виден адаптеру другого провайдера"
        мир.поместить("seo_rank", "project-1", {"site": "shop.test",
                                                "project_id": 1})
        assert set(tv._свои()) == {"project-1"}

    def test_владелец_ресурса_совпадает_с_матрицей(self):
        from factory.site_engine.changeset import model as M
        from factory.site_engine.provisioner.changeset_adapter import (
            ProviderTargetAdapter, ТИПЫ)
        for resource_type in ТИПЫ:
            адаптер = ProviderTargetAdapter(None, None, None,
                                            resource_type=resource_type)
            assert адаптер.owner_service == M.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ[resource_type]

    def test_готовность_восстанавливается_из_связей(self):
        """Готовность описывает сайт, а не последний прогон."""
        связи = [Связь("s-1", "dns", "record_set", "d", "f", None, "CREATED",
                       "CREATED"),
                 Связь("s-1", "tls", "certificate", "t", "f", None, "CREATED",
                       "CREATED"),
                 Связь("s-1", "analytics", "counter", "c", "f", None, "CREATED",
                       "CREATED"),
                 Связь("s-1", "template", "counter_tag", "g", "f", None,
                       "CREATED", "CREATED"),
                 Связь("s-1", "seo_rank", "project", "p", "f", None, "CREATED",
                       "CREATED")]
        запись = {"lifecycle_state": "DRAFT", "environment": "test"}
        # Ни одного «шага» — только долговечное состояние.
        г = R.вычислить(site_id="s-1", запись_реестра=запись, связи=связи,
                        наборы=[])
        assert г.stage == R.SEO_READY
        assert "TEMPLATE_READY" in г.reached

    def test_повторный_расчёт_не_понижает_стадию(self):
        связи = [Связь("s-1", "dns", "record_set", "d", "f", None, "CREATED",
                       "CREATED")]
        запись = {"lifecycle_state": "DRAFT", "environment": "test"}
        первый = R.вычислить(site_id="s-1", запись_реестра=запись, связи=связи,
                             наборы=[])
        второй = R.вычислить(site_id="s-1", запись_реестра=запись, связи=связи,
                             наборы=[])
        assert первый.stage == второй.stage == R.DNS_READY

    def test_жизненный_цикл_реестра_не_переопределяется(self):
        связи = [Связь("s-1", "dns", "record_set", "d", "f", None, "CREATED",
                       "CREATED")]
        г = R.вычислить(site_id="s-1",
                        запись_реестра={"lifecycle_state": "RETIRED",
                                        "environment": "production"},
                        связи=связи, наборы=[])
        assert г.details["lifecycle_state"] == "RETIRED"
        assert г.stage in R.ПОРЯДОК
