import type {
  Appointment,
  AppointmentStatus,
  CreateAppointmentDTO,
  UpdateAppointmentDTO,
} from "../types/appointment";
import api from "./api";

export interface AppointmentFilters {
  /** Rango [start, end) en ISO con zona horaria. */
  start?: string;
  end?: string;
  doctorId?: number;
  patientId?: number;
  statuses?: AppointmentStatus[];
}

export async function getAppointments(
  filters: AppointmentFilters,
): Promise<Appointment[]> {
  const params = new URLSearchParams();
  if (filters.start) params.append("start", filters.start);
  if (filters.end) params.append("end", filters.end);
  if (filters.doctorId) params.append("doctor_id", String(filters.doctorId));
  if (filters.patientId) params.append("patient_id", String(filters.patientId));
  // `status` se repite: ?status=scheduled&status=confirmed
  filters.statuses?.forEach((status) => params.append("status", status));

  const response = await api.get("/appointments/", { params });

  return response.data;
}

export async function createAppointment(
  appointment: CreateAppointmentDTO,
): Promise<Appointment> {
  const response = await api.post("/appointments/", appointment);

  return response.data;
}

export async function updateAppointment(
  id: number,
  changes: UpdateAppointmentDTO,
): Promise<Appointment> {
  const response = await api.patch(`/appointments/${id}`, changes);

  return response.data;
}
