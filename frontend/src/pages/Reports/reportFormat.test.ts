import { describe, expect, it } from "vitest";

import { CHART_STATUSES, bucketLabel, formatRate } from "./reportFormat";

describe("reportFormat", () => {
  const full = (start: string, end: string) => ({ period_start: start, period_end: end, partial: false });

  it("etiqueta cada agrupación", () => {
    expect(bucketLabel(full("2026-03-02", "2026-03-02"), "day")).not.toContain("Sem.");
    expect(bucketLabel(full("2026-03-02", "2026-03-08"), "week")).toMatch(/^Sem\. /);
    expect(bucketLabel(full("2026-03-01", "2026-03-31"), "month")).toContain("2026");
  });

  it("un grupo recortado muestra su rango real", () => {
    const partialWeek = { period_start: "2026-03-30", period_end: "2026-03-31", partial: true };
    expect(bucketLabel(partialWeek, "week")).toContain("–");
    expect(bucketLabel(partialWeek, "week")).not.toContain("Sem.");
    const oneDay = { period_start: "2026-03-01", period_end: "2026-03-01", partial: true };
    expect(bucketLabel(oneDay, "week")).not.toContain("–");
  });

  it("muestra «—» cuando la tasa no tiene base", () => {
    expect(formatRate(null)).toBe("—");
    expect(formatRate(12.5)).toBe("12.5 %");
  });

  it("cubre los cinco estados una sola vez", () => {
    const statuses = CHART_STATUSES.map((item) => item.status);
    expect(new Set(statuses).size).toBe(5);
    expect(new Set(CHART_STATUSES.map((item) => item.color)).size).toBe(5);
  });
});
