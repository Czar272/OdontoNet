import { describe, expect, it } from "vitest";

import type { Appointment } from "../../types/appointment";
import { toLocalIso } from "./appointmentFormData";
import { confirmationRange, groupByDay } from "./confirmations";

describe("confirmationRange", () => {
  const now = new Date(2026, 10, 10, 15, 42, 30);

  it("va desde este minuto hasta el final del día", () => {
    expect(confirmationRange(1, now)).toEqual({
      start: toLocalIso(new Date(2026, 10, 10, 15, 42)),
      end: toLocalIso(new Date(2026, 10, 11, 0, 0)),
    });
  });

  it("cuenta días completos hacia adelante", () => {
    expect(confirmationRange(7, now).end).toBe(toLocalIso(new Date(2026, 10, 17, 0, 0)));
  });
});

describe("groupByDay", () => {
  const at = (id: number, date: Date) => ({ id, starts_at: toLocalIso(date) }) as Appointment;

  it("agrupa por día local y ordena aunque lleguen desordenadas", () => {
    const groups = groupByDay([
      at(3, new Date(2026, 10, 6, 9, 0)),
      at(1, new Date(2026, 10, 5, 15, 0)),
      at(2, new Date(2026, 10, 5, 9, 0)),
    ]);

    expect(groups.map((g) => g.key)).toEqual(["2026-11-05", "2026-11-06"]);
    expect(groups[0].items.map((a) => a.id)).toEqual([2, 1]);
    expect(groups[0].label).toMatch(/^Jueves, 5 de noviembre$/);
  });

  it("el mismo día de años distintos son grupos distintos", () => {
    const groups = groupByDay([at(1, new Date(2026, 0, 6, 9, 0)), at(2, new Date(2020, 0, 6, 9, 0))]);

    expect(groups.map((g) => g.key)).toEqual(["2020-01-06", "2026-01-06"]);
  });
});
