import { z } from "zod";

import { runtimeConfig } from "../../lib/config";
import { getAccessToken } from "../identity/session";

const reportTypeSchema = z.enum([
  "executive_summary",
  "cost_detail",
  "recommendations",
]);
const reportFormatSchema = z.enum(["csv", "pdf"]);
const frequencySchema = z.enum(["daily", "weekly", "monthly"]);

const reportSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid().nullable(),
  schedule_id: z.string().uuid().nullable(),
  report_type: reportTypeSchema,
  report_format: reportFormatSchema,
  status: z.enum(["queued", "running", "completed", "failed", "expired"]),
  period_start: z.string(),
  period_end: z.string(),
  content_type: z.string().nullable(),
  byte_size: z.number().int().nullable(),
  checksum_sha256: z.string().nullable(),
  error_code: z.string().nullable(),
  expires_at: z.string().datetime(),
  created_at: z.string().datetime(),
  started_at: z.string().datetime().nullable(),
  completed_at: z.string().datetime().nullable(),
});

const scheduleSchema = z.object({
  id: z.string().uuid(),
  connection_id: z.string().uuid().nullable(),
  name: z.string(),
  report_type: reportTypeSchema,
  report_format: reportFormatSchema,
  frequency: frequencySchema,
  recipients: z.array(z.string()),
  enabled: z.boolean(),
  next_run_at: z.string().datetime(),
  last_run_at: z.string().datetime().nullable(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

const auditSchema = z.object({
  id: z.string().uuid(),
  actor_user_id: z.string().uuid(),
  action: z.string(),
  entity_type: z.string(),
  outcome: z.string(),
  correlation_id: z.string().uuid(),
  context: z.record(z.string(), z.unknown()),
  created_at: z.string().datetime(),
});

export type ReportType = z.infer<typeof reportTypeSchema>;
export type ReportFormat = z.infer<typeof reportFormatSchema>;
export type ReportFrequency = z.infer<typeof frequencySchema>;
export type GeneratedReport = z.infer<typeof reportSchema>;

function headers(contentType = false) {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${getAccessToken() ?? ""}`,
    ...(contentType ? { "Content-Type": "application/json" } : {}),
  };
}

async function parse<T>(response: Response, schema: z.ZodType<T>) {
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error("Report operation could not be completed.");
  return schema.parse(payload);
}

export async function listReports(signal?: AbortSignal) {
  const response = await fetch(`${runtimeConfig.apiBaseUrl}/reports`, {
    headers: headers(),
    signal,
  });
  return parse(response, z.array(reportSchema));
}

export async function createReport(input: {
  reportType: ReportType;
  reportFormat: ReportFormat;
  connectionId?: string;
  periodStart: string;
  periodEnd: string;
}) {
  const response = await fetch(`${runtimeConfig.apiBaseUrl}/reports`, {
    method: "POST",
    headers: headers(true),
    body: JSON.stringify({
      report_type: input.reportType,
      report_format: input.reportFormat,
      connection_id: input.connectionId || null,
      period_start: input.periodStart,
      period_end: input.periodEnd,
    }),
  });
  return parse(response, reportSchema);
}

export async function downloadReport(report: GeneratedReport) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/reports/${encodeURIComponent(report.id)}/download`,
    { headers: headers() },
  );
  if (!response.ok) throw new Error("Report download could not be completed.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `cloudwise-${report.report_type}.${report.report_format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function listSchedules(signal?: AbortSignal) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/reports/schedules`,
    {
      headers: headers(),
      signal,
    },
  );
  return parse(response, z.array(scheduleSchema));
}

export async function createSchedule(input: {
  name: string;
  reportType: ReportType;
  reportFormat: ReportFormat;
  frequency: ReportFrequency;
  connectionId?: string;
  recipients: string[];
}) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/reports/schedules`,
    {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        name: input.name,
        report_type: input.reportType,
        report_format: input.reportFormat,
        frequency: input.frequency,
        connection_id: input.connectionId || null,
        recipients: input.recipients,
      }),
    },
  );
  return parse(response, scheduleSchema);
}

export async function setScheduleEnabled(scheduleId: string, enabled: boolean) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/reports/schedules/${encodeURIComponent(scheduleId)}`,
    {
      method: "PATCH",
      headers: headers(true),
      body: JSON.stringify({ enabled }),
    },
  );
  return parse(response, scheduleSchema);
}

export async function listAuditEvents(signal?: AbortSignal) {
  const response = await fetch(
    `${runtimeConfig.apiBaseUrl}/reports/audit?limit=100`,
    {
      headers: headers(),
      signal,
    },
  );
  if (response.status === 403) return [];
  return parse(response, z.array(auditSchema));
}
