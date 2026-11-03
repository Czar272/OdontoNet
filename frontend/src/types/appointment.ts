import type { Doctor } from "./doctor";

export type AppointmentStatus =
  | "scheduled"
  | "confirmed"
  | "completed"
  | "cancelled"
  | "no_show";

export const APPOINTMENT_STATUSES: AppointmentStatus[] = [
  "scheduled",
  "confirmed",
  "completed",
  "cancelled",
  "no_show",
];

export const STATUS_LABELS: Record<AppointmentStatus, string> = {
  scheduled: "Programada",
  confirmed: "Confirmada",
  completed: "Atendida",
  cancelled: "Cancelada",
  no_show: "No asistió",
};

/** Colores por estado en la agenda y su leyenda. */
export const STATUS_COLORS: Record<AppointmentStatus, string> = {
  scheduled: "#2563eb",
  confirmed: "#059669",
  completed: "#6b7280",
  cancelled: "#dc2626",
  no_show: "#d97706",
};

/** Solo estas se reprograman (el backend responde 409 con las demás). */
export const PENDING_STATUSES: AppointmentStatus[] = ["scheduled", "confirmed"];

/** Datos mínimos del paciente que devuelve la agenda. */
export interface AppointmentPatient {
  id: number;
  first_name: string;
  last_name: string;
  /** Para llamar a confirmar (ODON-146). */
  phone: string | null;
  archived_at: string | null;
}

export interface Appointment {
  id: number;
  clinic_id: number;
  patient_id: number;
  doctor_id: number;
  /** ISO con zona horaria; se muestra en la hora local del navegador. */
  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  status: AppointmentStatus;
  reason: string | null;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
  patient: AppointmentPatient;
  doctor: Doctor;
}

export interface CreateAppointmentDTO {
  patient_id: number;
  doctor_id: number;
  starts_at: string;
  duration_minutes: number;
  reason?: string;
  /** Confirmación para agendar fuera del horario del doctor (ODON-142). */
  allow_outside_schedule?: boolean;
}

/** Reprogramación parcial: el paciente y el estado no cambian aquí. */
export interface UpdateAppointmentDTO {
  doctor_id?: number;
  starts_at?: string;
  duration_minutes?: number;
  reason?: string;
  allow_outside_schedule?: boolean;
}

/** La cita con la que choca un horario (409 de la API). */
export interface AppointmentConflict {
  appointment_id: number;
  starts_at: string;
  ends_at: string;
  doctor_id: number;
  doctor_name: string;
  patient_id: number;
  patient_name: string;
}

/** Un cambio de estado del historial (ODON-146). */
export interface AppointmentStatusChange {
  id: number;
  /** null en el registro de creación. */
  from_status: AppointmentStatus | null;
  to_status: AppointmentStatus;
  note: string | null;
  changed_at: string;
  changed_by: { id: number; name: string };
}
