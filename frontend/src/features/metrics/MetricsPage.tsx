import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { listConnections, listPersistedResources } from "../aws-accounts/api";
import { listMetricSyncs, listResourceMetrics, startMetricSync } from "./api";

const supportedResourceTypes = new Set([
  "ec2_instance",
  "ebs_volume",
  "nat_gateway",
  "rds_instance",
  "lambda_function",
  "load_balancer",
]);

function formatValue(value: number | undefined, unit: string | undefined) {
  if (value === undefined) return "—";
  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
  }).format(value);
  return unit ? `${formatted} ${unit}` : formatted;
}

export function MetricsPage() {
  const [region, setRegion] = useState("us-east-1");
  const [connectionId, setConnectionId] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [metricName, setMetricName] = useState("");
  const queryClient = useQueryClient();
  const connections = useQuery({
    queryKey: ["aws-connections"],
    queryFn: ({ signal }) => listConnections(signal),
  });
  const resources = useQuery({
    queryKey: ["inventory-resources", region],
    queryFn: ({ signal }) => listPersistedResources(region, false, signal),
  });
  const syncs = useQuery({
    queryKey: ["metric-syncs"],
    queryFn: ({ signal }) => listMetricSyncs(signal),
    refetchInterval: (query) =>
      query.state.data?.some((sync) =>
        ["queued", "running"].includes(sync.status),
      )
        ? 3000
        : false,
  });
  const points = useQuery({
    queryKey: ["resource-metrics", resourceId],
    queryFn: ({ signal }) => listResourceMetrics(resourceId, 14, signal),
    enabled: Boolean(resourceId),
  });
  const synchronize = useMutation({
    mutationFn: (input: { connectionId: string; region: string }) =>
      startMetricSync(input.connectionId, input.region),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["metric-syncs"] });
    },
  });
  const latestCompletedAt = syncs.data?.find((sync) =>
    ["completed", "partial", "failed"].includes(sync.status),
  )?.completed_at;

  useEffect(() => {
    if (!latestCompletedAt) return;
    void queryClient.invalidateQueries({ queryKey: ["resource-metrics"] });
  }, [latestCompletedAt, queryClient]);

  const visibleResources = (resources.data ?? []).filter(
    (resource) =>
      resource.connection_id === connectionId &&
      supportedResourceTypes.has(resource.resource_type),
  );
  const metricNames = [
    ...new Set(points.data?.map((point) => point.metric_name) ?? []),
  ].sort();
  const selectedMetric = metricNames.includes(metricName)
    ? metricName
    : metricNames[0];
  const selectedPoints = (points.data ?? []).filter(
    (point) => point.metric_name === selectedMetric,
  );
  const values = selectedPoints.map((point) => point.value);
  const latestPoint = selectedPoints.at(-1);
  const average = values.length
    ? values.reduce((total, value) => total + value, 0) / values.length
    : undefined;
  const maximum = values.length ? Math.max(...values) : undefined;
  const chartData = selectedPoints.map((point) => ({
    timestamp: point.timestamp,
    value: point.value,
  }));
  const latestProblem = syncs.data?.find(
    (sync) => sync.status === "partial" || sync.status === "failed",
  );
  const error =
    connections.error ??
    resources.error ??
    syncs.error ??
    points.error ??
    synchronize.error;

  return (
    <Box component="main" className="app-shell">
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <Stack spacing={3}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", md: "center" }}
            gap={2}
          >
            <Box>
              <Typography color="primary.main" fontWeight={700}>
                RESOURCE METRICS
              </Typography>
              <Typography variant="h2">CloudWatch utilization</Typography>
              <Typography color="text.secondary" mt={1}>
                Fourteen days of hourly, read-only metrics for supported active
                resources.
              </Typography>
            </Box>
            <Stack direction="row" gap={1}>
              <Button component={Link} to="/costs" variant="outlined">
                Costs
              </Button>
              <Button component={Link} to="/recommendations" variant="outlined">
                Recommendations
              </Button>
              <Button component={Link} to="/aws-account" variant="outlined">
                AWS accounts
              </Button>
            </Stack>
          </Stack>

          {error && <Alert severity="error">{error.message}</Alert>}
          {latestProblem && (
            <Alert
              severity={latestProblem.status === "failed" ? "error" : "warning"}
            >
              Latest metric synchronization: {latestProblem.status}
              {latestProblem.error_code ? ` (${latestProblem.error_code})` : ""}
              .
            </Alert>
          )}

          <Card>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h6">Synchronize CloudWatch</Typography>
                <FormControl size="small" sx={{ maxWidth: 220 }}>
                  <InputLabel id="metric-region-label">Region</InputLabel>
                  <Select
                    labelId="metric-region-label"
                    value={region}
                    label="Region"
                    onChange={(event) => setRegion(event.target.value)}
                  >
                    <MenuItem value="us-east-1">us-east-1</MenuItem>
                    <MenuItem value="us-east-2">us-east-2</MenuItem>
                    <MenuItem value="us-west-1">us-west-1</MenuItem>
                    <MenuItem value="us-west-2">us-west-2</MenuItem>
                    <MenuItem value="ap-south-1">ap-south-1</MenuItem>
                    <MenuItem value="eu-west-1">eu-west-1</MenuItem>
                  </Select>
                </FormControl>
                <Stack direction="row" gap={1} flexWrap="wrap">
                  {connections.data
                    ?.filter((connection) => connection.status === "verified")
                    .map((connection) => {
                      const latest = syncs.data?.find(
                        (sync) =>
                          sync.connection_id === connection.id &&
                          sync.region === region,
                      );
                      const active = ["queued", "running"].includes(
                        latest?.status ?? "",
                      );
                      return (
                        <Stack
                          key={connection.id}
                          direction="row"
                          gap={1}
                          alignItems="center"
                        >
                          <Button
                            variant="contained"
                            disabled={active || synchronize.isPending}
                            onClick={() =>
                              synchronize.mutate({
                                connectionId: connection.id,
                                region,
                              })
                            }
                          >
                            Sync {connection.alias}
                          </Button>
                          {latest && (
                            <Chip label={latest.status} size="small" />
                          )}
                        </Stack>
                      );
                    })}
                </Stack>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Stack direction={{ xs: "column", md: "row" }} gap={2}>
                <FormControl size="small" sx={{ minWidth: 220 }}>
                  <InputLabel id="metric-account-label">AWS account</InputLabel>
                  <Select
                    labelId="metric-account-label"
                    value={connectionId}
                    label="AWS account"
                    onChange={(event) => {
                      setConnectionId(event.target.value);
                      setResourceId("");
                    }}
                  >
                    {connections.data?.map((connection) => (
                      <MenuItem key={connection.id} value={connection.id}>
                        {connection.alias}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 280 }}>
                  <InputLabel id="metric-resource-label">Resource</InputLabel>
                  <Select
                    labelId="metric-resource-label"
                    value={resourceId}
                    label="Resource"
                    disabled={!connectionId}
                    onChange={(event) => {
                      setResourceId(event.target.value);
                      setMetricName("");
                    }}
                  >
                    {visibleResources.map((resource) => (
                      <MenuItem key={resource.id} value={resource.id}>
                        {resource.name} · {resource.resource_type}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 220 }}>
                  <InputLabel id="metric-name-label">Metric</InputLabel>
                  <Select
                    labelId="metric-name-label"
                    value={selectedMetric ?? ""}
                    label="Metric"
                    disabled={!metricNames.length}
                    onChange={(event) => setMetricName(event.target.value)}
                  >
                    {metricNames.map((name) => (
                      <MenuItem key={name} value={name}>
                        {name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Stack>
            </CardContent>
          </Card>

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography color="text.secondary">Latest</Typography>
                  <Typography variant="h4" mt={1}>
                    {formatValue(latestPoint?.value, latestPoint?.unit)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography color="text.secondary">Average</Typography>
                  <Typography variant="h4" mt={1}>
                    {formatValue(average, latestPoint?.unit)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography color="text.secondary">Maximum</Typography>
                  <Typography variant="h4" mt={1}>
                    {formatValue(maximum, latestPoint?.unit)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card>
            <CardContent>
              <Typography variant="h6">
                {selectedMetric ?? "Resource metric history"}
              </Typography>
              <Typography color="text.secondary" mb={2}>
                {latestPoint
                  ? `${latestPoint.statistic} · ${latestPoint.namespace}`
                  : "Select a synchronized resource to view its history."}
              </Typography>
              {points.isLoading ? (
                <CircularProgress size={28} />
              ) : chartData.length ? (
                <Box sx={{ width: "100%", height: 380 }}>
                  <ResponsiveContainer>
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="timestamp" minTickGap={40} />
                      <YAxis />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#5f8f7f"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              ) : (
                <Alert severity="info">
                  No CloudWatch datapoints match this resource and period.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Stack>
      </Container>
    </Box>
  );
}
