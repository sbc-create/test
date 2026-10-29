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


def test_запись_только_обмен_кода_на_ключ(сухой):
    """POST пропускается на одном точном адресе — обмене кода устройства на ключ; префикс остаётся на чтение."""
    блок = сухой.split("location = /api/app/v1/activate {", 1)[1].split("\n      }", 1)[0]
    assert "limit_except POST { deny all; }" in блок
    assert "client_max_body_size 1k;" in блок
    assert сухой.count("limit_except") == 2


def test_копия_конфигурации_сайта_снимается_до_правки(сухой):
    """Вывод сухого прогона зависит от состояния ХОСТА, и это учтено.

    Пока службы не было, прогон печатал снятие копии. После установки он честно
    говорит «include уже стоит» и копию не обещает — проверка «в выводе есть
    .before-…» стала бы падать на исправном сценарии (поймано 2026-10-11, сразу
    после установки). Поэтому здесь сторожится САМ механизм, а поведение на
    чистом хосте проверяет репетиция в
    `tests/unit/test_app_read_api_install_rehearsal.py`.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    копия = текст.index('cp -p "$SITE_CONF" "${SITE_CONF}.before-${MARK}')
    правка = текст.index("include вставлен в HTTPS-блок")
    assert копия < правка, "копия обязана сниматься до правки файла сайта"
    assert "nginx -t" in сухой
    assert (".before-app-read-api-animedia-01." in сухой
            or "include уже стоит" in сухой), сухой[-400:]


def test_откат_убирает_и_копию_кода():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    откат = текст.split('if [ "$rollback" = 1 ]', 1)[1].split("exit 0", 1)[0]
    assert "$INSTALLED_SCRIPT" in откат, "копия кода осталась бы после откат�"
    assert "$UNIT_PATH" in откат and "$SNIPPET" in откат


def test_значение_ключа_не_печатается_установкой():
    """Требование изменилось 2026-10-11, и вот почему.

    Прежде установка печатала значение ОДИН раз, чтобы владелец мог внести его
    в секрет CI приложения, — и эта проверка сторожила именно печать. Ключ,
    напечатанный 11 октября, попал в переписку и тем самым стал раскрытым.
    Значит «один раз» недостаточной защитой и было: вывод терминала копируется.

    Теперь значение не печатается вовсе, а передаётся файлом: владелец читает
    его `sudo cat` ровно в тот момент, когда вносит в секрет CI. Проверка
    сторожит новое правило; прежнее сохранено здесь как причина.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "ЗНАЧЕНИЕ КЛЮЧА" not in текст, "печать значения вернулась"
    assert 'cat "$KEY_FILE"' not in текст, "значение читается сценарием в вывод"
    assert "значение не печатается" in текст
    assert "logger" not in текст and "tee" not in текст, "ключ не идёт в журнал"
    # Передача — через файл: названа команда чтения в момент внесения в CI.
    assert "sudo cat %s" in текст
    подсказки = текст[текст.index('log "готово; проверить снаружи"'):]
    assert "--key-file ${KEY_FILE}" in подсказки
    assert "$(cat" not in подсказки, "значение ключа в подсказках не появляется"


def test_сухой_прогон_ключ_не_печатает(сухой):
    """Ветка зависит от состояния хоста: ключ либо создаётся, либо уже есть."""
    assert "ЗНАЧЕНИЕ КЛЮЧА" not in сухой
    assert ("сухой прогон] создать" in сухой
            or "ключ уже существует" in сухой), сухой[-400:]


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


def test_поворот_не_сохраняет_прежнее_значение():
    """И это тоже изменённое требование, с названной причиной.

    Прежде поворот сохранял прежнее значение с отметкой времени — чтобы
    вернуть доступ сборке, которая ещё не обновилась. После случая 11 октября
    правило обратное: поворот делают именно потому, что прежнее значение
    раскрыто, а копия раскрытого ключа на диске — тот же раскрытый ключ, только
    живущий дольше. Для возврата доступа достаточно нового значения из файла.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "before-rotate" not in текст, "копия прежнего значения вернулась"
    assert "копия НЕ сохраняется" in текст
    # След поворота остаётся, но без значения.
    assert "rotations.log" in текст and "key-%s" in текст


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


# --- доступ учётной записи к ключу ------------------------------------------
#
# Живой случай 2026-10-11. Владелец запустил установку, она создала ключ с
# правильными правами (`0640 root:claude`) и остановилась:
# «учётная запись claude не читает ключ». Причина была НЕ в файле: каталог
# `/etc/site-factory` — `0700 root:root`, то есть непроходим ни для кого, кроме
# root. Отказ этого не называл, и отличить неверные права файла от
# непроходимого пути было нечем.
#
# Выдать группе проход по `/etc/site-factory` значило бы открыть дорогу к
# настоящим серверным секретам, которые там лежат. Клиентский ключ серверным
# секретом не является (он уезжает в APK), поэтому у него теперь свой каталог
# с проходом ровно для нужной учётной записи.


def _функция_из_сценария(имя: str) -> str:
    """Текст одной функции сценария — чтобы проверить её, а не пересказ."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    начало = текст.index(f"{имя}() {{")
    конец = текст.index("\n}\n", начало) + 3
    return текст[начало:конец]


def test_ключ_живёт_в_своём_каталоге_а_не_среди_серверных_секретов():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'KEY_DIR="/etc/app-read-api"' in текст
    assert 'KEY_FILE="${KEY_DIR}/client-key"' in текст
    # Прежний путь остаётся упомянутым ТОЛЬКО как раскрытый, а не как рабочий.
    assert 'LEAKED_KEY_FILE="/etc/site-factory/secrets/app_client_key"' in текст
    assert "--key-file ${KEY_FILE}" in текст


def test_каталог_ключа_не_открыт_остальным():
    """0710: проход нужной записи, остальным ничего; перечисления нет ни у кого."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'install -d -m 0710 -o root -g "$RUN_USER" "$KEY_DIR"' in текст
    for запрещено in ("chmod 0755", "chmod 777", "chmod -R", "chown -R",
                      "chmod o+r", "chmod a+r"):
        assert запрещено not in текст, (
            f"{запрещено!r}: права открываются шире нужного или рекурсивно")


def test_права_чужих_секретов_не_меняются():
    """Единственное упоминание прежнего каталога — чтение и подсказка rm."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    for строка in текст.splitlines():
        if "/etc/site-factory" not in строка:
            continue
        assert not any(с in строка for с in ("chmod", "chown", "setfacl", "install -d")), (
            f"сценарий меняет права под /etc/site-factory: {строка.strip()!r}")


def test_значение_ключа_не_печатается_нигде():
    """Напечатанный ключ 11.10 попал в переписку — печати быть не должно."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "ЗНАЧЕНИЕ КЛЮЧА" not in текст
    assert "$(cat \"$KEY_FILE\")" not in текст
    assert "значение не печатается" in текст
    # Передача — через файл: названа команда чтения в момент внесения в CI.
    assert "sudo cat %s" in текст


def test_поворот_не_оставляет_копию_прежнего_значения():
    """Копия раскрытого ключа на диске — тот же раскрытый ключ, только дольше."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "before-rotate" not in текст, "копия прежнего значения не сохраняется"
    assert "копия НЕ сохраняется" in текст
    # В журнал идёт отметка без значения.
    assert "key-%s" in текст and "rotated" in текст


def test_поворот_перезапускает_службу_и_при_замене_без_флага():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'if [ "$rotate_key" = 1 ] || [ "$ROTATED" = 1 ]; then' in текст, (
        "замена ключа без флага тоже требует перезапуска: иначе служба "
        "продолжит принимать прежнее значение")


@pytest.mark.parametrize("непроходимый", ["верхний", "нижний"])
def test_отказ_называет_непроходимый_каталог(tmp_path, непроходимый):
    """Главное исправление диагностики: называется составляющая пути.

    Проверяется на настоящей файловой системе: каталог, снятый в режим 000,
    непроходим и для своего владельца (кроме root), поэтому случай
    воспроизводится без root и без боевых путей.
    """
    верхний = tmp_path / "верхний"
    нижний = верхний / "нижний"
    нижний.mkdir(parents=True)
    ключ = нижний / "client-key"
    ключ.write_text("не настоящий ключ", encoding="utf-8")
    ключ.chmod(0o640)
    закрытый = верхний if непроходимый == "верхний" else нижний
    закрытый.chmod(0o000)
    try:
        сценарий = (
            'RUN_USER="$(id -un)"\n'
            + _функция_из_сценария("as_run_user") + "\n"
            + _функция_из_сценария("why_unreadable") + "\n"
            + f'why_unreadable "{ключ}"\n')
        р = subprocess.run(["bash", "-c", сценарий], capture_output=True,
                           text=True, timeout=60)
        вывод = р.stdout + р.stderr
        assert "непроходим" in вывод, вывод
        assert str(закрытый) in вывод, вывод
    finally:
        закрытый.chmod(0o700)


def test_отказ_различает_нечитаемый_файл_при_проходимом_пути(tmp_path):
    ключ = tmp_path / "client-key"
    ключ.write_text("не настоящий ключ", encoding="utf-8")
    ключ.chmod(0o000)
    сценарий = (
        'RUN_USER="$(id -un)"\n'
        + _функция_из_сценария("as_run_user") + "\n"
        + _функция_из_сценария("why_unreadable") + "\n"
        + f'why_unreadable "{ключ}"\n')
    р = subprocess.run(["bash", "-c", сценарий], capture_output=True, text=True,
                       timeout=60)
    вывод = р.stdout + р.stderr
    assert "путь проходим" in вывод, вывод
    assert "сам файл не читается" in вывод, вывод


def test_читаемый_ключ_так_и_называется(tmp_path):
    ключ = tmp_path / "client-key"
    ключ.write_text("не настоящий ключ", encoding="utf-8")
    ключ.chmod(0o640)
    сценарий = (
        'RUN_USER="$(id -un)"\n'
        + _функция_из_сценария("as_run_user") + "\n"
        + _функция_из_сценария("why_unreadable") + "\n"
        + f'why_unreadable "{ключ}"\n')
    р = subprocess.run(["bash", "-c", сценарий], capture_output=True, text=True,
                       timeout=60)
    assert "файл читается" in (р.stdout + р.stderr)


def test_повторный_запуск_после_частичной_установки_безопасен():
    """Установка 11.10 остановилась на проверке ключа; повтор обязан доделать.

    Сторожится идемпотентность всех записывающих шагов: каталог и файлы — через
    `install`, ключ создаётся только при отсутствии (или по флагу), строка
    include добавляется только при отсутствии метки.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'if [ -s "$KEY_FILE" ] && [ "$rotate_key" != 1 ]; then' in текст
    assert "ключ уже существует: не перезаписываю" in текст
    assert 'if grep -q "$MARK" "$SITE_CONF"; then' in текст
    assert "повторная установка ничего не удвоит" in текст
    assert "--replace" not in текст


def test_откат_выпуска_возвращает_прежний_код_и_юнит():
    """Три возврата разные: снять службу (--rollback), вернуть прежний код
    (--rollback-release), вернуть ревизию главной (указатель в админке)."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    установка = текст.index('run install -m 0644 -o root -g root "$SERVICE_SCRIPT" "$INSTALLED_SCRIPT"')
    assert текст.index('"${INSTALLED_SCRIPT}.previous"') < установка, "прежний выпуск сохраняется до замены"
    откат = текст.split('if [ "$rollback_release" = 1 ]; then', 1)[1].split("exit 0", 1)[0]
    assert '"${INSTALLED_SCRIPT}.previous" "$INSTALLED_SCRIPT"' in откат
    assert '"${UNIT_PATH}.previous" "$UNIT_PATH"' in откат, "прежний код не знает новых аргументов запуска"
    assert "restart" in откат
    assert "$SNIPPET" not in откат and "KEY_FILE" not in откат, "маршрут и ключ откат выпуска не трогает"


def test_каталог_ревизий_создаётся_до_юнита():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert текст.index('"$CONFIG_DIR"\n') < текст.index("cat > \"$TMP_UNIT\""), \
        "ReadOnlyPaths с несуществующим путём не даёт службе стартовать"
    assert "ReadOnlyPaths=${DATA_DIR} ${INSTALL_DIR} ${CONFIG_DIR}" in текст
    assert "\nReadWritePaths=" not in текст, "служба по-прежнему ничего не пишет"
