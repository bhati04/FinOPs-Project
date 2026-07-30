import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import type { PropsWithChildren } from "react";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#59d6c2", light: "#9af0df", dark: "#21a892" },
    secondary: { main: "#84a7ff" },
    background: { default: "#07111f", paper: "#101d2e" },
    text: { primary: "#f3f7fb", secondary: "#a7b7ca" },
    success: { main: "#58d49d" },
    warning: { main: "#f6c66c" },
    error: { main: "#ff7b82" },
  },
  typography: {
    fontFamily:
      '"Inter", "Aptos", "Segoe UI", system-ui, -apple-system, sans-serif',
    h1: { fontWeight: 700, letterSpacing: "-0.04em" },
    h2: { fontWeight: 650, letterSpacing: "-0.025em" },
    button: { textTransform: "none", fontWeight: 650 },
  },
  shape: { borderRadius: 14 },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage:
            "linear-gradient(145deg, rgba(22, 39, 59, 0.96), rgba(12, 27, 43, 0.96))",
          border: "1px solid rgba(153, 186, 218, 0.13)",
        },
      },
    },
  },
});

export function AppThemeProvider({ children }: PropsWithChildren) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
