import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "../lib/queryClient";
import { AppThemeProvider } from "./AppThemeProvider";
import { router } from "./router";

export function App() {
  return (
    <AppThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </AppThemeProvider>
  );
}
