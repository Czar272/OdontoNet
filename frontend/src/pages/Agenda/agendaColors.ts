import type { Doctor } from "../../types/doctor";

/**
 * Colores de doctor (ODON-257). Tonos oscuros para que el texto blanco y las
 * tintas claras se lean bien, y distintos de los colores de estado
 * (azul, verde, gris, rojo y ámbar) para no confundir ambas cosas.
 */
export const DOCTOR_PALETTE = [
  "#6d28d9", // violeta
  "#0f766e", // verde azulado
  "#c2410c", // naranja quemado
  "#a21caf", // fucsia
  "#0e7490", // cian
  "#be123c", // rosa
  "#4d7c0f", // oliva
  "#92400e", // café
];

/**
 * Asigna un color estable a cada doctor según el orden de sus ids: el mismo
 * doctor conserva su color entre cargas, y los doctores nuevos (ids mayores)
 * no cambian el de los existentes.
 */
export function doctorColorMap(
  doctors: Pick<Doctor, "id">[],
): Map<number, string> {
  const ids = [...new Set(doctors.map((d) => d.id))].sort((a, b) => a - b);
  return new Map(
    ids.map((id, index) => [id, DOCTOR_PALETTE[index % DOCTOR_PALETTE.length]]),
  );
}

/** Color del doctor, aunque no venga en la lista (p. ej. aún cargando). */
export function doctorColor(
  colors: Map<number, string>,
  doctorId: number,
): string {
  return (
    colors.get(doctorId) ?? DOCTOR_PALETTE[doctorId % DOCTOR_PALETTE.length]
  );
}

/**
 * Mezcla el color con blanco y devuelve un color opaco: el fondo de la cita
 * tapa las líneas de la cuadrícula. amount=0.14 → 14 % del color.
 */
export function lighten(hex: string, amount: number): string {
  const value = Number.parseInt(hex.slice(1), 16);
  const channel = (shift: number) => {
    const c = (value >> shift) & 255;
    return Math.round(c * amount + 255 * (1 - amount))
      .toString(16)
      .padStart(2, "0");
  };
  return `#${channel(16)}${channel(8)}${channel(0)}`;
}

/**
 * Nombre corto para columnas angostas (vista de semana):
 * "Dra. Ana Morales" → "Dra. Morales"; "Luis Herrera" → "L. Herrera".
 */
export function doctorShortName(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length <= 2) return name.trim();
  const last = words[words.length - 1];
  if (/^dr(a)?\.?$/i.test(words[0])) return `${words[0]} ${last}`;
  return `${words[0].charAt(0)}. ${last}`;
}

/** Iniciales sin el título: "Dra. Ana Morales" → "AM"; "Luis" → "L". */
export function doctorInitials(name: string): string {
  const words = name
    .trim()
    .split(/\s+/)
    .filter((word) => !/^dr(a)?\.?$/i.test(word));
  const picked = words.length > 1 ? [words[0], words[words.length - 1]] : words;
  return picked.map((word) => word.charAt(0).toUpperCase()).join("");
}
