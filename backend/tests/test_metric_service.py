"""CloudWatch metric synchronization service boundary tests."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.metrics.models import MetricSyncStatus
from cloudwise.metrics.service import MetricSyncDispatchError, MetricSyncService


async def test_start_metric_sync_rejects_connection_outside_organization() -> None:
    """A tenant cannot dispatch metric work for another tenant's connection."""
    session = AsyncMock()
    session.scalar.return_value = None
    celery_app = MagicMock()

    with pytest.raises(LookupError):
        await MetricSyncService(session, celery_app).start_sync(
            uuid4(),
            uuid4(),
            "us-east-1",
            14,
        )

    celery_app.send_task.assert_not_called()


async def test_start_metric_sync_records_dispatch_failure() -> None:
    """A broker failure must not leave CloudWatch work permanently queued."""
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.side_effect = [
        AWSAccountConnection(status=ConnectionStatus.VERIFIED),
        None,
    ]
    celery_app = MagicMock()
    celery_app.send_task.side_effect = RuntimeError("broker unavailable")
    service = MetricSyncService(session, celery_app)

    with pytest.raises(MetricSyncDispatchError):
        await service.start_sync(uuid4(), uuid4(), "us-east-1", 14)

    sync = session.add.call_args.args[0]
    assert sync.status is MetricSyncStatus.FAILED
    assert sync.error_code == "DISPATCH_FAILED"
    assert sync.completed_at is not None
    assert session.commit.await_count == 2
