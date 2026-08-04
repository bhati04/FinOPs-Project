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
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listConnections } from "../aws-accounts/api";
import {
  RecommendationSeverity,
  RecommendationStatus,
  addRecommendationComment,
  evaluateRecommendations,
  listRecommendationActivities,
  listRecommendationSourceSyncs,
  listRecommendations,
  startRecommendationSourceSync,
  updateRecommendationStatus,
} from "./api";

function evidenceValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "None";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "object") return JSON.stringify(value) ?? "Object";
  return "Unsupported value";
}

function formatMoney(amount: number | null, currency: string | null): string {
  if (amount === null || !currency) return "Pricing pending";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function pricingLabel(source: string | null): string {
  if (source === "aws_price_list") return "AWS Price List";
  if (source === "aws_cost_optimization_hub")
    return "AWS Cost Optimization Hub";
  if (source === "aws_compute_optimizer") return "AWS Compute Optimizer";
  if (source === "mock_catalog") return "Development mock catalog";
  return "Unavailable";
}

function humanizeReason(reason: string | null): string {
  return reason ? reason.replaceAll("_", " ") : "pricing unavailable";
}

export function RecommendationsPage() {
  const [connectionId, setConnectionId] = useState("");
  const [syncRegion, setSyncRegion] = useState("us-east-1");
  const [statusFilter, setStatusFilter] = useState<RecommendationStatus | "">(
    "open",
  );
  const [severityFilter, setSeverityFilter] = useState<
    RecommendationSeverity | ""
  >("");
  const [selectedId, setSelectedId] = useState("");
  const [comment, setComment] = useState("");
  const queryClient = useQueryClient();
  const connections = useQuery({
    queryKey: ["aws-connections"],
    queryFn: ({ signal }) => listConnections(signal),
  });
  const recommendations = useQuery({
    queryKey: ["recommendations", statusFilter, severityFilter, connectionId],
    queryFn: ({ signal }) =>
      listRecommendations(
        {
          status: statusFilter || undefined,
          severity: severityFilter || undefined,
          connectionId: connectionId || undefined,
        },
        signal,
      ),
  });
  const selected = recommendations.data?.find(
    (recommendation) => recommendation.id === selectedId,
  );
  const activities = useQuery({
    queryKey: ["recommendation-activities", selectedId],
    queryFn: ({ signal }) => listRecommendationActivities(selectedId, signal),
    enabled: Boolean(selectedId),
  });
  const sourceSyncs = useQuery({
    queryKey: ["recommendation-source-syncs", connectionId],
    queryFn: ({ signal }) =>
      listRecommendationSourceSyncs(connectionId || undefined, signal),
    refetchInterval: 10_000,
  });
  const evaluate = useMutation({
    mutationFn: () => evaluateRecommendations(connectionId || undefined),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  const syncSources = useMutation({
    mutationFn: () => startRecommendationSourceSync(connectionId, syncRegion),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["recommendation-source-syncs"],
      });
    },
  });
  const changeStatus = useMutation({
    mutationFn: (input: { id: string; status: RecommendationStatus }) =>
      updateRecommendationStatus(input.id, input.status, comment || undefined),
    onSuccess: async () => {
      setComment("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recommendations"] }),
        queryClient.invalidateQueries({
          queryKey: ["recommendation-activities"],
        }),
      ]);
    },
  });
  const addComment = useMutation({
    mutationFn: () => addRecommendationComment(selectedId, comment),
    onSuccess: async () => {
      setComment("");
      await queryClient.invalidateQueries({
        queryKey: ["recommendation-activities", selectedId],
      });
    },
  });
  const error =
    connections.error ??
    recommendations.error ??
    activities.error ??
    sourceSyncs.error ??
    evaluate.error ??
    syncSources.error ??
    changeStatus.error ??
    addComment.error;

  function transition(status: RecommendationStatus) {
    if (!selected) return;
    changeStatus.mutate({ id: selected.id, status });
  }

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
                RECOMMENDATIONS
              </Typography>
              <Typography variant="h2">Explainable savings review</Typography>
              <Typography color="text.secondary" mt={1}>
                Versioned deterministic rules using persisted inventory
                evidence. CloudWise never performs customer AWS changes.
              </Typography>
            </Box>
            <Stack direction="row" gap={1} flexWrap="wrap">
              <Button component={Link} to="/costs" variant="outlined">
                Costs
              </Button>
              <Button component={Link} to="/metrics" variant="outlined">
                Metrics
              </Button>
              <Button component={Link} to="/aws-account" variant="outlined">
                AWS accounts
              </Button>
              <Button component={Link} to="/reports" variant="outlined">
                Reports
              </Button>
            </Stack>
          </Stack>

          {error && <Alert severity="error">{error.message}</Alert>}
          {evaluate.data && (
            <Alert severity="success">
              Rule set {evaluate.data.rule_set_version} evaluated{" "}
              {evaluate.data.evaluated_resource_count} resources and found{" "}
              {evaluate.data.eligible_recommendation_count} eligible findings.
            </Alert>
          )}
          {syncSources.data && (
            <Alert severity="info">
              AWS source sync {syncSources.data.status}. Imported{" "}
              {syncSources.data.imported_count} observations;{" "}
              {syncSources.data.deduplicated_count} merged with existing
              findings. Progress refreshes automatically.
            </Alert>
          )}
          {sourceSyncs.data?.[0] && (
            <Alert
              severity={
                sourceSyncs.data[0].status === "failed"
                  ? "error"
                  : sourceSyncs.data[0].status === "partial"
                    ? "warning"
                    : "success"
              }
            >
              Latest AWS import: {sourceSyncs.data[0].status} · matched{" "}
              {sourceSyncs.data[0].matched_resource_count}, unmatched{" "}
              {sourceSyncs.data[0].unmatched_resource_count}, deduplicated{" "}
              {sourceSyncs.data[0].deduplicated_count}.
            </Alert>
          )}

          <Card>
            <CardContent>
              <Stack
                direction={{ xs: "column", md: "row" }}
                gap={2}
                alignItems={{ xs: "stretch", md: "center" }}
              >
                <FormControl size="small" sx={{ minWidth: 210 }}>
                  <InputLabel id="recommendation-account-label">
                    AWS account
                  </InputLabel>
                  <Select
                    labelId="recommendation-account-label"
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
                <FormControl size="small" sx={{ minWidth: 170 }}>
                  <InputLabel id="recommendation-status-label">
                    Status
                  </InputLabel>
                  <Select
                    labelId="recommendation-status-label"
                    value={statusFilter}
                    label="Status"
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <MenuItem value="">All statuses</MenuItem>
                    <MenuItem value="open">Open</MenuItem>
                    <MenuItem value="acknowledged">Acknowledged</MenuItem>
                    <MenuItem value="dismissed">Dismissed</MenuItem>
                    <MenuItem value="resolved">Resolved</MenuItem>
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 150 }}>
                  <InputLabel id="recommendation-severity-label">
                    Severity
                  </InputLabel>
                  <Select
                    labelId="recommendation-severity-label"
                    value={severityFilter}
                    label="Severity"
                    onChange={(event) => setSeverityFilter(event.target.value)}
                  >
                    <MenuItem value="">All severities</MenuItem>
                    <MenuItem value="low">Low</MenuItem>
                    <MenuItem value="medium">Medium</MenuItem>
                    <MenuItem value="high">High</MenuItem>
                    <MenuItem value="critical">Critical</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="contained"
                  disabled={evaluate.isPending}
                  onClick={() => evaluate.mutate()}
                >
                  {evaluate.isPending ? "Evaluating…" : "Evaluate inventory"}
                </Button>
                <TextField
                  label="AWS Region"
                  size="small"
                  value={syncRegion}
                  onChange={(event) => setSyncRegion(event.target.value)}
                  inputProps={{ minLength: 9, maxLength: 30 }}
                  sx={{ maxWidth: 170 }}
                />
                <Button
                  variant="outlined"
                  disabled={!connectionId || syncSources.isPending}
                  onClick={() => syncSources.mutate()}
                >
                  {syncSources.isPending
                    ? "Queueing AWS sync…"
                    : "Sync AWS recommendations"}
                </Button>
              </Stack>
            </CardContent>
          </Card>

          {recommendations.isLoading ? (
            <CircularProgress size={30} />
          ) : recommendations.data?.length ? (
            <Grid container spacing={2}>
              {recommendations.data.map((recommendation) => (
                <Grid key={recommendation.id} size={{ xs: 12, md: 6 }}>
                  <Card
                    variant={
                      recommendation.id === selectedId
                        ? "elevation"
                        : "outlined"
                    }
                    sx={{ height: "100%" }}
                  >
                    <CardContent>
                      <Stack spacing={1.5}>
                        <Stack
                          direction="row"
                          justifyContent="space-between"
                          gap={1}
                        >
                          <Typography variant="h6">
                            {recommendation.title}
                          </Typography>
                          <Chip
                            label={recommendation.severity}
                            color={
                              recommendation.severity === "medium"
                                ? "warning"
                                : "default"
                            }
                            size="small"
                          />
                        </Stack>
                        <Typography color="text.secondary">
                          {recommendation.resource_name} ·{" "}
                          {recommendation.resource_type} ·{" "}
                          {recommendation.region}
                        </Typography>
                        <Stack direction="row" gap={1} flexWrap="wrap">
                          <Chip label={recommendation.status} size="small" />
                          <Chip
                            label={`${Math.round(recommendation.confidence * 100)}% confidence`}
                            size="small"
                            variant="outlined"
                          />
                          <Chip
                            label={`Rule ${recommendation.rule_version}`}
                            size="small"
                            variant="outlined"
                          />
                          {recommendation.sources.map((source) => (
                            <Chip
                              key={source}
                              label={source.replaceAll("_", " ")}
                              size="small"
                              color={
                                source === "cloudwise" ? "primary" : "info"
                              }
                              variant="outlined"
                            />
                          ))}
                          <Chip
                            label={"Pricing " + recommendation.pricing_status}
                            color={
                              recommendation.pricing_status === "available"
                                ? "success"
                                : recommendation.pricing_status === "stale"
                                  ? "warning"
                                  : "default"
                            }
                            size="small"
                            variant="outlined"
                          />
                        </Stack>
                        <Typography>
                          Current monthly list cost:{" "}
                          {formatMoney(
                            recommendation.current_monthly_cost,
                            recommendation.currency,
                          )}
                        </Typography>
                        <Typography>
                          Estimated monthly savings:{" "}
                          {formatMoney(
                            recommendation.estimated_monthly_savings,
                            recommendation.currency,
                          )}
                        </Typography>
                        {recommendation.estimated_monthly_savings !== null &&
                          recommendation.currency && (
                            <Typography>
                              Annualized opportunity:{" "}
                              {formatMoney(
                                recommendation.estimated_monthly_savings * 12,
                                recommendation.currency,
                              )}
                            </Typography>
                          )}
                        <Typography color="text.secondary">
                          {recommendation.calculation_summary}
                        </Typography>
                        <Button
                          variant="outlined"
                          onClick={() => {
                            setSelectedId(recommendation.id);
                            setComment("");
                          }}
                        >
                          Review evidence
                        </Button>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Alert severity="info">
              No recommendations match these filters. Run an inventory scan,
              then evaluate the persisted inventory.
            </Alert>
          )}

          {selected && (
            <Card>
              <CardContent>
                <Stack spacing={3}>
                  <Box>
                    <Typography variant="h5">{selected.title}</Typography>
                    <Typography color="text.secondary" mt={0.5}>
                      Evidence through {selected.evidence_period_end}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="h6" mb={1}>
                      Pricing and calculation
                    </Typography>
                    {selected.pricing_status === "stale" && (
                      <Alert severity="warning" sx={{ mb: 2 }}>
                        The last priced estimate was retained because pricing
                        could not be refreshed.
                      </Alert>
                    )}
                    {selected.pricing_status === "unavailable" && (
                      <Alert severity="info" sx={{ mb: 2 }}>
                        Pricing pending:{" "}
                        {humanizeReason(selected.pricing_unavailable_reason)}.
                      </Alert>
                    )}
                    <Stack spacing={0.75}>
                      <Typography>
                        Source: {pricingLabel(selected.pricing_source)}
                      </Typography>
                      {selected.pricing_version && (
                        <Typography>
                          Catalog version: {selected.pricing_version}
                        </Typography>
                      )}
                      {selected.pricing_effective_at && (
                        <Typography>
                          Effective: {selected.pricing_effective_at}
                        </Typography>
                      )}
                      {selected.pricing_retrieved_at && (
                        <Typography>
                          Retrieved: {selected.pricing_retrieved_at}
                        </Typography>
                      )}
                      {selected.calculation_inputs.map((input, index) => (
                        <Typography key={index} color="text.secondary">
                          {evidenceValue(input.component)}:{" "}
                          {evidenceValue(input.quantity)}{" "}
                          {evidenceValue(input.unit)} ={" "}
                          {evidenceValue(input.amount)}{" "}
                          {selected.currency ?? ""}
                        </Typography>
                      ))}
                      <Typography color="text.secondary">
                        {selected.calculation_summary}
                      </Typography>
                    </Stack>
                  </Box>
                  <Box>
                    <Typography variant="h6" mb={1}>
                      Eligibility evidence
                    </Typography>
                    <Stack spacing={1}>
                      {selected.evidence.map((item, index) => (
                        <Typography key={index}>
                          {evidenceValue(
                            item.metric ?? item.reference ?? "Evidence",
                          )}
                          : {evidenceValue(item.value)}
                          {item.unit ? ` ${evidenceValue(item.unit)}` : ""}
                        </Typography>
                      ))}
                    </Stack>
                  </Box>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="h6" mb={1}>
                        Risk notes
                      </Typography>
                      <Stack component="ul" spacing={0.5} pl={2.5}>
                        {selected.risk_notes.map((note) => (
                          <Typography component="li" key={note}>
                            {note}
                          </Typography>
                        ))}
                      </Stack>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="h6" mb={1}>
                        Verification steps
                      </Typography>
                      <Stack component="ol" spacing={0.5} pl={2.5}>
                        {selected.verification_steps.map((step) => (
                          <Typography component="li" key={step}>
                            {step}
                          </Typography>
                        ))}
                      </Stack>
                    </Grid>
                  </Grid>
                  <TextField
                    label="Review comment"
                    multiline
                    minRows={2}
                    value={comment}
                    inputProps={{ maxLength: 1000 }}
                    onChange={(event) => setComment(event.target.value)}
                  />
                  <Stack direction="row" gap={1} flexWrap="wrap">
                    {selected.status === "open" && (
                      <Button
                        onClick={() => transition("acknowledged")}
                        disabled={changeStatus.isPending}
                      >
                        Acknowledge
                      </Button>
                    )}
                    {(selected.status === "open" ||
                      selected.status === "acknowledged") && (
                      <Button
                        color="warning"
                        onClick={() => transition("dismissed")}
                        disabled={changeStatus.isPending}
                      >
                        Dismiss
                      </Button>
                    )}
                    {selected.status !== "resolved" && (
                      <Button
                        color="success"
                        onClick={() => transition("resolved")}
                        disabled={changeStatus.isPending}
                      >
                        Resolve
                      </Button>
                    )}
                    {selected.status !== "open" && (
                      <Button
                        onClick={() => transition("open")}
                        disabled={changeStatus.isPending}
                      >
                        Reopen
                      </Button>
                    )}
                    <Button
                      variant="outlined"
                      disabled={!comment.trim() || addComment.isPending}
                      onClick={() => addComment.mutate()}
                    >
                      Add comment
                    </Button>
                  </Stack>
                  <Box>
                    <Typography variant="h6" mb={1}>
                      Activity
                    </Typography>
                    {activities.isLoading ? (
                      <CircularProgress size={24} />
                    ) : activities.data?.length ? (
                      <Stack spacing={1}>
                        {activities.data.map((activity) => (
                          <Box key={activity.id}>
                            <Typography>
                              {activity.activity_type === "comment"
                                ? "Comment"
                                : `${activity.from_status ?? "new"} → ${activity.to_status}`}
                            </Typography>
                            {activity.comment && (
                              <Typography color="text.secondary">
                                {activity.comment}
                              </Typography>
                            )}
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {activity.created_at}
                            </Typography>
                          </Box>
                        ))}
                      </Stack>
                    ) : (
                      <Typography color="text.secondary">
                        No activity recorded.
                      </Typography>
                    )}
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          )}
        </Stack>
      </Container>
    </Box>
  );
}
