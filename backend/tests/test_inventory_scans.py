"""Inventory scan tenant and normalization tests."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from cloudwise.aws_accounts.models import AWSAccountConnection, ConnectionStatus
from cloudwise.core.database import Base
from cloudwise.scans import tasks as scan_tasks
from cloudwise.scans.models import InventoryScan, ScanStatus
from cloudwise.scans.service import InventoryScanService
from cloudwise.scans.tasks import _resource_values


def test_worker_model_metadata_resolves_foreign_keys() -> None:
    """The standalone worker must load every table referenced by scan models."""
    for table in Base.metadata.sorted_tables:
        for foreign_key in table.foreign_keys:
            assert foreign_key.column is not None


async def test_start_scan_rejects_connection_outside_organization() -> None:
    """A missing tenant-scoped connection must not dispatch a task."""
    session = AsyncMock()
    session.scalar.return_value = None
    celery_app = MagicMock()
    service = InventoryScanService(session, celery_app)

    with pytest.raises(LookupError):
        await service.start_scan(uuid4(), uuid4(), "us-east-1")

    celery_app.send_task.assert_not_called()


async def test_start_scan_requires_verified_connection() -> None:
    """Pending connections cannot invoke customer AWS APIs."""
    session = AsyncMock()
    session.scalar.return_value = AWSAccountConnection(status=ConnectionStatus.PENDING)
    celery_app = MagicMock()
    service = InventoryScanService(session, celery_app)

    with pytest.raises(ValueError, match="verified"):
        await service.start_scan(uuid4(), uuid4(), "us-east-1")

    celery_app.send_task.assert_not_called()


def test_resource_values_are_json_safe_and_tenant_scoped() -> None:
    """EC2 SDK values are normalized before PostgreSQL JSON persistence."""
    organization_id = uuid4()
    connection_id = uuid4()
    scan = InventoryScan(
        id=uuid4(),
        organization_id=organization_id,
        connection_id=connection_id,
        region="us-east-1",
        status=ScanStatus.RUNNING,
    )
    launch_time = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)

    values = _resource_values(
        scan,
        {
            "resource_type": "ec2_instance",
            "resource_id": "i-example",
            "name": "worker",
            "state": "running",
            "region": "us-east-1",
            "details": {
                "instance_type": "t3.micro",
                "availability_zone": "us-east-1a",
                "launch_time": launch_time.isoformat(),
            },
        },
        launch_time,
    )

    assert values["organization_id"] == organization_id
    assert values["connection_id"] == connection_id
    assert values["resource_type"] == "ec2_instance"
    assert values["is_active"] is True
    details = cast(dict[str, object], values["details"])
    assert details["launch_time"] == launch_time.isoformat()


def test_unexpected_worker_failure_marks_scan_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A task-level failure must not leave an inventory scan permanently queued."""
    scan_id = uuid4()
    failure_updates: list[tuple[object, str]] = []

    async def fail_scan_task(_scan_id: object) -> None:
        raise RuntimeError("worker failed")

    async def record_failure(scan_id_value: object, error_code: str) -> None:
        failure_updates.append((scan_id_value, error_code))

    monkeypatch.setattr(scan_tasks, "_run_inventory_scan", fail_scan_task)
    monkeypatch.setattr(scan_tasks, "_fail_scan", record_failure)

    with pytest.raises(RuntimeError, match="worker failed"):
        scan_tasks.run_inventory_scan.run(str(scan_id))

    assert failure_updates == [(scan_id, "INVENTORY_WORKER_FAILED")]
