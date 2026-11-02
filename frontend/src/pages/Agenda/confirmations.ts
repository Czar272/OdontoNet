import { getAppointments } from "../../services/appointmentService";
import { toLocalIso } from "./appointmentFormData";

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
