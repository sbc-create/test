"""Read-only source-cache adapter; no queue, registry, or persistent state."""
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
from uuid import UUID

if __package__:
    from .episode_feed_view import select_events, render_section, _url, _time, _positive
else:
    from episode_feed_view import select_events, render_section, _url, _time, _positive

MAX_FEED_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 20000


def provider_id(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def load_rows(view, runtime, site_id, catalog, *, eligible=None,
              detail_getter=None, limit=12, now=None):
    """Use source events, site catalog identity, and CURRENT runtime details.

    The cache is re-read per render, so arrival needs no catalog reload. Missing,
    oversized, malformed caches produce no section. snapshot.titles is metadata,
    never an identity/availability/catalog authority. Only event-matched slugs
    invoke the runtime getter, at most once each; input snapshots are not mutated.
    ``eligible(item, current_detail)`` is the site's existing thematic predicate.
    """
    catalog_path = getattr(runtime, 'КАТАЛОГ_ФАЙЛ', None)
    if not catalog_path:
        return []
    path = Path(catalog_path).parent / (site_id + '-new-series.json')
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_FEED_BYTES + 1)
        if len(raw) > MAX_FEED_BYTES:
            return []
        feed = json.loads(raw)
    except (OSError, ValueError, RecursionError):
        return []
    if not isinstance(feed, dict):
        return []
    events = feed.get('events')
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        return []
    wanted = {provider_id(e.get('titleId')) for e in events if isinstance(e, dict)}
    wanted.discard(None)
    raw_details = getattr(view.п, 'записи', {})
    if not isinstance(raw_details, Mapping):
        return []
    get_detail = detail_getter or view.деталь
    current, items, slugs = {}, [], {}
    for item in catalog:
        if not isinstance(item, dict) or not item.get('slug'):
            continue
        slug = item['slug']
        raw_detail = raw_details.get(slug)
        if not isinstance(raw_detail, Mapping):
            continue
        ident = provider_id(raw_detail.get('id'))
        if ident not in wanted or slug in current:
            continue
        detail = get_detail(slug)
        if (not isinstance(detail, dict) or detail.get('playable') is False
                or provider_id(detail.get('id')) != ident
                or (eligible is not None and not eligible(item, detail))):
            continue
        items.append(item)
        current[slug] = detail
        slugs.setdefault(ident, slug)
    rows = select_events(events, items, current, now=now, limit=limit)
    return [dict(row, slug=slugs[row['titleId']]) for row in rows]


def render_rows(rows, *, style='generic', heading='Новые серии'):
    """Reuse existing structural CSS classes; add no CSS or JavaScript.

    Inputs are selected rows from load_rows, not unvalidated watcher payloads.
    A semantic generic fallback is available for other hosts.
    """
    if not rows:
        return ''
    if style not in ('lords', 'zona', 'zona-cc'):
        return render_section(rows, heading)
    esc = lambda value: escape(str(value), quote=True)
    cards = []
    for row in rows:
        url = _url(row.get('episode_url'), relative=True) or _url(row.get('url'))
        poster = _url(row.get('poster'))
        if (not url or _time(row.get('observedAt')) is None
                or not _positive(row.get('season')) or not _positive(row.get('episode'))):
            continue
        stamp = datetime.fromisoformat(row['observedAt'].replace('Z', '+00:00'))
        local = stamp.astimezone(timezone(timedelta(hours=3))).isoformat(sep=' ').removesuffix('+03:00')
        label = f'Сезон {row["season"]}, серия {row["episode"]}'
        observed = ('<time datetime="' + esc(row['observedAt']) + '">'
                    + 'Обнаружено у источника: ' + esc(local) + ' МСК</time>')
        image = ('<img src="' + esc(poster) + '" alt="" loading="lazy" width="400" height="600">') if poster else ''
        if style == 'lords':
            cards.append('<a class="c" href="' + esc(url) + '"><span class="c__p">'
                         + image + '</span><span class="c__cap"><span class="c__t">'
                         + esc(row['title']) + '</span><span class="c__m">' + esc(label)
                         + '</span>' + observed + '</span></a>')
        elif style == 'zona':
            cards.append('<a class="zr" href="' + esc(url) + '"><span class="zr__p">'
                         + image + '</span><span class="zr__body"><span class="zr__t">'
                         + esc(row['title']) + '</span><span class="zr__m">' + esc(label)
                         + '</span>' + observed + '</span></a>')
        else:
            cards.append('<a class="zxep" href="' + esc(url) + '">' + image
                         + '<span class="zxep__b"><span class="zxep__t">' + esc(row['title'])
                         + '</span><span class="zxep__e">' + esc(label) + '</span>'
                         + observed + '</span></a>')
    if not cards:
        return ''
    section, head, grid = {'lords': ('sec-rail', 'sec-rail__h', 'grid'),
                           'zona': ('zsec zsec--eps', 'zsec__h', 'zl'),
                           'zona-cc': ('zxsec', 'zxsec__h', 'zxeps')}[style]
    return ('<section class="' + section + '"><div class="' + head + '"><h2>'
            + esc(heading) + '</h2></div><div class="' + grid + '">'
            + ''.join(cards) + '</div></section>')
