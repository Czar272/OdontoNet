import type { TimelineEventType } from "../../types/timeline";

export const TIMELINE_TYPES: { type: TimelineEventType; label: string }[] = [
  { type: "visit", label: "Consultas" },
  { type: "treatment", label: "Tratamientos" },
  { type: "medical_history", label: "Historia médica" },
  { type: "appointment", label: "Citas" },
];

/** Clave de React Query; cualquier cambio clínico del paciente la invalida. */
export const timelineKey = (patientId: number) =>
  ["patients", patientId, "timeline"] as const;
