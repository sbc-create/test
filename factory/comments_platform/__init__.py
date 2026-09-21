"""COMMUNITY_COMMENTS — the shared comments platform.

One module, many sites. Lords, Zona, Animedia and Yummy do not each get a copy
of this code; they get a pinned version of one artifact plus a thin adapter and
a configuration row. Copying comments sources into a tenant template is the
failure this package exists to prevent.

Layering, outermost last:

    tenancy   — who is asking and on whose behalf, derived server-side
    flags     — what is currently switched on, default off
    rbac      — what this principal may do, default deny
    states    — where a comment is in its life
    sanitize  — what a body is allowed to become
    identity  — who the author is, per tenant, never correlatable across them
    antiabuse — rate limits, duplicates, stoplists
    store     — tenant-scoped persistence
    audit     — append-only record of every privileged act
    service   — the use cases
    api       — the versioned wire contract
    ssr       — server-rendered published comments

This package does not import factory.community.*: ratings are a separate
product with separate tables, flags, migrations and kill switches, and a shared
import would make one product's incident the other's outage.
"""

from __future__ import annotations

# The version a site pins. Bump deliberately; sites name an exact value and
# there is no `latest` to fall back on.
MODULE_VERSION = "0.1.0-mvp"
MODULE_NAME = "COMMUNITY_COMMENTS"
SCHEMA_VERSION = "COMMENTS_PLATFORM_V1"

__all__ = ["MODULE_VERSION", "MODULE_NAME", "SCHEMA_VERSION"]
