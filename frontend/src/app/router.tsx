import { createBrowserRouter } from "react-router-dom";

import { FoundationPage } from "../features/platform-health/FoundationPage";
import { NotFoundPage } from "./NotFoundPage";

export const router = createBrowserRouter([
  { path: "/", element: <FoundationPage /> },
  { path: "*", element: <NotFoundPage /> },
]);
