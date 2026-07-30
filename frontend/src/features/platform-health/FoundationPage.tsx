import {
  CloudQueueRounded,
  DataObjectRounded,
  HubRounded,
  InsightsRounded,
  RefreshRounded,
  SecurityRounded,
} from "@mui/icons-material";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Grid,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { getReadiness } from "./api";

const capabilities: Array<{
  icon: ReactNode;
  title: string;
  description: string;
}> = [
  {
    icon: <CloudQueueRounded />,
    title: "AWS-aware",
    description: "Designed for secure, read-only multi-account visibility.",
  },
  {
    icon: <InsightsRounded />,
    title: "Explainable",
    description: "Every future saving estimate will retain its evidence.",
  },
  {
    icon: <SecurityRounded />,
    title: "Tenant-safe",
    description: "Isolation and authorization are architecture boundaries.",
  },
];

export function FoundationPage() {
  const readiness = useQuery({
    queryKey: ["platform-readiness"],
    queryFn: ({ signal }) => getReadiness(signal),
    refetchInterval: 30_000,
  });

  const platformReady = readiness.data?.status === "ready";

  return (
    <Box component="main" className="app-shell">
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 7 } }}>
        <Stack spacing={{ xs: 5, md: 8 }}>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
          >
            <Stack direction="row" spacing={1.25} alignItems="center">
              <Box className="brand-mark">
                <HubRounded fontSize="small" />
              </Box>
              <Typography fontWeight={750} letterSpacing="-0.02em">
                CloudWise
              </Typography>
            </Stack>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip
                label="Foundation · M0"
                size="small"
                variant="outlined"
                sx={{ borderColor: "rgba(89, 214, 194, .35)" }}
              />
              <Button
                component={Link}
                to="/aws-account"
                size="small"
                variant="outlined"
              >
                AWS account
              </Button>
            </Stack>
          </Stack>

          <Grid container spacing={4} alignItems="center">
            <Grid size={{ xs: 12, md: 7 }}>
              <Stack spacing={3} alignItems="flex-start">
                <Typography
                  color="primary.main"
                  fontWeight={700}
                  letterSpacing=".08em"
                >
                  AWS FINOPS, WITH EVIDENCE
                </Typography>
                <Typography
                  variant="h1"
                  fontSize={{ xs: "3rem", md: "5.1rem" }}
                >
                  See the cloud.
                  <br />
                  Spend with intent.
                </Typography>
                <Typography
                  color="text.secondary"
                  fontSize={{ xs: "1rem", md: "1.2rem" }}
                  maxWidth={650}
                  lineHeight={1.7}
                >
                  A production-oriented foundation for secure AWS cost
                  visibility, resource governance, and explainable optimization.
                </Typography>
              </Stack>
            </Grid>
            <Grid size={{ xs: 12, md: 5 }}>
              <Card className="status-card">
                <CardContent sx={{ p: 3.5 }}>
                  <Stack spacing={3}>
                    <Stack direction="row" justifyContent="space-between">
                      <Box>
                        <Typography variant="overline" color="text.secondary">
                          Platform status
                        </Typography>
                        <Typography variant="h5" mt={0.5}>
                          {readiness.isLoading
                            ? "Checking services"
                            : platformReady
                              ? "All systems ready"
                              : "Action required"}
                        </Typography>
                      </Box>
                      {readiness.isLoading ? (
                        <CircularProgress size={28} />
                      ) : (
                        <Box
                          className={
                            platformReady ? "pulse ready" : "pulse unavailable"
                          }
                          aria-label={platformReady ? "ready" : "unavailable"}
                        />
                      )}
                    </Stack>

                    <Stack spacing={1.25}>
                      {["API", "PostgreSQL", "Redis"].map((service) => (
                        <Stack
                          key={service}
                          direction="row"
                          justifyContent="space-between"
                          className="service-row"
                        >
                          <Typography color="text.secondary">
                            {service}
                          </Typography>
                          <Typography
                            color={
                              platformReady ? "success.main" : "text.secondary"
                            }
                            fontWeight={650}
                          >
                            {readiness.isLoading
                              ? "Checking"
                              : platformReady
                                ? "Operational"
                                : "Unknown"}
                          </Typography>
                        </Stack>
                      ))}
                    </Stack>

                    {readiness.isError && (
                      <Typography
                        color="error.main"
                        variant="body2"
                        role="alert"
                      >
                        {readiness.error.message}
                      </Typography>
                    )}
                    <Button
                      variant="outlined"
                      startIcon={<RefreshRounded />}
                      onClick={() => void readiness.refetch()}
                      disabled={readiness.isFetching}
                    >
                      Check again
                    </Button>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Grid container spacing={2}>
            {capabilities.map((capability) => (
              <Grid key={capability.title} size={{ xs: 12, md: 4 }}>
                <Card sx={{ height: "100%" }}>
                  <CardContent sx={{ p: 3 }}>
                    <Box color="primary.main" mb={2}>
                      {capability.icon}
                    </Box>
                    <Typography variant="h6" mb={1}>
                      {capability.title}
                    </Typography>
                    <Typography color="text.secondary" lineHeight={1.65}>
                      {capability.description}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            alignItems={{ sm: "center" }}
            justifyContent="space-between"
            className="foundation-note"
          >
            <Stack direction="row" spacing={1.5} alignItems="center">
              <DataObjectRounded color="primary" />
              <Box>
                <Typography fontWeight={650}>Foundation complete</Typography>
                <Typography color="text.secondary" variant="body2">
                  Identity and tenant boundaries arrive in Milestone 1.
                </Typography>
              </Box>
            </Stack>
            <Typography variant="caption" color="text.secondary">
              No customer AWS actions are enabled.
            </Typography>
          </Stack>
        </Stack>
      </Container>
    </Box>
  );
}
