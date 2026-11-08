import type { AppointmentStatus } from "./appointment";

/** Indicadores del periodo (ODON-202). Las tasas son 0–100 o null sin base. */
export interface DashboardIndicators {
  patients_active: number;
  /** Solo pacientes con fecha de alta (los anteriores a ODON-202 no la tienen). */
  patients_new: number;
  appointments_today: number;
  appointments_week: number;
  appointments_period: number;
  attendance_rate: number | null;
  no_show_rate: number | null;
  cancellation_rate: number | null;
  visits_registered: number;
  treatments_completed: number;
  periodontal_finalized: number;
  images_uploaded: number;
  occupancy_rate: number | null;
}

export interface DashboardAgendaItem {
  id: number;
  starts_at: string;
  duration_minutes: number;
  status: AppointmentStatus;
  patient: { id: number; name: string };
  doctor: { id: number; name: string };
}

export interface Dashboard {
  /** Fechas locales de la clínica, YYYY-MM-DD, incluidas. */
  date_from: string;
  date_to: string;
  timezone: string;
  doctor_id: number | null;
  indicators: DashboardIndicators;
  agenda_today: DashboardAgendaItem[];
}

export interface DashboardParams {
  from: string;
  to: string;
  doctorId?: number | null;
}
