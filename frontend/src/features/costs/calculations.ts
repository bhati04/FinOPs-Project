import { CostAggregate } from "./api";

type DailyServiceCost = Pick<
  CostAggregate,
  "period_start" | "service" | "amount" | "currency"
>;

export interface DailyServicePoint {
  date: string;
  [service: string]: string | number;
}

export interface DailyServiceBreakdown {
  data: DailyServicePoint[];
  services: string[];
}

export interface MonthlyEstimate {
  monthToDate: number;
  estimatedMonthEnd: number;
  through: string;
}

export function buildDailyServiceBreakdown(
  rows: DailyServiceCost[],
  currency: string | undefined,
  periodLimit = 7,
  serviceLimit = 6,
): DailyServiceBreakdown {
  if (!currency) return { data: [], services: [] };
  const matchingRows = rows.filter((row) => row.currency === currency);
  const latestPeriod = matchingRows
    .map((row) => row.period_start)
    .sort()
    .at(-1);
  if (!latestPeriod) return { data: [], services: [] };
  const latestDate = new Date(`${latestPeriod}T00:00:00Z`);
  const periods = Array.from({ length: periodLimit }, (_, index) => {
    const date = new Date(latestDate);
    date.setUTCDate(date.getUTCDate() - (periodLimit - index - 1));
    return date.toISOString().slice(0, 10);
  });
  const periodSet = new Set(periods);
  const serviceTotals = new Map<string, number>();

  for (const row of matchingRows) {
    if (!periodSet.has(row.period_start)) continue;
    const service = row.service || "Unknown service";
    serviceTotals.set(service, (serviceTotals.get(service) ?? 0) + row.amount);
  }

  const topServices = [...serviceTotals]
    .sort(
      ([leftName, leftTotal], [rightName, rightTotal]) =>
        rightTotal - leftTotal || leftName.localeCompare(rightName),
    )
    .slice(0, serviceLimit)
    .map(([service]) => service);
  const topServiceSet = new Set(topServices);
  const hasOtherServices = serviceTotals.size > topServices.length;
  const services = hasOtherServices
    ? [...topServices, "Other services"]
    : topServices;

  const data = periods.map((period) => {
    const point: DailyServicePoint = { date: period };
    for (const service of services) point[service] = 0;
    for (const row of matchingRows) {
      if (row.period_start !== period) continue;
      const service = row.service || "Unknown service";
      const key = topServiceSet.has(service) ? service : "Other services";
      point[key] = Number(point[key] ?? 0) + row.amount;
    }
    return point;
  });

  return { data, services };
}

export function estimateCurrentMonthCost(
  rows: DailyServiceCost[],
  currency: string | undefined,
  currentDate = new Date(),
): MonthlyEstimate | undefined {
  if (!currency) return undefined;
  const year = currentDate.getUTCFullYear();
  const month = currentDate.getUTCMonth() + 1;
  const monthKey = `${year}-${String(month).padStart(2, "0")}`;
  const matchingRows = rows.filter(
    (row) =>
      row.currency === currency && row.period_start.startsWith(`${monthKey}-`),
  );
  const through = matchingRows
    .map((row) => row.period_start)
    .sort()
    .at(-1);
  if (!through) return undefined;
  const observedDays = Number(through.slice(8, 10));
  if (!Number.isInteger(observedDays) || observedDays < 1) return undefined;
  const monthToDate = matchingRows.reduce(
    (total, row) => total + row.amount,
    0,
  );
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();

  return {
    monthToDate,
    estimatedMonthEnd: (monthToDate / observedDays) * daysInMonth,
    through,
  };
}
