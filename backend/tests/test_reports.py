"""Milestone 7 rendering, storage, schedule, and schema tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from cloudwise.reports.models import ReportFormat, ReportFrequency, ReportType
from cloudwise.reports.rendering import render_csv, render_pdf
from cloudwise.reports.schemas import ReportScheduleCreate
from cloudwise.reports.service import next_run
from cloudwise.reports.storage import LocalReportStorage, ReportStorageError
from cloudwise.reports.tasks import _cell


def test_report_renderers_create_downloadable_encodings() -> None:
    """CSV is UTF-8 and the dependency-free PDF has a valid header and trailer."""
    csv_content = render_csv(["Name"], [[_cell("=SUM(A1:A2)")]])
    pdf_content = render_pdf("CloudWise", ["Name"], [["Safe row"]])

    assert csv_content.startswith(b"\xef\xbb\xbf")
    assert b"'=SUM" in csv_content
    assert pdf_content.startswith(b"%PDF-1.4")
    assert pdf_content.endswith(b"%%EOF")


def test_local_report_storage_blocks_path_traversal(tmp_path: Path) -> None:
    """A storage key cannot escape the configured private directory."""
    storage = LocalReportStorage(str(tmp_path))

    with pytest.raises(ReportStorageError):
        storage.put("../outside.csv", b"data", "text/csv")


def test_monthly_schedule_advances_to_next_month_boundary() -> None:
    """Monthly schedules have deterministic UTC calendar behavior."""
    now = datetime(2026, 12, 18, 12, tzinfo=UTC)

    assert next_run(now, ReportFrequency.MONTHLY) == datetime(2027, 1, 1, 12, tzinfo=UTC)


def test_schedule_rejects_malformed_recipient() -> None:
    """Invalid email destinations never reach the notification provider."""
    with pytest.raises(ValidationError):
        ReportScheduleCreate(
            name="Weekly",
            report_type=ReportType.RECOMMENDATIONS,
            report_format=ReportFormat.PDF,
            frequency=ReportFrequency.WEEKLY,
            recipients=["not-an-email"],
        )
