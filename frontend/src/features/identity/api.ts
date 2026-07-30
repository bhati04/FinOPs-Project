import { z } from "zod";

import { runtimeConfig } from "../../lib/config";
import { getRefreshToken, type AuthTokens } from "./session";

const tokenSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(32),
  token_type: z.literal("bearer"),
  expires_in: z.number().int().positive(),
});

async function submitIdentity(
  path: string,
  body: Record<string, string>,
): Promise<AuthTokens> {
  const response = await fetch(runtimeConfig.apiBaseUrl + path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? "The email or password is incorrect."
        : "Authentication could not be completed.",
    );
  }
  const parsed = tokenSchema.safeParse(payload);
  if (!parsed.success) {
    throw new Error("The authentication service returned an invalid response.");
  }
  return parsed.data;
}

export function login(email: string, password: string) {
  return submitIdentity("/auth/login", { email, password });
}

export function register(
  email: string,
  password: string,
  organizationName: string,
) {
  return submitIdentity("/auth/register", {
    email,
    password,
    organization_name: organizationName,
  });
}

export async function logout() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return;
  }
  const response = await fetch(runtimeConfig.apiBaseUrl + "/auth/logout", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok && response.status !== 401) {
    throw new Error("The server session could not be revoked.");
  }
}
