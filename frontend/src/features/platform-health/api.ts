import { z } from "zod";

import { runtimeConfig } from "../../lib/config";

const readinessSchema = z.object({
  status: z.enum(["ready", "not_ready"]),
  checks: z.record(
    z.string(),
    z.object({
      status: z.enum(["up", "down"]),
    }),
  ),
});

export type Readiness = z.infer<typeof readinessSchema>;

export async function getReadiness(signal?: AbortSignal): Promise<Readiness> {
  const response = await fetch(`${runtimeConfig.apiBaseUrl}/health/ready`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  const body: unknown = await response.json();
  const parsed = readinessSchema.safeParse(body);
  if (!parsed.success) {
    throw new Error("The platform returned an invalid health response.");
  }
  if (!response.ok) {
    throw new Error("One or more platform dependencies are unavailable.");
  }
  return parsed.data;
}
