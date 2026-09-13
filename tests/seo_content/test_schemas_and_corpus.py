"""Схемы и полный прогон корпуса.

Схемы здесь — источник истины: если документ и схема расходятся, прав
документ, а схема нуждается в правке, и наоборот — ослаблять схему ради
прохождения данных нельзя. Поэтому проверяется не только то, что наши
черновики валидны, но и то, что подделку схема отвергает.

Детерминированные проверки применяются ко ВСЕМУ корпусу: и к золотому
набору, и к скрытому holdout, который контур раньше не видел.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

import jsonschema
import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ / "scripts" / "seo_content"))

from factory.seo_content import identity as ID          # noqa: E402
from factory.seo_content import store as ST             # noqa: E402
from factory.seo_content.draft import GateStatus        # noqa: E402
from factory.seo_content.pipeline import (ContentPipeline,   # noqa: E402
                                          SiteContext)
from factory.seo_content.testing import (пакет_сезона, пакет_серии,  # noqa: E402
                                         пакет_тайтла)

СХЕМЫ = КОРЕНЬ / "schemas"


def схема(имя: str) -> dict:
    return json.loads((СХЕМЫ / имя).read_text("utf-8"))


def валидатор(имя: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(схема(имя))


class TestСхемыКомпилируются:
    @pytest.mark.parametrize("имя", ["seo-fact-pack.schema.json",
                                     "seo-content-draft.schema.json",
                                     "seo-editorial-note.schema.json"])
    def test_схема_валидна(self, имя):
        jsonschema.Draft202012Validator.check_schema(схема(имя))


class TestПакетФактовПоСхеме:
    def test_наш_пакет_проходит(self):
        валидатор("seo-fact-pack.schema.json").validate(
            {**пакет_тайтла().payload(), "sha256": пакет_тайтла().sha256})

    def test_факт_без_источника_не_проходит(self):
        тело = пакет_тайтла().payload()
        del тело["facts"][0]["source_id"]
        with pytest.raises(jsonschema.ValidationError):
            валидатор("seo-fact-pack.schema.json").validate(тело)

    def test_чужое_поле_не_проходит(self):
        тело = пакет_тайтла().payload()
        тело["facts"][0]["field_path"] = "/model_rating"
        with pytest.raises(jsonschema.ValidationError):
            валидатор("seo-fact-pack.schema.json").validate(тело)

    def test_лишнее_поле_пакета_не_проходит(self):
        тело = пакет_тайтла().payload()
        тело["публиковать"] = True
        with pytest.raises(jsonschema.ValidationError):
            валидатор("seo-fact-pack.schema.json").validate(тело)


class TestЧерновикПоСхеме:
    def черновик(self):
        сайт = SiteContext("seo-test-0001", "https://seo-test-0001.invalid",
                           own_angle="разбор устройства")
        маршрут = ID.Route(url="/title/x/", resolved_entity_id="title-0001",
                           canonical="/title/x/")
        return ContentPipeline().run_pack(пакет_тайтла(), site=сайт,
                                          route=маршрут).draft

    def test_наш_черновик_проходит(self):
        валидатор("seo-content-draft.schema.json").validate(
            self.черновик().payload())

    def test_состояние_публикации_ограничено_черновиком(self):
        тело = self.черновик().payload()
        тело["publication_state"] = "PUBLISHED"
        with pytest.raises(jsonschema.ValidationError):
            валидатор("seo-content-draft.schema.json").validate(тело)

    def test_production_недостижим_по_схеме(self):
        тело = self.черновик().payload()
        тело["target_environment"] = "production"
        with pytest.raises(jsonschema.ValidationError):
            валидатор("seo-content-draft.schema.json").validate(тело)

    def test_больше_трёх_заметок_схема_не_принимает(self):
        тело = self.черновик().payload()
        одна = (тело["editorial_notes"] or [None])[0]
        if одна is None:
            pytest.skip("у этого пакета заметок нет")
        тело["editorial_notes"] = [одна] * 4
        with pytest.raises(jsonschema.ValidationError):
            валидатор("seo-content-draft.schema.json").validate(тело)


class TestСхемыНеРасходятся:
    """Схема черновика повторяет часть ограничений заметки. Повтор допустим
    только пока обе схемы говорят одно и то же."""

    def test_константы_совпадают(self):
        заметка = схема("seo-editorial-note.schema.json")
        внутри = схема("seo-content-draft.schema.json")[
            "properties"]["editorial_notes"]["items"]
        for поле in ("resource_kind", "comment_mode", "author_type"):
            assert внутри["properties"][поле]["const"] == \
                заметка["properties"][поле]["const"], поле

    def test_запрет_полей_отзыва_совпадает(self):
        заметка = схема("seo-editorial-note.schema.json")
        внутри = схема("seo-content-draft.schema.json")[
            "properties"]["editorial_notes"]["items"]
        assert внутри["not"] == заметка["not"]

    def test_обязательность_ссылок_на_факты_совпадает(self):
        заметка = схема("seo-editorial-note.schema.json")
        внутри = схема("seo-content-draft.schema.json")[
            "properties"]["editorial_notes"]["items"]
        assert внутри["properties"]["fact_refs"]["minItems"] == \
            заметка["properties"]["fact_refs"]["minItems"]


class TestЗаметкаПоСхеме:
    def заметка(self) -> dict:
        сайт = SiteContext("seo-test-0001", "https://seo-test-0001.invalid",
                           own_angle="разбор устройства")
        маршрут = ID.Route(url="/title/x/", resolved_entity_id="title-0001",
                           canonical="/title/x/")
        ч = ContentPipeline().run_pack(пакет_тайтла(), site=сайт,
                                       route=маршрут).draft
        assert ч.editorial_notes, "для проверки нужна хотя бы одна заметка"
        return ч.editorial_notes[0].to_dict()

    def test_наша_заметка_проходит(self):
        jsonschema.Draft202012Validator(
            схема("seo-editorial-note.schema.json")).validate(self.заметка())

    @pytest.mark.parametrize("поле", ["rating", "author_name", "likes",
                                      "posted_at", "aggregateRating"])
    def test_поля_отзыва_схема_отвергает(self, поле):
        тело = {**self.заметка(), поле: 1}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(
                схема("seo-editorial-note.schema.json")).validate(тело)

    def test_заметка_без_ссылок_на_факты_не_проходит(self):
        тело = {**self.заметка(), "fact_refs": []}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(
                схема("seo-editorial-note.schema.json")).validate(тело)

    def test_режим_комментария_закреплён(self):
        тело = {**self.заметка(), "comment_mode": "USER_COMMENT"}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(
                схема("seo-editorial-note.schema.json")).validate(тело)


ВОРОТА_НУЛЕЙ = ("contradicted", "unsupported_material", "player_false",
                "identity_errors", "number_errors", "language_critical",
                "cliches", "structured_errors", "canonical_conflicts",
                "visible_mismatches", "fake_review_markup",
                "unresolved_near_duplicates", "keyword_stuffing",
                "injection_escaped")


def прогнать(корпус: dict) -> dict:
    from run_corpus import прогон
    с = tempfile.mkdtemp()
    return прогон(корпус["cases"], база=pathlib.Path(с) / "drafts.sqlite3")


@pytest.fixture(scope="module")
def прогон_golden():
    путь = КОРЕНЬ / "tests" / "seo_content" / "fixtures" / "golden.json"
    return прогнать(json.loads(путь.read_text("utf-8")))


@pytest.fixture(scope="module")
def прогон_holdout():
    путь = КОРЕНЬ / "tests" / "seo_content" / "fixtures" / "holdout.json"
    return прогнать(json.loads(путь.read_text("utf-8")))


class TestЗолотойНабор:
    def test_размер_набора(self, golden):
        случаи = golden["cases"]
        assert len(случаи) >= 200
        виды = {}
        for с in случаи:
            виды[с["kind"]] = виды.get(с["kind"], 0) + 1
        assert виды.get("title", 0) >= 40
        assert виды.get("season", 0) >= 35
        assert виды.get("episode", 0) >= 60
        грани = [с for с in случаи
                 if с["kind"] == "negative" or "edge" in с["tags"]
                 or "boundary" in с["tags"] or "poor_factpack" in с["tags"]
                 or "no_synopsis" in с["tags"]]
        assert len(грани) >= 65, len(грани)

    def test_обязательные_виды_случаев_присутствуют(self, golden):
        теги = {т for с in golden["cases"] for т in с["tags"]}
        для_проверки = {"injection", "homonym", "remake", "long_title",
                        "no_synopsis", "no_year", "fact_conflict", "boundary",
                        "regression-210", "identity", "metadata_corrected",
                        "spoiler", "duplicate", "exact_duplicate",
                        "paraphrased_duplicate", "poor_factpack",
                        "needs_facts", "doorway", "player", "counts"}
        assert для_проверки <= теги, sorted(для_проверки - теги)

    def test_ожидания_сходятся(self, прогон_golden):
        assert прогон_golden["expectations"]["mismatches"] == 0, \
            прогон_golden["expectations"]["detail"][:5]

    @pytest.mark.parametrize("ворота", ВОРОТА_НУЛЕЙ)
    def test_ворота_нулевые_у_принятых(self, прогон_golden, ворота):
        """Ворота относятся к тому, что контур ПРИНЯЛ.

        В корпусе есть враждебные случаи — подменённый год, обещание
        просмотра без источника, адрес не к той серии. Они обязаны дать
        ошибку: ради этого и заведены. Требование «ноль» относится к
        принятым черновикам, иначе оно означало бы, что проверять нечего.
        """
        assert прогон_golden["accepted_counters"][ворота] == 0

    def test_ни_одной_записи_без_решения(self, прогон_golden):
        assert прогон_golden["store"]["drafts"] == прогон_golden["cases"]
        assert прогон_golden["store"]["orphan_records"] == 0
        assert прогон_golden["store"]["duplicate_drafts"] == 0

    def test_бюджет_вступлений_соблюдён(self, прогон_golden):
        assert прогон_golden["corpus_patterns"]["within_budget"]

    def test_живых_вызовов_модели_нет(self, прогон_golden):
        assert прогон_golden["writer"]["live_calls"] == 0
        assert прогон_golden["writer"]["model_downloads"] == 0
        assert прогон_golden["writer"]["mode"] == "FAKE_SHADOW"

    def test_платных_вызовов_нет(self, прогон_golden):
        assert прогон_golden["budget"]["PAID_SPEND"] == 0

    def test_отклонённые_случаи_действительно_дали_ошибки(self, прогон_golden):
        """Обратная сторона: если враждебные случаи ничего не выявили,
        значит, проверка не сработала, а не «всё чисто»."""
        общие = прогон_golden["counters"]
        assert общие["contradicted"] > 0
        assert общие["identity_errors"] > 0
        assert общие["player_false"] > 0
        assert общие["injection_detected"] > 0

    def test_есть_и_принятые_и_отклонённые(self, прогон_golden):
        исходы = прогон_golden["statuses"]
        assert исходы.get("PASSED", 0) >= 20
        отклонённых = sum(n for к, n in исходы.items() if к != "PASSED")
        assert отклонённых >= 20


class TestСкрытыйНабор:
    def test_размер(self, holdout):
        assert len(holdout["cases"]) >= 300

    def test_не_пересекается_с_золотым(self, golden, holdout):
        общие = {с["case_id"] for с in golden["cases"]} & \
            {с["case_id"] for с in holdout["cases"]}
        assert общие == set()

    def test_названия_не_встречались(self, golden, holdout):
        def названия(корпус):
            итог = set()
            for с in корпус["cases"]:
                for ф in с["event"]["facts"]:
                    if ф["field_path"] == "/canonical_title_ru":
                        итог.add(ф["value"])
            return итог
        assert названия(golden) & названия(holdout) == set()

    def test_ожидания_сходятся(self, прогон_holdout):
        assert прогон_holdout["expectations"]["mismatches"] == 0, \
            прогон_holdout["expectations"]["detail"][:5]

    @pytest.mark.parametrize("ворота", ВОРОТА_НУЛЕЙ)
    def test_ворота_нулевые_у_принятых(self, прогон_holdout, ворота):
        assert прогон_holdout["accepted_counters"][ворота] == 0

    def test_проверки_применены_ко_всему_корпусу(self, прогон_holdout, holdout):
        assert прогон_holdout["cases"] == len(holdout["cases"])
        assert прогон_holdout["store"]["drafts"] == len(holdout["cases"])
