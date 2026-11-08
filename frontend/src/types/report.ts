/** Reportes de citas y pacientes (ODON-206). */
export type ReportGrouping = "day" | "week" | "month";

export interface StatusCounts {
  scheduled: number;
  confirmed: number;
  completed: number;
  cancelled: number;
  no_show: number;
  total: number;
  /** Sobre atendidas + no asistió; null sin base. */
  attendance_rate: number | null;
  no_show_rate: number | null;
}

/** Grupo de fechas (YYYY-MM-DD, zona de la clínica), recortado al periodo. */
export interface Bucket {
  period_start: string;
  period_end: string;
  /** La semana o el mes no está completo dentro del periodo. */
  partial: boolean;
}

export interface AppointmentBucket extends StatusCounts, Bucket {}

export interface DoctorAppointments extends StatusCounts {
  doctor: { id: number; name: string };
}

interface ReportBase {
  date_from: string;
  date_to: string;
  timezone: string;
  group: ReportGrouping;
  doctor_id: number | null;
}

export interface AppointmentsReport extends ReportBase {
  series: AppointmentBucket[];
  by_doctor: DoctorAppointments[];
  totals: StatusCounts;
}

export interface PatientsReport extends ReportBase {
  series: (Bucket & { new_patients: number })[];
  total_new: number;
  /** Pacientes registrados antes de que existiera la fecha de alta. */
  without_registration_date: number;
}

export interface ReportParams {
  from: string;
  to: string;
  doctorId?: number | null;
  group: ReportGrouping;
}

export type ReportKind = "appointments" | "patients";
