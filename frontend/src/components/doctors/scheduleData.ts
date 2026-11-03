import type { AvailabilityBlock } from "../../types/availability";
import { WEEKDAY_NAMES } from "../../types/availability";

/** Bloque editable: horas "HH:mm". */
export interface ScheduleRange {
  start: string;
  end: string;
}

/** Horario por día: índice 0 = lunes … 6 = domingo. */
export type WeekSchedule = ScheduleRange[][];

export const DEFAULT_RANGE: ScheduleRange = { start: "08:00", end: "12:00" };

const hhmm = (value: string) => value.slice(0, 5);

export function emptyWeek(): WeekSchedule {
  return WEEKDAY_NAMES.map(() => []);
}

/** Bloques de la API → horario por día, ordenado. */
export function blocksToWeek(blocks: AvailabilityBlock[]): WeekSchedule {
  const week = emptyWeek();
  for (const block of blocks) {
    week[block.weekday].push({
      start: hhmm(block.start_time),
      end: hhmm(block.end_time),
    });
  }
  week.forEach((day) => day.sort((a, b) => a.start.localeCompare(b.start)));
  return week;
}

export function weekToBlocks(week: WeekSchedule): AvailabilityBlock[] {
  return week.flatMap((day, weekday) =>
    day.map((range) => ({
      weekday,
      start_time: range.start,
      end_time: range.end,
    })),
  );
}

/** Mensaje del primer error, o null si el horario es válido (mismo criterio que el backend). */
export function validateWeek(week: WeekSchedule): string | null {
  for (const [weekday, day] of week.entries()) {
    const name = WEEKDAY_NAMES[weekday].toLowerCase();
    const sorted = [...day].sort((a, b) => a.start.localeCompare(b.start));
    for (const range of sorted) {
      if (!range.start || !range.end) return `Completa las horas del ${name}.`;
      if (range.end <= range.start) {
        return `En el ${name}, la hora de fin debe ser posterior a la de inicio.`;
      }
    }
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i].start < sorted[i - 1].end)
        return `Los bloques del ${name} se cruzan.`;
    }
  }
  return null;
}

/** Copia el lunes a martes–viernes (atajo habitual). */
export function copyMondayToWeekdays(week: WeekSchedule): WeekSchedule {
  return week.map((day, weekday) =>
    weekday >= 1 && weekday <= 4 ? week[0].map((range) => ({ ...range })) : day,
  );
}

/** «08:00–12:00 y 14:00–18:00» o «No atiende». */
export function describeDay(day: ScheduleRange[]): string {
  if (day.length === 0) return "No atiende";
  const ranges = day.map((r) => `${r.start}–${r.end}`);
  return ranges.length === 1
    ? ranges[0]
    : `${ranges.slice(0, -1).join(", ")} y ${ranges.at(-1)}`;
}
