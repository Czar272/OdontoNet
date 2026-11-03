export type ConditionKey =
  | "diabetes"
  | "hypertension"
  | "heart_disease"
  | "bleeding_disorder"
  | "respiratory_disease"
  | "liver_kidney_disease"
  | "immunosuppression"
  | "pregnancy_lactation";

export type SmokingStatus = "never" | "former" | "current";

export interface ConditionEntry {
  /** null = sin dato. */
  present: boolean | null;
  detail: string | null;
}

/** Contenido de una versión de la historia médica (ODON-150). */
export interface MedicalHistoryData {
  conditions: Record<ConditionKey, ConditionEntry>;
  other_conditions: string | null;
  allergies: string | null;
  current_medications: string | null;
  smoking_status: SmokingStatus | null;
  cigarettes_per_day: number | null;
  alcohol: boolean | null;
  alcohol_detail: string | null;
  bruxism: boolean | null;
  chief_complaint: string | null;
  last_dental_visit: string | null;
  previous_treatments: string | null;
  brushing_per_day: number | null;
  uses_floss: boolean | null;
  gum_bleeding: boolean | null;
  notes: string | null;
}

export interface HistoryAuthor {
  id: number;
  name: string;
}

export interface MedicalHistory extends MedicalHistoryData {
  version: number;
  created_at: string;
  created_by: HistoryAuthor;
}

export interface MedicalHistoryVersionSummary {
  version: number;
  created_at: string;
  created_by: HistoryAuthor;
}

export interface SaveMedicalHistoryDTO extends MedicalHistoryData {
  /** Versión que se editaba; null si el paciente aún no tiene historia. */
  base_version: number | null;
}
