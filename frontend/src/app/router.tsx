import { createBrowserRouter } from "react-router-dom";

import { AwsAccountPage } from "../features/aws-accounts/AwsAccountPage";
import { CostDashboardPage } from "../features/costs/CostDashboardPage";
import { LoginPage } from "../features/identity/LoginPage";
import { RequireAuth } from "../features/identity/RequireAuth";
import { MetricsPage } from "../features/metrics/MetricsPage";
import { FoundationPage } from "../features/platform-health/FoundationPage";
import { NotFoundPage } from "./NotFoundPage";

export const router = createBrowserRouter([
  { path: "/", element: <FoundationPage /> },
  { path: "/login", element: <LoginPage /> },
  {
    path: "/aws-account",
    element: (
      <RequireAuth>
        <AwsAccountPage />
      </RequireAuth>
    ),
  },
  {
    path: "/costs",
    element: (
      <RequireAuth>
        <CostDashboardPage />
      </RequireAuth>
    ),
  },
  {
    path: "/metrics",
    element: (
      <RequireAuth>
        <MetricsPage />
      </RequireAuth>
    ),
  },
  { path: "*", element: <NotFoundPage /> },
]);
