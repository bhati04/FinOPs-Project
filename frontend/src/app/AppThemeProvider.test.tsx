import { fireEvent, render, screen } from "@testing-library/react";

import { AppThemeProvider } from "./AppThemeProvider";

test("persists an accessible light and dark theme preference", () => {
  localStorage.removeItem("cloudwise.color-mode");
  render(
    <AppThemeProvider>
      <div>Content</div>
    </AppThemeProvider>,
  );

  fireEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));

  expect(localStorage.getItem("cloudwise.color-mode")).toBe("dark");
  expect(
    screen.getByRole("button", { name: "Switch to light theme" }),
  ).toBeInTheDocument();
  localStorage.removeItem("cloudwise.color-mode");
  document.documentElement.dataset.theme = "light";
});
