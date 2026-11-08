import type { PersonRef } from "./clinicalVisit";

/** Sitios por pieza: mesial, centro y distal por vestibular (b) y por palatino/lingual (l). */
export type SiteCode = "mb" | "b" | "db" | "ml" | "l" | "dl";
export type FurcationEntrance = "b" | "mp" | "dp" | "l";
export type ExamStatus = "draft" | "final";
/** manual: lo escribió el profesional; default: valor propuesto aún no editado (ODON-262). */
export type ValueSource = "manual" | "default";

export interface SiteData {
  probing_depth: number | null;
  /** Distancia del margen a la UAC: negativa = recesión, positiva = agrandamiento. */
  gingival_margin: number | null;
  bleeding: boolean;
  suppuration: boolean;
  plaque: boolean;
  /** Ausente equivale a "manual". */
  source?: ValueSource;
}

export interface SiteResponse extends SiteData {
  /** NIC = sondaje − margen (calculado por el backend). */
  attachment_level: number | null;
}

export type Furcation = Record<FurcationEntrance, number | null>;

export interface ToothData {
  tooth: number;
  missing: boolean;
  implant: boolean;
  mobility: number | null;
  furcation: Furcation;
  note: string | null;
  /** Origen de la movilidad (default si se propuso con los valores de salud). */
  source?: ValueSource;
  sites: Record<SiteCode, SiteData>;
}

export interface ToothResponse extends Omit<ToothData, "sites"> {
  sites: Record<SiteCode, SiteResponse>;
}

/** Estadística descriptiva; no constituye diagnóstico. */
export interface ExamSummary {
  present_teeth: number;
  measured_sites: number;
  mean_probing_depth: number | null;
  mean_attachment_level: number | null;
  bleeding_pct: number | null;
  plaque_pct: number | null;
  deep_sites_pct: number | null;
  /** Sitios con sondaje cuyo valor es predeterminado (no editado). */
  default_sites: number;
}

export interface PeriodontalExamListItem {
  id: number;
  patient_id: number;
  exam_date: string;
  clinical_visit: { id: number; reason: string; visit_at: string } | null;
  notes: string | null;
  status: ExamStatus;
  revision: number;
  created_by: PersonRef;
  created_at: string;
  updated_at: string;
  finalized_by: PersonRef | null;
  finalized_at: string | null;
  voided_by: PersonRef | null;
  voided_at: string | null;
  void_reason: string | null;
  summary: ExamSummary;
}

export interface PeriodontalExam extends PeriodontalExamListItem {
  teeth: ToothResponse[];
}

export interface ExamContentDTO {
  exam_date: string;
  clinical_visit_id: number | null;
  notes: string | null;
  teeth: ToothData[];
}

export interface ExamUpdateDTO extends ExamContentDTO {
  base_revision: number;
}

export interface ExamRevision {
  revision: number;
  edited_by: PersonRef;
  edited_at: string;
}
