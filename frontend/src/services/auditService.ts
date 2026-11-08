import type { AuditFilters, AuditPage } from "../types/audit";
import api from "./api";

/** Auditoría de la clínica, del evento más reciente al más antiguo (ODON-222). */
export async function getAuditEvents({ from, to, actorUserId, action, cursor }: AuditFilters): Promise<AuditPage> {
  const params: Record<string, string | number> = {};
  if (from) params.from = from;
  if (to) params.to = to;
  if (actorUserId) params.actor_user_id = actorUserId;
  if (action) params.action = action;
  if (cursor) params.cursor = cursor;
  const response = await api.get<AuditPage>("/audit", { params });
  return response.data;
}
