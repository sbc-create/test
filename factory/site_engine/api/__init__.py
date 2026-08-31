"""Site Engine API v1 — только чтение, выключен по умолчанию.

Каркас существует, чтобы доказать вертикальный путь: профиль сайта → адаптер →
нормализованная модель → ответ. Он читает через публичные интерфейсы модулей и
не обращается ни к API поставщика, ни к базе витрины.

Почему выключен по умолчанию: включённый по умолчанию маршрут однажды
оказывается доступным снаружи, и узнаёт об этом не автор. Включение —
осознанное действие, а не поведение по умолчанию.
"""
from factory.site_engine.api.app import SiteEngineApi, create_api  # noqa: F401
from factory.site_engine.api.control_plane import ControlPlaneApi  # noqa: F401
from factory.site_engine.api.openapi_v1 import spec as control_plane_spec  # noqa: F401
from factory.site_engine.api.openapi_v1 import write as write_control_plane_spec  # noqa: F401

__all__ = [
    "SiteEngineApi",
    "create_api",
    # Control Plane выведен наружу намеренно: интерфейс управления обязан
    # обращаться к движку через публичный интерфейс, а не к его внутренностям.
    # Гейт границ поймал ровно это — сначала у CMS, написанной в этой же задаче.
    "ControlPlaneApi",
    "control_plane_spec",
    "write_control_plane_spec",
]
