import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AppThemeProvider } from "../../app/AppThemeProvider";
import { CostDashboardPage } from "./CostDashboardPage";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("refreshes dashboard data after a cost sync finishes", async () => {
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
    if (url.includes("/costs/syncs")) {
      return Promise.resolve(
        jsonResponse([
          {
            id: "15ca6105-f4a6-4be5-a397-076f70848899",
            connection_id: "688dd57d-911c-493d-aa15-9cbd59053937",
            status: "completed",
            record_count: 12,
            error_code: null,
            failed_facets: [],
            created_at: "2026-08-03T04:30:00Z",
            started_at: "2026-08-03T04:30:01Z",
            completed_at: "2026-08-03T04:30:04Z",
          },
        ]),
      );
    }
    if (url.includes("/costs/aggregates") || url.includes("/costs/forecasts")) {
      return Promise.resolve(jsonResponse([]));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const invalidate = vi.spyOn(client, "invalidateQueries");

  render(
    <MemoryRouter>
      <AppThemeProvider>
        <QueryClientProvider client={client}>
          <CostDashboardPage />
        </QueryClientProvider>
      </AppThemeProvider>
    </MemoryRouter>,
  );

  expect(
    await screen.findByText("No synchronized cost period"),
  ).toBeInTheDocument();
  await waitFor(() => {
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["cost-aggregates"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["cost-forecasts"] });
  });
});
