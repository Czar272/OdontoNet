import { describe, expect, it } from "vitest";

import {
  blocksToWeek,
  copyMondayToWeekdays,
  describeDay,
  emptyWeek,
  validateWeek,
  weekToBlocks,
} from "./scheduleData";

describe("scheduleData", () => {
  it("convierte bloques de la API a días y de vuelta", () => {
    const week = blocksToWeek([
      { weekday: 0, start_time: "14:00:00", end_time: "18:00:00" },
      { weekday: 0, start_time: "08:00:00", end_time: "12:00:00" },
      { weekday: 6, start_time: "09:00:00", end_time: "11:00:00" },
    ]);

    expect(week[0]).toEqual([
      { start: "08:00", end: "12:00" },
      { start: "14:00", end: "18:00" },
    ]);
    expect(week[6]).toEqual([{ start: "09:00", end: "11:00" }]);
    expect(weekToBlocks(week)).toEqual([
      { weekday: 0, start_time: "08:00", end_time: "12:00" },
      { weekday: 0, start_time: "14:00", end_time: "18:00" },
      { weekday: 6, start_time: "09:00", end_time: "11:00" },
    ]);
  });

  it("valida fin posterior al inicio, horas completas y cruces", () => {
    const week = emptyWeek();
    expect(validateWeek(week)).toBeNull();

    week[1] = [{ start: "12:00", end: "08:00" }];
    expect(validateWeek(week)).toBe("En el martes, la hora de fin debe ser posterior a la de inicio.");

    week[1] = [{ start: "08:00", end: "" }];
    expect(validateWeek(week)).toBe("Completa las horas del martes.");

    week[1] = [{ start: "08:00", end: "12:00" }, { start: "11:00", end: "13:00" }];
    expect(validateWeek(week)).toBe("Los bloques del martes se cruzan.");

    week[1] = [{ start: "08:00", end: "12:00" }, { start: "12:00", end: "13:00" }];
    expect(validateWeek(week)).toBeNull();
  });

  it("copia el lunes a martes–viernes sin tocar el fin de semana", () => {
    const week = emptyWeek();
    week[0] = [{ start: "08:00", end: "12:00" }];
    week[5] = [{ start: "09:00", end: "10:00" }];

    const copied = copyMondayToWeekdays(week);

    expect(copied.slice(0, 5).every((day) => day.length === 1 && day[0].start === "08:00")).toBe(true);
    expect(copied[5]).toEqual([{ start: "09:00", end: "10:00" }]);
    expect(copied[6]).toEqual([]);
    copied[1][0].start = "07:00";
    expect(copied[0][0].start).toBe("08:00");
  });

  it("describe el día", () => {
    expect(describeDay([])).toBe("No atiende");
    expect(describeDay([{ start: "08:00", end: "12:00" }, { start: "14:00", end: "18:00" }])).toBe(
      "08:00–12:00 y 14:00–18:00",
    );
  });
});
