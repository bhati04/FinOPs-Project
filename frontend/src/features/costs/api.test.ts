import { listCostAggregates, listCostForecasts, listCostSyncs } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

test("validates cost aggregates and sends tenant-safe filters", async () => {
  const connectionId = "7fbec1f8-1150-4dd4-a207-a7c587c50f4c";
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify([
        {
          connection_id: connectionId,
          period_start: "2026-08-01",
          granularity: "daily",
          grouping: "service_region",
          service: "Amazon EC2",
          region: "us-east-1",
          usage_type: "",
          tag_key: "",
          tag_value: "",
          amount: "12.50000000",
          currency: "USD",
        },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  const rows = await listCostAggregates(
    "daily",
    "service_region",
    connectionId,
  );

  expect(rows[0]?.amount).toBe(12.5);
  expect(fetchMock.mock.calls[0]?.[0]).toContain(
    `connection_id=${connectionId}`,
  );
  expect(fetchMock.mock.calls[0]?.[0]).toContain("grouping=service_region");
});

test("validates partial synchronization details", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify([
        {
          id: "6423d346-e766-44e7-9360-67e44b47f741",
          connection_id: "7fbec1f8-1150-4dd4-a207-a7c587c50f4c",
          status: "partial",
          record_count: 10,
          error_code: "COST_DATA_PARTIAL",
          failed_facets: ["daily:forecast"],
          created_at: "2026-08-03T10:00:00Z",
          started_at: "2026-08-03T10:00:01Z",
          completed_at: "2026-08-03T10:00:02Z",
        },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  const syncs = await listCostSyncs();

  expect(syncs[0]?.status).toBe("partial");
  expect(syncs[0]?.failed_facets).toEqual(["daily:forecast"]);
});

test("converts forecast decimal strings to numbers", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify([
        {
          connection_id: "7fbec1f8-1150-4dd4-a207-a7c587c50f4c",
          period_start: "2026-08-04",
          period_end: "2026-08-05",
          granularity: "daily",
          mean_amount: "3.25",
          lower_bound: "2.50",
          upper_bound: "4.00",
          currency: "USD",
        },
      ]),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  const forecasts = await listCostForecasts("daily");

  expect(forecasts[0]?.mean_amount).toBe(3.25);
  expect(forecasts[0]?.upper_bound).toBe(4);
});
