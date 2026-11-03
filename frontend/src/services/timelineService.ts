import type { TimelineEventType, TimelinePage } from "../types/timeline";
import api from "./api";

export interface TimelineParams {
  /** Tipos a incluir; vacío o sin definir = todos. */
  types?: TimelineEventType[];
  /** next_cursor de la página anterior. */
  cursor?: string | null;
  limit?: number;
}

/** Eventos del paciente del más reciente al más antiguo, por páginas. */
export async function getTimeline(
  patientId: number,
  { types, cursor, limit }: TimelineParams = {},
): Promise<TimelinePage> {
  const params = new URLSearchParams();
  types?.forEach((type) => params.append("types", type));
  if (cursor) params.set("cursor", cursor);
  if (limit) params.set("limit", String(limit));

  const response = await api.get<TimelinePage>(
    `/patients/${patientId}/timeline`,
    { params },
  );

  return response.data;
}
