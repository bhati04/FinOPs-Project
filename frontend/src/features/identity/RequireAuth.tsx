import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { getAccessToken } from "./session";

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!getAccessToken()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
