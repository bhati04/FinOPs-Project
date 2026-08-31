"""Regression tests for migration-specific PostgreSQL DDL contracts."""

from collections.abc import Callable
from pathlib import Path
from runpy import run_path
from typing import Any, cast

from sqlalchemy.dialects import postgresql


def test_recommendation_sync_enum_is_not_recreated_by_table_ddl() -> None:
    """Migration 0009 must create its enum once, then only reference it."""
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0009_aws_recommendation_sources.py"
    )
    namespace = run_path(str(migration_path))
    enum_factory = cast(
        Callable[..., postgresql.ENUM],
        cast(dict[str, Any], namespace)["_recommendation_sync_status"],
    )

    assert enum_factory(create_type=True).create_type is True
    assert enum_factory(create_type=False).create_type is False
