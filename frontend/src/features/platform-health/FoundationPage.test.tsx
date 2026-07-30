import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";

import { AppThemeProvider } from "../../app/AppThemeProvider";
import { FoundationPage } from "./FoundationPage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <AppThemeProvider>
      <QueryClientProvider client={client}>
        <FoundationPage />
      </QueryClientProvider>
    </AppThemeProvider>,
  );
}

test("shows the ready state from a validated API response", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        status: "ready",
        checks: {
          database: { status: "up" },
          redis: { status: "up" },
        },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  renderPage();

  expect(
    await screen.findByRole("heading", { name: "All systems ready" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("No customer AWS actions are enabled."),
  ).toBeInTheDocument();
});

test("shows a useful error when readiness cannot be reached", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new Error("Network unavailable"),
  );

  renderPage();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Network unavailable",
  );
});
