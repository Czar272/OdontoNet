import type { BusinessHoursInput } from "@fullcalendar/core";

import type { DoctorAvailability } from "../../types/availability";

/**
 * Horario para sombrear la agenda (ODON-142). Con un doctor filtrado, el suyo;
 * sin filtro, la unión de todos. Sin bloques no se sombrea nada: los doctores
 * sin horario registrado se agendan libremente.
 *
 * FullCalendar numera los días desde el domingo (0); el backend desde el lunes (0).
 */
export function toBusinessHours(
  availability: DoctorAvailability[],
  doctorIds: number[],
): BusinessHoursInput {
  const blocks = availability
    .filter((a) => doctorIds.includes(a.doctor_id))
    .flatMap((a) => a.blocks);

  if (blocks.length === 0) return false;

  return blocks.map((block) => ({
    daysOfWeek: [(block.weekday + 1) % 7],
    startTime: block.start_time.slice(0, 5),
    endTime: block.end_time.slice(0, 5),
  }));
}

/** Ids de los doctores que todavía no tienen horario registrado. */
export function withoutSchedule(
  availability: DoctorAvailability[],
  doctorIds: number[],
): number[] {
  const withBlocks = new Set(
    availability.filter((a) => a.blocks.length > 0).map((a) => a.doctor_id),
  );
  return doctorIds.filter((id) => !withBlocks.has(id));
}
