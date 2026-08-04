import { DarkModeRounded, LightModeRounded } from "@mui/icons-material";
import {
  CssBaseline,
  IconButton,
  ThemeProvider,
  Tooltip,
  createTheme,
} from "@mui/material";
import type { PropsWithChildren } from "react";
import { useEffect, useMemo, useState } from "react";

type ColorMode = "light" | "dark";

const STORAGE_KEY = "cloudwise.color-mode";

function buildTheme(mode: ColorMode) {
  const dark = mode === "dark";
  return createTheme({
    palette: {
      mode,
      primary: {
        main: dark ? "#8bcfba" : "#356f61",
        light: dark ? "#b6e6d6" : "#5f9789",
        dark: dark ? "#579b88" : "#214f45",
      },
      secondary: { main: dark ? "#d2b77f" : "#80683c" },
      background: {
        default: dark ? "#151816" : "#f5f5f1",
        paper: dark ? "#202421" : "#ffffff",
      },
      text: {
        primary: dark ? "#f1f3ef" : "#202622",
        secondary: dark ? "#aeb8b1" : "#66706a",
      },
      divider: dark ? "rgba(235, 240, 235, 0.12)" : "rgba(31, 43, 36, 0.12)",
      success: { main: dark ? "#86c99d" : "#357a4d" },
      warning: { main: dark ? "#ddb76a" : "#966917" },
      error: { main: dark ? "#e68e8e" : "#b84b4b" },
    },
    typography: {
      fontFamily:
        '"Inter", "Aptos", "Segoe UI", system-ui, -apple-system, sans-serif',
      h1: { fontWeight: 700, letterSpacing: "-0.04em" },
      h2: { fontWeight: 650, letterSpacing: "-0.025em" },
      button: { textTransform: "none", fontWeight: 650 },
    },
    shape: { borderRadius: 12 },
    components: {
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            border: dark
              ? "1px solid rgba(235, 240, 235, 0.1)"
              : "1px solid rgba(31, 43, 36, 0.1)",
            boxShadow: dark
              ? "0 12px 34px rgba(0, 0, 0, 0.2)"
              : "0 10px 30px rgba(33, 43, 37, 0.06)",
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
      },
    },
  });
}

export function AppThemeProvider({ children }: PropsWithChildren) {
  const [mode, setMode] = useState<ColorMode>(() =>
    localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light",
  );
  const theme = useMemo(() => buildTheme(mode), [mode]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode);
    document.documentElement.dataset.theme = mode;
    document.documentElement.style.colorScheme = mode;
  }, [mode]);

  const nextMode = mode === "light" ? "dark" : "light";
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
      <Tooltip title={"Use " + nextMode + " theme"}>
        <IconButton
          aria-label={"Switch to " + nextMode + " theme"}
          onClick={() => setMode(nextMode)}
          sx={{
            position: "fixed",
            right: 20,
            bottom: 20,
            zIndex: (value) => value.zIndex.modal + 1,
            bgcolor: "background.paper",
            border: 1,
            borderColor: "divider",
            boxShadow: 3,
            "&:hover": { bgcolor: "action.hover" },
          }}
        >
          {mode === "light" ? <DarkModeRounded /> : <LightModeRounded />}
        </IconButton>
      </Tooltip>
    </ThemeProvider>
  );
}
