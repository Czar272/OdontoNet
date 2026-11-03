import { describe, expect, it } from "vitest";

import type { DoctorAvailability } from "../../types/availability";
import { toBusinessHours, withoutSchedule } from "./agendaSchedule";

const availability: DoctorAvailability[] = [
  {
    doctor_id: 1,
    timezone: "America/Guatemala",
    blocks: [
      { weekday: 0, start_time: "08:00:00", end_time: "12:00:00" },
      { weekday: 6, start_time: "09:00:00", end_time: "11:00:00" },
    ],
  },
  { doctor_id: 2, timezone: "America/Guatemala", blocks: [] },
];

describe("toBusinessHours", () => {
  it("convierte lunes=0 del backend a lunes=1 de FullCalendar (domingo=0)", () => {
    expect(toBusinessHours(availability, [1])).toEqual([
      { daysOfWeek: [1], startTime: "08:00", endTime: "12:00" },
      { daysOfWeek: [0], startTime: "09:00", endTime: "11:00" },
    ]);
  });

  it("sin bloques no sombrea nada", () => {
    expect(toBusinessHours(availability, [2])).toBe(false);
    expect(toBusinessHours([], [1, 2])).toBe(false);
  });
});

describe("withoutSchedule", () => {
  it("lista los doctores sin horario registrado", () => {
    expect(withoutSchedule(availability, [1, 2, 3])).toEqual([2, 3]);
  });
});
