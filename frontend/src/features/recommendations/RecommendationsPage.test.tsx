import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AppThemeProvider } from "../../app/AppThemeProvider";
import { RecommendationsPage } from "./RecommendationsPage";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("shows verified evidence without inventing an unpriced savings amount", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    if (url.includes("/aws-accounts/connections")) {
      return Promise.resolve(jsonResponse([]));
    }
    if (url.includes("/recommendations?status=open")) {
      return Promise.resolve(
        jsonResponse([
          {
            id: "15ca6105-f4a6-4be5-a397-076f70848899",
            connection_id: "688dd57d-911c-493d-aa15-9cbd59053937",
            inventory_resource_id: "7dbe101e-10cb-4c0e-b7e6-b044aa2e8cb5",
            resource_type: "ebs_volume",
            resource_name: "retained-data",
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
            status: "open",
            evidence: [
              {
                reference: "volume.attachments",
                metric: "Attachment count",
                value: 0,
                unit: "count",
              },
            ],
            exclusions: [],
            risk_notes: ["The volume may contain retained data."],
            verification_steps: ["Confirm retention requirements."],
            evidence_period_start: null,
            evidence_period_end: "2026-08-03T04:30:00Z",
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
            calculation_summary: "Verified pricing is not yet attached.",
            created_at: "2026-08-03T04:31:00Z",
            updated_at: "2026-08-03T04:31:00Z",
            resolved_at: null,
          },
        ]),
      );
    }
    if (url.includes("/recommendations/source-syncs")) {
      return Promise.resolve(jsonResponse([]));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <MemoryRouter>
      <AppThemeProvider>
        <QueryClientProvider client={client}>
          <RecommendationsPage />
        </QueryClientProvider>
      </AppThemeProvider>
    </MemoryRouter>,
  );

  expect(
    await screen.findByText("Review unattached EBS volume"),
  ).toBeInTheDocument();
  expect(screen.getAllByText(/Pricing pending/)).toHaveLength(2);
  expect(
    screen.getByText(/Verified pricing is not yet attached/),
  ).toBeInTheDocument();
});
