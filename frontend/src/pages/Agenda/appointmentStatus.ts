import type { Appointment, AppointmentStatus } from "../../types/appointment";

/**
 * Reflejo de las reglas del backend (app/services/appointment_service.py)
 * para decidir qué botones mostrar. El backend sigue siendo la autoridad.
 */
export const ALLOWED_TRANSITIONS: Record<
  AppointmentStatus,
  AppointmentStatus[]
> = {
  scheduled: ["confirmed", "completed", "no_show", "cancelled"],
  confirmed: ["completed", "no_show", "scheduled", "cancelled"],
  cancelled: ["scheduled"],
  completed: ["no_show"],
  no_show: ["completed"],
};

const AFTER_START: AppointmentStatus[] = ["completed", "no_show"];

/** Texto del botón según el estado de origen y el de destino. */
export function actionLabel(
  from: AppointmentStatus,
  to: AppointmentStatus,
): string {
  if (to === "scheduled")
    return from === "cancelled" ? "Reactivar" : "Quitar confirmación";
  return {
    confirmed: "Confirmar",
    completed: "Marcar atendida",
    no_show: "Marcar no asistió",
    cancelled: "Cancelar cita",
  }[to];
}

/** Cambios de estado posibles ahora mismo para la cita. */
export function availableTransitions(
  appointment: Appointment,
  now: Date = new Date(),
): AppointmentStatus[] {
  const started = new Date(appointment.starts_at) <= now;
  const ended = new Date(appointment.ends_at) <= now;

  return ALLOWED_TRANSITIONS[appointment.status].filter((target) => {
    if (AFTER_START.includes(target)) return started;
    // Reactivar una cancelada: solo si todavía no empieza.
    if (appointment.status === "cancelled") return !started;
    return !ended;
  });
}
