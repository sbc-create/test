"""Путь сущности от события до черновика.

    событие → SEOFactPack → Writer → детерминированные проверки →
    Blind Judge → ворота → SEOContentDraft → (тень) предложение

Контур ничего не публикует. Последняя точка — черновик в собственном
эфемерном хранилище и, если ворота пропустили, заявка на каноническое
предложение. Дальше начинается чужая ответственность: одобрение, применение
и публикация принадлежат control-plane, и прав на них у контура нет.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from . import identity as ID
from . import store as ST
from . import structured_data as SD
from .budget import BudgetLedger
from .dedup import CorpusEntry, NearDuplicateDetector
from .draft import GateStatus, SEOContentDraft
from .factpack import SEOFactPack, from_event
from .gate import GateInputs, GateOutcome, evaluate
from .writer import DeterministicWriter, Writer, WriterRefused, build_request


@dataclass
class SiteContext:
    """Что контур знает о витрине. Приходит снаружи, не добывается обходом."""

    site_id: str
    site_url: str
    own_angle: str | None = None
    sibling_sites: tuple[str, ...] = ()
    same_catalog: bool = False
    target_environment: str = "test"


@dataclass
class PipelineResult:
    outcome: GateOutcome
    draft_id: str | None
    created: bool
    structured: SD.StructuredDataReport | None

    @property
    def status(self) -> GateStatus:
        return self.outcome.draft.quality_gate_status

    @property
    def draft(self) -> SEOContentDraft:
        return self.outcome.draft


@dataclass
class ContentPipeline:
    writer: Writer = field(default_factory=DeterministicWriter)
    detector: NearDuplicateDetector | None = None
    budget: BudgetLedger = field(default_factory=BudgetLedger)
    corpus_note_hashes: set[str] = field(default_factory=set)
    #: Счётчики прогона — попадают в отчёт как есть.
    counters: dict[str, int] = field(default_factory=lambda: {
        "events": 0, "drafts": 0, "writer_refusals": 0})

    def run_event(self, событие: Mapping[str, Any], *, site: SiteContext,
                  route: ID.Route, соед: sqlite3.Connection | None = None,
                  video_url: str | None = None,
                  video_license_ok: bool = False,
                  video_present: bool = False,
                  visible_h1: str | None = None,
                  visible_breadcrumbs: Sequence[str] = (),
                  canonical_sitemap: str | None = None,
                  internal_links: Iterable[str] = (),
                  crash_hook=None) -> PipelineResult:
        self.counters["events"] += 1
        pack = from_event(событие)
        return self.run_pack(
            pack, site=site, route=route, соед=соед, video_url=video_url,
            video_license_ok=video_license_ok, video_present=video_present,
            visible_h1=visible_h1, visible_breadcrumbs=visible_breadcrumbs,
            canonical_sitemap=canonical_sitemap,
            internal_links=internal_links, crash_hook=crash_hook)

    def run_pack(self, pack: SEOFactPack, *, site: SiteContext,
                 route: ID.Route, соед: sqlite3.Connection | None = None,
                 video_url: str | None = None, video_license_ok: bool = False,
                 video_present: bool = False, visible_h1: str | None = None,
                 visible_breadcrumbs: Sequence[str] = (),
                 canonical_sitemap: str | None = None,
                 internal_links: Iterable[str] = (),
                 crash_hook=None) -> PipelineResult:
        # 1. Личность разрешается ДО генерации. Писать текст о серии, номер
        #    которой не разрешён, нельзя — номер пришлось бы угадать.
        личность = ID.resolve(pack, route)

        # 2. Запрос. Факты уходят автору только внутри ограждённого блока.
        запрос = build_request(
            pack, display_number=личность.display_number,
            season_number=(int(pack.value("/season_number"))
                           if pack.value("/season_number") is not None else None))

        # 3. Автор. Бесплатный вызов проходит бюджет так же, как платный:
        #    учёт не должен зависеть от того, платим ли мы сегодня.
        self.budget.assert_call_allowed(
            provider=getattr(self.writer, "mode", "unknown").lower(),
            estimated_cost=0)
        try:
            содержимое = self.writer.write(запрос)
        except WriterRefused as отказ:
            self.counters["writer_refusals"] += 1
            содержимое = {"outcome": "NEEDS_FACTS",
                          "missing": [f"WRITER:{отказ.code}"]}

        # 4. Разметка — по фактам, не по тексту.
        путь_тайтла, путь_сезона = ID.parent_paths(route)
        узлы = SD.build_jsonld(
            pack, site_url=site.site_url,
            canonical_path=route.canonical or route.url,
            title_path=путь_тайтла, season_path=путь_сезона,
            display_number=личность.display_number,
            season_number=(int(pack.value("/season_number"))
                           if pack.value("/season_number") is not None else None),
            breadcrumbs=tuple((имя, путь) for имя, путь in
                              _крошки(route, visible_breadcrumbs)),
            video_url=video_url, video_license_ok=video_license_ok)
        разметка = SD.validate(
            узлы, pack=pack, canonical_html=route.canonical or route.url,
            canonical_sitemap=canonical_sitemap, internal_links=internal_links,
            visible_h1=visible_h1 or содержимое.get("h1_recommendation"),
            visible_breadcrumbs=visible_breadcrumbs,
            display_number=личность.display_number,
            season_number=(int(pack.value("/season_number"))
                           if pack.value("/season_number") is not None else None),
            video_present=video_present)

        # 5. Ворота.
        исход = evaluate(GateInputs(
            pack=pack, content=содержимое, route=route,
            model_version=self.writer.model_version,
            prompt_version=запрос.prompt_version,
            generation_parameters=запрос.generation_parameters,
            detector=self.detector, structured=разметка,
            corpus_note_hashes=tuple(self.corpus_note_hashes),
            site_own_angle=site.own_angle, sibling_sites=site.sibling_sites,
            same_catalog=site.same_catalog,
            target_environment=site.target_environment))

        for н in исход.notes.notes:
            self.corpus_note_hashes.add(н.text_sha256)

        # 6. Устойчивая запись — в собственное хранилище.
        ид, создан = (None, False)
        if соед is not None:
            ид, создан = ST.сохранить(соед, pack, исход.draft,
                                      crash_hook=crash_hook)
            if создан:
                self.counters["drafts"] += 1
        return PipelineResult(исход, ид, создан, разметка)


def _крошки(route: ID.Route,
            видимые: Sequence[str]) -> list[tuple[str, str]]:
    """Крошки для разметки строятся из тех же данных, что и видимые.

    Собрать их отдельно значило бы завести второй источник правды и получить
    расхождение, которое потом ловится проверкой.
    """
    if not видимые:
        return []
    сегменты = [с for с in (route.canonical or route.url).strip("/").split("/") if с]
    пути, накопитель = [], ""
    for с in сегменты:
        накопитель += f"/{с}"
        пути.append(накопитель + "/")
    while len(пути) < len(видимые):
        пути.insert(0, "/")
    return list(zip(видимые, пути[-len(видимые):]))
