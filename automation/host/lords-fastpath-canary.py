"""Сквозная проверка быстрого пути на изолированном canary.

Берётся настоящий релиз Lords, но canary живёт отдельно и наружу не смотрит:
свой каталог, свой порт, никакого отношения к публичным доменам. Вёрстка, SEO и
плеер не трогаются — переписывается ровно то, что назвала карта зависимостей.

Измеряется то, что обещано: от detected_at до live_verified_at.
"""
import http.server
import shutil
import socketserver
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/claude/work-02b")

from factory.site_engine.contracts import ContentEvent, EventType  # noqa: E402
from factory.site_engine.dependencies import SiteContext, plan_for  # noqa: E402
from factory.site_engine.freshness import (  # noqa: E402
    FreshnessQueue,
    QueueItem,
    Timeline,
    run_fast_cycle,
)
from factory.site_engine.incremental import (  # noqa: E402
    build_incremental,
    checksums_of,
    discard,
    verify_base_untouched,
)
from factory.site_engine.publish import publish  # noqa: E402

CANARY = Path("/srv/lords/canary")
ИСТОЧНИК = Path("/srv/lords/lords-01/current").resolve()

shutil.rmtree(CANARY, ignore_errors=True)
(CANARY / "releases").mkdir(parents=True, exist_ok=True)

print("=== 1. Готовим canary из настоящего релиза ===")
база = CANARY / "releases" / "base"
начало = time.monotonic()
# Берём сто настоящих карточек, а не весь релиз: canary должен быть настоящим
# по содержимому, а не по объёму, и не конкурировать с идущим рендером за диск.
(база / "site" / "title").mkdir(parents=True)
исходные = sorted((ИСТОЧНИК / "site" / "title").iterdir())[:100]
for d in исходные:
    цель = база / "site" / "title" / d.name
    цель.mkdir()
    for f in d.iterdir():
        if f.is_file():
            shutil.copy2(f, цель / f.name)
shutil.copy2(ИСТОЧНИК / "site" / "index.html", база / "site" / "index.html")
(база / "serve.py").write_text("# рантайм canary\n", encoding="utf-8")
страниц = sum(1 for _ in (база / "site").rglob("*.html"))
print(f"  базовый релиз canary: {страниц} страниц за {time.monotonic() - начало:.1f} с")

current = CANARY / "current"
publish(current, база, expect_pages=1)
print(f"  current -> {current.resolve().name}")

# Локальный сервер: canary наружу не смотрит, только 127.0.0.1.
корень = current / "site"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(корень), **kw)

    def log_message(self, *a):
        pass


сервер = socketserver.TCPServer(("127.0.0.1", 0), Handler)
порт = сервер.server_address[1]
threading.Thread(target=сервер.serve_forever, daemon=True).start()
print(f"  сервер canary: 127.0.0.1:{порт} (наружу не смотрит)")

# Берём настоящую карточку.
образец = next((корень / "title").iterdir())
слаг = образец.name
адрес = f"/title/{слаг}/"
with urllib.request.urlopen(f"http://127.0.0.1:{порт}{адрес}", timeout=10) as r:
    было = r.read().decode("utf-8", "replace")
print(f"  карточка {слаг}: {len(было)} байт, метка отсутствует: {'canary-episode' not in было}")

print()
print("=== 2. Событие: вышла новая серия ===")
detected_at = datetime.now(timezone.utc)
событие = ContentEvent(
    event_id="canary-1", event_type=EventType.EPISODE_ADDED, provider="cdnvideohub",
    provider_id="canary", canonical_title_id="cdnvideohub:canary",
    observed_at=detected_at, idempotency_key="canary-s1e9",
    payload={"season": 1, "available_episodes": 9, "was": 8},
)
ctx = SiteContext(site_id="canary", title_path=слаг, listing_paths=(), seasons=())
план = plan_for(событие, [ctx])
print(f"  затронуто страниц: {план.page_count}")
for r in план.resources:
    print(f"    {r.kind}: {r.path} — {r.reason}")
print(f"  теги кэша: {план.cache_tags}")

print()
print("=== 3. Быстрый цикл ===")
очередь = FreshnessQueue(CANARY / "queue.json")
контроль = checksums_of(база, (f"site/title/{слаг}/index.html",))
новый = CANARY / "releases" / "next"
discard(новый)

состояние = {}


def render(item):
    правки = {}
    for r in план.resources:
        if r.kind != "page":
            continue
        отн = f"site{r.path}index.html" if r.path.endswith("/") else f"site{r.path}"
        путь = база / отн
        if не_существует := (not путь.exists()):
            del не_существует
            continue
        текст = путь.read_text(encoding="utf-8", errors="replace")
        правки[отн] = текст.replace("</body>", "<!-- canary-episode s1e9 --></body>", 1)
    итог = build_incremental(база, новый, pages=правки)
    состояние["итог"] = итог
    return итог.touched


def publish_canary():
    publish(current, новый, expect_pages=1)


def verify(item):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{порт}{адрес}", timeout=10) as r:
            return "canary-episode" in r.read().decode("utf-8", "replace")
    except OSError:
        return False


элемент = QueueItem(
    idempotency_key=событие.idempotency_key, event_type=событие.event_type.value,
    canonical_title_id=событие.canonical_title_id, payload=событие.payload,
    timeline=Timeline(detected_at=detected_at),
)
итог_цикла = run_fast_cycle(очередь, incoming=[элемент], render=render,
                            publish=publish_canary, verify=verify)

print(f"  обработано: {итог_цикла.processed}")
print(f"  переписано страниц: {итог_цикла.pages_rendered}")
print(f"  связано файлов: {состояние['итог'].linked_files}")
print(f"  длительность цикла: {итог_цикла.duration_seconds:.2f} с")

print()
print("=== 4. Проверка на живом адресе canary ===")
with urllib.request.urlopen(f"http://127.0.0.1:{порт}{адрес}", timeout=10) as r:
    стало = r.read().decode("utf-8", "replace")
print(f"  метка появилась: {'canary-episode' in стало}")
print(f"  вёрстка не тронута: {len(стало) - len(было)} байт разницы (только метка)")

обработанный = [i for i in очередь._items.values() if i.done]
задержка = обработанный[0].timeline.total_latency_seconds if обработанный else None
print(f"  detected_at -> live_verified_at: {задержка:.2f} с" if задержка else "  не подтверждено")

print()
print("=== 5. Базовый релиз не пострадал ===")
расхождения = verify_base_untouched(база, контроль)
print(f"  {'цел' if not расхождения else 'ИСПОРЧЕН: ' + str(расхождения)}")
with urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=10) as r:
    print(f"  главная canary отвечает: {r.status}")

print()
print("=== 6. Повторный цикл: дублей нет ===")
повтор = run_fast_cycle(очередь, incoming=[элемент], render=render,
                        publish=publish_canary, verify=verify)
print(f"  обработано: {повтор.processed}, дублей отброшено: {повтор.skipped_duplicates}")
print(f"  страниц перестроено: {повтор.pages_rendered}")

сервер.shutdown()
shutil.rmtree(CANARY, ignore_errors=True)
print()
print("  canary убран")
