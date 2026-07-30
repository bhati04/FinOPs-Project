import { z } from "zod";

import { runtimeConfig } from "../../lib/config";

const identitySchema = z.object({
  account_id: z.string().regex(/^\d{12}$/),
  principal_arn: z.string(),
  principal_id: z.string(),
  authentication_type: z.string(),
  region: z.string(),
  status: z.string(),
});

const inventorySchema = z.object({
  account_id: z.string().regex(/^\d{12}$/),
  region: z.string(),
  resource_count: z.number().int().nonnegative(),
  resources: z.array(
    z.object({
      resource_id: z.string(),
      name: z.string(),
      instance_type: z.string(),
      state: z.string(),
      availability_zone: z.string(),
      private_ip: z.string().nullable().optional(),
      public_ip: z.string().nullable().optional(),
      launch_time: z.string().datetime(),
      tags: z.record(z.string(), z.unknown()),
    }),
  ),
});

export type AwsIdentity = z.infer<typeof identitySchema>;
export type Ec2Inventory = z.infer<typeof inventorySchema>;

async function getJson<T>(
  url: string,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  const body: unknown = await response.json();
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new Error("The AWS service returned an invalid response.");
  }
  if (!response.ok) {
    throw new Error("AWS account information could not be retrieved.");
  }
  return parsed.data;
}

export function getAwsIdentity(region: string, signal?: AbortSignal) {
  return getJson(
    runtimeConfig.apiBaseUrl +
      "/aws-accounts/current/identity?region=" +
      encodeURIComponent(region),
    identitySchema,
    signal,
  );
}

export function getEc2Inventory(region: string, signal?: AbortSignal) {
  return getJson(
    runtimeConfig.apiBaseUrl +
      "/aws-accounts/current/inventory/ec2?region=" +
      encodeURIComponent(region),
    inventorySchema,
    signal,
  );
}
