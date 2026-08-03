import {
  buildDailyServiceBreakdown,
  estimateCurrentMonthCost,
} from "./calculations";

function row(period: string, service: string, amount: number) {
  return {
    period_start: period,
    service,
    amount,
    currency: "USD",
  };
}

test("builds a seven-day service series and combines Regions", () => {
  const rows = [
    row("2026-08-01", "Amazon EC2", 50),
    row("2026-08-02", "Amazon EC2", 4),
    row("2026-08-02", "Amazon EC2", 6),
    row("2026-08-08", "Amazon S3", 3),
  ];

  const result = buildDailyServiceBreakdown(rows, "USD", 7);

  expect(result.data).toHaveLength(7);
  expect(result.data[0]?.date).toBe("2026-08-02");
  expect(result.data[6]?.date).toBe("2026-08-08");
  expect(result.data[0]?.["Amazon EC2"]).toBe(10);
  expect(result.data[6]?.["Amazon S3"]).toBe(3);
});

test("projects the current month from daily month-to-date cost", () => {
  const rows = Array.from({ length: 8 }, (_, index) =>
    row(`2026-08-${String(index + 1).padStart(2, "0")}`, "Amazon EC2", 10),
  );

  const result = estimateCurrentMonthCost(
    rows,
    "USD",
    new Date("2026-08-09T00:00:00Z"),
  );

  expect(result).toEqual({
    monthToDate: 80,
    estimatedMonthEnd: 310,
    through: "2026-08-08",
  });
});
