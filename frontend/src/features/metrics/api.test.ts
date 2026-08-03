import { listResourceMetrics, startMetricSync } from "./api";

test("starts a bounded regional metric synchronization", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "15ca6105-f4a6-4be5-a397-076f70848899",
        connection_id: "688dd57d-911c-493d-aa15-9cbd59053937",
        region: "us-east-1",
        status: "queued",
        window_start: "2026-07-20T04:30:00Z",
        window_end: "2026-08-03T04:30:00Z",
        record_count: 0,
        failed_batch_count: 0,
        error_code: null,
        created_at: "2026-08-03T04:30:00Z",
        started_at: null,
        completed_at: null,
      }),
      { status: 202, headers: { "Content-Type": "application/json" } },
    ),
  );

  await startMetricSync(
    "688dd57d-911c-493d-aa15-9cbd59053937",
    "us-east-1",
    14,
  );

  expect(fetchMock.mock.calls[0]?.[0]).toContain(
    "/metrics/connections/688dd57d-911c-493d-aa15-9cbd59053937/sync?region=us-east-1&days=14",
  );
});

test("validates decimal resource metric values", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify([
        {
          inventory_resource_id: "c46b39fd-6755-4b7d-8ec3-e50948793e28",
          resource_type: "ec2_instance",
          resource_name: "worker",
          region: "us-east-1",
          namespace: "AWS/EC2",
          metric_name: "CPUUtilization",
          statistic: "Average",
          unit: "Percent",
          timestamp: "2026-08-03T04:00:00Z",
          value: "12.50000000",
        },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  const points = await listResourceMetrics(
    "c46b39fd-6755-4b7d-8ec3-e50948793e28",
  );

  expect(points[0]?.value).toBe(12.5);
});
