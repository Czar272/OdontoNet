import { describe, expect, it } from "vitest";

import { formatPeriod, periodError, presetPeriod, toIsoDate } from "./period";

// Miércoles 11 de marzo de 2026, hora local.
const TODAY = new Date(2026, 2, 11, 15, 30);

describe("presetPeriod", () => {
  it("mes en curso por defecto", () => {
    expect(presetPeriod("this_month", TODAY)).toEqual({ from: "2026-03-01", to: "2026-03-31" });
  });

  it("mes anterior, incluso al cruzar de año", () => {
    expect(presetPeriod("last_month", TODAY)).toEqual({ from: "2026-02-01", to: "2026-02-28" });
    expect(presetPeriod("last_month", new Date(2026, 0, 5))).toEqual({ from: "2025-12-01", to: "2025-12-31" });
  });

  it("semana de lunes a domingo", () => {
    expect(presetPeriod("this_week", TODAY)).toEqual({ from: "2026-03-09", to: "2026-03-15" });
    // Un domingo pertenece a la semana que empezó el lunes anterior.
    expect(presetPeriod("this_week", new Date(2026, 2, 15))).toEqual({ from: "2026-03-09", to: "2026-03-15" });
  });

  it("últimos 30 días incluyen hoy", () => {
    expect(presetPeriod("last_30_days", TODAY)).toEqual({ from: "2026-02-10", to: "2026-03-11" });
  });

  it("año completo", () => {
    expect(presetPeriod("this_year", TODAY)).toEqual({ from: "2026-01-01", to: "2026-12-31" });
  });
});

describe("periodError", () => {
  it("acepta un periodo válido", () => {
    expect(periodError({ from: "2026-03-01", to: "2026-03-01" })).toBeNull();
  });

  it("rechaza fechas vacías, invertidas o un periodo demasiado largo", () => {
    expect(periodError({ from: "", to: "2026-03-01" })).toMatch(/dos fechas/);
    expect(periodError({ from: "2026-03-10", to: "2026-03-01" })).toMatch(/anterior/);
    expect(periodError({ from: "2025-01-01", to: "2026-03-01" })).toMatch(/400 días/);
  });
});

describe("formato", () => {
  it("usa la fecha local, no UTC", () => {
    expect(toIsoDate(new Date(2026, 2, 31, 23, 59))).toBe("2026-03-31");
  });

  it("muestra un solo día sin rango", () => {
    expect(formatPeriod({ from: "2026-03-05", to: "2026-03-05" })).not.toContain("–");
    expect(formatPeriod({ from: "2026-03-01", to: "2026-03-31" })).toContain("–");
  });
});
