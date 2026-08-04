import { z } from "zod";

import { runtimeConfig } from "../../lib/config";
import { getAccessToken } from "../identity/session";

const statusSchema = z.enum(["open", "acknowledged", "dismissed", "resolved"]);
const severitySchema = z.enum(["low", "medium", "high", "critical"]);
const sourceSchema = z.enum([
  "cloudwise",
  "cost_optimization_hub",
  "compute_optimizer",
]);

const evaluationSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid().nullable(),
  rule_set_version: z.string(),
  evaluated_resource_count: z.number().int().nonnegative(),
  eligible_recommendation_count: z.number().int().nonnegative(),
  created_at: z.string().datetime(),
  completed_at: z.string().datetime(),
});

const recommendationSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid(),
  inventory_resource_id: z.string().uuid(),
  resource_type: z.string(),
  resource_name: z.string(),
  region: z.string(),
  rule_id: z.string(),
  rule_version: z.string(),
  canonical_action: z.string(),
  sources: z.array(sourceSchema),
  source_metadata: z.record(z.string(), z.unknown()),
  title: z.string(),
  category: z.string(),
  severity: severitySchema,
  confidence: z.union([z.string(), z.number()]).transform(Number),
  status: statusSchema,
  evidence: z.array(z.record(z.string(), z.unknown())),
  exclusions: z.array(z.string()),
  risk_notes: z.array(z.string()),
  verification_steps: z.array(z.string()),
  evidence_period_start: z.string().datetime().nullable(),
  evidence_period_end: z.string().datetime(),
  estimate_type: z.enum(["exact", "usage_based", "advisory"]),
  current_monthly_cost: z
    .union([z.string(), z.number()])
    .transform(Number)
    .nullable(),
  estimated_monthly_savings: z
    .union([z.string(), z.number()])
    .transform(Number)
    .nullable(),
  currency: z.string().nullable(),
  pricing_status: z.enum(["available", "stale", "unavailable"]),
  pricing_source: z.string().nullable(),
  pricing_version: z.string().nullable(),
  pricing_effective_at: z.string().datetime().nullable(),
  pricing_retrieved_at: z.string().datetime().nullable(),
  pricing_unavailable_reason: z.string().nullable(),
  calculation_inputs: z.array(z.record(z.string(), z.unknown())),
  calculation_summary: z.string(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  resolved_at: z.string().datetime().nullable(),
});

const activitySchema = z.object({
  id: z.string().uuid(),
  actor_user_id: z.string().uuid().nullable(),
  activity_type: z.enum(["status_changed", "comment"]),
  from_status: statusSchema.nullable(),
  to_status: statusSchema.nullable(),
  comment: z.string().nullable(),
  created_at: z.string().datetime(),
});

const sourceSyncSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid(),
  region: z.string(),
  status: z.enum(["queued", "running", "completed", "partial", "failed"]),
  imported_count: z.number().int().nonnegative(),
  matched_resource_count: z.number().int().nonnegative(),
  unmatched_resource_count: z.number().int().nonnegative(),
  deduplicated_count: z.number().int().nonnegative(),
  completed_sources: z.array(z.string()),
  failed_sources: z.array(z.string()),
  error_code: z.string().nullable(),
  created_at: z.string().datetime(),
  started_at: z.string().datetime().nullable(),
  completed_at: z.string().datetime().nullable(),
});

export type Recommendation = z.infer<typeof recommendationSchema>;
export type RecommendationStatus = z.infer<typeof statusSchema>;
export type RecommendationSeverity = z.infer<typeof severitySchema>;
export type RecommendationActivity = z.infer<typeof activitySchema>;
export type RecommendationSourceSync = z.infer<typeof sourceSyncSchema>;

function headers(contentType = false) {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${getAccessToken() ?? ""}`,
    ...(contentType ? { "Content-Type": "application/json" } : {}),
  };
}

async function parseResponse<T>(response: Response, schema: z.ZodType<T>) {
  const payload: unknown = await response.json();
  if (!response.ok)
    throw new Error("Recommendation operation could not be completed.");
  return schema.parse(payload);
}

export async function evaluateRecommendations(connectionId?: string) {
  const params = new URLSearchParams();
  if (connectionId) params.set("connection_id", connectionId);
  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations/evaluate${query}`,
    { method: "POST", headers: headers(true) },
  );
  return parseResponse(response, evaluationSchema);
}

export async function listRecommendations(
  filters: {
    status?: RecommendationStatus;
    severity?: RecommendationSeverity;
    connectionId?: string;
  },
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.connectionId) params.set("connection_id", filters.connectionId);
  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations${query}`,
    { headers: headers(), signal },
  );
  return parseResponse(response, z.array(recommendationSchema));
}

export async function updateRecommendationStatus(
  recommendationId: string,
  status: RecommendationStatus,
  comment?: string,
) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations/${encodeURIComponent(recommendationId)}/status`,
    {
      method: "PATCH",
      headers: headers(true),
      body: JSON.stringify({ status, comment: comment || null }),
    },
  );
  return parseResponse(response, recommendationSchema);
}

export async function addRecommendationComment(
  recommendationId: string,
  comment: string,
) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations/${encodeURIComponent(recommendationId)}/comments`,
    {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({ comment }),
    },
  );
  return parseResponse(response, activitySchema);
}

export async function listRecommendationActivities(
  recommendationId: string,
  signal?: AbortSignal,
) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations/${encodeURIComponent(recommendationId)}/activities`,
    { headers: headers(), signal },
  );
  return parseResponse(response, z.array(activitySchema));
}

export async function startRecommendationSourceSync(
  connectionId: string,
  region: string,
) {
  const params = new URLSearchParams({ region });
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations/connections/${encodeURIComponent(connectionId)}/source-syncs?${params.toString()}`,
    { method: "POST", headers: headers(true) },
  );
  return parseResponse(response, sourceSyncSchema);
}

export async function listRecommendationSourceSyncs(
  connectionId?: string,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (connectionId) params.set("connection_id", connectionId);
  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/recommendations/source-syncs${query}`,
    { headers: headers(), signal },
  );
  return parseResponse(response, z.array(sourceSyncSchema));
}
