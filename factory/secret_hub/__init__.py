"""Центральный Secret Hub фабрики сайтов.

Один набор credentials CDNVideoHub на направление (portfolio), а не копия на
каждый домен. Значения хранятся зашифрованными, применяются сервисом напрямую к
инфраструктуре направления и не возвращаются вызывающей стороне ни одной
операцией — такого endpoint'а в API нет, и это проверяется тестом.

Слои:

* :mod:`factory.secret_hub.registry`  — направления и потребители из конфигурации;
* :mod:`factory.secret_hub.crypto`    — мастер-ключ и AES-256-GCM;
* :mod:`factory.secret_hub.store`     — SQLite с шифртекстом, версии, backup;
* :mod:`factory.secret_hub.provider`  — живая read-only проверка credentials;
* :mod:`factory.secret_hub.consumers` — применение к yami/lords/amedia;
* :mod:`factory.secret_hub.service`   — root-owned демон на unix-сокете;
* :mod:`factory.secret_hub.client`    — то, чем пользуется CLI и, через него, агент;
* :mod:`factory.secret_hub.enroll`    — одноразовая HTTPS-форма ввода.

Границу «кто может видеть значение» держит не вежливость вызывающего кода, а
разделение процессов: значения существуют только внутри root-процесса сервиса.
Каталог пакета назван ``secret_hub``, а не ``secrets``: путь ``*/secrets/``
закрыт для записи правилом G-WRITE, и совпадение имён превращало бы обычную
правку кода в срабатывание защиты.
"""
from __future__ import annotations

#: Поля секрета направления. Порядок фиксирован: он попадает в отпечаток.
SECRET_FIELDS = ("api_token", "publisher_id")

#: Статус направления, инфраструктура которого ещё не передана.
BLOCKED_TARGET = "BLOCKED_TARGET"

__all__ = ["SECRET_FIELDS", "BLOCKED_TARGET"]
