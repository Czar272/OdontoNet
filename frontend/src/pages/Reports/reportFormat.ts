import type { AppointmentStatus } from "../../types/appointment";
import type { Bucket, ReportGrouping } from "../../types/report";

export const GROUP_OPTIONS: { value: ReportGrouping; label: string }[] = [
  { value: "day", label: "Por día" },
  { value: "week", label: "Por semana" },
  { value: "month", label: "Por mes" },
];

/**
 * Orden de las barras apiladas y su color (paleta categórica validada para
 * daltonismo en ese orden de vecinos). Es propia de los gráficos: los colores
 * de estado de la agenda incluyen un gris que no se distingue en una pila.
 */
export const CHART_STATUSES: { status: AppointmentStatus; color: string }[] = [
  { status: "completed", color: "#2a78d6" },
  { status: "no_show", color: "#eb6834" },
  { status: "cancelled", color: "#1baf7a" },
  { status: "scheduled", color: "#eda100" },
  { status: "confirmed", color: "#e87ba4" },
];

export const SINGLE_SERIES_COLOR = "#2a78d6";

function localDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

const shortDate = (iso: string) =>
  localDate(iso).toLocaleDateString("es-GT", { day: "numeric", month: "short" });

/**
 * Etiqueta del grupo: «2 mar», «Sem. 2 mar», «mar 2026». Una semana o un mes
 * recortado por el periodo muestra su rango real («1–2 mar») para que una
 * barra corta no parezca una caída de actividad.
 */
export function bucketLabel(bucket: Bucket, group: ReportGrouping): string {
  if (group !== "day" && bucket.partial) {
    return bucket.period_start === bucket.period_end
      ? shortDate(bucket.period_start)
      : `${shortDate(bucket.period_start)} – ${shortDate(bucket.period_end)}`;
  }
  if (group === "month") {
    return localDate(bucket.period_start).toLocaleDateString("es-GT", { month: "short", year: "numeric" });
  }
  const short = shortDate(bucket.period_start);
  return group === "week" ? `Sem. ${short}` : short;
}

export function formatRate(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString("es-GT", { maximumFractionDigits: 1 })} %`;
}
