import {
  evaluateRecommendations,
  listRecommendations,
  updateRecommendationStatus,
} from "./api";

test("evaluates a selected organization-scoped connection", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "15ca6105-f4a6-4be5-a397-076f70848899",
        connection_id: "688dd57d-911c-493d-aa15-9cbd59053937",
        rule_set_version: "1.1.0",
        evaluated_resource_count: 4,
        eligible_recommendation_count: 2,
        created_at: "2026-08-03T04:30:00Z",
        completed_at: "2026-08-03T04:30:01Z",
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    ),
  );

  await evaluateRecommendations("688dd57d-911c-493d-aa15-9cbd59053937");

  expect(fetchMock.mock.calls[0]?.[0]).toContain(
    "/recommendations/evaluate?connection_id=688dd57d-911c-493d-aa15-9cbd59053937",
  );
});

test("sends recommendation filters", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await listRecommendations({ status: "open", severity: "medium" });

  expect(fetchMock.mock.calls[0]?.[0]).toContain(
    "/recommendations?status=open&severity=medium",
  );
});

test("updates status with an analyst comment", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "15ca6105-f4a6-4be5-a397-076f70848899",
        connection_id: "688dd57d-911c-493d-aa15-9cbd59053937",
        inventory_resource_id: "c46b39fd-6755-4b7d-8ec3-e50948793e28",
        resource_type: "ebs_volume",
        resource_name: "database-backup",
        region: "us-east-1",
        rule_id: "ebs.unattached_volume",
        rule_version: "1.1.0",
        canonical_action: "delete",
        sources: ["cloudwise"],
        source_metadata: {},
        title: "Review unattached EBS volume",
        category: "storage_optimization",
        severity: "medium",
        confidence: "0.9900",
        status: "acknowledged",
        evidence: [],
        exclusions: [],
        risk_notes: [],
        verification_steps: [],
        evidence_period_start: null,
        evidence_period_end: "2026-08-03T04:00:00Z",
        estimate_type: "advisory",
        current_monthly_cost: null,
        estimated_monthly_savings: null,
        currency: null,
        pricing_status: "unavailable",
        pricing_source: null,
        pricing_version: null,
        pricing_effective_at: null,
        pricing_retrieved_at: null,
        pricing_unavailable_reason: "incomplete_inventory",
        calculation_inputs: [],
        calculation_summary: "Pricing pending.",
        created_at: "2026-08-03T04:30:00Z",
        updated_at: "2026-08-03T04:31:00Z",
        resolved_at: null,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  await updateRecommendationStatus(
    "15ca6105-f4a6-4be5-a397-076f70848899",
    "acknowledged",
    "Owner review started",
  );

  expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
    method: "PATCH",
    body: JSON.stringify({
      status: "acknowledged",
      comment: "Owner review started",
    }),
  });
});
