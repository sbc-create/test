"""План сайта Lords: какие поверхности он создаёт и почему.

План считается из manifest, профиля и состояний типов контента — без сети и без
учётных данных. Это сознательно: проектирование, проверка непересекаемости и
ворота дублей не должны ждать токена. Токен нужен, чтобы наполнить разделы
данными, а не чтобы понять, какие разделы бывают.

Раздел появляется в плане, только если выполнены оба условия: тип контента, от
которого раздел зависит, находится в состоянии `enabled`, и профиль сайта его
либо владеет, либо держит как навигацию. Ни одно другое состояние поверхностей
не создаёт — ни маршрута, ни пункта меню, ни URL в sitemap, ни SEO-страницы, ни
внутренней ссылки, ни фасета, ни результата поиска.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from factory.lords import content_types as ct
from factory.paths import PATHS
from factory.seo.uniqueness import PageObservation

BLUEPRINT_DIR = "blueprints/lords"
#: Раздел, зависящий от «любого» типа, живёт, пока активен хоть один тип.
ANY = "any"
#: Раздел, который каждый сайт держит и индексирует сам (главная).
OWNER_SELF = "self"
#: Раздел, который не индексирует никто: он служебный (поиск).
OWNER_NONE = "none"


@dataclass(frozen=True)
class PlannedPage:
    site_id: str
    section: str
    path: str
    page_type: str
    owner_profile: str
    owned: bool
    indexable: bool
    in_menu: bool
    in_sitemap: bool
    title: str = ""
    h1: str = ""
    description: str = ""
    own_text: str = ""
    canonical: str = ""
    #: Собственный хост сайта. Без него CSU-7 не с чем сравнивать canonical.
    site_host: str = ""

    def observation(self, site_name: str = "") -> PageObservation:
        return PageObservation(
            site_id=self.site_id,
            path=self.path,
            page_type=self.page_type,
            indexable=self.indexable,
            title=self.title,
            description=self.description,
            h1=self.h1,
            own_text=self.own_text,
            canonical=self.canonical,
            site_name=site_name,
            site_host=self.site_host,
        )

    def as_dict(self) -> dict:
        return {
            "section": self.section,
            "path": self.path,
            "page_type": self.page_type,
            "owner_profile": self.owner_profile,
            "owned": self.owned,
            "indexable": self.indexable,
            "in_menu": self.in_menu,
            "in_sitemap": self.in_sitemap,
            "title": self.title,
            "h1": self.h1,
            "description": self.description,
        }


@dataclass
class SitePlan:
    site_id: str
    profile: str
    pages: list[PlannedPage] = field(default_factory=list)
    type_states: dict = field(default_factory=dict)
    absent: list[dict] = field(default_factory=list)

    @property
    def indexable_paths(self) -> list[str]:
        return sorted(page.path for page in self.pages if page.indexable)

    @property
    def sitemap_paths(self) -> list[str]:
        return sorted(page.path for page in self.pages if page.in_sitemap)

    @property
    def menu_paths(self) -> list[str]:
        return sorted(page.path for page in self.pages if page.in_menu)

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "profile": self.profile,
            "content_types": {n: s.as_dict() for n, s in self.type_states.items()},
            "type_state_counts": ct.counts(self.type_states),
            "pages": [p.as_dict() for p in self.pages],
            "absent_sections": self.absent,
            "counts": {
                "pages": len(self.pages),
                "indexable": len(self.indexable_paths),
                "sitemap": len(self.sitemap_paths),
                "menu": len(self.menu_paths),
            },
        }


def _root(root: Path | None) -> Path:
    return Path(root) if root else PATHS.root


def load_blueprint(root: Path | None = None) -> dict:
    path = _root(root) / BLUEPRINT_DIR / "blueprint.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_profiles(root: Path | None = None) -> dict[str, dict]:
    """Профили направления по имени. Профиль без файла — ошибка, а не пустышка."""
    directory = _root(root) / BLUEPRINT_DIR / "profiles"
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        name = data.get("profile")
        if not name:
            raise ValueError(f"{path}: профиль без поля profile")
        out[name] = data
    return out


def owners(profiles: dict[str, dict]) -> dict[str, str]:
    """Раздел → профиль-владелец. Двойное владение — ошибка конфигурации.

    Именно это правило делает четыре сайта четырьмя сайтами, а не четырьмя
    копиями: индексируемую версию раздела отдаёт ровно один из них.
    """
    out: dict[str, str] = {}
    for name, profile in sorted(profiles.items()):
        for section in profile.get("owns") or []:
            if section in out:
                raise ValueError(
                    f"раздел «{section}» объявлен во владении и у «{out[section]}», и у «{name}»"
                )
            out[section] = name
    return out


def _satisfied(requires: str, states: dict[str, ct.TypeState]) -> bool:
    if requires == ANY:
        return any(state.active for state in states.values())
    state = states.get(requires)
    return bool(state and state.active)


def _blocking_reason(requires: str, states: dict[str, ct.TypeState]) -> tuple[str, str]:
    """Состояние и причина, по которым раздел не появился."""
    if requires == ANY:
        blocking = [s for s in states.values() if not s.active]
        state = blocking[0] if blocking else None
    else:
        state = states.get(requires)
    if state is None:
        return ct.DISABLED_BY_CONFIG, f"тип «{requires}» не объявлен"
    return state.state, state.reason


def build_plan(
    package: dict,
    *,
    credentials_available: bool = False,
    api_capabilities: set | None = None,
    root: Path | None = None,
) -> SitePlan:
    """План одного сайта направления Lords."""
    site_id = str(package.get("site_id", ""))
    tenant = package.get("tenant") or {}
    profile_name = str(tenant.get("seo_profile") or "")
    profiles = load_profiles(root)
    if profile_name not in profiles:
        raise ValueError(f"{site_id}: профиль «{profile_name}» отсутствует в {BLUEPRINT_DIR}/profiles")

    blueprint = load_blueprint(root)
    sections = blueprint["sections"]
    owner_of = owners(profiles)
    states = ct.resolve(
        package,
        credentials_available=credentials_available,
        api_capabilities=api_capabilities,
    )

    domain = package.get("domain")
    indexing_enabled = bool(package.get("seo_indexing_enabled", False))
    my_profile = profiles[profile_name]
    my_sections = my_profile.get("sections") or {}

    plan = SitePlan(site_id=site_id, profile=profile_name, type_states=states)

    for section, spec in sections.items():
        requires = spec.get("requires", ANY)
        declared = spec.get("owner")
        if declared == OWNER_SELF:
            owner = profile_name
        elif declared == OWNER_NONE:
            owner = OWNER_NONE
        else:
            owner = owner_of.get(section)
        if owner is None:
            raise ValueError(f"раздел «{section}» не имеет владельца среди профилей")

        if not _satisfied(requires, states):
            state, reason = _blocking_reason(requires, states)
            plan.absent.append({
                "section": section,
                "path": spec["path"],
                "requires": requires,
                "state": state,
                "reason": reason,
            })
            continue

        owned = owner == profile_name and declared != OWNER_NONE
        text = my_sections.get(section) or {}
        canonical = f"https://{domain}{spec['path']}" if domain else ""

        plan.pages.append(PlannedPage(
            site_id=site_id,
            section=section,
            path=spec["path"],
            page_type=spec.get("page_type", "category"),
            owner_profile=owner,
            owned=owned,
            # Владелец индексирует раздел; остальные держат его как навигацию.
            indexable=owned,
            in_menu=True,
            in_sitemap=bool(owned and indexing_enabled and domain),
            title=str(text.get("title", "")) if owned else "",
            h1=str(text.get("h1", "")) if owned else "",
            description=str(text.get("description", "")) if owned else "",
            own_text=str(text.get("intro", "")) if owned else "",
            canonical=canonical if owned else "",
            site_host=str(domain or ""),
        ))

    return plan


def observations(plans: list[SitePlan], names: dict[str, str] | None = None) -> list[PageObservation]:
    """Наблюдения для ворот уникальности. Имя сайта вырезается из заголовков."""
    names = names or {}
    return [page.observation(names.get(plan.site_id, "")) for plan in plans for page in plan.pages]
