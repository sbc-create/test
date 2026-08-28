"""Предпросмотр SEO на контролируемой выборке страниц.

Массовая генерация не начинается, пока выборка не проверена. Тридцать страниц
подбираются так, чтобы попали и удобные случаи, и неудобные: записи без
описания, записи с одной оценкой, дубли и неполные данные. Именно на них
ломаются тексты, а не на тех, где всё заполнено.
"""
from __future__ import annotations

from dataclasses import dataclass

from factory.seo.validate import check_corpus, check_page, failures, warnings

BUCKETS = (
    ("movies_full", "фильмы с полными метаданными"),
    ("series_seasons", "сериалы с сезонами"),
    ("anime", "аниме"),
    ("no_synopsis", "без синопсиса"),
    ("single_rating", "только с одной оценкой"),
    ("incomplete", "дубли и неполные записи"),
)
PER_BUCKET = 5


@dataclass
class PreviewResult:
    pages: list
    findings: list
    corpus_findings: list

    @property
    def failed(self):
        return failures(self.findings) + failures(self.corpus_findings)

    @property
    def warned(self):
        return warnings(self.findings) + warnings(self.corpus_findings)

    def summary(self) -> dict:
        return {
            "pages": len(self.pages),
            "checks": len(self.findings) + len(self.corpus_findings),
            "failures": len(self.failed),
            "warnings": len(self.warned),
        }


def pick_sample(titles, *, per_bucket: int = PER_BUCKET) -> dict:
    """Разбор каталога по корзинам. Берутся реальные записи, а не выдуманные.

    Запись обычно подходит сразу нескольким корзинам, и первая версия
    раскладывала её в первую подошедшую. Записей без описания в каталоге
    большинство, поэтому они забирали всё, а корзины «фильмы с полными
    метаданными» и «сериалы с сезонами» оставались пустыми — то есть выборка
    не проверяла как раз те случаи, ради которых составлялась.

    Теперь запись уходит в ту из подходящих корзин, которая заполнена меньше
    всех: так наполняются все шесть, пока в каталоге есть подходящие записи.
    """
    buckets = {key: [] for key, _ in BUCKETS}
    seen_names: dict = {}

    for title in titles:
        description = (getattr(title, "summary", "") or getattr(title, "description", "") or "").strip()
        kp = getattr(title, "kinopoisk_rating", None)
        imdb = getattr(title, "imdb_rating", None)
        rated = [r for r in (kp, imdb) if isinstance(r, int | float) and r > 0]
        name = (title.name or "").strip().lower()

        fits = []
        if name in seen_names:
            fits.append("incomplete")
        seen_names.setdefault(name, title)
        if not description:
            fits.append("no_synopsis")
        if len(rated) == 1:
            fits.append("single_rating")
        if title.content_type == "anime":
            fits.append("anime")
        if getattr(title, "episodic", False):
            fits.append("series_seasons")
        if description and len(rated) == 2 and not getattr(title, "episodic", False):
            fits.append("movies_full")

        open_buckets = [k for k in fits if len(buckets[k]) < per_bucket]
        if not open_buckets:
            continue
        target = min(open_buckets, key=lambda k: len(buckets[k]))
        buckets[target].append(title)

    # Корзины, которые каталог не смог наполнить, честно остаются короче:
    # подставлять туда неподходящие записи значит проверять не то.
    return buckets


def run_preview(pages) -> PreviewResult:
    findings = []
    for page in pages:
        findings.extend(check_page(page))
    return PreviewResult(list(pages), findings, check_corpus(pages))
