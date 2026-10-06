#!/usr/bin/env python3
"""Заголовки кеша и сжатия Yummy: HTML, статика Next и Link: preload плеера.

yummy_headers.py <домен> [путь карточки]
Печатает Cache-Control / Content-Encoding / Link для главной, одного файла
/_next/static/ (берётся из разметки главной) и карточки. Ничего не пишет.
"""
import re
import sys
import urllib.request

домен = sys.argv[1]
карточка = sys.argv[2] if len(sys.argv) > 2 else None


def взять(путь):
    з = urllib.request.Request(f"https://{домен}{путь}", headers={
        "Accept-Encoding": "gzip", "User-Agent": "site-factory-perf-audit"})
    with urllib.request.urlopen(з, timeout=60) as о:
        тело = о.read()
        return о.status, dict(о.headers), тело


def показать(имя, путь):
    код, з, тело = взять(путь)
    print(f"{имя:10s} {код} cache-control={з.get('Cache-Control')!r} encoding={з.get('Content-Encoding')!r} "
          f"bytes={len(тело)} link={'preload' if 'preload' in (з.get('Link') or '') else '-'}")
    return тело


тело = показать("главная", "/")
if тело[:2] == b"\x1f\x8b":
    import gzip
    тело = gzip.decompress(тело)
м = re.search(rb'/_next/static/[^"\']+\.js', тело)
if м:
    показать("статика", м.group(0).decode())
if карточка:
    показать("карточка", карточка)
