"""Cost synchronization service boundary tests."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.cost_management.models import CostSyncStatus
from cloudwise.cost_management.service import CostSyncDispatchError, CostSyncService


async def test_start_cost_sync_rejects_connection_outside_organization() -> None:
    """A tenant cannot dispatch cost work for another tenant's connection."""
    session = AsyncMock()
    session.scalar.return_value = None
    celery_app = MagicMock()
    service = CostSyncService(session, celery_app)

    with pytest.raises(LookupError):
        await service.start_sync(uuid4(), uuid4())

    celery_app.send_task.assert_not_called()


async def test_start_cost_sync_requires_verified_connection() -> None:
    """Pending customer roles cannot be used for Cost Explorer requests."""
    session = AsyncMock()
    session.scalar.return_value = AWSAccountConnection(status=ConnectionStatus.PENDING)
    celery_app = MagicMock()
    service = CostSyncService(session, celery_app)

    with pytest.raises(ValueError, match="verified"):
        await service.start_sync(uuid4(), uuid4())

    celery_app.send_task.assert_not_called()


async def test_start_cost_sync_records_dispatch_failure() -> None:
    """A broker failure must not leave cost work permanently queued."""
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.side_effect = [
        AWSAccountConnection(status=ConnectionStatus.VERIFIED),
        None,
    ]
    celery_app = MagicMock()
    celery_app.send_task.side_effect = RuntimeError("broker unavailable")
    service = CostSyncService(session, celery_app)

    with pytest.raises(CostSyncDispatchError):
        await service.start_sync(uuid4(), uuid4())

    sync = session.add.call_args.args[0]
    assert sync.status is CostSyncStatus.FAILED
    assert sync.error_code == "DISPATCH_FAILED"
    assert sync.completed_at is not None
    assert session.commit.await_count == 2
