import type { Role } from "./auth";

/** Evento de auditoría (ODON-222): quién cambió o exportó qué. Sin valores. */
export interface AuditEvent {
  id: number;
  occurred_at: string;
  actor: { id: number; name: string; role: Role };
  action: string;
  entity_type: string;
  entity_id: number | null;
  patient_id: number | null;
  /** Nombres de los campos cambiados (nunca sus valores). */
  fields: string[];
}

export interface AuditPage {
  items: AuditEvent[];
  next_cursor: string | null;
}

export interface AuditFilters {
  from?: string;
  to?: string;
  actorUserId?: number | null;
  action?: string;
  cursor?: string | null;
}
