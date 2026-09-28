"""Идентичность произведения: нормализация, вид, сопоставление, рейтинги.

Главная проверка — adversarial-набор. Он построен ПРОТИВ реализации: почти
каждый случай обязан дать отказ, неоднозначность или противоречие. Один
ошибочный AUTO_ACCEPT здесь означает, что чужой рейтинг привяжется к чужому
произведению, а такую ошибку в выдаче не видно.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.site_engine import catalog_identity, rating_discovery
from factory.site_engine import identity_resolver as res
from factory.site_engine import title_normalize as norm
from factory.site_engine.content_identity import (
    SCHEMA_VERSION,
    ContentIdentity,
    IdentityStatus,
    payload_hash,
    stamp,
)
from factory.site_engine.content_kind import (
    CONTRACT,
    ContentKind,
    ContentKindError,
    contract_for,
    emits_schema,
    is_animation_marker,
)
from factory.site_engine.content_kind import (
    resolve as resolve_kind,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "reports/CORE-CONTENT-IDENTITY-RESOLUTION-19/ADVERSARIAL-FIXTURES.json"


@pytest.fixture(scope="module")
def cfg():
    return res.load_config(ROOT)


# --------------------------------------------------------------------------
# Нормализация
# --------------------------------------------------------------------------
class TestНормализация:
    def test_отображаемое_название_не_меняется(self):
        """Нормализация теряет сведения и потому наружу не выходит."""
        исходное = "Ёлки (2010) BDRip"
        assert norm.варианты(исходное)["source"] == исходное

    @pytest.mark.parametrize(
        "а,б",
        [
            ("Рокки IV", "Рокки 4"),
            ("Ёлки", "Елки"),
            ("Тайна   леса", "Тайна леса"),
            ("Тайна леса!", "Тайна леса"),
            ("ТАЙНА ЛЕСА", "тайна леса"),
            ("Дюна (2021)", "Дюна"),
            ("Хищник BDRip дубляж", "Хищник"),
        ],
    )
    def test_один_ключ_поиска(self, а, б):
        assert norm.ключ_поиска(а) == norm.ключ_поиска(б)

    def test_ё_сводится_только_в_ключе(self):
        assert norm.ключ_поиска("Ёлки") == norm.ключ_поиска("Елки")
        assert norm.базовая("Ёлки") != norm.базовая("Елки")

    def test_транслитерация_сводит_кириллицу_и_латиницу(self):
        assert norm.ключ_транслита("Атака титанов") == norm.ключ_поиска("ataka titanov")

    def test_год_в_скобках_извлекается(self):
        без, год = norm.извлечь_год("Дюна (2021)")
        assert год == 2021 and "2021" not in без

    def test_отсутствующий_год_остаётся_отсутствующим(self):
        assert norm.извлечь_год("Дюна")[1] is None

    @pytest.mark.parametrize(
        "текст,ожидание",
        [
            ("Атака титанов сезон 3", {"season": 3}),
            ("Gintama часть 2", {"part": 2}),
            ("Аниме cour 2", {"cour": 2}),
            ("Рокки IV", {}),
        ],
    )
    def test_сезоны_части_и_cour(self, текст, ожидание):
        assert norm.извлечь_части(текст)[1] == ожидание

    def test_хвостовой_номер_даёт_оба_ключа(self):
        """Голое число в конце неоднозначно: «Рокки 4» и «Атака титанов 3»."""
        к = norm.ключи(["Атака титанов 3"])
        assert "атака титанов" in к and "атака титанов 3" in к

    def test_пустое_название_не_даёт_ключей(self):
        assert norm.ключи(["", None]) == set()


# --------------------------------------------------------------------------
# Вид произведения
# --------------------------------------------------------------------------
class TestВид:
    def test_unknown_не_выпускает_разметку(self):
        assert not emits_schema(ContentKind.UNKNOWN)
        assert contract_for(ContentKind.UNKNOWN).schema_type == ""

    def test_каждый_вид_кроме_unknown_имеет_разметку(self):
        for вид, контракт in CONTRACT.items():
            if вид is ContentKind.UNKNOWN:
                continue
            assert контракт.schema_type, f"{вид} без Schema.org"
            assert контракт.og_type, f"{вид} без og:type"

    def test_фильм_не_имеет_сезонов_и_серий(self):
        к = contract_for(ContentKind.MOVIE)
        assert not к.allows_seasons and not к.allows_episodes

    def test_сериал_не_размечается_как_фильм(self):
        assert contract_for(ContentKind.SERIES).schema_type == "TVSeries"
        assert contract_for(ContentKind.MOVIE).schema_type == "Movie"

    @pytest.mark.parametrize("вид", [ContentKind.OVA, ContentKind.ONA, ContentKind.SPECIAL])
    def test_ova_ona_special_не_становятся_фильмом(self, вид):
        assert contract_for(вид).schema_type != "Movie"

    def test_анимация_не_является_видом(self):
        """Аниме бывает и фильмом, и сериалом: вид из способа не следует."""
        assert resolve_kind("anime") is ContentKind.UNKNOWN
        assert resolve_kind("мультфильм") is ContentKind.UNKNOWN
        assert is_animation_marker("anime") and is_animation_marker("мультфильм")

    def test_неизвестное_написание_даёт_unknown(self):
        assert resolve_kind("чепуха") is ContentKind.UNKNOWN
        assert resolve_kind(None) is ContentKind.UNKNOWN

    def test_tv_series_принимается_но_наружу_идёт_series(self):
        assert resolve_kind("TV_SERIES") is ContentKind.SERIES
        assert ContentKind.SERIES.value == "SERIES"

    def test_чужой_вид_это_ошибка_а_не_молчаливый_unknown(self):
        with pytest.raises(ContentKindError):
            contract_for("PODCAST")

    def test_сезон_и_серия_требуют_родителя(self):
        assert contract_for(ContentKind.SEASON).requires_parent
        assert contract_for(ContentKind.EPISODE).requires_parent


class TestВидИзКаталога:
    def test_отсутствие_сезонов_не_доказывает_фильм(self):
        """type=movie — это утверждение поставщика, а не вывод из пустоты."""
        d = catalog_identity.decide(provider_type=None, tags=[])
        assert d.kind is ContentKind.UNKNOWN

    def test_тег_уточняет_тип_внутри_группы(self):
        d = catalog_identity.decide(provider_type="tv", tags=["ona"])
        assert d.kind is ContentKind.ONA and not d.conflicted

    def test_тег_из_другой_группы_даёт_конфликт_а_не_выбор(self):
        d = catalog_identity.decide(provider_type="movie", tags=["ona"])
        assert d.kind is ContentKind.UNKNOWN
        assert d.conflicts == ("PROVIDER_TYPE_VS_KIND_TAG",)

    def test_два_вида_в_тегах_не_разрешаются_автоматически(self):
        d = catalog_identity.decide(provider_type="movie", tags=["ova", "special"])
        assert d.kind is ContentKind.UNKNOWN
        assert d.conflicts == ("MULTIPLE_KIND_TAGS",)

    def test_возрастные_пометки_видом_не_являются(self):
        d = catalog_identity.decide(provider_type="movie", tags=["13+", "18+", "NR"])
        assert d.kind is ContentKind.MOVIE and not d.conflicted


# --------------------------------------------------------------------------
# ContentIdentity
# --------------------------------------------------------------------------
class TestИдентичность:
    def test_нулевая_длительность_запрещена(self):
        with pytest.raises(ValueError, match="duration=0"):
            ContentIdentity(internal_entity_id="e", duration=0)

    def test_отсутствующая_длительность_остаётся_none(self):
        assert ContentIdentity(internal_entity_id="e").duration is None

    def test_отпечаток_детерминирован(self):
        a = ContentIdentity(internal_entity_id="e", displayed_title="Х", release_year=2020)
        b = ContentIdentity(internal_entity_id="e", displayed_title="Х", release_year=2020)
        assert payload_hash(a) == payload_hash(b)

    def test_отпечаток_не_зависит_от_времени_разбора(self):
        import datetime as dt

        a = ContentIdentity(internal_entity_id="e", displayed_title="Х")
        stamp(a, resolver_version="v1", now=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc))
        первый = a.payload_hash
        stamp(a, resolver_version="v2", now=dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))
        assert a.payload_hash == первый

    def test_версия_схемы_объявлена(self):
        assert ContentIdentity(internal_entity_id="e").schema_version == SCHEMA_VERSION

    def test_повторный_разбор_не_плодит_сущности(self):
        """Идемпотентность: тот же вход — тот же internalEntityId и отпечаток."""
        строить = lambda: ContentIdentity(  # noqa: E731
            internal_entity_id="lords-01:abc", displayed_title="Х", release_year=2020
        )
        a, b = строить(), строить()
        assert a.internal_entity_id == b.internal_entity_id
        assert payload_hash(a) == payload_hash(b)


# --------------------------------------------------------------------------
# Резолвер
# --------------------------------------------------------------------------
class TestРезолвер:
    def test_пороги_читаются_из_настройки(self, cfg):
        assert cfg["thresholds"]["auto_accept"] == 0.98
        assert cfg["thresholds"]["review"] == 0.85
        assert cfg["thresholds"]["ambiguity_margin"] == 0.03

    def test_настройка_версионирована(self, cfg):
        assert cfg["policy_version"].startswith("identity-resolution/")
        assert cfg["status"] == "proposal"

    def test_нет_кандидатов_даёт_unmatched(self, cfg):
        r = res.resolve(res.Candidate("s"), [], cfg)
        assert r.status is IdentityStatus.UNMATCHED and r.considered == 0

    def test_точный_идентификатор_разрешает(self, cfg):
        s = res.Candidate(
            "s",
            external_ids={"kp": "1"},
            original_title="A",
            release_year=2000,
            content_kind=ContentKind.MOVIE,
        )
        c = res.Candidate(
            "c",
            external_ids={"kp": "1"},
            original_title="A",
            release_year=2000,
            content_kind=ContentKind.MOVIE,
        )
        r = res.resolve(s, [c], cfg)
        assert r.status is IdentityStatus.RESOLVED_EXACT_ID

    def test_противоречие_закрывает_а_не_понижает(self, cfg):
        """Иначе фильм привяжется к сериалу, добрав порог другими признаками."""
        s = res.Candidate(
            "s",
            original_title="A",
            release_year=2000,
            content_kind=ContentKind.MOVIE,
            country="USA",
            studio="X",
        )
        c = res.Candidate(
            "c",
            original_title="A",
            release_year=2000,
            content_kind=ContentKind.SERIES,
            country="USA",
            studio="X",
        )
        r = res.resolve(s, [c], cfg)
        assert r.status is IdentityStatus.CONFLICTED
        assert "KIND_MOVIE_VS_SERIES" in r.conflicts

    def test_оценка_объяснима(self, cfg):
        s = res.Candidate(
            "s", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
        )
        c = res.Candidate(
            "c", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
        )
        разбор = res.score(s, c, cfg)
        имена = {f.feature for f in разбор.features}
        assert {"external_id", "original_title", "year", "content_kind"} <= имена
        assert all(f.detail for f in разбор.features)

    def test_отсутствующий_признак_не_топит_оценку(self, cfg):
        """Запись без студии не хуже сопоставлена — о ней просто меньше известно."""
        s = res.Candidate(
            "s", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
        )
        c = res.Candidate(
            "c", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
        )
        assert res.score(s, c, cfg).confidence == pytest.approx(1.0)

    def test_близкие_кандидаты_дают_ambiguous(self, cfg):
        s = res.Candidate(
            "s", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
        )
        одинаковые = [
            res.Candidate(
                "c1", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
            ),
            res.Candidate(
                "c2", original_title="A", release_year=2000, content_kind=ContentKind.MOVIE
            ),
        ]
        r = res.resolve(s, одинаковые, cfg)
        assert r.status is IdentityStatus.AMBIGUOUS

    def test_одного_русского_названия_недостаточно(self, cfg):
        """Совпало только название — до порога не хватает."""
        s = res.Candidate("s", displayed_title="Хищник", original_title="Хищник")
        c = res.Candidate(
            "c",
            displayed_title="Хищник",
            original_title="Хищник",
            release_year=2018,
            content_kind=ContentKind.MOVIE,
            country="USA",
        )
        r = res.resolve(s, [c], cfg)
        assert r.status is not IdentityStatus.RESOLVED_HIGH_CONFIDENCE

    def test_порог_не_понижается_молча(self, cfg):
        """Значения зафиксированы: их изменение обязано ломать этот тест."""
        assert cfg["thresholds"]["auto_accept"] >= 0.98


# --------------------------------------------------------------------------
# Adversarial
# --------------------------------------------------------------------------
def _кандидат(d: dict) -> res.Candidate:
    поля = dict(d)
    вид = поля.pop("content_kind", None)
    альт = поля.pop("alternative_titles", ()) or ()
    твор = поля.pop("creators", ()) or ()
    return res.Candidate(
        entity_id=поля.pop("entity_id"),
        content_kind=ContentKind(вид) if вид else None,
        alternative_titles=tuple(альт),
        creators=tuple(твор),
        **поля,
    )


@pytest.fixture(scope="module")
def набор():
    assert FIXTURES.exists(), f"нет adversarial-набора: {FIXTURES}"
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


class TestAdversarial:
    def test_набор_не_меньше_пятидесяти(self, набор):
        assert набор["count"] >= 50

    def test_ни_одного_ложного_auto_accept(self, набор, cfg):
        """Блокирующая проверка задачи."""
        ошибки = []
        for случай in набор["cases"]:
            r = res.resolve(
                _кандидат(случай["subject"]), [_кандидат(c) for c in случай["candidates"]], cfg
            )
            авто = r.status in (
                IdentityStatus.RESOLVED_EXACT_ID,
                IdentityStatus.RESOLVED_HIGH_CONFIDENCE,
            )
            if случай["expect"]["mustNotAutoAccept"] and авто:
                ошибки.append(
                    f"{случай['id']}: {r.status.value} "
                    f"уверенность {r.confidence:.3f} — {случай['note']}"
                )
        assert not ошибки, "ложные AUTO_ACCEPT:\n" + "\n".join(ошибки)

    def test_ожидаемые_противоречия_названы(self, набор, cfg):
        ошибки = []
        for случай in набор["cases"]:
            ждём = случай["expect"]["conflictsInclude"]
            if not ждём:
                continue
            r = res.resolve(
                _кандидат(случай["subject"]), [_кандидат(c) for c in случай["candidates"]], cfg
            )
            пропущены = [c for c in ждём if c not in r.conflicts]
            if пропущены:
                ошибки.append(f"{случай['id']}: нет {пропущены}, есть {r.conflicts}")
        assert not ошибки, "\n".join(ошибки)


# --------------------------------------------------------------------------
# Рейтинги
# --------------------------------------------------------------------------
class TestРейтинги:
    def _identity(self, **kw):
        d = {
            "internal_entity_id": "e",
            "content_kind": ContentKind.MOVIE,
            "release_year": 2020,
            "identity_status": IdentityStatus.RESOLVED_EXACT_ID,
        }
        d.update(kw)
        return ContentIdentity(**d)

    def test_каждая_запись_получает_состояние(self):
        политика = rating_discovery.SourcePolicy()
        for i in (
            self._identity(),
            self._identity(identity_status=IdentityStatus.UNMATCHED),
            self._identity(release_year=None),
            self._identity(content_kind=ContentKind.EPISODE),
        ):
            assert rating_discovery.discover(i, policy=политика).rating_state

    def test_отсутствие_числа_не_становится_нулём(self):
        r = rating_discovery.discover(self._identity(), policy=rating_discovery.SourcePolicy())
        assert r.numeric_rating_present is False
        assert r.blocker != "0"

    def test_неразрешённая_запись_не_получает_рейтинга(self):
        r = rating_discovery.discover(
            self._identity(identity_status=IdentityStatus.AMBIGUOUS),
            policy=rating_discovery.SourcePolicy(),
        )
        assert r.rating_state is rating_discovery.RatingState.ENTITY_NOT_MATCHED

    def test_невышедшее_не_является_пробелом(self):
        r = rating_discovery.discover(
            self._identity(release_year=2999), policy=rating_discovery.SourcePolicy()
        )
        assert r.rating_state is rating_discovery.RatingState.PRE_RELEASE

    def test_отсутствие_лицензии_отличается_от_отсутствия_оценок(self):
        без = rating_discovery.SourcePolicy()
        с_кандидатами = rating_discovery.SourcePolicy(known_unlicensed=("tmdb",))
        assert (
            rating_discovery.discover(self._identity(), policy=без).rating_state
            is rating_discovery.RatingState.SOURCE_UNAVAILABLE
        )
        assert (
            rating_discovery.discover(self._identity(), policy=с_кандидатами).rating_state
            is rating_discovery.RatingState.NOT_CHECKED_LICENSE_BLOCKED
        )

    def test_покрытие_считается_от_названного_знаменателя(self):
        политика = rating_discovery.SourcePolicy()
        итог = rating_discovery.coverage(
            [
                rating_discovery.discover(
                    self._identity(), policy=политика, feed_ratings={"imdb": 7.0}
                ),
                rating_discovery.discover(self._identity(), policy=политика),
            ]
        )
        assert итог["ratingStateCoverage"] == 1.0
        assert итог["eligibleReleased"] == 2
        assert итог["numericSourceCoverageEligibleReleased"] == 0.5


# --------------------------------------------------------------------------
# Миграция
# --------------------------------------------------------------------------
def _миграция():
    import importlib.util

    путь = ROOT / "migrations" / "0001_content_identity.py"
    spec = importlib.util.spec_from_file_location("m0001", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


class TestМиграция:
    def test_обратима(self, tmp_path):
        """Необратимая миграция — решение, которое нельзя отменить."""
        import sqlite3

        m = _миграция()
        conn = sqlite3.connect(tmp_path / "t.db")
        assert not m.applied(conn)
        m.upgrade(conn)
        assert m.applied(conn)
        m.downgrade(conn)
        assert not m.applied(conn)
        таблицы = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "content_identity" not in таблицы

    def test_повторный_upgrade_безопасен(self, tmp_path):
        import sqlite3

        m = _миграция()
        conn = sqlite3.connect(tmp_path / "t.db")
        m.upgrade(conn)
        m.upgrade(conn)
        assert m.applied(conn)

    def test_база_не_принимает_нулевую_длительность(self, tmp_path):
        """Запрет живёт и в коде, и в схеме: обойти его нечем."""
        import sqlite3

        m = _миграция()
        conn = sqlite3.connect(tmp_path / "t.db")
        m.upgrade(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO content_identity(internal_entity_id, schema_version,"
                " identity_status, mapping_method, duration) VALUES (?,?,?,?,0)",
                ("z", "v", "UNMATCHED", "NONE"),
            )

    def test_повторный_разбор_не_плодит_строк(self, tmp_path):
        import sqlite3

        m = _миграция()
        conn = sqlite3.connect(tmp_path / "t.db")
        m.upgrade(conn)
        i = ContentIdentity(
            internal_entity_id="lords-01:a", content_kind=ContentKind.ONA, displayed_title="Х"
        )
        stamp(i, resolver_version="v1")
        m.upsert_identity(conn, i)
        m.upsert_identity(conn, i)
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM content_identity").fetchone()[0] == 1


# --------------------------------------------------------------------------
# Согласованность между витринами и потребителями
# --------------------------------------------------------------------------
class TestСогласованность:
    def test_один_актив_даёт_один_вид_на_всех_витринах(self):
        """Кросс-доменная согласованность: вид считается от данных, не от домена."""
        запись = {"type": "tv", "tags": ["ona", "anime"]}
        решения = [
            catalog_identity.decide(provider_type=запись["type"], tags=запись["tags"])
            for _ in ("lords-01", "lords-02", "lords-03")
        ]
        assert len({d.kind for d in решения}) == 1

    def test_проводные_имена_совпадают_с_контрактом_seo(self):
        """Расхождение имён — то же самое расхождение, только внутри контракта."""
        обязательные = {"MOVIE", "SERIES", "SEASON", "EPISODE", "OVA", "ONA", "SPECIAL", "UNKNOWN"}
        assert обязательные <= {k.value for k in ContentKind}

    def test_минимальный_перечень_задачи_покрыт(self):
        """MOVIE, TV_SERIES, SEASON, EPISODE, OVA, ONA, SPECIAL, SHORT, MUSIC."""
        from factory.site_engine.content_kind import resolve as r

        for имя in (
            "MOVIE",
            "TV_SERIES",
            "SEASON",
            "EPISODE",
            "OVA",
            "ONA",
            "SPECIAL",
            "SHORT",
            "MUSIC",
        ):
            assert r(имя) is not ContentKind.UNKNOWN, имя

    def test_unknown_не_создаёт_ложный_schema_type(self):
        i = ContentIdentity(internal_entity_id="e", content_kind=ContentKind.UNKNOWN)
        assert not emits_schema(i.content_kind)

    @pytest.mark.parametrize(
        "вид,ожидание",
        [
            (ContentKind.MOVIE, "Movie"),
            (ContentKind.SERIES, "TVSeries"),
            (ContentKind.SEASON, "TVSeason"),
            (ContentKind.EPISODE, "TVEpisode"),
            (ContentKind.SPECIAL, "TVSpecial"),
            (ContentKind.ONA, "TVSeries"),
            (ContentKind.OVA, "TVSeries"),
            (ContentKind.MUSIC, "MusicVideoObject"),
            (ContentKind.UNKNOWN, ""),
        ],
    )
    def test_отображение_в_schema_org_зафиксировано(self, вид, ожидание):
        assert contract_for(вид).schema_type == ожидание

    def test_секретов_в_коде_нет(self):
        """Простой скан по файлам модуля: ключей и токенов быть не должно."""
        import re

        подозрительное = re.compile(
            r"(api[_-]?key|secret|token|password|Bearer\s+[A-Za-z0-9]{12,})\s*[=:]\s*"
            r"[\"'][A-Za-z0-9_\-]{12,}[\"']",
            re.IGNORECASE,
        )
        файлы = [
            ROOT / "factory/site_engine/content_kind.py",
            ROOT / "factory/site_engine/content_identity.py",
            ROOT / "factory/site_engine/identity_resolver.py",
            ROOT / "factory/site_engine/catalog_identity.py",
            ROOT / "factory/site_engine/rating_discovery.py",
            ROOT / "factory/site_engine/title_normalize.py",
            ROOT / "config/identity-resolution.yaml",
        ]
        for файл in файлы:
            assert not подозрительное.search(файл.read_text(encoding="utf-8")), файл
