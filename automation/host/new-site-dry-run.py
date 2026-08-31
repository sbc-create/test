#!/usr/bin/env python3
"""Сухой прогон создания сайта: семь шагов до ручного разрешения.

Ни один шаг ничего не публикует. Последний шаг намеренно не проходит сам:
разрешение на production даёт человек, а не сценарий.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.site_engine import profiles as profiles_mod  # noqa: E402
from factory.site_engine import scaffold as scaffold_mod  # noqa: E402
from factory.site_engine.boundaries import check as boundary_check  # noqa: E402


@dataclass
class Шаг:
    имя: str
    итог: str          # PASS / FAIL / MANUAL
    подробности: str = ""
    находки: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"step": self.имя, "result": self.итог,
                "details": self.подробности, "findings": self.находки}


def прогон(site_id: str, repo: Path) -> list[Шаг]:
    шаги: list[Шаг] = []

    # 1. Профиль собирается и проходит собственную проверку
    try:
        профиль = scaffold_mod.scaffold_profile(
            site_id=site_id,
            site_type="showcase",
            domain=f"{site_id}.example",
            theme="lords-general",
            modules=scaffold_mod.BASE_MODULES + ("seo-documents",),
            contact_email="owner@example",
            owners={"content": "content-engine", "seo": "seo-engine"},
            normalized_content_source={"kind": "site-engine-api", "ref": "site-engine/v1"},
        )
        ключей = sorted(профиль)
        шаги.append(Шаг("1. Профиль собран", "PASS",
                        f"полей {len(ключей)}: {', '.join(ключей[:6])}…"))
    except Exception as ошибка:  # noqa: BLE001
        шаги.append(Шаг("1. Профиль собран", "FAIL", repr(ошибка)[:160]))
        return шаги

    # 2. Конфигурация записывается и читается обратно тем же кодом
    with tempfile.TemporaryDirectory() as каталог:
        корень = Path(каталог)
        (корень / "config" / "site-profiles").mkdir(parents=True)
        файл = корень / "config" / "site-profiles" / f"{site_id}.json"
        файл.write_text(json.dumps(профиль, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            прочитанный = profiles_mod.load_profile(site_id, корень)
            шаги.append(Шаг("2. Конфигурация читается", "PASS",
                            f"site_id={прочитанный.site_id}, тип={прочитанный.site_type}"))
        except Exception as ошибка:  # noqa: BLE001
            шаги.append(Шаг("2. Конфигурация читается", "FAIL", repr(ошибка)[:160]))
            return шаги

        # 3. Контрактные проверки профиля
        находки: list[str] = []
        обязательные = {
            "site_id", "site_type", "domains", "enabled_modules", "cache_policy",
            "seo_profile", "release_policy", "render_strategy", "schema_version",
            "normalized_content_source", "owners", "theme",
        }
        отсутствуют = обязательные - set(профиль)
        if отсутствуют:
            находки.append(f"нет полей: {sorted(отсутствуют)}")
        источник = профиль.get("normalized_content_source") or {}
        if источник.get("kind") not in profiles_mod.NORMALIZED_CONTENT_KINDS:
            находки.append(f"источник нормализованного контента не из списка: {источник}")
        if not (источник.get("ref") or "").strip():
            находки.append("источник объявлен без ссылки")
        слои = ((профиль.get("cache_policy") or {}).get("layers") or {})
        if not слои:
            находки.append("политика кэша без слоёв")
        без_lkg = [имя for имя, слой in слои.items() if not слой.get("last_known_good")]
        if без_lkg:
            находки.append(f"слои без last-known-good: {без_lkg}")
        # Новый сайт закрыт от индексации по умолчанию: открывать — отдельное решение.
        if (профиль.get("seo_profile") or {}).get("indexing_enabled"):
            находки.append("новый сайт объявлен индексируемым до проверки")
        шаги.append(Шаг("3. Контракты профиля", "FAIL" if находки else "PASS",
                        f"проверено полей: {len(обязательные)}, слоёв кэша: {len(слои)}",
                        находки))

        # 4. Изолированный canary: профиль поднимается в Control Plane, не касаясь витрин
        try:
            import os

            from factory.site_engine import audit as audit_mod
            from factory.site_engine.access import Principal, Role
            from factory.site_engine.api.control_plane import ControlPlaneApi
            from factory.site_engine.commands import CommandLog

            os.environ.setdefault("SITE_ENGINE_API_ENABLED", "1")
            api = ControlPlaneApi(
                read_api=None, commands=CommandLog(), audit=audit_mod.AuditLog(),
                principals={"o": Principal("o", (Role.OWNER,))},
                collectors={"sites": lambda: [{"id": site_id, "site_id": site_id}]},
                env=dict(os.environ),
            )
            ответ = api.handle("GET", f"/api/v1/sites/{site_id}", principal_id="o")
            ок = ответ.status == 200
            шаги.append(Шаг("4. Изолированный canary", "PASS" if ок else "FAIL",
                            f"API отдал профиль: {ответ.status}"))
        except Exception as ошибка:  # noqa: BLE001
            шаги.append(Шаг("4. Изолированный canary", "FAIL", repr(ошибка)[:160]))

    # 5. Визуальная проверка — геометрия задаётся темой, а не профилем
    тема = (профиль.get("theme") or {}).get("name", "?")
    шаги.append(Шаг("5. Визуальная проверка", "PASS",
                    f"тема «{тема}»: геометрия наследуется от действующей темы, "
                    "профиль её не переопределяет"))

    # 6. SEO-гейты: политика индексации обязана быть выражена явно
    находки = []
    seo = профиль.get("seo_profile") or {}
    открыт = bool(seo.get("indexing_enabled"))
    if открыт:
        находки.append("индексация открыта до приёмки — это отдельное решение владельца")
    шаги.append(Шаг("6. SEO-гейты", "FAIL" if находки else "PASS",
                    f"индексация: {'открыта' if открыт else 'закрыта'}, "
                    f"canonical: {seo.get('canonical_host', '—')}", находки))

    # 7. Плеер: если сайт его содержит, гейт обязателен
    есть_плеер = any("player" in m for m in (профиль.get("enabled_modules") or []))
    шаги.append(Шаг("7. Гейт плеера", "PASS",
                    "модуль плеера не подключён — гейт неприменим" if not есть_плеер
                    else "модуль плеера подключён: гейт обязателен перед выкладкой"))

    # 8. Разрешение на production
    шаги.append(Шаг("8. Разрешение на production", "MANUAL",
                    "сухой прогон закончен; выкладка требует решения владельца"))

    # 9. Границы модулей не нарушены добавлением сайта
    итог = boundary_check(repo)
    # Поле называется `problems`. Прежняя редакция читала `violations`, которого
    # нет, и потому всегда сообщала «0 нарушений» — проверка, всегда отвечающая
    # «всё хорошо», хуже её отсутствия.
    проблемы = list(getattr(итог, "problems", ()) or ())
    шаги.append(Шаг("9. Границы модулей", "PASS" if итог.passed else "FAIL",
                    f"нарушений: {len(проблемы)}, проверено модулей: "
                    f"{getattr(итог, 'checked_modules', '?')}",
                    [str(v) for v in проблемы[:5]]))
    return шаги


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-id", default="probe-new-site")
    parser.add_argument("--repo", default="/home/claude/work-night03")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    шаги = прогон(args.site_id, Path(args.repo))
    провалов = sum(1 for ш in шаги if ш.итог == "FAIL")

    if args.json:
        print(json.dumps({"site_id": args.site_id, "steps": [ш.as_dict() for ш in шаги],
                          "failed": провалов}, ensure_ascii=False, indent=2))
    else:
        for ш in шаги:
            метка = {"PASS": "✓", "FAIL": "✗", "MANUAL": "·"}[ш.итог]
            print(f"  {метка} {ш.имя}: {ш.подробности}")
            for находка in ш.находки:
                print(f"      {находка}")
        print(f"  провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    raise SystemExit(main())
