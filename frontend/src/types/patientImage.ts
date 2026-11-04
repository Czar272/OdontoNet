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

/** Fotografía clínica del paciente (ODON-166, ODON-170). */
export interface PatientImage {
  id: number;
  patient_id: number;
  clinical_visit: VisitRef | null;
  tooth: number | null;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  consent_id: number;
  uploaded_by: PersonRef;
  uploaded_at: string;
}

export interface ImageUploadData {
  file: File;
  clinical_visit_id: number | null;
  tooth: number | null;
}
