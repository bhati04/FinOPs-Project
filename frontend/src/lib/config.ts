import { z } from "zod";

const runtimeConfigSchema = z.object({
  apiBaseUrl: z.string().url(),
});

interface CloudWiseImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

const environment = import.meta.env as CloudWiseImportMetaEnv;

export const runtimeConfig = runtimeConfigSchema.parse({
  apiBaseUrl: environment.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1",
});
