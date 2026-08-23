"""Data source adapters.

Every adapter answers two questions separately: *can I reach this source* and
*what does it say*. Conflating them is how a broken credential turns into a
report full of zeros, so ``probe()`` never returns data and ``fetch()`` never
runs on an unavailable source.
"""

from seo_operator.datasources.base import (
    Availability,
    DataSource,
    SourceStatus,
    StaticSource,
)

__all__ = ["Availability", "DataSource", "SourceStatus", "StaticSource"]
