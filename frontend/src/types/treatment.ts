import type { PersonRef } from "./clinicalVisit";

export type TreatmentStatus =
  "proposed" | "accepted" | "in_progress" | "completed" | "cancelled";

export interface VisitRef {
  id: number;
  visit_at: string;
  reason: string;
  voided: boolean;
}

/** Tratamiento del paciente (ODON-158). */
export interface Treatment {
  id: number;
  patient_id: number;
  procedure: string;
  /** Pieza dental FDI (11–48, 51–85). */
  tooth: number | null;
  notes: string | null;
  /** YYYY-MM-DD */
  planned_date: string | null;
  status: TreatmentStatus;
  status_reason: string | null;
  status_changed_at: string;
  proposed_visit: VisitRef | null;
  completed_visit: VisitRef | null;
  created_by: PersonRef;
  created_at: string;
  updated_by: PersonRef;
  updated_at: string;
}

export interface TreatmentStatusChange {
  from_status: TreatmentStatus | null;
  to_status: TreatmentStatus;
  reason: string | null;
  changed_by: PersonRef;
  changed_at: string;
}

export interface TreatmentDTO {
  procedure: string;
  tooth: number | null;
  notes: string | null;
  planned_date: string | null;
  proposed_visit_id: number | null;
}

export interface TreatmentStatusDTO {
  status: TreatmentStatus;
  reason?: string;
  completed_visit_id?: number;
}
