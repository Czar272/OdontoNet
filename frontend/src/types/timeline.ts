import type { PersonRef } from "./clinicalVisit";

export type TimelineEventType =
  "visit" | "treatment" | "medical_history" | "appointment" | "image" | "periodontal";

/** Un evento del historial cronológico del paciente (ODON-162). */
export interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  /**
   * visit: attended | edited | voided · treatment: estado al que pasó ·
   * medical_history: version · appointment: completed | no_show ·
   * image: uploaded | edited | voided · periodontal: finalized | voided
   */
  action: string;
  occurred_at: string;
  title: string;
  detail: string | null;
  actor: PersonRef | null;
  ref_id: number;
  voided: boolean;
}

export interface TimelinePage {
  items: TimelineEvent[];
  next_cursor: string | null;
}
