"""Адаптеры внешних провайдеров.

Здесь же — то, чем пакет пользуются снаружи. Конкретный адаптер берут по имени
(`providers.fake`), а общий тип отказа — отсюда: `ProviderError` принадлежит не
какому-то одному провайдеру, а самому понятию провайдера, и потребителю незачем
знать, что он объявлен в `base.py`.
"""
from factory.site_engine.provisioner.providers.base import ProviderError

__all__ = ["ProviderError"]
