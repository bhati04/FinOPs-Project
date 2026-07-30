import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { clearSession, saveSession } from "./session";
import { RequireAuth } from "./RequireAuth";

afterEach(() => clearSession());

function renderProtectedRoute() {
  return render(
    <MemoryRouter initialEntries={["/aws-account"]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route
          path="/aws-account"
          element={
            <RequireAuth>
              <div>AWS account page</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

test("redirects an unauthenticated visitor to login", () => {
  renderProtectedRoute();
  expect(screen.getByText("Login page")).toBeInTheDocument();
});

test("renders the protected page when an access token exists", () => {
  saveSession({
    access_token: "test-access-token",
    refresh_token: "test-refresh-token",
  });
  renderProtectedRoute();
  expect(screen.getByText("AWS account page")).toBeInTheDocument();
});
