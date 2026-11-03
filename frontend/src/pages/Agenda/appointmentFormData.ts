import axios from "axios";

import { getApiErrorMessage } from "../../services/apiError";
import type {
  Appointment,
  AppointmentConflict,
  CreateAppointmentDTO,
  UpdateAppointmentDTO,
} from "../../types/appointment";

/** Estado del formulario de cita: fecha y hora locales del navegador. */
export interface AppointmentFormData {
  patient_id: number | null;
  doctor_id: string;
  date: string; // YYYY-MM-DD
  time: string; // HH:mm
  duration_minutes: string;
  reason: string;
}

export const DURATION_OPTIONS = [15, 20, 30, 45, 60, 90, 120, 180];
export const DEFAULT_DURATION = 30;
export const MIN_DURATION = 5;
export const MAX_DURATION = 480;

const pad = (value: number) => String(value).padStart(2, "0");

/** "2026-11-10" y "09:00" en la hora local del navegador. */
export function localDateParts(date: Date): { date: string; time: string } {
  return {
    date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`,
  };
}

/**
 * ISO con la zona horaria del navegador: "2026-11-10T09:00:00-06:00".
 * El backend exige la zona para guardar el instante correcto.
 */
export function toLocalIso(date: Date): string {
  const { date: day, time } = localDateParts(date);
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hours = pad(Math.floor(Math.abs(offset) / 60));
  const minutes = pad(Math.abs(offset) % 60);

  return `${day}T${time}:00${sign}${hours}:${minutes}`;
}

/** Fecha local a partir de los campos del formulario (null si están incompletos). */
export function formDateTime(formData: AppointmentFormData): Date | null {
  if (!formData.date || !formData.time) return null;
  const value = new Date(`${formData.date}T${formData.time}:00`);

  return Number.isNaN(value.getTime()) ? null : value;
}

/** Duración entre dos fechas, ajustada a los límites del backend. */
export function durationBetween(start: Date, end: Date): number {
  const minutes = Math.round((end.getTime() - start.getTime()) / 60000);

  return Math.min(MAX_DURATION, Math.max(MIN_DURATION, minutes));
}

export function newAppointmentData(
  start: Date,
  durationMinutes = DEFAULT_DURATION,
  doctorId?: number,
): AppointmentFormData {
  return {
    patient_id: null,
    doctor_id: doctorId ? String(doctorId) : "",
    ...localDateParts(start),
    duration_minutes: String(durationMinutes),
    reason: "",
  };
}

export function appointmentToFormData(appointment: Appointment): AppointmentFormData {
  return {
    patient_id: appointment.patient_id,
    doctor_id: String(appointment.doctor_id),
    ...localDateParts(new Date(appointment.starts_at)),
    duration_minutes: String(appointment.duration_minutes),
    reason: appointment.reason ?? "",
  };
}

export function buildCreateAppointment(
  formData: AppointmentFormData,
): CreateAppointmentDTO | null {
  const start = formDateTime(formData);
  if (!formData.patient_id || !formData.doctor_id || !start) return null;

  const data: CreateAppointmentDTO = {
    patient_id: formData.patient_id,
    doctor_id: Number(formData.doctor_id),
    starts_at: toLocalIso(start),
    duration_minutes: Number(formData.duration_minutes),
  };
  if (formData.reason.trim()) data.reason = formData.reason.trim();

  return data;
}

/** Solo los campos que cambiaron; "" en el motivo lo borra. */
export function buildAppointmentChanges(
  appointment: Appointment,
  formData: AppointmentFormData,
): UpdateAppointmentDTO {
  const changes: UpdateAppointmentDTO = {};

  if (Number(formData.doctor_id) !== appointment.doctor_id) {
    changes.doctor_id = Number(formData.doctor_id);
  }

  const start = formDateTime(formData);
  if (start && start.getTime() !== new Date(appointment.starts_at).getTime()) {
    changes.starts_at = toLocalIso(start);
  }

  if (Number(formData.duration_minutes) !== appointment.duration_minutes) {
    changes.duration_minutes = Number(formData.duration_minutes);
  }

  if (formData.reason.trim() !== (appointment.reason ?? "")) {
    changes.reason = formData.reason.trim();
  }

  return changes;
}

const timeFormat = new Intl.DateTimeFormat("es-GT", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const dayFormat = new Intl.DateTimeFormat("es-GT", { weekday: "long", day: "numeric", month: "long" });

/** "09:00 – 09:30" en la hora local. */
export function formatTimeRange(startIso: string, endIso: string): string {
  return `${timeFormat.format(new Date(startIso))} – ${timeFormat.format(new Date(endIso))}`;
}

export function formatDay(iso: string): string {
  return dayFormat.format(new Date(iso));
}

/**
 * Mensaje para un error al guardar. Si es un cruce (409 con `conflict`),
 * agrega con qué cita choca, en la hora local del navegador.
 */
export function appointmentErrorMessage(error: unknown, fallback: string): string {
  const message = getApiErrorMessage(error, fallback);

  if (axios.isAxiosError<{ conflict?: AppointmentConflict }>(error)) {
    const conflict = error.response?.data?.conflict;
    if (conflict) {
      return `${message} Choca con la cita de ${conflict.patient_name} (${formatTimeRange(
        conflict.starts_at,
        conflict.ends_at,
      )}).`;
    }
  }

  return message;
}

/**
 * true si el backend avisó que la cita queda fuera del horario del doctor
 * (409 con outside_schedule). Se puede reenviar con allow_outside_schedule.
 */
export function isOutsideSchedule(error: unknown): boolean {
  return (
    axios.isAxiosError<{ outside_schedule?: boolean }>(error) &&
    error.response?.status === 409 &&
    error.response.data?.outside_schedule === true
  );
}
