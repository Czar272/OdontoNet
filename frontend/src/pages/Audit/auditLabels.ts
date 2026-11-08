/** Textos de la auditoría en español (ODON-222). Una acción desconocida se muestra tal cual. */
export const ACTION_LABELS: Record<string, string> = {
  "patient.created": "Registró un paciente",
  "patient.updated": "Editó un paciente",
  "patient.archived": "Archivó un paciente",
  "patient.reactivated": "Reactivó un paciente",
  "patient.doctor_changed": "Cambió el doctor de un paciente",
  "appointment.created": "Agendó una cita",
  "appointment.updated": "Reprogramó o editó una cita",
  "appointment.status_changed": "Cambió el estado de una cita",
  "medical_history.created": "Guardó una versión de la historia médica",
  "clinical_visit.created": "Registró una consulta",
  "clinical_visit.updated": "Editó una consulta",
  "clinical_visit.voided": "Anuló una consulta",
  "treatment.created": "Propuso un tratamiento",
  "treatment.updated": "Editó un tratamiento",
  "treatment.status_changed": "Cambió el estado de un tratamiento",
  "photo_consent.recorded": "Registró el consentimiento de fotografías",
  "image.stored": "Subió una imagen clínica",
  "image.updated": "Editó los datos de una imagen",
  "image.voided": "Anuló una imagen",
  "periodontal_exam.created": "Creó un periodontograma",
  "periodontal_exam.updated": "Guardó un periodontograma",
  "periodontal_exam.finalized": "Finalizó un periodontograma",
  "periodontal_exam.voided": "Anuló un periodontograma",
  "periodontal_exam.exported": "Exportó un periodontograma (PDF)",
  "report.exported": "Exportó un reporte (CSV)",
  "user.created": "Creó un usuario",
  "user.updated": "Editó un usuario",
  "user.deactivated": "Desactivó un usuario",
  "user.reactivated": "Reactivó un usuario",
  "clinic.updated": "Editó los datos de la clínica",
  "doctor.created": "Creó un perfil de doctor",
  "doctor.updated": "Editó un perfil de doctor",
  "doctor.availability_updated": "Cambió el horario de un doctor",
  "auth.password_changed": "Cambió su contraseña",
  "auth.password_reset_completed": "Restableció su contraseña",
};

export const ENTITY_LABELS: Record<string, string> = {
  patient: "Paciente",
  appointment: "Cita",
  medical_history: "Historia médica",
  clinical_visit: "Consulta",
  treatment: "Tratamiento",
  photo_consent: "Consentimiento",
  image: "Imagen",
  periodontal_exam: "Periodontograma",
  report: "Reporte",
  user: "Usuario",
  clinic: "Clínica",
  doctor: "Doctor",
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

export function entityLabel(entityType: string, entityId: number | null): string {
  const label = ENTITY_LABELS[entityType] ?? entityType;
  return entityId === null ? label : `${label} #${entityId}`;
}

/** Campos en español. Un campo desconocido se muestra tal cual. */
export const FIELD_LABELS: Record<string, string> = {
  first_name: "nombre",
  last_name: "apellido",
  name: "nombre",
  birth_date: "fecha de nacimiento",
  phone: "teléfono",
  email: "correo",
  address: "dirección",
  doctor_id: "doctor",
  archived_at: "archivado",
  is_active: "activo",
  role: "rol",
  password: "contraseña",
  starts_at: "fecha y hora",
  duration_minutes: "duración",
  status: "estado",
  reason: "motivo",
  notes: "notas",
  note: "nota",
  void_reason: "motivo de anulación",
  voided_at: "anulación",
  timezone: "zona horaria",
  specialization: "especialidad",
  license_number: "número de colegiado",
  blocks: "bloques de horario",
  procedure: "procedimiento",
  tooth: "pieza",
  planned_date: "fecha planificada",
  exam_date: "fecha del examen",
  teeth: "piezas",
  origin: "origen",
  view: "vista",
  taken_on: "fecha de toma",
  clinical_visit_id: "consulta",
  appointments: "reporte de citas",
  patients: "reporte de pacientes nuevos",
};

export function fieldsLabel(fields: string[]): string {
  return fields.map((field) => FIELD_LABELS[field] ?? field).join(", ");
}
