export interface PersonRef {
  id: number;
  name: string;
}

/** Contenido clínico de una consulta (ODON-154). */
export interface VisitContent {
  /** ISO con zona horaria. */
  visit_at: string;
  doctor_id: number;
  reason: string;
  findings: string | null;
  diagnosis: string | null;
  procedures: string | null;
  instructions: string | null;
  /** YYYY-MM-DD */
  next_visit_date: string | null;
}

export interface ClinicalVisit extends Omit<VisitContent, "doctor_id"> {
  id: number;
  patient_id: number;
  revision: number;
  doctor: PersonRef;
  created_by: PersonRef;
  created_at: string;
  updated_by: PersonRef;
  updated_at: string;
  voided_at: string | null;
  voided_by: PersonRef | null;
  void_reason: string | null;
}

export interface ClinicalVisitRevision extends Omit<VisitContent, "doctor_id"> {
  revision: number;
  edited_by: PersonRef;
  edited_at: string;
  doctor: PersonRef;
}

export interface UpdateVisitDTO extends VisitContent {
  base_revision: number;
}
