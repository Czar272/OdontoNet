import type { SiteCode, ToothData } from "../../types/periodontal";
import { displaySites, type Face } from "./periodontalChart";

/** Ancho de la columna de etiquetas de la grilla. */
export const LABEL_WIDTH = 132;

export type NumericField = "gingival_margin" | "probing_depth";

export const inputKey = (field: NumericField, tooth: number, site: SiteCode) => `${field}:${tooth}:${site}`;

/** Orden de captura de una fila: de izquierda a derecha, saltando piezas ausentes. */
export function rowKeys(field: NumericField, face: Face, teeth: ToothData[]): string[] {
  return teeth
    .filter((tooth) => !tooth.missing)
    .flatMap((tooth) => displaySites(tooth.tooth, face).map((site) => inputKey(field, tooth.tooth, site)));
}

/**
 * Un valor puede seguir creciendo: «1» puede ser 10–15 en el sondaje, y «-» o
 * «-1» pueden ser −1…−15 en el margen. En esos casos no se salta de campo.
 */
export function isComplete(field: NumericField, text: string): boolean {
  if (text === "" || text === "-") return false;
  if (field === "probing_depth") return text !== "1";
  return text !== "-1";
}
