import { createBrowserRouter } from "react-router-dom";

import { AwsAccountPage } from "../features/aws-accounts/AwsAccountPage";
import { FoundationPage } from "../features/platform-health/FoundationPage";
import { NotFoundPage } from "./NotFoundPage";

export const router = createBrowserRouter([
  { path: "/", element: <FoundationPage /> },
  { path: "/aws-account", element: <AwsAccountPage /> },
  { path: "*", element: <NotFoundPage /> },
]);
