import { createReport, createSchedule, listAuditEvents } from "./api";

test("queues a bounded report request", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "15ca6105-f4a6-4be5-a397-076f70848899",
        connection_id: null,
        schedule_id: null,
        report_type: "executive_summary",
        report_format: "csv",
        status: "queued",
        period_start: "2026-07-01",
        period_end: "2026-07-31",
        content_type: null,
        byte_size: null,
        checksum_sha256: null,
        error_code: null,
        expires_at: "2026-09-01T00:00:00Z",
        created_at: "2026-08-01T00:00:00Z",
        started_at: null,
        completed_at: null,
      }),
      { status: 202, headers: { "Content-Type": "application/json" } },
    ),
  );

  await createReport({
    reportType: "executive_summary",
    reportFormat: "csv",
    periodStart: "2026-07-01",
    periodEnd: "2026-07-31",
  });

  expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
});

test("creates schedules with normalized API fields", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "15ca6105-f4a6-4be5-a397-076f70848899",
        connection_id: null,
        name: "Weekly",
        report_type: "recommendations",
        report_format: "pdf",
        frequency: "weekly",
        recipients: ["owner@example.com"],
        enabled: true,
        next_run_at: "2026-08-11T00:00:00Z",
        last_run_at: null,
        created_at: "2026-08-04T00:00:00Z",
        updated_at: "2026-08-04T00:00:00Z",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    ),
  );

  await createSchedule({
    name: "Weekly",
    reportType: "recommendations",
    reportFormat: "pdf",
    frequency: "weekly",
    recipients: ["owner@example.com"],
  });

  expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
});

test("treats forbidden audit access as an empty admin-only view", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Insufficient role" }), {
      status: 403,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await expect(listAuditEvents()).resolves.toEqual([]);
});
