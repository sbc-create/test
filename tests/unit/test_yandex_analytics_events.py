"""REQ-ANALYTICS-EVENTS: в Метрику не уезжают персональные данные.

Проверяется поведение сгенерированного клиента, а не наличие фильтра в коде:
JavaScript исполняется настоящим node, TypeScript сверяется с ним по контракту.
Отдельно проверяется, что на staging, при чужом hostname и без counter ID тег
Метрики не загружается вовсе — не «загрузился и молчит».
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from factory.analytics import client_codegen, events
from factory.paths import PATHS

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node не установлен")

GENERATED_JS = PATHS.root / client_codegen.JS_TARGET
GENERATED_TS = PATHS.root / client_codegen.TS_TARGET


def _attrs(**overrides) -> str:
    base = {
        "data-counter-id": "90000001",
        "data-allowed-hosts": "yummyani.site",
        "data-environment": "production",
        "data-analytics-enabled": "true",
    }
    base.update(overrides)
    return json.dumps(base)


def _exec(attrs: str, hostname: str, body: str) -> dict:
    """Исполняет сгенерированный клиент в поддельном DOM и возвращает, что он сделал.

    Поддельный DOM, а не заглушка функции: проверять надо тот же файл, который
    уедет в браузер, включая загрузку тега и разбор data-атрибутов.
    """
    harness = f"""
const loaded = [];
const attrs = {attrs};
global.window = {{ location: {{ hostname: {json.dumps(hostname)} }} }};
const scriptEl = {{ getAttribute: (name) => (name in attrs ? attrs[name] : null) }};
const head = {{ parentNode: {{ insertBefore: (node) => loaded.push(node.src) }} }};
global.document = {{
  currentScript: scriptEl,
  querySelector: () => scriptEl,
  createElement: () => ({{}}),
  getElementsByTagName: () => [head],
}};
{GENERATED_JS.read_text(encoding='utf-8')}
{body}
// ym.a — очередь вызовов из официального загрузчика: каждый элемент это
// объект arguments, который надо развернуть в массив явно.
const sent = (global.window.ym && global.window.ym.a)
  ? Array.from(global.window.ym.a).map((call) => Array.from(call))
  : [];
console.log(JSON.stringify({{
  active: global.window.siteAnalytics.active,
  reason: global.window.siteAnalytics.reason,
  loaded: loaded,
  sent: sent,
}}));
"""
    result = subprocess.run(
        [NODE, "-e", harness], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def _reach(out: dict) -> dict:
    """Параметры единственного отправленного reachGoal."""
    calls = [c for c in out["sent"] if len(c) > 1 and c[1] == "reachGoal"]
    assert calls, f"reachGoal не отправлен: {out['sent']}"
    return calls[0][3]


# ------------------------------------------------------- когда клиент молчит
def test_production_with_matching_hostname_loads_the_tag():
    out = _exec(_attrs(), "yummyani.site", "")
    assert out["active"] is True
    assert out["loaded"], "тег Метрики обязан загрузиться на боевом домене"


def test_staging_does_not_load_the_tag_at_all():
    out = _exec(_attrs(**{"data-environment": "staging"}), "yummyani.site", "")
    assert out["active"] is False
    assert out["loaded"] == [], "на staging в странице не должно быть запроса к Метрике"
    assert "production" in out["reason"]


def test_wrong_hostname_is_blocked():
    out = _exec(_attrs(), "preview.yummyani.site", "")
    assert out["active"] is False
    assert out["loaded"] == []
    assert "hostname" in out["reason"]


def test_similar_hostname_is_not_a_match():
    """Совпадение точное: `yummyani.site.evil.tld` — чужой домен."""
    out = _exec(_attrs(), "yummyani.site.evil.tld", "")
    assert out["active"] is False


def test_missing_counter_id_blocks_everything():
    out = _exec(_attrs(**{"data-counter-id": ""}), "yummyani.site", "")
    assert out["active"] is False
    assert out["loaded"] == []
    assert "counter ID" in out["reason"]


def test_analytics_enabled_false_blocks_everything():
    out = _exec(_attrs(**{"data-analytics-enabled": "false"}), "yummyani.site", "")
    assert out["active"] is False
    assert out["loaded"] == []
    assert "ANALYTICS_ENABLED=false" in out["reason"]


def test_empty_allowed_hosts_blocks_everything():
    out = _exec(_attrs(**{"data-allowed-hosts": ""}), "yummyani.site", "")
    assert out["active"] is False
    assert out["loaded"] == []


def test_track_is_a_silent_no_op_when_disabled():
    out = _exec(_attrs(**{"data-environment": "staging"}), "yummyani.site",
                "window.siteAnalytics.track('search', {results_bucket: '1-10'});")
    assert out["sent"] == []


# --------------------------------------------------------- фильтр параметров
def test_allowed_parameters_are_sent():
    out = _exec(_attrs(), "yummyani.site",
                "window.siteAnalytics.track('search', {results_bucket: '1-10', source: 'header'});")
    calls = [c for c in out["sent"] if len(c) > 1 and c[1] == "reachGoal"]
    assert calls[0][2] == "search"
    assert calls[0][3] == {"results_bucket": "1-10", "source": "header"}


@pytest.mark.parametrize("forbidden", [
    {"comment_text": "мне очень понравилось это аниме"},
    {"email": "user@example.com"},
    {"name": "Иван Иванов"},
    {"query": "как посмотреть аниме бесплатно"},
    {"token": "y0_AgAAAAAsecret"},
    {"publisher_id": "pub-123"},
    {"user_id": "42"},
    {"ip": "203.0.113.9"},
    {"session": "abc"},
    {"password": "hunter2"},
])
def test_forbidden_parameters_never_leave_the_browser(forbidden):
    body = (
        "window.siteAnalytics.track('comment_submit', "
        f"Object.assign({{title_id: 'naruto', length_bucket: 'short'}}, {json.dumps(forbidden)}));"
    )
    out = _exec(_attrs(), "yummyani.site", body)
    sent = _reach(out)
    for key, value in forbidden.items():
        assert key not in sent, f"запрещённый параметр {key} ушёл в Метрику"
        assert value not in sent.values()
    assert sent == {"title_id": "naruto", "length_bucket": "short"}


def test_unknown_parameters_are_dropped():
    out = _exec(_attrs(), "yummyani.site",
                "window.siteAnalytics.track('title_view', {title_id: 'x', whatever: 'y'});")
    sent = _reach(out)
    assert sent == {"title_id": "x"}


def test_enum_values_outside_the_dictionary_are_dropped():
    out = _exec(_attrs(), "yummyani.site",
                "window.siteAnalytics.track('player_error', "
                "{title_id: 'x', error_code: 'подробное описание ошибки с путём /home/user'});")
    sent = _reach(out)
    assert "error_code" not in sent


def test_identifiers_that_look_like_free_text_are_dropped():
    out = _exec(_attrs(), "yummyani.site",
                "window.siteAnalytics.track('title_view', "
                "{title_id: 'какой-то очень длинный текст с пробелами и / слешами'});")
    sent = _reach(out)
    assert sent == {}


def test_unknown_event_is_not_sent():
    out = _exec(_attrs(), "yummyani.site",
                "window.siteAnalytics.track('exfiltrate', {x: 1});")
    assert [c for c in out["sent"] if len(c) > 1 and c[1] == "reachGoal"] == []


# ------------------------------------------------------------------ Вебвизор
def test_webvisor_is_explicitly_disabled_in_the_init_call():
    out = _exec(_attrs(), "yummyani.site", "")
    init = [c for c in out["sent"] if len(c) > 1 and c[1] == "init"]
    assert init, out["sent"]
    options = init[0][2]
    assert options["webvisor"] is False, "Вебвизор обязан быть выключен явно"


# --------------------------------------------------------------- генерация
def test_generated_files_match_the_specification():
    """Файл, поправленный руками, расходится с целями Метрики — это ловится здесь."""
    assert GENERATED_JS.read_text(encoding="utf-8") == client_codegen.render_js()
    assert GENERATED_TS.read_text(encoding="utf-8") == client_codegen.render_ts()


def test_every_event_has_a_goal_and_every_goal_an_event():
    goals = events.goals_payload()
    assert len(goals) == len(events.EVENTS) == 9
    ids = {g["conditions"][0]["url"] for g in goals}
    assert ids == set(events.EVENT_IDS)
    for goal in goals:
        assert goal["type"] == "action", "цель JavaScript-события — только action"
        assert len(goal["name"]) <= 255


def test_the_nine_events_are_exactly_the_ones_requested():
    assert list(events.EVENT_IDS) == [
        "search", "filter_apply", "title_view", "season_select", "episode_select",
        "player_start", "player_ready", "player_error", "comment_submit",
    ]


def test_no_event_declares_a_free_text_parameter():
    """Свободного текста среди типов параметров нет — это и есть гарантия."""
    for event in events.EVENTS:
        for param in event.params:
            assert param.kind in {"id", "int", "enum", "bool"}
            assert param.name.lower() not in events.FORBIDDEN_PARAM_NAMES


def test_both_clients_declare_the_same_events():
    ts = GENERATED_TS.read_text(encoding="utf-8")
    js = GENERATED_JS.read_text(encoding="utf-8")
    for event_id in events.EVENT_IDS:
        assert f"'{event_id}'" in ts
        assert f'"{event_id}"' in js
