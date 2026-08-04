import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listConnections } from "../aws-accounts/api";
import {
  ReportFormat,
  ReportFrequency,
  ReportType,
  createReport,
  createSchedule,
  downloadReport,
  listAuditEvents,
  listReports,
  listSchedules,
  setScheduleEnabled,
} from "./api";

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

const today = new Date();
const weekAgo = new Date(today);
weekAgo.setUTCDate(today.getUTCDate() - 7);

export function ReportsPage() {
  const [connectionId, setConnectionId] = useState("");
  const [reportType, setReportType] = useState<ReportType>("executive_summary");
  const [reportFormat, setReportFormat] = useState<ReportFormat>("csv");
  const [periodStart, setPeriodStart] = useState(isoDate(weekAgo));
  const [periodEnd, setPeriodEnd] = useState(isoDate(today));
  const [scheduleName, setScheduleName] = useState("Weekly FinOps review");
  const [frequency, setFrequency] = useState<ReportFrequency>("weekly");
  const [recipients, setRecipients] = useState("");
  const queryClient = useQueryClient();

  const connections = useQuery({
    queryKey: ["aws-connections"],
    queryFn: ({ signal }) => listConnections(signal),
  });
  const reports = useQuery({
    queryKey: ["reports"],
    queryFn: ({ signal }) => listReports(signal),
    refetchInterval: 10_000,
  });
  const schedules = useQuery({
    queryKey: ["report-schedules"],
    queryFn: ({ signal }) => listSchedules(signal),
  });
  const audit = useQuery({
    queryKey: ["audit-events"],
    queryFn: ({ signal }) => listAuditEvents(signal),
  });

  const generate = useMutation({
    mutationFn: () =>
      createReport({
        reportType,
        reportFormat,
        connectionId: connectionId || undefined,
        periodStart,
        periodEnd,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
  const addSchedule = useMutation({
    mutationFn: () =>
      createSchedule({
        name: scheduleName,
        reportType,
        reportFormat,
        frequency,
        connectionId: connectionId || undefined,
        recipients: recipients
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report-schedules"] });
    },
  });
  const toggleSchedule = useMutation({
    mutationFn: (input: { id: string; enabled: boolean }) =>
      setScheduleEnabled(input.id, input.enabled),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report-schedules"] });
    },
  });
  const download = useMutation({ mutationFn: downloadReport });
  const error =
    connections.error ??
    reports.error ??
    schedules.error ??
    audit.error ??
    generate.error ??
    addSchedule.error ??
    toggleSchedule.error ??
    download.error;

  return (
    <Box component="main" className="app-shell">
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <Stack spacing={3}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            justifyContent="space-between"
            gap={2}
          >
            <Box>
              <Typography color="primary.main" fontWeight={700}>
                REPORTS & AUDIT
              </Typography>
              <Typography variant="h2">Shareable FinOps reporting</Typography>
              <Typography color="text.secondary" mt={1}>
                Generate private CSV or PDF reports, schedule delivery, and
                review append-only platform activity.
              </Typography>
            </Box>
            <Stack direction="row" gap={1} flexWrap="wrap">
              <Button component={Link} to="/costs" variant="outlined">
                Costs
              </Button>
              <Button component={Link} to="/recommendations" variant="outlined">
                Recommendations
              </Button>
            </Stack>
          </Stack>

          {error && <Alert severity="error">{error.message}</Alert>}
          {generate.data && (
            <Alert severity="success">
              Report queued. This page refreshes generation status
              automatically.
            </Alert>
          )}

          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>
                Create report
              </Typography>
              <Stack
                direction={{ xs: "column", md: "row" }}
                gap={2}
                flexWrap="wrap"
              >
                <FormControl size="small" sx={{ minWidth: 190 }}>
                  <InputLabel id="report-account-label">AWS account</InputLabel>
                  <Select
                    labelId="report-account-label"
                    label="AWS account"
                    value={connectionId}
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
                <FormControl size="small" sx={{ minWidth: 190 }}>
                  <InputLabel id="report-type-label">Report</InputLabel>
                  <Select
                    labelId="report-type-label"
                    label="Report"
                    value={reportType}
                    onChange={(event) => setReportType(event.target.value)}
                  >
                    <MenuItem value="executive_summary">
                      Executive summary
                    </MenuItem>
                    <MenuItem value="cost_detail">Cost detail</MenuItem>
                    <MenuItem value="recommendations">Recommendations</MenuItem>
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 110 }}>
                  <InputLabel id="report-format-label">Format</InputLabel>
                  <Select
                    labelId="report-format-label"
                    label="Format"
                    value={reportFormat}
                    onChange={(event) => setReportFormat(event.target.value)}
                  >
                    <MenuItem value="csv">CSV</MenuItem>
                    <MenuItem value="pdf">PDF</MenuItem>
                  </Select>
                </FormControl>
                <TextField
                  type="date"
                  label="Start"
                  size="small"
                  value={periodStart}
                  onChange={(event) => setPeriodStart(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  type="date"
                  label="End"
                  size="small"
                  value={periodEnd}
                  onChange={(event) => setPeriodEnd(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <Button variant="contained" onClick={() => generate.mutate()}>
                  Generate
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <Grid container spacing={2}>
            {reports.data?.map((report) => (
              <Grid key={report.id} size={{ xs: 12, md: 6 }}>
                <Card variant="outlined" sx={{ height: "100%" }}>
                  <CardContent>
                    <Stack spacing={1.25}>
                      <Typography variant="h6">
                        {report.report_type.replaceAll("_", " ")}
                      </Typography>
                      <Stack direction="row" gap={1}>
                        <Chip label={report.report_format} size="small" />
                        <Chip label={report.status} size="small" />
                      </Stack>
                      <Typography color="text.secondary">
                        {report.period_start} to {report.period_end} · expires{" "}
                        {new Date(report.expires_at).toLocaleDateString()}
                      </Typography>
                      <Button
                        variant="outlined"
                        disabled={
                          report.status !== "completed" || download.isPending
                        }
                        onClick={() => download.mutate(report)}
                      >
                        Download
                      </Button>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>
                Scheduled delivery
              </Typography>
              <Stack direction={{ xs: "column", md: "row" }} gap={2} mb={3}>
                <TextField
                  label="Schedule name"
                  size="small"
                  value={scheduleName}
                  onChange={(event) => setScheduleName(event.target.value)}
                />
                <FormControl size="small" sx={{ minWidth: 130 }}>
                  <InputLabel id="report-frequency-label">Frequency</InputLabel>
                  <Select
                    labelId="report-frequency-label"
                    label="Frequency"
                    value={frequency}
                    onChange={(event) => setFrequency(event.target.value)}
                  >
                    <MenuItem value="daily">Daily</MenuItem>
                    <MenuItem value="weekly">Weekly</MenuItem>
                    <MenuItem value="monthly">Monthly</MenuItem>
                  </Select>
                </FormControl>
                <TextField
                  label="Recipients (comma-separated)"
                  size="small"
                  value={recipients}
                  onChange={(event) => setRecipients(event.target.value)}
                  sx={{ minWidth: 280 }}
                />
                <Button variant="outlined" onClick={() => addSchedule.mutate()}>
                  Create schedule
                </Button>
              </Stack>
              <Stack spacing={1}>
                {schedules.data?.map((schedule) => (
                  <Stack
                    key={schedule.id}
                    direction={{ xs: "column", md: "row" }}
                    justifyContent="space-between"
                    alignItems={{ xs: "stretch", md: "center" }}
                    gap={1}
                  >
                    <Typography>
                      {schedule.name} · {schedule.frequency} · next{" "}
                      {new Date(schedule.next_run_at).toLocaleString()}
                    </Typography>
                    <Button
                      size="small"
                      onClick={() =>
                        toggleSchedule.mutate({
                          id: schedule.id,
                          enabled: !schedule.enabled,
                        })
                      }
                    >
                      {schedule.enabled ? "Disable" : "Enable"}
                    </Button>
                  </Stack>
                ))}
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Typography variant="h5">Audit log</Typography>
              <Typography color="text.secondary" mb={2}>
                Administrator-only, append-only authenticated mutation history.
              </Typography>
              <Stack spacing={1}>
                {audit.data?.slice(0, 20).map((event) => (
                  <Box key={event.id}>
                    <Typography>{event.action}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {event.outcome} ·{" "}
                      {new Date(event.created_at).toLocaleString()} ·
                      correlation {event.correlation_id}
                    </Typography>
                  </Box>
                ))}
                {audit.data?.length === 0 && (
                  <Typography color="text.secondary">
                    No audit events are visible for this role yet.
                  </Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Stack>
      </Container>
    </Box>
  );
}
