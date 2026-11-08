import type { DashboardIndicators } from "../../types/dashboard";

export type IndicatorKey = keyof DashboardIndicators;

export interface IndicatorDefinition {
  key: IndicatorKey;
  label: string;
  /** Aclaración breve bajo el valor. */
  hint: string;
  percent?: boolean;
}

/**
 * Orden de la cuadrícula: los cuatro primeros se ven siempre; el resto
 * aparece debajo con «Mostrar más indicadores» (decisión ODON-10).
 */
export const INDICATORS: IndicatorDefinition[] = [
  { key: "appointments_today", label: "Citas de hoy", hint: "Sin contar canceladas" },
  { key: "attendance_rate", label: "Asistencia", hint: "Atendidas sobre atendidas + no asistió", percent: true },
  { key: "patients_new", label: "Pacientes nuevos", hint: "Con fecha de alta en el periodo" },
  { key: "occupancy_rate", label: "Ocupación de agenda", hint: "Minutos citados sobre horario disponible", percent: true },
  { key: "appointments_week", label: "Citas de esta semana", hint: "Lunes a domingo, sin canceladas" },
  { key: "appointments_period", label: "Citas del periodo", hint: "Todas, incluidas las canceladas" },
  { key: "no_show_rate", label: "Inasistencia", hint: "No asistió sobre atendidas + no asistió", percent: true },
  { key: "cancellation_rate", label: "Cancelación", hint: "Canceladas sobre citas del periodo", percent: true },
  { key: "patients_active", label: "Pacientes activos", hint: "No archivados (a la fecha)" },
  { key: "visits_registered", label: "Consultas registradas", hint: "Sin contar anuladas" },
  { key: "treatments_completed", label: "Tratamientos completados", hint: "Completados en el periodo" },
  { key: "periodontal_finalized", label: "Periodontogramas finalizados", hint: "Sin contar anulados" },
  { key: "images_uploaded", label: "Imágenes clínicas", hint: "Subidas en el periodo, sin anuladas" },
];

export const PRIMARY_COUNT = 4;

/** Valor para mostrar: «—» cuando no hay base para calcular la tasa. */
export function formatIndicator(value: number | null, percent = false): string {
  if (value === null) return "—";
  if (percent) return `${value.toLocaleString("es-GT", { maximumFractionDigits: 1 })} %`;
  return value.toLocaleString("es-GT");
}

/** Preferencia «mostrar más» por usuario; el almacenamiento puede fallar. */
function storageKey(userId: number): string {
  return `odontonet.dashboard.expanded.${userId}`;
}

export function loadExpanded(userId: number | undefined): boolean {
  if (userId === undefined) return false;
  try {
    return localStorage.getItem(storageKey(userId)) === "1";
  } catch {
    return false;
  }
}

export function saveExpanded(userId: number | undefined, expanded: boolean): void {
  if (userId === undefined) return;
  try {
    if (expanded) localStorage.setItem(storageKey(userId), "1");
    else localStorage.removeItem(storageKey(userId));
  } catch {
    // Sin almacenamiento disponible: la preferencia dura solo esta visita.
  }
}
