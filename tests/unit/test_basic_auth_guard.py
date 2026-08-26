"""REQ-NO-BASIC-AUTH: на публичном сайте не может появиться Basic Auth.

Правило неприкосновенно: пароль на публичном домене закрывает сайт и от людей,
и от поисковых роботов, а nginx при этом стартует нормально — по логам выкладки
это не видно. Поэтому запрет проверяется статически по репозиторию и отдельно
по живому ответу.

Область — ПУБЛИЧНЫЕ сайты. Незапущенный стенд под паролем нарушением не
является; ошибкой он становится ровно в тот момент, когда домен помечен
запущенным. Тесты ниже проверяют именно этот переход, а не наличие слова
«staging» в пути.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.basic_auth_guard import (
    LiveResult,
    Severity,
    check_live_response,
    public_domains,
    scan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo(tmp_path: Path, *, launched: bool, conf: str) -> Path:
    (tmp_path / "config" / "directions").mkdir(parents=True)
    (tmp_path / "config" / "directions" / "lords.json").write_text(json.dumps({
        "direction": "lords",
        "domains": [{"apex": "lordfilm47.space", "launched": launched}],
    }), encoding="utf-8")
    (tmp_path / "nginx").mkdir()
    (tmp_path / "nginx" / "site.conf").write_text(conf, encoding="utf-8")
    return tmp_path


PROTECTED = """server {
    server_name lordfilm47.space;
    auth_basic "restricted";
    auth_basic_user_file /etc/nginx/lords/.htpasswd;
}
"""

OPEN = """server {
    server_name lordfilm47.space;
    location / { try_files $uri /index.html; }
}
"""


# --- переход «стенд → публичный сайт» ------------------------------------------

def test_password_on_unlaunched_stand_is_a_warning(tmp_path):
    report = scan(_repo(tmp_path, launched=False, conf=PROTECTED))
    assert report.passed, "непубличный стенд под паролем нарушением не является"
    assert report.warnings
    assert all(f.severity is Severity.WARNING for f in report.warnings)


def test_same_config_fails_once_the_domain_is_launched(tmp_path):
    """Текст конфигурации тот же — меняется только статус домена."""
    report = scan(_repo(tmp_path, launched=True, conf=PROTECTED))
    assert not report.passed
    assert report.errors
    assert any("lordfilm47.space" in f.domains for f in report.errors)


def test_open_config_on_public_domain_passes(tmp_path):
    report = scan(_repo(tmp_path, launched=True, conf=OPEN))
    assert report.passed and not report.findings


# --- что именно ловится --------------------------------------------------------

@pytest.mark.parametrize("snippet,reason_fragment", [
    ('auth_basic "closed";', "auth_basic"),
    ("auth_basic_user_file /etc/nginx/.htpasswd;", "файл паролей"),
    ("HTPASSWD = '/etc/nginx/lords/.htpasswd'", ".htpasswd"),
    ("htpasswd -bc /etc/nginx/.htpasswd user pass", "htpasswd"),
    ('add_header WWW-Authenticate "Basic";', "WWW-Authenticate"),
])
def test_each_form_of_basic_auth_is_detected(tmp_path, snippet, reason_fragment):
    conf = f"server {{\n    server_name lordfilm47.space;\n    {snippet}\n}}\n"
    report = scan(_repo(tmp_path, launched=True, conf=conf))
    assert report.errors, f"не обнаружено: {snippet}"
    assert any(reason_fragment.lower() in f.reason.lower() for f in report.errors)


def test_auth_basic_off_is_not_a_violation(tmp_path):
    """`auth_basic off;` снимает защиту — именно им открывают ACME-challenge."""
    conf = """server {
    server_name lordfilm47.space;
    location ^~ /.well-known/acme-challenge/ {
        auth_basic off;
    }
}
"""
    report = scan(_repo(tmp_path, launched=True, conf=conf))
    assert report.passed and not report.findings


def test_generator_not_just_config_is_scanned(tmp_path):
    """Пароль обычно приходит из генератора, а не из руками написанного файла."""
    root = _repo(tmp_path, launched=True, conf=OPEN)
    (root / "gen.py").write_text(
        'def nginx(site):\n'
        '    return f"server {{ server_name lordfilm47.space; auth_basic \\"x\\"; }}"\n',
        encoding="utf-8")
    report = scan(root)
    assert any(f.path == "gen.py" for f in report.errors)


@pytest.mark.parametrize("name", ["deploy.sh", "template.j2", "vhost.template", "app.ts"])
def test_all_relevant_file_kinds_are_scanned(tmp_path, name):
    root = _repo(tmp_path, launched=True, conf=OPEN)
    (root / name).write_text('server_name lordfilm47.space; auth_basic "x";\n', encoding="utf-8")
    report = scan(root)
    assert any(f.path == name for f in report.errors), f"не просмотрен {name}"


# --- определение публичности ---------------------------------------------------

def test_analytics_enabled_domain_counts_as_public(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "analytics.json").write_text(json.dumps({
        "properties": [{"domain": "yummyani.site", "analytics_enabled": True},
                       {"domain": "off.example", "analytics_enabled": False}]
    }), encoding="utf-8")
    domains = public_domains(tmp_path)
    assert "yummyani.site" in domains
    assert "off.example" not in domains


def test_unlaunched_domain_is_not_public(tmp_path):
    _repo(tmp_path, launched=False, conf=OPEN)
    assert public_domains(tmp_path) == set()


def test_extra_public_domains_can_be_supplied(tmp_path):
    root = _repo(tmp_path, launched=False, conf=PROTECTED)
    report = scan(root, extra_public={"lordfilm47.space"})
    assert not report.passed, "явно переданный публичный домен обязан ужесточать проверку"


def test_guard_module_itself_is_not_flagged():
    """Иначе описание запрета срабатывало бы как его нарушение."""
    report = scan(REPO_ROOT)
    flagged = [f for f in report.findings if f.path.endswith("basic_auth_guard.py")]
    assert not flagged


# --- живой ответ ---------------------------------------------------------------

class _Response:
    def __init__(self, status: int, headers: dict) -> None:
        self.status = status
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def getcode(self) -> int:
        return self.status


def test_live_200_without_header_passes():
    result = check_live_response(
        "lordfilm47.space", opener=lambda url, timeout: _Response(200, {}))
    assert result.passed


def test_live_401_fails():
    def opener(url, timeout):
        raise _http_error(401, {"WWW-Authenticate": 'Basic realm="x"'})

    result = check_live_response("lordfilm47.space", opener=opener)
    assert not result.passed
    assert result.status_code == 401 and result.has_www_authenticate


def test_live_200_with_www_authenticate_still_fails():
    result = check_live_response(
        "lordfilm47.space",
        opener=lambda url, timeout: _Response(200, {"WWW-Authenticate": "Basic"}))
    assert not result.passed


def test_network_error_is_not_reported_as_passed():
    """Недоступный сайт — это не сайт без Basic Auth."""
    def opener(url, timeout):
        raise OSError("connection refused")

    result = check_live_response("lordfilm47.space", opener=opener)
    assert not result.passed
    assert "НЕ ПРОВЕРЕНО" in result.render()


def _http_error(code: int, headers: dict) -> Exception:
    exc = OSError(f"HTTP {code}")
    exc.code = code
    exc.headers = headers
    return exc


# --- фактическое состояние репозитория -----------------------------------------

def test_repository_has_no_basic_auth_on_public_sites():
    """
    Главная проверка: ни один ПУБЛИЧНЫЙ домен репозитория не закрыт паролем.

    Провал означает конкретный файл и строку, а не общее «что-то не так».
    """
    report = scan(REPO_ROOT)
    assert report.passed, "Basic Auth на публичном сайте:\n" + "\n".join(
        f.render() for f in report.errors)
