"""Установщик читающего API ставит службу, которая переживёт эту сессию.

Повод. Юнит собирался из пути, откуда запущен установщик, то есть из рабочего
дерева сессии (`/home/claude/wt-…`). Дерево — временное: `git worktree remove`
его снимает, и служба осталась бы с `ExecStart` в несуществующий файл, а в
`ReadOnlyPaths` — с несуществующим каталогом. Поймано при подготовке команды
владельцу: ставить службу, живущую в моём дереве, нельзя.

Поэтому код службы и её контракт копируются в `/usr/local/lib/site-factory` —
туда же, где на хосте уже лежат другие хостовые сценарии фабрики, — и юнит
указывает на копию. Откат эту копию убирает.

Сам путь установки здесь НЕ исполняется: он требует root, nginx и systemd.
Проверяются сухой прогон и состав юнита; «проверено» о непройденном не
говорится.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "install-app-read-api.sh"
СТАБИЛЬНЫЙ = "/usr/local/lib/site-factory"


@pytest.fixture(scope="module")
def сухой() -> str:
    р = subprocess.run(["bash", str(СЦЕНАРИЙ), "--dry-run"],
                       capture_output=True, text=True, timeout=300)
    assert р.returncode == 0, р.stdout + р.stderr
    return р.stdout + р.stderr


def test_синтаксис():
    р = subprocess.run(["bash", "-n", str(СЦЕНАРИЙ)], capture_output=True, text=True)
    assert р.returncode == 0, р.stderr


def test_код_службы_копируется_в_стабильное_место(сухой):
    assert f"{СТАБИЛЬНЫЙ}/app-read-api-animedia-01.py" in сухой


@pytest.mark.parametrize("строка", [
    f"ExecStart=/usr/bin/python3 {СТАБИЛЬНЫЙ}/app-read-api-animedia-01.py",
    f"WorkingDirectory={СТАБИЛЬНЫЙ}",
    f"ReadOnlyPaths=/srv/animedia-icu/data {СТАБИЛЬНЫЙ}",
])
def test_юнит_не_смотрит_в_рабочее_дерево(сухой, строка):
    assert строка in сухой, строка


def test_в_юните_нет_пути_сессии(сухой):
    """Главное утверждение: ни одной ссылки на дерево сессии внутри юнита."""
    юнит = сухой.split("записать /etc/systemd/system/", 1)[1]
    юнит = юнит.split("systemctl daemon-reload", 1)[0]
    assert "/home/claude/wt-" not in юнит, (
        "юнит зависит от рабочего дерева сессии: оно будет снято")


def test_служба_ничего_не_пишет(сухой):
    assert "ProtectSystem=strict" in сухой
    assert "ReadWritePaths=" not in сухой, "запись разрешать нечему: API читающее"


def test_предел_памяти_назван(сухой):
    assert "MemoryMax=512M" in сухой, (
        "без предела утечка в службе добирала бы память у витрин и редактора")


def test_маршрут_только_на_чтение(сухой):
    assert "limit_except GET HEAD { deny all; }" in сухой
    assert 'add_header X-Robots-Tag "noindex, nofollow" always;' in сухой


def test_копия_конфигурации_сайта_снимается_до_правки(сухой):
    assert ".before-app-read-api-animedia-01." in сухой
    assert "nginx -t" in сухой


def test_откат_убирает_и_копию_кода():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    откат = текст.split('if [ "$rollback" = 1 ]', 1)[1].split("exit 0", 1)[0]
    assert "$INSTALLED_SCRIPT" in откат, "копия кода осталась бы после откат�"
    assert "$UNIT_PATH" in откат and "$SNIPPET" in откат


def test_ключ_показывается_один_раз_и_только_при_создании():
    """Ключ владелец обязан получить — но ровно один раз и только в терминале.

    Значение печатается ТОЛЬКО в ветке создания файла: повторный запуск
    установщика его не покажет, а в подсказках и примерах стоит
    местозаполнитель. В отчёты, журналы и передачи ключ не попадает — там он
    назван словом «ключ», а не значением.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    показ = текст.index('ЗНАЧЕНИЕ КЛЮЧА')
    создание = текст.index("secrets.token_urlsafe")
    конец_ветки = текст.index("if [ \"$dry_run\" = 0 ]", создание)
    assert создание < показ < конец_ветки, (
        "значение печатается вне ветки создания ключа: повторный запуск "
        "показал бы его снова")
    assert "показывается один раз" in текст
    assert "logger" not in текст and "tee" not in текст, "ключ не идёт в журнал"
    # Подсказки после установки ссылаются на ФАЙЛ ключа, а не на значение:
    # приёмка читает его сама, поэтому примеру с подставленным ключом там
    # делать нечего.
    подсказки = текст[текст.index('log "готово; проверить снаружи"'):]
    assert "--key-file ${KEY_FILE}" in подсказки
    assert "$(cat" not in подсказки, "значение ключа в подсказках не появляется"


def test_сухой_прогон_ключ_не_печатает(сухой):
    assert "ЗНАЧЕНИЕ КЛЮЧА" not in сухой


# --- разбор аргументов и поворот ключа --------------------------------------
#
# Поймано пробой 2026-10-10: разбор читал только `$1`, поэтому
# `--dry-run --rotate-key` исполнялся как один `--dry-run` — поворот ключа
# «проходил», ничего не сделав, а опечатка во втором аргументе не вызывала
# отказа. Ключ уезжает в APK, то есть рано или поздно становится известен,
# значит поворот обязан работать и быть отдельной операцией.


def test_все_аргументы_разбираются_а_не_только_первый():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "while [ $# -gt 0 ]" in текст, (
        "разбор по $1 молча отбрасывает остальные аргументы")


def test_неизвестный_аргумент_отвергается():
    р = subprocess.run(["bash", str(СЦЕНАРИЙ), "--dry-run", "--нет-такого"],
                       capture_output=True, text=True, timeout=300)
    assert р.returncode == 2, р.stdout + р.stderr
    assert "неизвестный аргумент" in (р.stdout + р.stderr)


def test_откат_и_поворот_вместе_не_принимаются():
    р = subprocess.run(["bash", str(СЦЕНАРИЙ), "--rollback", "--rotate-key"],
                       capture_output=True, text=True, timeout=300)
    assert р.returncode == 2, р.stdout + р.stderr
    assert "не имеют смысла" in (р.stdout + р.stderr)


def test_поворот_сохраняет_прежний_ключ_перед_заменой():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    ветка = текст[текст.index('"$rotate_key" = 1'):]
    сохранение = ветка.index("before-rotate")
    замена = текст.index("secrets.token_urlsafe")
    assert текст.index("before-rotate") < замена, (
        "прежний ключ обязан быть сохранён до замены: пока новая сборка "
        "приложения не вышла, доступ возвращают старым значением")
    assert сохранение >= 0


def test_поворот_перезапускает_службу():
    """Ключ читается при старте: без перезапуска поворот ничего не меняет."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    enable = текст.index('systemctl enable --now "$UNIT"')
    restart = текст.index('systemctl restart "$UNIT"')
    assert enable < restart, "перезапуск идёт после enable --now"
    assert "новый ключ прочитан" in текст


def test_поворот_предупреждает_о_прежних_сборках():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "прежний ключ больше не принимается" in текст


# --- что установка делает с конфигурацией витрины ---------------------------


КОНФИГ_ВИТРИНЫ = """upstream cell_animedia_01 { server 127.0.0.1:9121; }

server {
    listen 80;
    server_name animedia.icu www.animedia.icu;

    location ^~ /.well-known/acme-challenge/ { root /var/www/html; }
    location / { proxy_pass http://cell_animedia_01; }
    location = /healthz { proxy_pass http://cell_animedia_01/healthz; }
}

server {
    listen 443 ssl;
    server_name animedia.icu;

    add_header X-Robots-Tag $cell_robots_animedia_01 always;
    include /etc/nginx/snippets/webmaster-verification.conf;

    location / { proxy_pass http://cell_animedia_01; }
    location = /healthz { proxy_pass http://cell_animedia_01/healthz; }
}
"""


def _вставить(текст: str, сниппет: str) -> str:
    """Тот же код, что в блоке PYINS установщика."""
    начало = текст.rfind("server {")
    конец = текст.rindex("}")
    блок = текст[начало:конец]
    return текст[:начало] + блок + f"\n    include {сниппет};\n" + текст[конец:]


def test_вставка_не_трогает_существующие_маршруты():
    """Главный вопрос установки: витрина и её плеер обязаны работать как были.

    Проверяется на копии той же раскладки, что у боевой конфигурации: ни одна
    прежняя строка не исчезает, число location не меняется, скобки остаются
    сбалансированы, добавляется РОВНО одна строка include.
    """
    стало = _вставить(КОНФИГ_ВИТРИНЫ, "/etc/nginx/snippets/app-read-api-animedia-01.conf")
    было_строк = КОНФИГ_ВИТРИНЫ.splitlines()
    assert all(с in стало.splitlines() for с in было_строк), "строка исчезла"
    assert стало.count("location ") == КОНФИГ_ВИТРИНЫ.count("location ")
    assert стало.count("{") == стало.count("}")
    assert стало.count("app-read-api-animedia-01.conf") == 1


def test_вставка_попадает_в_блок_HTTPS_а_не_в_HTTP():
    """В HTTP-блоке API открывать нельзя: ключ ушёл бы по открытому каналу."""
    стало = _вставить(КОНФИГ_ВИТРИНЫ, "/snip.conf")
    assert стало.rindex("include /snip.conf") > стало.rindex("listen 443 ssl")
    http_блок = стало[:стало.index("listen 443 ssl")]
    assert "/snip.conf" not in http_блок


def test_внешний_адрес_состояния_описан_в_контракте():
    """Разработчик спрашивал /api/app/v1/healthz и получал 404 от витрины."""
    текст = (КОРЕНЬ / "docs" / "APP_READ_API.md").read_text(encoding="utf-8")
    assert "/api/app/v1/healthz" in текст
    assert "location = /healthz" in текст, (
        "в контракте должно быть сказано, почему корневой /healthz не наш")
