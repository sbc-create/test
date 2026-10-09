"""Секрет модерации комментариев Yummy не едет переменной compose.

Зачем это проверять. Снять опубликованный комментарий может только маршрут
модерации приложения, и он работает лишь при `ADMIN_MODERATION_SECRET` не
короче 16 знаков (`src/modules/admin/session.ts`). Пока секрета нет, маршрут
отвечает 503 `not_configured`, то есть у публикации нет отката — измерено
2026-10-09, и первая же ошибочная запись оказалась неудаляемой.

Способ доставки задан не вкусом, а самим образом: его entrypoint читает токены
провайдера из файла и прямо объясняет, почему не переменной — «значение,
объявленное в compose `environment:`, видно в `docker inspect`, в
`docker compose config` и в любом дампе окружения контейнера».

Отсюда три свойства, которые держат эти проверки:

* секрет объявляется compose-секретом (Docker подкладывает его в
  `/run/secrets` правами демона, поэтому на хосте файл остаётся 0600 у
  `claude`, а контейнерный пользователь `node` его читает);
* в `environment:` его нет ни у одного сервиса;
* точка входа не содержит ни одного символа `$`. Это не косметика: compose
  подставляет свои переменные в значения, и `$ADMIN_MODERATION_SECRET`
  превратился бы в пустоту, а `$$` — в номер процесса оболочки. Тогда
  приложение стартовало бы с мусорным секретом, и модерация выглядела бы
  настроенной, не будучи ею.
"""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover — окружение без PyYAML
    yaml = None

НАЛОЖЕНИЕ = (pathlib.Path(__file__).resolve().parents[2]
             / "automation" / "host" / "yummy-overlays.override.yaml")
СЕРВИСЫ_С_МОДЕРАЦИЕЙ = ("web-org", "web-site", "web-biz")


@pytest.fixture(scope="module")
def состав() -> dict:
    if yaml is None:
        pytest.skip("нет PyYAML")
    return yaml.safe_load(НАЛОЖЕНИЕ.read_text(encoding="utf-8"))


def test_секрет_объявлен_compose_секретом(состав):
    объявленные = состав.get("secrets") or {}
    # Третий тенант добавлен в ночь 9→10 октября: у web-biz публикация
    # комментариев была бы необратимой, пока маршрут снятия отвечает 503.
    assert set(объявленные) == {"moderation_org", "moderation_site",
                                "moderation_biz"}, объявленные
    for имя, запись in объявленные.items():
        путь = pathlib.Path(запись["file"])
        assert путь.is_absolute() and "runtime/moderation" in str(путь), запись
        assert ".." not in str(путь)
        # Источник лежит ВНЕ репозитория: иначе секрет уехал бы в git.
        assert not str(путь).startswith(str(НАЛОЖЕНИЕ.parents[2])), путь


#: Какой секрет принадлежит какому сервису. Тенанты значение не делят: один
#: секрет на всех означал бы, что модератор одной витрины снимает комментарии
#: на соседней.
СЕКРЕТ_СЕРВИСА = {"web-org": "moderation_org", "web-site": "moderation_site",
                  "web-biz": "moderation_biz"}


def test_сервисы_получают_свой_секрет(состав):
    for имя in СЕРВИСЫ_С_МОДЕРАЦИЕЙ:
        сервис = состав["services"][имя]
        секреты = сервис.get("secrets") or []
        assert секреты == [СЕКРЕТ_СЕРВИСА[имя]], (имя, секреты)
        чужие = [с for с in СЕКРЕТ_СЕРВИСА.values() if с != СЕКРЕТ_СЕРВИСА[имя]]
        assert not set(секреты) & set(чужие), (имя, секреты)


def test_в_переменных_окружения_секрета_нет(состав):
    for имя, сервис in (состав.get("services") or {}).items():
        окружение = сервис.get("environment") or {}
        assert "ADMIN_MODERATION_SECRET" not in окружение, (
            f"{имя}: значение в `environment:` видно в docker inspect и в "
            "docker compose config — так секрет не передают")


def test_точка_входа_без_подстановок(состав):
    for имя in СЕРВИСЫ_С_МОДЕРАЦИЕЙ:
        точка = состав["services"][имя]["entrypoint"]
        assert точка[:2] == ["/bin/sh", "-c"], (имя, точка[:2])
        строка = точка[2]
        assert "$" not in строка, (
            f"{имя}: compose подставляет переменные в значения, поэтому символ "
            "$ здесь означает либо пустоту, либо номер процесса")
        assert "/run/secrets/" in строка, имя
        # Пустой или короткий секрет — отказ ЗАПУСКА, а не тихий старт без
        # модерации: иначе снятие комментария осталось бы невозможным.
        assert "exit 64" in строка and "16,"in строка, строка
        # Штатная точка входа образа запускается без изменений: миграции и
        # чтение токенов провайдера остаются её работой.
        assert строка.rstrip().endswith("exec ./scripts/docker-entrypoint.staging.sh"), строка


def test_показ_накладок_не_потерян(состав):
    """Наложение отвечает и за показ текстов: одно не должно вытеснить другое."""
    for имя in СЕРВИСЫ_С_МОДЕРАЦИЕЙ:
        сервис = состав["services"][имя]
        окружение = сервис.get("environment") or {}
        assert окружение.get("TITLE_OVERLAYS_PATH") == (
            "/app/content/overlays/title-overlays.json"), имя
        цели = [т.get("target") for т in сервис.get("volumes") or []]
        assert "/app/content/overlays" in цели, имя
