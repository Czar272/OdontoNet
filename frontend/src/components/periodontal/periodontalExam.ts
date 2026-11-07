import type { CurrentUser } from "../../types/auth";
import type { PeriodontalExam, PeriodontalExamListItem, ToothData } from "../../types/periodontal";
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
