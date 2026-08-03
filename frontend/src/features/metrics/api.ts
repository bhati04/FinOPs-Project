import { z } from "zod";

import { runtimeConfig } from "../../lib/config";
import { getAccessToken } from "../identity/session";

const metricSyncSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid(),
  region: z.string(),
  status: z.enum(["queued", "running", "completed", "partial", "failed"]),
  window_start: z.string().datetime(),
  window_end: z.string().datetime(),
  record_count: z.number().int().nonnegative(),
  failed_batch_count: z.number().int().nonnegative(),
  error_code: z.string().nullable(),
  created_at: z.string().datetime(),
  started_at: z.string().datetime().nullable(),
  completed_at: z.string().datetime().nullable(),
});

const resourceMetricSchema = z.object({
  inventory_resource_id: z.string().uuid(),
  resource_type: z.string(),
  resource_name: z.string(),
  region: z.string(),
  namespace: z.string(),
  metric_name: z.string(),
  statistic: z.string(),
  unit: z.string(),
  timestamp: z.string().datetime(),
  value: z.union([z.string(), z.number()]).transform(Number),
});

export type MetricSync = z.infer<typeof metricSyncSchema>;
export type ResourceMetric = z.infer<typeof resourceMetricSchema>;

function headers() {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${getAccessToken() ?? ""}`,
  };
}

async function parseResponse<T>(response: Response, schema: z.ZodType<T>) {
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error("Resource metrics could not be retrieved.");
  return schema.parse(payload);
}

export async function startMetricSync(
  connectionId: string,
  region: string,
  days = 14,
) {
  const params = new URLSearchParams({ region, days: String(days) });
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/metrics/connections/${encodeURIComponent(connectionId)}/sync?${params.toString()}`,
    { method: "POST", headers: headers() },
  );
  return parseResponse(response, metricSyncSchema);
}

export async function listMetricSyncs(signal?: AbortSignal) {
  const response = await fetch(`${runtimeConfig.apiBaseUrl}/metrics/syncs`, {
    headers: headers(),
    signal,
  });
  return parseResponse(response, z.array(metricSyncSchema));
}

export async function listResourceMetrics(
  resourceId: string,
  days = 14,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ days: String(days) });
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/metrics/resources/${encodeURIComponent(resourceId)}?${params.toString()}`,
    { headers: headers(), signal },
  );
  return parseResponse(response, z.array(resourceMetricSchema));
}
