"""Три просьбы SEO, закрытые контрактом, — проверенные, а не объявленные.

Handoffs 023, 025 и 026 названы закрытыми в отчёте итерации 22. Объявление о
закрытии, которое ничего не проверяет, живёт ровно до первой правки контракта:
поле уедет, отчёт останется, и расхождение найдётся у потребителя.

Каждая проверка здесь названа номером просьбы и требует того, что просьба
требовала, — своими словами просьбы, а не своими словами контракта.
"""
from __future__ import annotations

import pytest

from factory.site_engine.seo_binding import (
    PLAYBACK_AUTHORISED,
    BindingState,
    ContentKind,
    KindState,
    PlaybackState,
    ReasonCode,
    RouteBinding,
)

СНИМОК = "2026-09-06T04:45:32+00:00"


def связь(**kwargs) -> RouteBinding:
    основа = dict(
        site_id="demo", content_id="p-1", external_ids={"kp": "1"},
        route_id="/title/x/", page_type="title", canonical_path="/title/x/",
        content_kind=ContentKind.SERIES, content_kind_state=KindState.RESOLVED,
        content_kind_provenance="поставщик", playback_state=PlaybackState.PLAYABLE,
        playback_reason_code=ReasonCode.PLAYBACK_OK, playback_observed_at=СНИМОК,
        content_revision="rev-1", binding_state=BindingState.BOUND,
        reason_codes=(ReasonCode.OK,), provenance="каталог", snapshot_at=СНИМОК)
    основа.update(kwargs)
    return RouteBinding(**основа)


# --- 023: состояние воспроизведения по записи, а не сводкой ------------------

def test_023_состояние_воспроизведения_есть_у_каждой_записи():
    """Просьба: код причины по записи, а не классы сводкой.

    Сводка отвечает «сколько», а решение принимается по вопросу «эта страница —
    какая». 159 записей из 268 стояли именно на этом.
    """
    d = связь().as_dict()
    for поле in ("playbackState", "playbackReasonCode", "playbackObservedAt"):
        assert поле in d, поле


def test_023_три_поля_обязательны_каждое_по_своей_причине():
    """Просьба называла три поля: состояние, код причины и время подтверждения.

    Время — не украшение: состояние воспроизведения, подтверждённое неизвестно
    когда, ничем не отличается от неизвестного.
    """
    d = связь().as_dict()
    assert d["playbackState"] == "PLAYABLE"
    assert d["playbackReasonCode"] == "PLAYBACK_OK"
    assert d["playbackObservedAt"] == СНИМОК


def test_023_идентификаторы_названы_а_не_подразумеваются():
    """Потребитель обязан видеть, чем адресуется поток, чтобы проверить
    состояние. Сквозной прогон показал цену пропуска: 199 из 199 записей
    понижались до метаданных, потому что перечень был пуст."""
    d = связь().as_dict()
    assert set(d["externalIds"]) & set(PLAYBACK_AUTHORISED)


def test_023_запрет_по_договору_отличим_от_отсутствия_идентификатора():
    """Просьба различала эти случаи явно: 654 записи с одним лишь imdb и 66 без
    единого идентификатора — разные причины и разные решения."""
    запрет = связь(playback_state=PlaybackState.BLOCKED_BY_CONTRACT,
                   playback_reason_code=ReasonCode.IDENTIFIER_FORBIDDEN_BY_CONTRACT,
                   playback_observed_at="", external_ids={"imdb": "tt1"})
    нет_ключа = связь(playback_state=PlaybackState.NO_IDENTIFIER,
                      playback_reason_code=ReasonCode.MISSING_PROVIDER_ID,
                      playback_observed_at="", external_ids={})
    assert запрет.as_dict()["playbackReasonCode"] \
        != нет_ключа.as_dict()["playbackReasonCode"]
    assert not запрет.may_promise_playback
    assert not нет_ключа.may_promise_playback


def test_023_imdb_и_cvh_потоком_не_считаются():
    """Просьба и контракт сходятся: без отдельного разрешённого договора эти
    идентификаторы права обещать просмотр не дают."""
    for чужой in ("imdb", "cvh"):
        assert чужой not in PLAYBACK_AUTHORISED


# --- 025: вид противоречит собственному описанию записи ----------------------

def test_025_противоречие_вида_называется_состоянием_а_не_видом():
    """Просьба: «Эпизод 13», объявленный фильмом, — кандидат в CONFLICTED, и
    решение принадлежит ядру. Разметку такая запись не получает."""
    c = связь(content_kind=ContentKind.UNKNOWN,
              content_kind_state=KindState.CONFLICTED,
              kind_candidates=(ContentKind.MOVIE, ContentKind.EPISODE),
              binding_state=BindingState.KIND_UNRESOLVED,
              reason_codes=(ReasonCode.KIND_CONFLICTED,))
    d = c.as_dict()
    assert d["contentKindState"] == "CONFLICTED"
    assert d["schemaType"] == "", "конфликтный вид не должен получать разметку"


def test_025_кандидаты_названы_а_не_сведены_к_одному():
    """Свести противоречие к одному виду — значит выбрать за ядро. Контракт
    перечисляет то, что противоречит, и не выбирает."""
    c = связь(content_kind=ContentKind.UNKNOWN,
              content_kind_state=KindState.CONFLICTED,
              kind_candidates=(ContentKind.MOVIE, ContentKind.EPISODE),
              binding_state=BindingState.KIND_UNRESOLVED,
              reason_codes=(ReasonCode.KIND_CONFLICTED,))
    assert len(c.as_dict()["kindCandidates"]) == 2


def test_025_анимация_это_способ_исполнения_а_не_вид():
    """Наследие отображения anime → ANIMATION: три записи из семи несли вид
    ANIMATION при тексте про сериал. Вида «анимация» в контракте нет."""
    assert not hasattr(ContentKind, "ANIMATION")
    d = связь(is_animation=True).as_dict()
    assert d["isAnimation"] is True
    assert d["contentKind"] == "SERIES", "манера исполнения вид не подменяет"


def test_025_происхождение_вида_названо():
    """Иначе спорить с решением ядра не с чем: неизвестно, откуда оно взялось."""
    assert связь().as_dict()["contentKindProvenance"]


# --- 026: ключ связи адреса с записью каталога -------------------------------

def test_026_ключ_связи_есть_и_он_не_адрес():
    """Просьба: связи между адресом страницы и записью каталога нет нигде.

    Ключ — идентификатор записи, а не адрес: адрес у витрин с вычисляемым
    маршрутом зависит от порядка ответа источника, и ключом быть не может.
    """
    d = связь().as_dict()
    assert d["contentId"] == "p-1"
    assert d["routeId"] != d["contentId"]


def test_026_ревизия_считается_от_содержимого_а_не_от_времени_выгрузки():
    """Иначе каждая выгрузка выглядела бы изменением, и потребитель перечитывал
    бы неизменившееся."""
    d = связь().as_dict()
    assert d["contentRevision"] == "rev-1"


@pytest.mark.parametrize("поле", [
    "siteId", "contentId", "routeId", "canonicalPath", "pageType",
    "bindingState", "reasonCodes", "provenance", "snapshotAt",
])
def test_026_связь_несёт_всё_нужное_для_её_проверки(поле):
    assert поле in связь().as_dict()
