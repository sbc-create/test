"""Адаптеры существующих реализаций к нормализованной модели.

Адаптер читает то, что уже работает, и переводит в общий контракт. Он
ничего не меняет в живом поведении — в этом весь смысл: подключить, а не
переписать. Поставщики и рендереры лежат в разных файлах, потому что это
разные модули реестра с разными разрешёнными зависимостями.
"""
from factory.site_engine.adapters import (  # noqa: F401
    lords,
    lords_renderer,
    yummy,
    yummy_renderer,
)

__all__ = ["lords", "lords_renderer", "yummy", "yummy_renderer"]


# --- производители связей `seo-route-binding` --------------------------------
#
# Реестр живёт здесь, а не в универсальном модуле выдачи: он по необходимости
# знает, какой адаптер обслуживает какой способ адресации, а адаптеры для того
# и существуют, чтобы знать про конкретную реализацию. Гейт границ это и
# потребовал, поймав имя семьи витрин в модуле API.
#
# Вид производителя описывает **способ получения адреса**, а не семью витрин:
#
#   computed-routes  — адрес вычисляется функцией движка витрины и её же
#                      правилом разведения совпадений;
#   declared-routes  — витрина объявляет соответствие сама, таблицей маршрутов.
#
# Список закрыт: третий способ — это новый адаптер, а не строка в настройке.
PRODUCERS: tuple[str, ...] = ("computed-routes", "declared-routes")


def _неизвестен(kind: str) -> LookupError:
    """Один отказ на все входы: иначе один изъян настройки даёт потребителю
    вежливое «нет такого» в одном месте и поломку сервера в другом."""
    return LookupError(
        f"производитель {kind!r} неизвестен: разрешены {', '.join(PRODUCERS)}. "
        "Новый способ адресации — это новый адаптер, а не строка в настройке")


def export_bindings(kind: str, *, root, site_id: str, spec: dict):
    """Выгрузка связей витрины производителем названного вида."""
    if kind == "computed-routes":
        from factory.site_engine.adapters import lords_seo_binding as producer

        return producer.export(root / str(spec.get("catalog") or ""),
                               site_id=site_id)
    if kind == "declared-routes":
        from factory.site_engine.adapters import yummy_seo_binding as producer

        return producer.export(root / str(spec.get("routes") or ""),
                               root / str(spec.get("catalog") or ""),
                               site_id=site_id)
    raise _неизвестен(kind)


def page_shape(kind: str, path: str):
    """Тип страницы и ключ произведения по адресу — правилами адресации витрины."""
    if kind == "declared-routes":
        from factory.site_engine.adapters import yummy_seo_binding as producer

        return producer.page_type_of(path)
    if kind == "computed-routes":
        # У витрин с вычисляемым адресом вложенных страниц произведения нет:
        # сезон и серия там адресуются иначе и отдельным типом страницы.
        части = [c for c in (path or "").split("/") if c]
        if len(части) == 2 and части[0] == "title":
            return "title", части[1]
        return "", ""
    raise _неизвестен(kind)


def route_for(kind: str, key: str) -> str:
    """Маршрут страницы произведения по ключу."""
    if kind == "declared-routes":
        from factory.site_engine.adapters import yummy_seo_binding as producer

        return producer.route_of(key)
    if kind == "computed-routes":
        return f"/title/{key}/"
    raise _неизвестен(kind)
