"""Feature flags and kill switches for the shared comments platform.

Three properties are enforced here rather than trusted to callers.

The safe default is off. Read, write, publication and rollout all start at 0,
so a site that is deployed but not yet configured serves nothing rather than
serving everything.

Production gates cannot be raised from the environment in this stage. The
process may *lower* a flag through the environment — that is the emergency
path — but `_clamped` refuses to let it rise above the compiled ceiling, so a
stray `COMMENTS_PUBLICATION_ENABLED=1` in a unit file cannot publish comments
on four sites by accident.

Flags are per site, not global. `lords` going dark must not darken `zona`, and
the kill switch therefore has both a global and a per-site form: the global one
wins when set, because an incident does not wait for a loop over tenants.

This module is deliberately independent of factory.community.* — the ratings
product owns its own flags, and a shared flag object would make one product's
incident the other product's outage.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .tenancy import SiteBinding, TenantScope

# Compiled ceilings for the public cohort. These stay at 0: Stage 1 is an
# owner test, and the public experience must be the site exactly as it is
# today. A value here is what an ordinary visitor can ever receive.
CEILING_READ_ENABLED = 0
CEILING_WRITE_ENABLED = 0
CEILING_PUBLICATION_ENABLED = 0
CEILING_ROLLOUT_PERCENT = 0
CEILING_SSR_ENABLED = 0

# Per-cohort ceilings. The public row is the one above, restated so that the
# two cannot drift; the owner row is what the Stage 1 authorisation opens, and
# it opens for one named audience rather than for a percentage of traffic.
#
# SSR stays 0 for every cohort. Server-rendering comments into HTML is
# publishing them, and an owner test must not put text where a crawler could
# read it even in principle.
COHORT_CEILINGS: dict[str, dict[str, int]] = {
    "public": {
        "read": CEILING_READ_ENABLED,
        "write": CEILING_WRITE_ENABLED,
        "publication": CEILING_PUBLICATION_ENABLED,
        "rollout": CEILING_ROLLOUT_PERCENT,
        "ssr": CEILING_SSR_ENABLED,
    },
    "owner_test": {
        "read": 1,
        "write": 1,
        "publication": 1,
        # Rollout percent is a *public* traffic dial. The owner cohort is not
        # a percentage of visitors, so this stays 0 and the two mechanisms
        # never get confused for one another.
        "rollout": 0,
        "ssr": 0,
    },
}

# Sites this stage is authorised to serve at all, in any cohort. A site absent
# from this tuple is refused before cohorts are even considered, so a token
# minted by mistake for another site cannot enable anything.
#
# Stage 1 authorisation: animedia.icu only. animedia.space is explicitly out.
PILOT_SITES: tuple[tuple[str, str], ...] = (("animedia", "animedia-01"),)

# Capabilities that must never exist, in any stage, for any role. They are
# listed so that a test can assert their absence instead of a reviewer noticing.
PERMANENTLY_FORBIDDEN = frozenset(
    {
        "ADMIN_FAKE_COMMENT_INSERT",
        "ADMIN_IMPERSONATE_USER",
        "ADMIN_SILENT_TEXT_REWRITE",
        "ADMIN_SHADOW_BAN",
        "COMMENTS_AFFECT_RATINGS",
        "CROSS_TENANT_READ",
        "HARD_DELETE_BY_AUTOMATION",
    }
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _clamped(name: str, configured: int, ceiling: int) -> int:
    """Environment may lower a gate, never raise it past the compiled ceiling."""
    value = _env_int(name, int(configured))
    return max(0, min(int(value), int(configured), int(ceiling)))


@dataclass(frozen=True, slots=True)
class EffectiveFlags:
    tenant_id: str
    site_id: str
    # Which audience this answer is about. Two cohorts on one site get two
    # different EffectiveFlags, and carrying the label prevents one being
    # mistaken for the other downstream.
    cohort: str
    read_enabled: int
    write_enabled: int
    publication_enabled: int
    rollout_percent: int
    ssr_enabled: int
    seo_mode: str
    moderation_mode: str
    kill_switch_global: int
    kill_switch_site: int

    @property
    def writes_allowed(self) -> bool:
        return bool(self.write_enabled) and not self.any_kill_switch

    @property
    def reads_allowed(self) -> bool:
        return bool(self.read_enabled) and not self.any_kill_switch

    @property
    def any_kill_switch(self) -> bool:
        return bool(self.kill_switch_global or self.kill_switch_site)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "cohort": self.cohort,
            "COMMENTS_READ_ENABLED": self.read_enabled,
            "COMMENTS_WRITE_ENABLED": self.write_enabled,
            "COMMENTS_PUBLICATION_ENABLED": self.publication_enabled,
            "COMMENTS_ROLLOUT_PERCENT": self.rollout_percent,
            "COMMENTS_SSR_ENABLED": self.ssr_enabled,
            "COMMENTS_SEO_MODE": self.seo_mode,
            "COMMENTS_MODERATION_MODE": self.moderation_mode,
            "KILL_SWITCH_GLOBAL": self.kill_switch_global,
            "KILL_SWITCH_SITE": self.kill_switch_site,
        }


class FlagResolver:
    """Resolves a site binding plus overrides into effective flags.

    `overrides` is the operator surface — a per-site row an operator can flip
    to 0 during an incident without a deploy. It can only lower, exactly like
    the environment, so an operator mistake cannot turn comments on.
    """

    def __init__(self, overrides: Mapping[str, Mapping[str, int]] | None = None) -> None:
        self._overrides = dict(overrides or {})

    def set_site_override(self, scope: TenantScope, **values: int) -> None:
        current = dict(self._overrides.get(scope.key, {}))
        current.update({k: int(v) for k, v in values.items()})
        self._overrides[scope.key] = current

    def site_override(self, scope: TenantScope) -> dict[str, int]:
        return dict(self._overrides.get(scope.key, {}))

    def _override(self, scope: TenantScope, name: str, default: int) -> int:
        """Feature-flag polarity: an override may lower a gate, never raise it."""
        value = self._overrides.get(scope.key, {}).get(name, default)
        return max(0, min(int(value), int(default)))

    def _safety_override(self, scope: TenantScope, name: str) -> int:
        """Safety polarity: the opposite of :meth:`_override`.

        A kill switch is not a feature gate. Passing it through the lowering
        clamp above pins it at 0 for ever, which is how an operator discovers
        during an incident that the stop button does nothing.
        """
        return 1 if int(self._overrides.get(scope.key, {}).get(name, 0)) else 0

    def resolve(self, binding: SiteBinding) -> EffectiveFlags:
        """What an ordinary visitor gets. Kept as the default on purpose.

        A caller that forgets to say which cohort it is resolving for receives
        the public answer, which is the safe one. The unsafe direction has to
        be asked for by name.
        """
        return self.resolve_for_cohort(binding, "public")

    def resolve_for_cohort(self, binding: SiteBinding, cohort: str) -> EffectiveFlags:
        scope = binding.scope

        if cohort not in COHORT_CEILINGS:
            raise ValueError(f"unknown cohort {cohort!r}")

        # Site allowlist first. A site outside the pilot gets nothing, whatever
        # cohort the caller claims and whatever the configuration says.
        if (scope.tenant_id, scope.site_id) not in PILOT_SITES:
            ceilings = COHORT_CEILINGS["public"]
        else:
            ceilings = COHORT_CEILINGS[cohort]

        read = _clamped(
            "COMMENTS_READ_ENABLED",
            self._override(scope, "read_enabled", int(binding.read_enabled)),
            ceilings["read"],
        )
        write = _clamped(
            "COMMENTS_WRITE_ENABLED",
            self._override(scope, "write_enabled", int(binding.write_enabled)),
            ceilings["write"],
        )
        publication = _clamped(
            "COMMENTS_PUBLICATION_ENABLED",
            self._override(scope, "publication_enabled", int(binding.publication_enabled)),
            ceilings["publication"],
        )
        rollout = _clamped(
            "COMMENTS_ROLLOUT_PERCENT",
            self._override(scope, "rollout_percent", int(binding.rollout_percent)),
            ceilings["rollout"],
        )
        # SSR is a strict subset of publication: rendering comments into HTML
        # that a crawler can read *is* publishing them.
        ssr_configured = 1 if binding.seo_mode in ("ssr_first_page", "ssr_paginated") else 0
        ssr = _clamped(
            "COMMENTS_SSR_ENABLED",
            min(ssr_configured, publication),
            ceilings["ssr"],
        )
        return EffectiveFlags(
            tenant_id=binding.tenant_id,
            site_id=binding.site_id,
            cohort=cohort,
            read_enabled=read,
            write_enabled=write,
            publication_enabled=publication,
            rollout_percent=rollout,
            ssr_enabled=ssr,
            seo_mode=binding.seo_mode,
            moderation_mode=binding.moderation_mode,
            kill_switch_global=int(KillSwitch.global_state()),
            kill_switch_site=self._safety_override(scope, "kill_switch"),
        )


class KillSwitch:
    """Emergency stop for writes.

    Global state lives in one place and is read fresh on every check. Caching
    it would mean an operator flipping the switch waits for a process restart,
    which is precisely the wrong behaviour during an incident.
    """

    _ENV = "COMMENTS_KILL_SWITCH"
    _global: int = 0

    @classmethod
    def global_state(cls) -> int:
        # The environment may only *raise* the stop — the opposite direction to
        # feature flags, and for the same reason: safety wins ties.
        return 1 if (cls._global or _env_int(cls._ENV, 0)) else 0

    @classmethod
    def engage_global(cls) -> None:
        cls._global = 1

    @classmethod
    def release_global(cls) -> None:
        cls._global = 0


def assert_dark(flags: EffectiveFlags) -> None:
    """Fail loudly if a gate left 0 while this stage still forbids it."""
    lit = {
        name: value
        for name, value in (
            ("COMMENTS_READ_ENABLED", flags.read_enabled),
            ("COMMENTS_WRITE_ENABLED", flags.write_enabled),
            ("COMMENTS_PUBLICATION_ENABLED", flags.publication_enabled),
            ("COMMENTS_ROLLOUT_PERCENT", flags.rollout_percent),
            ("COMMENTS_SSR_ENABLED", flags.ssr_enabled),
        )
        if value != 0
    }
    if lit:
        raise RuntimeError(f"comments platform must stay dark in this stage: {lit}")


def forbidden_capability(name: str) -> bool:
    return name in PERMANENTLY_FORBIDDEN
