import { afterEach, describe, expect, it, vi } from "vitest";

import {
  INDICATORS,
  PRIMARY_COUNT,
  formatIndicator,
  loadExpanded,
  saveExpanded,
} from "./dashboardIndicators";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("indicadores", () => {
  it("cuatro principales y sin claves repetidas", () => {
    expect(INDICATORS.slice(0, PRIMARY_COUNT).map((i) => i.key)).toEqual([
      "appointments_today",
      "attendance_rate",
      "patients_new",
      "occupancy_rate",
    ]);
    expect(new Set(INDICATORS.map((i) => i.key)).size).toBe(INDICATORS.length);
  });

  it("formatea conteos, porcentajes y tasas sin base", () => {
    expect(formatIndicator(0)).toBe("0");
    expect(formatIndicator(16.7, true)).toBe("16.7 %");
    expect(formatIndicator(null, true)).toBe("—");
  });
});

describe("preferencia «mostrar más»", () => {
  it("se guarda por usuario", () => {
    saveExpanded(1, true);
    expect(loadExpanded(1)).toBe(true);
    expect(loadExpanded(2)).toBe(false);
    saveExpanded(1, false);
    expect(loadExpanded(1)).toBe(false);
    expect(loadExpanded(undefined)).toBe(false);
  });

  it("no falla si el almacenamiento no está disponible", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    expect(() => saveExpanded(1, true)).not.toThrow();
    expect(loadExpanded(1)).toBe(false);
  });
});
