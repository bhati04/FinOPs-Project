import { z } from "zod";

import { runtimeConfig } from "../../lib/config";
import { getAccessToken } from "../identity/session";

const syncSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid(),
  status: z.enum(["queued", "running", "completed", "partial", "failed"]),
  record_count: z.number().int().nonnegative(),
  error_code: z.string().nullable(),
  failed_facets: z.array(z.string()),
  created_at: z.string().datetime(),
  started_at: z.string().datetime().nullable(),
  completed_at: z.string().datetime().nullable(),
});

const aggregateSchema = z.object({
  connection_id: z.string().uuid(),
  period_start: z.string(),
  granularity: z.enum(["daily", "monthly"]),
  grouping: z.enum(["service_region", "usage_type", "tag"]),
  service: z.string(),
  region: z.string(),
  usage_type: z.string(),
  tag_key: z.string(),
  tag_value: z.string(),
  amount: z.union([z.string(), z.number()]).transform(Number),
  currency: z.string(),
});

const forecastSchema = z.object({
  connection_id: z.string().uuid(),
  period_start: z.string(),
  period_end: z.string(),
  granularity: z.enum(["daily", "monthly"]),
  mean_amount: z.union([z.string(), z.number()]).transform(Number),
  lower_bound: z.union([z.string(), z.number()]).transform(Number),
  upper_bound: z.union([z.string(), z.number()]).transform(Number),
  currency: z.string(),
});

export type CostSync = z.infer<typeof syncSchema>;
export type CostAggregate = z.infer<typeof aggregateSchema>;
export type CostForecast = z.infer<typeof forecastSchema>;
export type CostGranularity = "daily" | "monthly";
export type CostGrouping = "service_region" | "usage_type" | "tag";

function headers() {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${getAccessToken() ?? ""}`,
  };
}

async function parseResponse<T>(response: Response, schema: z.ZodType<T>) {
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error("Cost information could not be retrieved.");
  return schema.parse(payload);
}

export async function startCostSync(connectionId: string) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/costs/connections/${encodeURIComponent(connectionId)}/sync`,
    { method: "POST", headers: headers() },
  );
  return parseResponse(response, syncSchema);
}

export async function listCostSyncs(signal?: AbortSignal) {
  const response = await fetch(`${runtimeConfig.apiBaseUrl}/costs/syncs`, {
    headers: headers(),
    signal,
  });
  return parseResponse(response, z.array(syncSchema));
}

export async function listCostAggregates(
  granularity: CostGranularity,
  grouping: CostGrouping,
  connectionId?: string,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ granularity, grouping });
  if (connectionId) params.set("connection_id", connectionId);
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/costs/aggregates?${params.toString()}`,
    { headers: headers(), signal },
  );
  return parseResponse(response, z.array(aggregateSchema));
}

export async function listCostForecasts(
  granularity: CostGranularity,
  connectionId?: string,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ granularity });
  if (connectionId) params.set("connection_id", connectionId);
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/costs/forecasts?${params.toString()}`,
    { headers: headers(), signal },
  );
  return parseResponse(response, z.array(forecastSchema));
}
