"""Перечень идентификаторов, которыми разрешено адресовать плеер.

Проверяется не «работает ли функция», а три свойства, потеря которых уже
приводила к дефекту:

* перечень один. Каталог и разметка обязаны отвечать одинаково — раньше они
  отвечали по-разному, каталог построил 645 дескрипторов, плеер их отверг, и
  дефект выглядел как исправление;
* включить идентификатор вне контракта нельзя ни файлом, ни переменной
  окружения без записи авторизации;
* отсутствие разрешённого идентификатора не приводит к подстановке другого.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from factory.site_engine import playback_policy as политика

ROOT = Path(__file__).resolve().parents[2]

КОНТРАКТ = textwrap.dedent("""
    schema_version: 1
    contract_version: "TEST_PACK_v1"
    attributes:
      - name: data-aggregator
        allowed: [kp, mali, mdl]
""")


def стенд(tmp_path: Path, идентификаторы: dict, *, версия: str = "TEST_PACK_v1") -> Path:
    (tmp_path / "knowledge" / "cdnvideohub").mkdir(parents=True, exist_ok=True)
    (tmp_path / "knowledge" / "cdnvideohub" / "PLAYER_CONTRACT.yaml").write_text(
        КОНТРАКТ, encoding="utf-8"
    )
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "playback-identifiers.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "policy_version": "9.9.9",
                "providers": {
                    "cdnvideohub": {
                        "contract_ref": "knowledge/cdnvideohub/PLAYER_CONTRACT.yaml",
                        "contract_version": версия,
                        "baseline_attribute": "data-aggregator",
                        "identifiers": идентификаторы,
                    }
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return tmp_path


class TestДействующийПеречень:
    def test_боевая_настройка_даёт_ровно_основу_контракта(self):
        """Ни один идентификатор сверх контракта сейчас не включён."""
        решение = политика.resolve(root=ROOT)
        assert решение.allowed == ("kp", "mali", "mdl")
        assert решение.allowed == решение.baseline
        assert решение.beyond_baseline == ()

    @pytest.mark.parametrize("код", ["imdb", "cvh"])
    def test_imdb_и_cvh_выключены(self, код):
        решение = политика.resolve(root=ROOT)
        assert not решение.permits(код)
        assert решение.reason_for(код) == "IDENTIFIER_FORBIDDEN_BY_CONTRACT"

    def test_основа_читается_из_контракта_а_не_из_кода(self, tmp_path):
        """Перечень в коде отстал бы от документа при первой же его правке."""
        корень = стенд(tmp_path, {})
        (корень / "knowledge/cdnvideohub/PLAYER_CONTRACT.yaml").write_text(
            КОНТРАКТ.replace("[kp, mali, mdl]", "[kp, zz]"), encoding="utf-8"
        )
        assert политика.resolve(root=корень).allowed == ("kp", "zz")


class TestВоротаСоответствия:
    def test_включение_вне_основы_без_авторизации_отклонено(self, tmp_path):
        корень = стенд(tmp_path, {"imdb": {"enabled": True}})
        with pytest.raises(политика.PlaybackPolicyError, match="authorization"):
            политика.resolve(root=корень)

    def test_переменная_окружения_не_обходит_ворота(self, tmp_path):
        """Флаг включает, но не разрешает. Иначе ворота обходились бы деплоем."""
        корень = стенд(
            tmp_path,
            {"imdb": {"enabled": False, "flag": "F_IMDB", "authorization": {"status": "absent"}}},
        )
        with pytest.raises(политика.PlaybackPolicyError):
            политика.resolve(root=корень, env={"F_IMDB": "1"})

    def test_отказанная_авторизация_не_считается_разрешением(self, tmp_path):
        корень = стенд(
            tmp_path, {"imdb": {"enabled": True, "authorization": {"status": "requested"}}}
        )
        with pytest.raises(политика.PlaybackPolicyError):
            политика.resolve(root=корень)

    def test_с_авторизацией_идентификатор_включается(self, tmp_path):
        корень = стенд(
            tmp_path,
            {
                "imdb": {
                    "enabled": True,
                    "authorization": {"status": "granted", "granted_by": "владелец"},
                }
            },
        )
        решение = политика.resolve(root=корень)
        assert решение.permits("imdb")
        assert решение.beyond_baseline == ("imdb",)

    def test_устаревшая_версия_контракта_отклонена(self, tmp_path):
        """Разрешение, выданное по прежней редакции документа, недействительно."""
        корень = стенд(tmp_path, {}, версия="TEST_PACK_v0")
        with pytest.raises(политика.PlaybackPolicyError, match="устаревш"):
            политика.resolve(root=корень)

    def test_контракт_без_нужного_атрибута_это_отказ_а_не_пустой_перечень(self, tmp_path):
        корень = стенд(tmp_path, {})
        (корень / "knowledge/cdnvideohub/PLAYER_CONTRACT.yaml").write_text(
            "contract_version: TEST_PACK_v1\nattributes: []\n", encoding="utf-8"
        )
        with pytest.raises(политика.PlaybackPolicyError):
            политика.resolve(root=корень)


class TestСужение:
    def test_выключение_убирает_идентификатор_из_основы(self, tmp_path):
        корень = стенд(tmp_path, {"mdl": {"enabled": False}})
        решение = политика.resolve(root=корень)
        assert решение.allowed == ("kp", "mali")
        assert решение.reason_for("mdl") == "IDENTIFIER_DISABLED_BY_POLICY"

    def test_неупомянутый_в_настройке_остаётся_разрешённым(self, tmp_path):
        """Сужение обязано быть явным: забывчивость не должна выключать плеер."""
        assert политика.resolve(root=стенд(tmp_path, {})).allowed == ("kp", "mali", "mdl")

    def test_область_применения_сужает_по_типу_содержимого(self, tmp_path):
        корень = стенд(
            tmp_path,
            {
                "cvh": {
                    "enabled": True,
                    "authorization": {"status": "granted"},
                    "scope": {"content_types": ["movie"]},
                }
            },
        )
        assert политика.resolve(root=корень, content_type="movie").permits("cvh")
        сериал = политика.resolve(root=корень, content_type="series")
        assert not сериал.permits("cvh")
        assert сериал.reason_for("cvh") == "IDENTIFIER_OUT_OF_SCOPE"

    def test_пустая_область_это_отсутствие_ограничения(self, tmp_path):
        """Пустой список — ненастроенное ограничение, а не запрет на всё."""
        корень = стенд(tmp_path, {"kp": {"enabled": True, "scope": {"content_types": []}}})
        assert политика.resolve(root=корень, content_type="series").permits("kp")

    def test_порядок_приоритета_из_контракта_сохраняется(self, tmp_path):
        корень = стенд(tmp_path, {"zzz": {"enabled": True, "authorization": {"status": "granted"}}})
        решение = политика.resolve(root=корень)
        assert решение.allowed[:3] == ("kp", "mali", "mdl")
        assert решение.allowed[-1] == "zzz"


class TestОтсутствиеНастройки:
    def test_без_файла_действует_основа_контракта(self, tmp_path):
        """Пропавшая настройка не вправе расширить перечень — только оставить основу."""
        (tmp_path / "knowledge" / "cdnvideohub").mkdir(parents=True)
        (tmp_path / "knowledge" / "cdnvideohub" / "PLAYER_CONTRACT.yaml").write_text(
            КОНТРАКТ, encoding="utf-8"
        )
        решение = политика.resolve(root=tmp_path)
        assert решение.allowed == ("kp", "mali", "mdl")
        assert решение.policy_version == "baseline"


class TestОдинПеречеьНаВсех:
    def test_каталог_не_строит_дескриптор_запрещённым_идентификатором(self):
        """Ровно тот дефект, ради которого модуль и появился.

        Договор собирается штатным загрузчиком: пересобранный в тесте отвечал бы
        на вопрос про тест, а не про боевую сборку каталога.
        """
        from factory.lords import content_live

        запись = content_live.normalize_title(
            {
                "id": "e1",
                "name": "Тайтл",
                "type": "movie",
                "year": 2026,
                "external_ids": {"imdb": "43670638"},
            },
            content_live.load_live_contract(),
        )
        assert запись is not None
        assert запись.get("playback") is None

    def test_разметка_отвергает_запрещённый_идентификатор(self):
        from factory.lords import player

        with pytest.raises(player.PlayerContractError):
            player.player_attributes(
                publisher_id="1", aggregator="imdb", title_id="42", ident="i", season=1, episode=1
            )

    def test_классификатор_берёт_перечень_оттуда_же(self):
        from factory.site_engine.api import reasons

        разрешены, запрещены = reasons.действующий_перечень()
        assert разрешены == политика.resolve(root=ROOT).allowed
        assert "imdb" in запрещены


class TestКэш:
    def test_правка_настройки_подхватывается_без_перезапуска(self, tmp_path):
        """Кэш по времени изменения, а не навсегда: иначе откат требовал бы рестарта."""
        корень = стенд(tmp_path, {})
        assert политика.resolve_cached(root=корень).allowed == ("kp", "mali", "mdl")
        import os

        путь = корень / "config" / "playback-identifiers.yaml"
        стенд(tmp_path, {"mdl": {"enabled": False}})
        os.utime(путь, (0, 0))
        assert политика.resolve_cached(root=корень).allowed == ("kp", "mali")


class TestСверкаНаЗаписи:
    """Откат обязан доходить до каталога без полного обхода.

    Каталог обновляется приращением: запись, не изменившаяся у поставщика,
    переносится из прежнего кэша как есть. Без сверки на записи запрет,
    возвращённый сегодня, дошёл бы до витрины через шесть часов — а до тех пор
    покрытие показывало бы 645 карточек исправными. Так и было 2026-09-05.
    """

    def test_запись_каталога_снимает_запрещённый_дескриптор(self, tmp_path):
        from factory.lords import content_live

        путь = tmp_path / "catalog.json"
        content_live.write_cache(
            путь,
            [
                {
                    "external_id": "a",
                    "name": "разрешённый",
                    "playback": {"aggregator": "kp", "title_id": "1"},
                },
                {
                    "external_id": "b",
                    "name": "запрещённый",
                    "playback": {"aggregator": "imdb", "title_id": "2"},
                },
            ],
            now_ms=0,
            source="test",
        )
        import json

        данные = json.loads(путь.read_text(encoding="utf-8"))
        записи = {i["external_id"]: i for i in данные["items"]}
        assert записи["a"]["playback"]["aggregator"] == "kp"
        assert записи["b"]["playback"] is None
        assert записи["b"]["playback_blocked_reason"] == "IDENTIFIER_FORBIDDEN_BY_CONTRACT"
        assert данные["playback_policy_stripped"] == {"imdb": 1}

    def test_карточка_не_исчезает_а_остаётся_с_заглушкой(self, tmp_path):
        """Удалить запись значило бы убрать страницу из каталога и из выдачи."""
        from factory.lords import content_live

        путь = tmp_path / "catalog.json"
        content_live.write_cache(
            путь,
            [
                {
                    "external_id": "b",
                    "name": "запрещённый",
                    "playback": {"aggregator": "imdb", "title_id": "2"},
                }
            ],
            now_ms=0,
            source="test",
        )
        import json

        данные = json.loads(путь.read_text(encoding="utf-8"))
        assert len(данные["items"]) == 1
        assert данные["items"][0]["name"] == "запрещённый"
