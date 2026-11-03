import type { CurrentUser } from "../../types/auth";
import type { ClinicalVisit, VisitContent } from "../../types/clinicalVisit";
import type { Doctor } from "../../types/doctor";

export interface VisitFormData {
  /** datetime-local en la hora del navegador: "YYYY-MM-DDTHH:mm". */
  visit_at: string;
  doctor_id: string;
  reason: string;
  findings: string;
  diagnosis: string;
  procedures: string;
  instructions: string;
  next_visit_date: string;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** Fecha ISO → valor de un input datetime-local en la hora del navegador. */
export function toLocalInput(value: Date | string): string {
  const d = new Date(value);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Valor de datetime-local (hora del navegador) → ISO en UTC. */
export function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

/** Doctor propuesto: el perfil del usuario si atiende; si no, ninguno. */
export function defaultDoctorId(
  user: CurrentUser | null,
  doctors: Doctor[],
): string {
  const own = doctors.find((d) => d.user.id === user?.id);
  return own ? String(own.id) : "";
}

export function initialVisitForm(
  visit: ClinicalVisit | null,
  doctorId: string,
  now: Date = new Date(),
): VisitFormData {
  return {
    visit_at: toLocalInput(visit?.visit_at ?? now),
    doctor_id: visit ? String(visit.doctor.id) : doctorId,
    reason: visit?.reason ?? "",
    findings: visit?.findings ?? "",
    diagnosis: visit?.diagnosis ?? "",
    procedures: visit?.procedures ?? "",
    instructions: visit?.instructions ?? "",
    next_visit_date: visit?.next_visit_date ?? "",
  };
}

const text = (value: string) => value.trim() || null;

export function buildVisitContent(form: VisitFormData): VisitContent {
  return {
    visit_at: fromLocalInput(form.visit_at),
    doctor_id: Number(form.doctor_id),
    reason: form.reason.trim(),
    findings: text(form.findings),
    diagnosis: text(form.diagnosis),
    procedures: text(form.procedures),
    instructions: text(form.instructions),
    next_visit_date: form.next_visit_date || null,
  };
}

/** Igual que el backend: solo quien la registró o administración, y no anulada. */
export function canModifyVisit(
  visit: ClinicalVisit,
  user: CurrentUser | null,
): boolean {
  if (!user || visit.voided_at) return false;
  return user.role === "admin" || visit.created_by.id === user.id;
}

/** true si el formulario no cambia nada respecto de la consulta. */
export function isVisitUnchanged(
  form: VisitFormData,
  visit: ClinicalVisit,
): boolean {
  const current = buildVisitContent(
    initialVisitForm(visit, String(visit.doctor.id)),
  );
  return JSON.stringify(buildVisitContent(form)) === JSON.stringify(current);
}
