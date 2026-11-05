"""Pure, fail-closed episode feed selection and markup (standard library only).

``allowed`` is an optional iterable of provider UUIDs. ``current_available``
may explicitly verify availability when a season has no ``nums``; it receives
(detail, season_number, episode_number) and must return True. No I/O occurs.
"""
from collections.abc import Mapping
from datetime import datetime, timezone, timedelta
from html import escape
from urllib.parse import urlsplit
from uuid import UUID


MSK = timezone(timedelta(hours=3))


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _time(value):
    try:
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if value.utcoffset() is not None:
            return value.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def _positive(value):
    return type(value) is int and value > 0


def _url(value, relative=False):
    if not isinstance(value, str) or not value or any(
        c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value
    ) or '\\' in value:
        return None
    try:
        parsed = urlsplit(value)
        if value.startswith('/') and not value.startswith('//'):
            return value if not parsed.scheme and not parsed.netloc else None
        if not relative and parsed.scheme in ('https', 'http') and parsed.hostname and not (
            parsed.username or parsed.password
        ):
            return value
    except ValueError:
        pass
    return None


def select_events(events, catalog, details, allowed=None, now=None, limit=10,
                  *, current_available=None):
    """Return one latest eligible observation per UUID, newest UTC first.

    Equal timestamps retain input order. Missing/invalid IDs, dates, paths, and
    availability fail closed. Source observation strings are retained verbatim.
    Catalog metadata is authoritative; watcher titles/posters are ignored.
    ``avail`` explicitly False or zero rejects a season even with listed nums.
    """
    if type(limit) is not int or limit <= 0:
        return []
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError('now must be a timezone-aware datetime')
    now = now.astimezone(timezone.utc)
    permitted = None if allowed is None else {_uuid(v) for v in allowed}
    index = {}
    for item in catalog:
        if not isinstance(item, Mapping):
            continue
        detail = details.get(item.get('slug'))
        if not isinstance(detail, Mapping):
            continue
        ident = _uuid(detail.get('id'))
        if ident and _url(item.get('url')):
            index.setdefault(ident, (item, detail))
    selected = {}
    for event in events:
        if not isinstance(event, Mapping) or event.get('kind') != 'EPISODE_ADDED':
            continue
        ident = _uuid(event.get('titleId'))
        if ident not in index or (permitted is not None and ident not in permitted):
            continue
        season, episode = event.get('season'), event.get('episode')
        stamp = _time(event.get('observedAt'))
        if (event.get('playable') is not True or not _positive(season)
                or not _positive(episode) or stamp is None or stamp > now):
            continue
        item, detail = index[ident]
        seasons = detail.get('seasons')
        if not isinstance(seasons, list):
            continue
        available = False
        for current in seasons:
            if not isinstance(current, Mapping) or type(current.get('n')) is not int or current['n'] != season:
                continue
            if current.get('avail') is False or current.get('avail') == 0:
                continue
            if 'nums' in current:
                nums = current['nums']
                available = isinstance(nums, list) and any(
                    type(n) is int and n == episode for n in nums)
            elif current_available is not None:
                available = current_available(detail, season, episode) is True
            break
        if not available:
            continue
        if ident in selected and selected[ident][0] >= stamp:
            continue
        row = {
            'titleId': ident, 'title': item.get('title', ''),
            'poster': _url(item.get('poster')) or '', 'url': item['url'],
            'season': season, 'episode': episode,
            'observedAt': event['observedAt'],
        }
        episode_url = _url(event.get('episode_url'), relative=True)
        if episode_url:
            row['episode_url'] = episode_url
        selected[ident] = (stamp, row)
    return [row for stamp, row in sorted(selected.values(), key=lambda pair: pair[0], reverse=True)][:limit]


def render_section(rows, heading='Новые серии', *, classes=None):
    """Render escaped semantic markup; classes maps tag roles to CSS classes.

    Roles: section, heading, list, card, link, poster, title, episode, observed.
    No default CSS classes, inline styles, scripts, or release-date assertions.
    """
    classes = classes or {}

    def attr(role):
        value = classes.get(role)
        return ' class="' + escape(str(value), quote=True) + '"' if value else ''

    def esc(value):
        return escape(str(value), quote=True)

    cards = []
    for row in rows:
        url = _url(row.get('episode_url'), relative=True) or _url(row.get('url'))
        stamp = _time(row.get('observedAt'))
        if not url or stamp is None or not _positive(row.get('season')) or not _positive(row.get('episode')):
            continue
        poster = _url(row.get('poster'))
        picture = ('<img' + attr('poster') + ' src="' + esc(poster) + '" alt="' + esc(row.get('title', '')) + '">') if poster else ''
        # Include seconds and fractional seconds, so the displayed instant is exact.
        local = stamp.astimezone(MSK).isoformat(sep=' ').removesuffix('+03:00')
        cards.append('<li' + attr('card') + '><a' + attr('link') + ' href="' + esc(url) + '">' + picture
                     + '<span' + attr('title') + '>' + esc(row.get('title', '')) + '</span></a>'
                     + '<span' + attr('episode') + '>Сезон ' + str(row['season']) + ', серия ' + str(row['episode']) + '</span>'
                     + '<time' + attr('observed') + ' datetime="' + esc(row['observedAt']) + '">Обнаружено у источника: '
                     + local + ' МСК</time></li>')
    return '<section' + attr('section') + '><h2' + attr('heading') + '>' + esc(heading) + '</h2><ul' + attr('list') + '>' + ''.join(cards) + '</ul></section>'
