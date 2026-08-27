"""REQ-BACKUP-UNIT-PRIVILEGE: юнит бэкапа способен прочитать то, что обязан сохранить.

История отказа, ради которой этот файл существует. Скрипт бэкапа собирает
шифрованное хранилище Secret Hub — без него из архива нельзя восстановить
consumer-файлы, потому что те исключены как открытые секреты. Хранилище лежит
под 0700 root:root, а юнит был объявлен `User=claude`. Значит ни один запуск не
мог создать восстановимую копию: каждую ночь `rsync` получал EACCES, бэкап падал
целиком, подтверждённая копия старела, и `site-factory-health` начинал падать
каждые пятнадцать минут — уже не по своей вине.

Соблазнительных «исправлений» два, и оба хуже болезни: исключить хранилище из
архива (получится копия, из которой нельзя восстановиться) или ослабить права
самого хранилища (сломанный бэкап меняется на более слабый секрет). Поэтому
проверяется пара: юнит запускается с достаточными правами И остаётся при этом
ограниченным. Одно без другого — не исправление.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNIT = REPO / "automation" / "host" / "systemd" / "site-factory-backup.service"
SCRIPT = REPO / "automation" / "host" / "site-factory-backup.sh"
REGISTRY = REPO / "config" / "secret-hub.json"


def unit_text() -> str:
    return UNIT.read_text(encoding="utf-8")


def directive(name: str) -> list[str]:
    """Значения директивы из [Service], без комментариев."""
    values = []
    for line in unit_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            values.append(value.strip())
    return values


def store_dir() -> str:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return registry.get("store_dir") or "/var/lib/site-factory-secret-hub"


class TestUnitCanReadWhatItMustArchive:
    def test_unit_is_not_pinned_to_an_unprivileged_user(self):
        """`User=claude` и 0700 root:root — взаимоисключающие требования."""
        users = [u for u in directive("User") if u not in ("root", "0")]
        assert not users, (
            f"юнит объявлен User={users[0]!r}, а хранилище Secret Hub "
            f"({store_dir()}) намеренно закрыто под root. Такой запуск не может "
            "создать восстановимую копию — только упасть на EACCES"
        )

    def test_script_still_refuses_when_the_store_is_unreadable(self):
        """Права юнита не отменяют проверку: регрессия должна быть слышной."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert re.search(r'\[ ! -r "\$HUB_STORE_DIR" \]', text), (
            "скрипт перестал проверять доступность хранилища: молчаливый пропуск "
            "снова даст архив, из которого нельзя восстановиться"
        )


class TestPrivilegeStaysConfined:
    """Права подняты ровно настолько, насколько нужно, и не шире."""

    def test_writes_are_limited_to_backups_and_logs(self):
        paths = " ".join(directive("ReadWritePaths"))
        assert paths, "юнит не ограничивает, куда ему можно писать"
        allowed = set(paths.split())
        assert allowed <= {"/srv/backups", "/var/log/site-factory"}, (
            f"бэкапу разрешена запись за пределами своих каталогов: {sorted(allowed)}"
        )

    def test_filesystem_is_read_only_by_default(self):
        assert directive("ProtectSystem") == ["strict"], (
            "ProtectSystem=strict обязателен: привилегированный процесс без него "
            "может писать куда угодно"
        )

    def test_no_new_privileges_and_private_tmp(self):
        assert directive("NoNewPrivileges") == ["yes"]
        assert directive("PrivateTmp") == ["yes"]

    def test_master_key_directory_is_inaccessible(self):
        """Ключ и шифртекст в одном процессе — это шифрование как украшение."""
        from factory.secret_hub import crypto

        key_dir = str(Path(crypto.DEFAULT_KEY_FILE).parent)
        blocked = " ".join(directive("InaccessiblePaths")).split()
        assert key_dir in blocked, (
            f"каталог мастер-ключа {key_dir} доступен процессу бэкапа; "
            "он обязан быть недоступен, а не только исключён из архива"
        )

    def test_network_is_closed(self):
        """Бэкап работает с локальной файловой системой и никуда не ходит."""
        assert directive("PrivateNetwork") == ["yes"], (
            "сеть открыта процессу, которому она не нужна"
        )

    def test_encrypted_store_is_readable_but_not_writable(self):
        readonly = " ".join(directive("ReadOnlyPaths")).split()
        assert store_dir() in readonly, (
            f"{store_dir()} не объявлен доступным на чтение — при ProtectSystem=strict "
            "и InaccessiblePaths это легко потерять молча"
        )
        assert store_dir() not in " ".join(directive("ReadWritePaths")).split(), (
            "бэкапу разрешено писать в хранилище Secret Hub; он обязан только читать"
        )
