"""REQ-TEMPLATE-SOURCE-DIGEST: отпечаток шаблона отвечает про шаблон.

Найдено при сверке флота перед приёмкой третьей витрины: две боевые витрины
показали разные `template_digest`, и это читалось как «флот разъехался, одна
не получила исправление». Diff по всем источникам отпечатка между двумя
ревизиями оказался пуст — содержимое шаблона совпадало полностью.

Разошлись не шаблоны, а архивы. `template_digest` — это sha256 тарбола, а
тарбол собирается со всего дерева ревизии: правка теста, отчёта или документа
меняет «отпечаток шаблона», не тронув ни одного шаблонного файла.

Поле называется `template_digest`, показывается на экране флота как признак
для сравнения витрин и читается как ответ на вопрос «чем отрисован сайт».
Отвечает оно на другой — «какой тарбол закреплён». Два сайта, отрисованные
одинаково, показывают разное, и оператор делает верный по форме и неверный по
существу вывод: надо выкатывать. Выкат не изменит ни одной страницы.

Здесь закреплено разделение: артефактный отпечаток остаётся якорем
неизменяемости, а на вопрос «чем отрисовано» отвечает отдельное поле.
"""

from __future__ import annotations

import pytest

from factory.lords import release_manifest as рм
from factory.templates import digest as отпечаток_шаблона

ШАБЛОННЫЙ_ФАЙЛ = "factory/lords/render.py"
ПОСТОРОННИЙ_ФАЙЛ = "tests/unit/test_zzz_ничей.py"


def дерево(tmp_path, посторонний: str):
    """Минимальное дерево с шаблонными источниками и одним посторонним файлом."""
    корень = tmp_path / f"репо-{abs(hash(посторонний)) % 10000}"
    for отн in (ШАБЛОННЫЙ_ФАЙЛ, "factory/lords/theme.py", "factory/lords/player.py",
                "factory/lords/pagination.py"):
        путь = корень / отн
        путь.parent.mkdir(parents=True, exist_ok=True)
        путь.write_text("# шаблонный источник\n", encoding="utf-8")
    (корень / "blueprints" / "lords").mkdir(parents=True, exist_ok=True)
    (корень / "blueprints" / "lords" / "blueprint.yaml").write_text(
        "version: 1\n", encoding="utf-8")
    (корень / "factory" / "templates").mkdir(parents=True, exist_ok=True)
    (корень / "factory" / "templates" / "__init__.py").write_text("", encoding="utf-8")

    чужой = корень / ПОСТОРОННИЙ_ФАЙЛ
    чужой.parent.mkdir(parents=True, exist_ok=True)
    чужой.write_text(посторонний, encoding="utf-8")
    return корень


class TestОтпечатокШаблонаНеЗависитОтПостороннего:
    def test_правка_постороннего_файла_не_меняет_отпечаток_шаблона(self, tmp_path):
        было = отпечаток_шаблона.compute(дерево(tmp_path, "# первая версия\n"))
        стало = отпечаток_шаблона.compute(дерево(tmp_path, "# вторая версия\n"))
        assert было["template_digest"] == стало["template_digest"], (
            "правка постороннего файла изменила отпечаток шаблона")

    def test_правка_шаблонного_файла_отпечаток_меняет(self, tmp_path):
        корень = дерево(tmp_path, "# одна версия\n")
        было = отпечаток_шаблона.compute(корень)
        (корень / ШАБЛОННЫЙ_ФАЙЛ).write_text("# другой шаблон\n", encoding="utf-8")
        стало = отпечаток_шаблона.compute(корень)
        assert было["template_digest"] != стало["template_digest"], (
            "правка шаблона осталась незамеченной — отпечаток бесполезен")


class TestМанифестРазличаетДваОтпечатка:
    def _манифест(self, **over) -> dict:
        основа = {
            "tenant_id": "lords-03", "domain": "example.test", "theme": "lords_light",
            "template_package_ref": "lords-tooling/aaaaaaaaaaaa",
            "template_artifact_ref": "templates/aaaaaaaaaaaa.tar.gz",
            "template_digest": "a" * 64,
            "renderer_revision": "a" * 40,
            "content_snapshot_id": "снимок-1", "content_source": "поставщик",
            "content_count": 10, "created_at": "2026-09-07T00:00:00Z",
            "created_by": "стенд", "previous_release": None,
            "rollback_target": None, "release_reason": "content-refresh",
            "production_authorized": True,
        }
        основа.update(over)
        return основа

    def test_поле_источников_объявлено_отдельно_от_артефактного(self):
        assert рм.ИСТОЧНИКИ_ШАБЛОНА not in рм.ОБЯЗАТЕЛЬНЫЕ, (
            "новое поле объявлено обязательным — старые манифесты станут негодными")
        assert рм.ИСТОЧНИКИ_ШАБЛОНА in рм.ШАБЛОННЫЕ, (
            "отпечаток источников не защищён как шаблонное поле: "
            "обновление каталога сможет его переписать")

    def test_манифест_без_нового_поля_остаётся_годным(self):
        """Старый манифест не становится негодным от появления поля."""
        рм.проверить(self._манифест())

    def test_обновление_каталога_не_вправе_менять_отпечаток_источников(self):
        текущий = self._манифест(**{рм.ИСТОЧНИКИ_ШАБЛОНА: "b" * 64})
        следующий = рм.следующий(
            текущий, content_snapshot_id="снимок-2", content_count=11,
            created_at="2026-09-07T01:00:00Z", created_by="стенд",
            release_reason="content-refresh", previous_release="rel-1")
        assert следующий[рм.ИСТОЧНИКИ_ШАБЛОНА] == "b" * 64, (
            "обновление каталога изменило отпечаток источников шаблона")

    def test_два_манифеста_с_разными_артефактами_но_одним_шаблоном_различимы(self):
        """Ровно тот случай, что случился на флоте."""
        первый = self._манифест(
            template_artifact_ref="templates/aaaaaaaaaaaa.tar.gz",
            template_digest="a" * 64, **{рм.ИСТОЧНИКИ_ШАБЛОНА: "c" * 64})
        второй = self._манифест(
            template_artifact_ref="templates/bbbbbbbbbbbb.tar.gz",
            template_digest="b" * 64, **{рм.ИСТОЧНИКИ_ШАБЛОНА: "c" * 64})
        assert первый["template_digest"] != второй["template_digest"]
        assert первый[рм.ИСТОЧНИКИ_ШАБЛОНА] == второй[рм.ИСТОЧНИКИ_ШАБЛОНА], (
            "витрины отрисованы одинаково, а сравнить их по отпечатку нечем")

    def test_отпечаток_источников_проверяется_на_вид(self):
        with pytest.raises(рм.ManifestError, match="не sha256"):
            рм.проверить(self._манифест(**{рм.ИСТОЧНИКИ_ШАБЛОНА: "не-sha256"}))

    def test_пустой_отпечаток_источников_отвергается(self):
        with pytest.raises(рм.ManifestError, match="присутствует и пуст"):
            рм.проверить(self._манифест(**{рм.ИСТОЧНИКИ_ШАБЛОНА: ""}))
