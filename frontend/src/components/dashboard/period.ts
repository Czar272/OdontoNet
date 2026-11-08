/**
 * Periodos del panel (ODON-202). Las fechas son locales (YYYY-MM-DD) e
 * incluidas; el backend las interpreta en la zona horaria de la clínica.
 */
export type PeriodPreset =
  | "this_month"
  | "last_month"
  | "this_week"
  | "last_30_days"
  | "this_year";

export const PERIOD_PRESETS: { value: PeriodPreset; label: string }[] = [
  { value: "this_month", label: "Mes en curso" },
  { value: "last_month", label: "Mes anterior" },
  { value: "this_week", label: "Esta semana" },
  { value: "last_30_days", label: "Últimos 30 días" },
  { value: "this_year", label: "Este año" },
];

export interface Period {
  from: string;
  to: string;
}

/** Fecha local en formato ISO (sin pasar por UTC). */
export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

export function presetPeriod(preset: PeriodPreset, today: Date = new Date()): Period {
  const year = today.getFullYear();
  const month = today.getMonth();
  switch (preset) {
    case "this_month":
      return { from: toIsoDate(new Date(year, month, 1)), to: toIsoDate(new Date(year, month + 1, 0)) };
    case "last_month":
      return { from: toIsoDate(new Date(year, month - 1, 1)), to: toIsoDate(new Date(year, month, 0)) };
    case "this_week": {
      // Semana de lunes a domingo, como la agenda.
      const monday = addDays(today, -((today.getDay() + 6) % 7));
      return { from: toIsoDate(monday), to: toIsoDate(addDays(monday, 6)) };
    }
    case "last_30_days":
      return { from: toIsoDate(addDays(today, -29)), to: toIsoDate(today) };
    case "this_year":
      return { from: toIsoDate(new Date(year, 0, 1)), to: toIsoDate(new Date(year, 11, 31)) };
  }
}

/** El backend acepta hasta 400 días. */
export const MAX_PERIOD_DAYS = 400;

/** Mensaje de error del periodo personalizado, o null si es válido. */
export function periodError({ from, to }: Period): string | null {
  if (!from || !to) return "Indica las dos fechas.";
  if (to < from) return "La fecha final no puede ser anterior a la inicial.";
  const days = (Date.parse(to) - Date.parse(from)) / 86_400_000 + 1;
  if (days > MAX_PERIOD_DAYS) return `El periodo no puede superar ${MAX_PERIOD_DAYS} días.`;
  return null;
}

/** «1 mar 2026 – 31 mar 2026», en hora local. */
export function formatPeriod({ from, to }: Period): string {
  const format = (iso: string) => {
    const [year, month, day] = iso.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString("es-GT", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };
  return from === to ? format(from) : `${format(from)} – ${format(to)}`;
}
