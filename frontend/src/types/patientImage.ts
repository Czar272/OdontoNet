import type { PersonRef } from "./clinicalVisit";
import type { VisitRef } from "./treatment";

/** Versión del consentimiento para fotografías clínicas (ODON-170). */
export interface PhotoConsent {
  id: number;
  version: number;
  granted: boolean;
  /** Solo constancia del formulario; lo rige el protocolo del comité de ética. */
  research_use: boolean;
  /** YYYY-MM-DD: fecha de firma o de revocación. */
  signed_on: string;
  notes: string | null;
  recorded_by: PersonRef;
  recorded_at: string;
}

export interface PhotoConsentStatus {
  current: PhotoConsent | null;
  /** Más reciente primero. */
  history: PhotoConsent[];
}

export interface PhotoConsentDTO {
  granted: boolean;
  research_use: boolean;
  signed_on: string;
  notes: string | null;
}

export type ImageOrigin = "intraoral_camera" | "phone" | "camera" | "external";
export type ImageView =
  | "frontal"
  | "right_lateral"
  | "left_lateral"
  | "upper_occlusal"
  | "lower_occlusal"
  | "detail"
  | "other";

/** Fotografía clínica del paciente (ODON-166, ODON-170, ODON-178). */
export interface PatientImage {
  id: number;
  patient_id: number;
  clinical_visit: VisitRef | null;
  tooth: number | null;
  /** null en imágenes anteriores a ODON-178 («sin registrar»). */
  origin: ImageOrigin | null;
  view: ImageView | null;
  /** YYYY-MM-DD */
  taken_on: string | null;
  revision: number;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  consent_id: number;
  uploaded_by: PersonRef;
  uploaded_at: string;
  voided_at: string | null;
  voided_by: PersonRef | null;
  void_reason: string | null;
}

/** Metadatos corregibles; el archivo nunca cambia. */
export interface ImageMetadata {
  origin: ImageOrigin;
  view: ImageView | null;
  taken_on: string | null;
  clinical_visit_id: number | null;
  tooth: number | null;
}

export interface ImageUploadData extends ImageMetadata {
  file: File;
}

export interface ImageUpdateDTO extends ImageMetadata {
  base_revision: number;
}

export interface PatientImageRevision {
  revision: number;
  origin: ImageOrigin | null;
  view: ImageView | null;
  taken_on: string | null;
  clinical_visit_id: number | null;
  tooth: number | null;
  edited_by: PersonRef;
  edited_at: string;
}

export interface ImageAccess {
  user: PersonRef;
  accessed_at: string;
}
