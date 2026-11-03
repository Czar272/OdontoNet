import type {
  Treatment,
  TreatmentDTO,
  TreatmentStatus,
} from "../../types/treatment";

export const TREATMENT_STATUS_LABELS: Record<TreatmentStatus, string> = {
  proposed: "Propuesto",
  accepted: "Aceptado",
  in_progress: "En curso",
  completed: "Completado",
  cancelled: "Cancelado",
};

export const TREATMENT_STATUS_STYLES: Record<TreatmentStatus, string> = {
  proposed: "bg-gray-100 text-gray-700",
  accepted: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-800",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
};

/** Espejo de TREATMENT_TRANSITIONS en backend/app/models/treatment.py. */
export const TREATMENT_TRANSITIONS: Record<TreatmentStatus, TreatmentStatus[]> =
  {
    proposed: ["accepted", "cancelled"],
    accepted: ["in_progress", "completed", "cancelled"],
    in_progress: ["completed", "cancelled"],
    completed: [],
    cancelled: [],
  };

/** Texto del botón que lleva a cada estado. */
export const TRANSITION_ACTIONS: Record<TreatmentStatus, string> = {
  proposed: "Proponer",
  accepted: "Aceptar",
  in_progress: "Iniciar",
  completed: "Completar",
  cancelled: "Cancelar",
};

export function isClosed(status: TreatmentStatus): boolean {
  return TREATMENT_TRANSITIONS[status].length === 0;
}

/** Numeración FDI: permanentes 11–48 y temporales 51–85. */
export function isValidTooth(tooth: number): boolean {
  if (!Number.isInteger(tooth)) return false;
  const quadrant = Math.floor(tooth / 10);
  const piece = tooth % 10;
  return (
    (quadrant >= 1 && quadrant <= 4 && piece >= 1 && piece <= 8) ||
    (quadrant >= 5 && quadrant <= 8 && piece >= 1 && piece <= 5)
  );
}

export interface TreatmentFormData {
  procedure: string;
  tooth: string;
  planned_date: string;
  proposed_visit_id: string;
  notes: string;
}

export function initialTreatmentForm(
  treatment: Treatment | null,
): TreatmentFormData {
  return {
    procedure: treatment?.procedure ?? "",
    tooth: treatment?.tooth ? String(treatment.tooth) : "",
    planned_date: treatment?.planned_date ?? "",
    proposed_visit_id: treatment?.proposed_visit
      ? String(treatment.proposed_visit.id)
      : "",
    notes: treatment?.notes ?? "",
  };
}

export function buildTreatmentDTO(form: TreatmentFormData): TreatmentDTO {
  return {
    procedure: form.procedure.trim(),
    tooth: form.tooth.trim() ? Number(form.tooth) : null,
    planned_date: form.planned_date || null,
    proposed_visit_id: form.proposed_visit_id
      ? Number(form.proposed_visit_id)
      : null,
    notes: form.notes.trim() || null,
  };
}

/** Solo los campos que cambiaron respecto del tratamiento. */
export function buildTreatmentChanges(
  treatment: Treatment,
  form: TreatmentFormData,
): Partial<TreatmentDTO> {
  const next = buildTreatmentDTO(form);
  const current = buildTreatmentDTO(initialTreatmentForm(treatment));
  return Object.fromEntries(
    (Object.keys(next) as (keyof TreatmentDTO)[])
      .filter((key) => next[key] !== current[key])
      .map((key) => [key, next[key]]),
  ) as Partial<TreatmentDTO>;
}

/** Mensaje si el formulario no es válido; null si se puede enviar. */
export function validateTreatmentForm(form: TreatmentFormData): string | null {
  if (!form.procedure.trim()) return "Indica el procedimiento.";
  if (form.tooth.trim() && !isValidTooth(Number(form.tooth))) {
    return "Pieza dental inválida: usa la numeración FDI (11–48 o 51–85).";
  }
  return null;
}
