"""Окружение стенда — одно на все инструменты, которые его поднимают.

Три инструмента поднимали стенд и задавали окружение каждый своей копией:
`browser_multisite.py`, `cross_site_uniqueness.py`, `frontend_http.py`.
Копии уже разошлись — у одной есть заведомо поддельный токен для проверки
утечки и порт, у двух других нет, — и разойтись дальше им ничто не мешало.

Цена расхождения не теоретическая. Проверки пошли бы по разным настройкам,
объявляя одно и то же поведение проверенным, а «Publisher ID не попадает в
страницу» подтверждалось бы там, где токена в окружении и не было.

Здесь общая часть и только она. Своё каждый инструмент добавляет сам: у него на
то свои причины, и сводить их в одно место значило бы связать несвязанное.
"""

from __future__ import annotations

import os

#: Идентификаторы издателя для трёх витрин стенда. Не секреты: это заведомо
#: стендовые значения, и настоящий Publisher ID приходит из области секретов,
#: а не отсюда.
PUBLISHERS = {
    "PLAYER_PUBLISHER_ID_A": "stand-publisher-a",
    "PLAYER_PUBLISHER_ID_B": "stand-publisher-b",
    "PLAYER_PUBLISHER_ID_C": "stand-publisher-c",
}

#: Заведомо «секретное» значение. Настоящим секретом не является и им быть не
#: может: оно существует ровно затем, чтобы проверка искала его в собранных
#: страницах и не находила. Настоящий токен в стенд не передаётся никогда.
LEAK_CANARY_TOKEN = "stand-content-api-token-must-not-leak"


def stand_environment(*, port: int | None = None, with_leak_canary: bool = False) -> dict:
    """Окружение процесса стенда поверх текущего.

    `with_leak_canary` включает заведомо поддельный токен: его добавляют те
    инструменты, которые затем ищут его в выдаче. Включать его везде было бы
    соблазнительно и неверно — проверка, которая ничего не ищет, от наличия
    значения в окружении не становится строже, зато выглядит строже.
    """
    env = dict(os.environ)
    env.update(PUBLISHERS)
    env.update({"PLAYER_MODE": "mock", "FACTORY_ENVIRONMENT": "staging"})
    if with_leak_canary:
        env["CDNVIDEOHUB_API_TOKEN"] = LEAK_CANARY_TOKEN
    if port is not None:
        env["FACTORY_MULTISITE_PORT"] = str(port)
    return env


__all__ = ["LEAK_CANARY_TOKEN", "PUBLISHERS", "stand_environment"]
