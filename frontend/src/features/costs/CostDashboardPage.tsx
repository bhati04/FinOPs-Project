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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { listConnections } from "../aws-accounts/api";
import {
  CostAggregate,
  CostGranularity,
  CostGrouping,
  listCostAggregates,
  listCostForecasts,
  listCostSyncs,
  startCostSync,
} from "./api";
import {
  buildDailyServiceBreakdown,
  estimateCurrentMonthCost,
} from "./calculations";

const groupingLabels: Record<CostGrouping, string> = {
  service_region: "Service and Region",
  usage_type: "Usage type",
  tag: "Configured cost tag",
};

const serviceColors = [
  "#5f8f7f",
  "#aa8a50",
  "#7a746a",
  "#8b6f75",
  "#b46c55",
  "#5e8066",
  "#969890",
];

function categoryLabel(row: CostAggregate) {
  if (row.grouping === "usage_type") return row.usage_type || "Unknown";
  if (row.grouping === "tag") return row.tag_value || "Untagged";
  return row.region ? `${row.service} · ${row.region}` : row.service;
}

function formatMoney(amount: number | undefined, currency: string | undefined) {
  if (amount === undefined || !currency) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function CostDashboardPage() {
  const [currency, setCurrency] = useState<string>();
  const [connectionId, setConnectionId] = useState("");
  const [granularity, setGranularity] = useState<CostGranularity>("daily");
  const [grouping, setGrouping] = useState<CostGrouping>("service_region");
  const queryClient = useQueryClient();
  const selectedConnection = connectionId || undefined;

  const connections = useQuery({
    queryKey: ["aws-connections"],
    queryFn: ({ signal }) => listConnections(signal),
  });
  const syncs = useQuery({
    queryKey: ["cost-syncs"],
    queryFn: ({ signal }) => listCostSyncs(signal),
    refetchInterval: (query) =>
      query.state.data?.some((sync) =>
        ["queued", "running"].includes(sync.status),
      )
        ? 3000
        : false,
  });
  const aggregates = useQuery({
    queryKey: ["cost-aggregates", granularity, grouping, selectedConnection],
    queryFn: ({ signal }) =>
      listCostAggregates(granularity, grouping, selectedConnection, signal),
  });
  const dailyServices = useQuery({
    queryKey: [
      "cost-aggregates",
      "daily",
      "service_region",
      selectedConnection,
    ],
    queryFn: ({ signal }) =>
      listCostAggregates("daily", "service_region", selectedConnection, signal),
  });
  const forecasts = useQuery({
    queryKey: ["cost-forecasts", granularity, selectedConnection],
    queryFn: ({ signal }) =>
      listCostForecasts(granularity, selectedConnection, signal),
  });
  const synchronize = useMutation({
    mutationFn: startCostSync,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cost-syncs"] });
    },
  });
  const latestCompletedAt = syncs.data?.find((sync) =>
    ["completed", "partial", "failed"].includes(sync.status),
  )?.completed_at;

  useEffect(() => {
    if (!latestCompletedAt) return;
    void queryClient.invalidateQueries({ queryKey: ["cost-aggregates"] });
    void queryClient.invalidateQueries({ queryKey: ["cost-forecasts"] });
  }, [latestCompletedAt, queryClient]);

  const currencies = [
    ...new Set([
      ...(aggregates.data?.map((row) => row.currency) ?? []),
      ...(dailyServices.data?.map((row) => row.currency) ?? []),
      ...(forecasts.data?.map((row) => row.currency) ?? []),
    ]),
  ].sort();
  const selectedCurrency = currencies.includes(currency ?? "")
    ? currency
    : currencies[0];
  const dailyServiceBreakdown = buildDailyServiceBreakdown(
    dailyServices.data ?? [],
    selectedCurrency,
  );
  const monthlyEstimate = estimateCurrentMonthCost(
    dailyServices.data ?? [],
    selectedCurrency,
  );
  const periodTotals = new Map<string, number>();
  for (const row of aggregates.data ?? []) {
    if (row.currency !== selectedCurrency) continue;
    periodTotals.set(
      row.period_start,
      (periodTotals.get(row.period_start) ?? 0) + row.amount,
    );
  }
  const forecastTotals = new Map<string, number>();
  for (const row of forecasts.data ?? []) {
    if (row.currency !== selectedCurrency) continue;
    forecastTotals.set(
      row.period_start,
      (forecastTotals.get(row.period_start) ?? 0) + row.mean_amount,
    );
  }
  const periods = [
    ...new Set([...periodTotals.keys(), ...forecastTotals.keys()]),
  ].sort();
  const chartData = periods.map((date) => ({
    date,
    actual: periodTotals.get(date),
    forecast: forecastTotals.get(date),
  }));
  const latestPeriod = [...periodTotals.keys()].sort().at(-1);
  const latestTotal = latestPeriod ? periodTotals.get(latestPeriod) : undefined;
  const categories = new Map<string, number>();
  for (const row of aggregates.data ?? []) {
    if (row.currency !== selectedCurrency || row.period_start !== latestPeriod)
      continue;
    const label = categoryLabel(row);
    categories.set(label, (categories.get(label) ?? 0) + row.amount);
  }
  const topCategories = [...categories]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 8);
  const latestPartial = syncs.data?.find(
    (sync) => sync.status === "partial" || sync.status === "failed",
  );
  const error =
    connections.error ??
    syncs.error ??
    aggregates.error ??
    dailyServices.error ??
    forecasts.error ??
    synchronize.error;
  const loading = aggregates.isLoading || forecasts.isLoading;

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
                COST MANAGEMENT
              </Typography>
              <Typography variant="h2">AWS spend visibility</Typography>
              <Typography color="text.secondary" mt={1}>
                Tenant-scoped Cost Explorer actuals and forecasts. Values are
                estimates and may change as AWS finalizes billing data.
              </Typography>
            </Box>
            <Stack direction="row" gap={1}>
              <Button component={Link} to="/metrics" variant="outlined">
                Metrics
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
          {latestPartial && (
            <Alert
              severity={latestPartial.status === "failed" ? "error" : "warning"}
            >
              Latest cost synchronization status: {latestPartial.status}
              {latestPartial.failed_facets.length
                ? `. Unavailable facets: ${latestPartial.failed_facets.join(", ")}.`
                : "."}
            </Alert>
          )}

          <Card>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h6">Synchronize Cost Explorer</Typography>
                <Stack direction="row" gap={1} flexWrap="wrap">
                  {connections.data
                    ?.filter((connection) => connection.status === "verified")
                    .map((connection) => {
                      const latest = syncs.data?.find(
                        (sync) => sync.connection_id === connection.id,
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
                            onClick={() => synchronize.mutate(connection.id)}
                          >
                            Sync {connection.alias}
                          </Button>
                          {latest && (
                            <Chip label={latest.status} size="small" />
                          )}
                        </Stack>
                      );
                    })}
                  {connections.data?.filter(
                    (connection) => connection.status === "verified",
                  ).length === 0 && (
                    <Typography color="text.secondary">
                      Verify an AWS account connection before synchronizing
                      costs.
                    </Typography>
                  )}
                </Stack>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Stack
                direction={{ xs: "column", md: "row" }}
                gap={2}
                alignItems={{ xs: "stretch", md: "center" }}
              >
                <FormControl size="small" sx={{ minWidth: 190 }}>
                  <InputLabel id="cost-account-label">AWS account</InputLabel>
                  <Select
                    labelId="cost-account-label"
                    value={connectionId}
                    label="AWS account"
                    onChange={(event) => setConnectionId(event.target.value)}
                  >
                    <MenuItem value="">All accounts</MenuItem>
                    {connections.data?.map((connection) => (
                      <MenuItem key={connection.id} value={connection.id}>
                        {connection.alias}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 145 }}>
                  <InputLabel id="cost-granularity-label">Period</InputLabel>
                  <Select
                    labelId="cost-granularity-label"
                    value={granularity}
                    label="Period"
                    onChange={(event) => setGranularity(event.target.value)}
                  >
                    <MenuItem value="daily">Daily</MenuItem>
                    <MenuItem value="monthly">Monthly</MenuItem>
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 205 }}>
                  <InputLabel id="cost-grouping-label">Grouping</InputLabel>
                  <Select
                    labelId="cost-grouping-label"
                    value={grouping}
                    label="Grouping"
                    onChange={(event) => setGrouping(event.target.value)}
                  >
                    {Object.entries(groupingLabels).map(([value, label]) => (
                      <MenuItem key={value} value={value}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Stack direction="row" gap={1} flexWrap="wrap">
                  {currencies.map((item) => (
                    <Chip
                      key={item}
                      label={item}
                      color={item === selectedCurrency ? "primary" : "default"}
                      onClick={() => setCurrency(item)}
                    />
                  ))}
                </Stack>
              </Stack>
            </CardContent>
          </Card>

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography color="text.secondary">
                    Latest {granularity === "daily" ? "day" : "month"}
                  </Typography>
                  <Typography variant="h3" mt={1}>
                    {formatMoney(latestTotal, selectedCurrency)}
                  </Typography>
                  <Typography color="text.secondary" mt={1}>
                    {latestPeriod ?? "No synchronized cost period"}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography color="text.secondary">Month to date</Typography>
                  <Typography variant="h3" mt={1}>
                    {formatMoney(
                      monthlyEstimate?.monthToDate,
                      selectedCurrency,
                    )}
                  </Typography>
                  <Typography color="text.secondary" mt={1}>
                    {monthlyEstimate
                      ? `Daily actuals through ${monthlyEstimate.through}`
                      : "No current-month daily data"}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent>
                  <Typography color="text.secondary">
                    Estimated monthly cost
                  </Typography>
                  <Typography variant="h3" mt={1}>
                    {formatMoney(
                      monthlyEstimate?.estimatedMonthEnd,
                      selectedCurrency,
                    )}
                  </Typography>
                  <Typography color="text.secondary" mt={1}>
                    Month-to-date daily average projected through month end.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card>
            <CardContent>
              <Typography variant="h6">
                Daily cost by AWS service
                {selectedCurrency ? ` (${selectedCurrency})` : ""}
              </Typography>
              <Typography color="text.secondary" mb={2}>
                Seven calendar days ending with the latest synchronized day.
                Regions are combined, with the six largest services shown
                separately.
              </Typography>
              {dailyServices.isLoading ? (
                <CircularProgress size={28} />
              ) : dailyServiceBreakdown.data.length ? (
                <Box sx={{ width: "100%", height: 380 }}>
                  <ResponsiveContainer>
                    <ComposedChart data={dailyServiceBreakdown.data}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      {dailyServiceBreakdown.services.map((service, index) => (
                        <Bar
                          key={service}
                          dataKey={service}
                          stackId="services"
                          fill={serviceColors[index % serviceColors.length]}
                        />
                      ))}
                    </ComposedChart>
                  </ResponsiveContainer>
                </Box>
              ) : (
                <Alert severity="info">
                  No daily service costs are available yet. Run a cost
                  synchronization after enabling Cost Explorer.
                </Alert>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6">
                Actual and forecast cost
                {selectedCurrency ? ` (${selectedCurrency})` : ""}
              </Typography>
              <Typography color="text.secondary" mb={2}>
                Actual UnblendedCost compared with the Cost Explorer mean
                forecast.
              </Typography>
              {loading ? (
                <CircularProgress size={28} />
              ) : chartData.length ? (
                <Box sx={{ width: "100%", height: 360 }}>
                  <ResponsiveContainer>
                    <ComposedChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="actual" fill="#5f8f7f" name="Actual" />
                      <Line
                        dataKey="forecast"
                        stroke="#aa8a50"
                        strokeWidth={2}
                        name="Forecast"
                        connectNulls
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </Box>
              ) : (
                <Alert severity="info">
                  No cost data matches these filters. Run a synchronization or
                  choose another grouping.
                </Alert>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h6" mb={2}>
                Largest {groupingLabels[grouping].toLowerCase()} groups
              </Typography>
              {topCategories.length ? (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Group</TableCell>
                      <TableCell align="right">Cost</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {topCategories.map(([label, amount]) => (
                      <TableRow key={label}>
                        <TableCell>{label}</TableCell>
                        <TableCell align="right">
                          {formatMoney(amount, selectedCurrency)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Typography color="text.secondary">
                  No category breakdown is available for the latest period.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Stack>
      </Container>
    </Box>
  );
}
