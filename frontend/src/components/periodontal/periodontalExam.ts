import type { CurrentUser } from "../../types/auth";
import type { PeriodontalExam, PeriodontalExamListItem, ToothData } from "../../types/periodontal";
import { CLINICAL_DRAFT_PREFIX } from "../../services/session";
import { SITES, valueError } from "./periodontalChart";

export const periodontalExamsKey = (patientId: number) => ["patients", patientId, "periodontal-exams"] as const;
export const periodontalExamKey = (patientId: number, examId: number) =>
  [...periodontalExamsKey(patientId), examId] as const;

/** Edita el borrador su autor o administración (ODON-182). */
export function canEditExam(exam: PeriodontalExam, user: CurrentUser | null, isArchived: boolean): boolean {
  if (!user || isArchived || exam.status !== "draft" || exam.voided_at) return false;
  return user.role === "admin" || exam.created_by.id === user.id;
}

export function chartErrors(chart: ToothData[]): string[] {
  return chart.flatMap((tooth) =>
    SITES.flatMap((site) => {
      const data = tooth.sites[site];
      return [valueError("probing_depth", data.probing_depth), valueError("gingival_margin", data.gingival_margin)]
        .filter((error): error is string => error !== null)
        .map((error) => `Pieza ${tooth.tooth}: ${error}`);
    }),
  );
}

export function statusLabel(exam: PeriodontalExamListItem): { text: string; className: string } {
  if (exam.voided_at) return { text: "Anulado", className: "bg-red-100 text-red-800" };
  if (exam.status === "final") return { text: "Finalizado", className: "bg-teal-100 text-teal-800" };
  return { text: "Borrador", className: "bg-amber-100 text-amber-800" };
}

/** Anula su autor o administración, tanto un borrador como uno finalizado. */
export function canVoidExam(exam: PeriodontalExam, user: CurrentUser | null, isArchived: boolean): boolean {
  if (!user || isArchived || exam.voided_at) return false;
  return user.role === "admin" || exam.created_by.id === user.id;
}

/** Espera tras el último cambio antes de autoguardar. */
export const AUTOSAVE_MS = 2500;

export interface DraftBackup {
  /** Quién editaba: el respaldo no se ofrece a otro usuario en la misma pestaña. */
  userId: number;
  baseRevision: number;
  examDate: string;
  visitId: number | null;
  notes: string;
  chart: ToothData[];
  savedAt: string;
}

/**
 * Respaldo de cambios sin guardar en sessionStorage (no localStorage): no
 * sobrevive al cierre del navegador, para no dejar datos clínicos en un equipo
 * compartido. Guarda el id del examen, el usuario, las medidas y las notas;
 * se borra al guardar, al descartar y al cerrar sesión (clearSessionDrafts).
 */
const backupKey = (examId: number) => `${CLINICAL_DRAFT_PREFIX}${examId}`;

/** Respaldo del examen para ese usuario (null: de cualquier usuario). */
export function readBackup(examId: number, userId: number | null): DraftBackup | null {
  try {
    const raw = sessionStorage.getItem(backupKey(examId));
    const backup = raw ? (JSON.parse(raw) as DraftBackup) : null;
    return backup && (userId === null || backup.userId === userId) ? backup : null;
  } catch {
    return null;
  }
}

export function writeBackup(examId: number, backup: DraftBackup): void {
  try {
    sessionStorage.setItem(backupKey(examId), JSON.stringify(backup));
  } catch {
    // Sin almacenamiento disponible: el autoguardado sigue funcionando.
  }
}

export function clearBackup(examId: number): void {
  try {
    sessionStorage.removeItem(backupKey(examId));
  } catch {
    // Nada que limpiar.
  }
}
