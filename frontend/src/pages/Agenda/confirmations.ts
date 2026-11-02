import { getAppointments } from "../../services/appointmentService";
import type { Appointment } from "../../types/appointment";
import { formatDay, localDateParts, toLocalIso } from "./appointmentFormData";

/** Se vuelve a consultar cada minuto: varias personas pueden confirmar a la vez. */
export const TO_CONFIRM_REFRESH_MS = 60_000;

/** Días hacia adelante que cubre la lista (desde ahora). */
export type ConfirmationWindow = 1 | 2 | 3 | 7 | 14;

export const CONFIRMATION_WINDOWS: {
  value: ConfirmationWindow;
  label: string;
}[] = [
  { value: 1, label: "Hoy" },
  { value: 2, label: "Hoy y mañana" },
  { value: 3, label: "Próximos 3 días" },
  { value: 7, label: "Próximos 7 días" },
  { value: 14, label: "Próximos 14 días" },
];

/** Rango [ahora, fin del día N) en ISO local. */
export function confirmationRange(days: ConfirmationWindow, now = new Date()) {
  const start = new Date(now);
  start.setSeconds(0, 0);
  const end = new Date(now);
  end.setHours(0, 0, 0, 0);
  end.setDate(end.getDate() + days);
  return { start: toLocalIso(start), end: toLocalIso(end) };
}

/** Consulta de citas programadas sin confirmar (compartida con el contador). */
export function toConfirmQuery(days: ConfirmationWindow) {
  return {
    queryKey: ["appointments", "to-confirm", days],
    queryFn: () =>
      getAppointments({ ...confirmationRange(days), statuses: ["scheduled"] }),
  };
}

export interface DayGroup {
  /** Fecha local "2026-11-05": clave única aunque el texto se repita entre años. */
  key: string;
  /** "Jueves, 5 de noviembre". */
  label: string;
  items: Appointment[];
}

/** Agrupa por día local y ordena por inicio, sin depender del orden recibido. */
export function groupByDay(appointments: Appointment[]): DayGroup[] {
  const sorted = [...appointments].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
  );
  const groups = new Map<string, DayGroup>();
  for (const appointment of sorted) {
    const key = localDateParts(new Date(appointment.starts_at)).date;
    const group = groups.get(key);
    if (group) {
      group.items.push(appointment);
    } else {
      const label = formatDay(appointment.starts_at);
      groups.set(key, {
        key,
        label: label.charAt(0).toUpperCase() + label.slice(1),
        items: [appointment],
      });
    }
  }
  return [...groups.values()];
}
