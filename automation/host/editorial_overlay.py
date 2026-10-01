"""ОБЩИЙ ИСТОЧНИК читателя редакторских правок для семейства Lords/Zona.

Этот файл — источник шаблона, а не копия сайта. Новый сайт получает его через
`factory.cell.newsite` (`РАНТАЙМ_LORDS`), существующий — обычным выпуском.

Почему он здесь, а не заводится заново каждому домену. Поддержка редакторских
данных — обязательная часть архитектуры шаблона, а не доработка под домен.
Пока читателя не было в источнике, каждый новый сайт создавался без
возможности показать написанный текст, и подключение приходилось повторять
вручную — именно это и потребовалось трижды (an1meg0.site, an1mego.site,
animeg0.site), прежде чем стало ясно, что проблема не в доменах.

Модуль перенесён из `var/site-repos/zonafilm-space/src/editorial_overlay.py`,
где он работает и проверен: `/__editorial_status` отвечает 200, правки
накладываются при показе, чужой `site_id` не применяется. Ниже — его текст без
изменений смысла; расхождение с работающей витриной было бы худшим из
возможных исходов.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: Поля, которые редактор вправе изменить. Список намеренно короткий: всё
#: остальное принадлежит поставщику, и правка там означала бы, что витрина
#: спорит с источником, а не дополняет его.
#:
#: Совпадает с `factory.site_engine.editorial.OVERRIDABLE_FIELDS` плюс
#: `description` и SEO-поля: их правка — основной сценарий редактора, а без
#: них админка умеет менять обложку и год, но не текст, ради которого её и
#: заводят.
ПОЛЯ_ЗАПИСИ = ("name", "original_name", "poster_url", "year", "kind")
ПОЛЯ_ПОДРОБНОСТЕЙ = ("description", "seo_title", "seo_description")
ВСЕ_ПОЛЯ = ПОЛЯ_ЗАПИСИ + ПОЛЯ_ПОДРОБНОСТЕЙ

#: Как поле правки называется в данных витрины.
В_ЗАПИСИ = {"name": "title", "poster_url": "poster", "year": "year", "kind": "kind",
            "original_name": "original_title"}
В_ПОДРОБНОСТЯХ = {"description": "description", "seo_title": "seo_title",
                  "seo_description": "seo_description"}


class Правки:
    """Опубликованные правки одного сайта, перечитываемые по mtime."""

    def __init__(self, путь: str | os.PathLike[str], site_id: str) -> None:
        self.путь = Path(путь)
        self.site_id = site_id
        self.mtime = 0.0
        self.по_записям: dict[str, dict[str, Any]] = {}
        self.причина: str = "не читались"
        self.перечитать()

    @property
    def есть(self) -> bool:
        return bool(self.по_записям)

    def перечитать(self) -> bool:
        """True, если состав правок изменился."""
        try:
            свежий = self.путь.stat().st_mtime
        except OSError:
            if self.по_записям or self.причина == "не читались":
                self.по_записям = {}
                self.причина = "файла правок нет"
                return True
            return False
        if свежий <= self.mtime and self.причина == "прочитано":
            return False
        try:
            сырое = json.loads(self.путь.read_text(encoding="utf-8"))
        except (OSError, ValueError) as ош:
            # Испорченный файл не должен ронять витрину и не должен молча
            # означать «правок нет»: причина называется в /__editorial_status.
            self.по_записям = {}
            self.причина = f"файл не читается: {type(ош).__name__}"
            self.mtime = свежий
            return True
        чей = str(сырое.get("site_id") or "")
        if чей != self.site_id:
            self.по_записям = {}
            self.причина = (f"файл принадлежит сайту {чей!r}, а читает его "
                            f"{self.site_id!r}: правки не применяются")
            self.mtime = свежий
            return True
        собрано: dict[str, dict[str, Any]] = {}
        for ключ, запись in (сырое.get("overrides") or {}).items():
            поля = {к: з for к, з in (запись.get("fields") or {}).items()
                    if к in ВСЕ_ПОЛЯ and з not in (None, "")}
            if поля:
                собрано[str(ключ)] = поля
        self.по_записям = собрано
        self.причина = "прочитано"
        self.mtime = свежий
        return True

    def для(self, идентификатор: str | None, slug: str | None = None) -> dict[str, Any]:
        """Правки этой записи. Ключ — постоянный ID, slug — запасной."""
        if not self.по_записям:
            return {}
        if идентификатор and идентификатор in self.по_записям:
            return self.по_записям[идентификатор]
        if slug and slug in self.по_записям:
            return self.по_записям[slug]
        return {}

    def наложить_на_запись(self, запись: dict) -> dict:
        поля = self.для(str(запись.get("id") or ""), запись.get("slug"))
        if not поля:
            return запись
        новая = dict(запись)
        for поле in ПОЛЯ_ЗАПИСИ:
            if поле in поля:
                новая[В_ЗАПИСИ[поле]] = поля[поле]
        новая["_edited"] = True
        return новая

    def наложить_на_деталь(self, деталь: dict, slug: str | None = None) -> dict:
        if not isinstance(деталь, dict):
            return деталь
        поля = self.для(str(деталь.get("id") or ""), slug)
        if not поля:
            return деталь
        новая = dict(деталь)
        for поле in ПОЛЯ_ПОДРОБНОСТЕЙ:
            if поле in поля:
                новая[В_ПОДРОБНОСТЯХ[поле]] = поля[поле]
        новая["_edited"] = True
        return новая

    def состояние(self) -> dict[str, Any]:
        """Машинно читаемый ответ «почему правок не видно»."""
        return {"path": str(self.путь), "site_id": self.site_id,
                "status": self.причина, "entries": len(self.по_записям),
                "mtime": self.mtime}
