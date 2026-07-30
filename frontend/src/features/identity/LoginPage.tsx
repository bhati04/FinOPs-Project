import { LockRounded } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Container,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { login, register } from "./api";
import { saveSession } from "./session";

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  async function submit() {
    setSubmitting(true);
    setError(undefined);
    try {
      const tokens =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, organizationName);
      saveSession(tokens);
      const destination =
        (location.state as { from?: string } | null)?.from ?? "/aws-account";
      void navigate(destination, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Authentication failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Box component="main" className="app-shell">
      <Container maxWidth="sm" sx={{ py: { xs: 6, md: 12 } }}>
        <Card>
          <CardContent sx={{ p: { xs: 3, md: 5 } }}>
            <Stack spacing={3}>
              <Box className="brand-mark">
                <LockRounded fontSize="small" />
              </Box>
              <Box>
                <Typography variant="h3">
                  {mode === "login" ? "Welcome back" : "Create your workspace"}
                </Typography>
                <Typography color="text.secondary" mt={1}>
                  Authenticate before accessing AWS account information.
                </Typography>
              </Box>
              {error && <Alert severity="error">{error}</Alert>}
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
              {mode === "register" && (
                <TextField
                  label="Organization name"
                  value={organizationName}
                  onChange={(event) => setOrganizationName(event.target.value)}
                  required
                />
              )}
              <TextField
                label="Password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                helperText={
                  mode === "register"
                    ? "Use at least 12 characters."
                    : undefined
                }
                required
              />
              <Button
                variant="contained"
                size="large"
                disabled={
                  submitting ||
                  !email ||
                  !password ||
                  (mode === "register" && !organizationName)
                }
                onClick={() => void submit()}
              >
                {submitting
                  ? "Please wait"
                  : mode === "login"
                    ? "Sign in"
                    : "Create account"}
              </Button>
              <Button
                onClick={() => {
                  setMode(mode === "login" ? "register" : "login");
                  setError(undefined);
                }}
              >
                {mode === "login"
                  ? "Create a new account"
                  : "Already have an account? Sign in"}
              </Button>
            </Stack>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
}
