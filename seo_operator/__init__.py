"""Autonomous SEO editorial operator.

The operator runs unattended. Every module here assumes it may execute with no
human watching, so the defaults are conservative: unknown data sources are
unavailable rather than empty, unknown actions are blocked rather than allowed,
and any mutation carries a rollback payload before it is applied.
"""

__version__ = "0.1.0"
