import type { Role } from "../types/auth";

/**
 * Permisos del frontend: reflejo de la matriz de docs/PERMISSIONS.md.
 *
 * Solo decide qué se muestra. El backend sigue siendo la autoridad:
 * aunque la interfaz se equivoque, la API responde 403.
 * Al agregar un módulo, declara aquí su permiso y úsalo en el menú y en la ruta.
 */
export const PERMISSIONS = {
  "patients:view": ["admin", "doctor", "receptionist"],
  "patients:create": ["admin", "doctor", "receptionist"],
  "patients:edit": ["admin", "doctor", "receptionist"],
  "patients:archive": ["admin", "doctor", "receptionist"],
  "appointments:view": ["admin", "doctor", "receptionist"],
  "appointments:manage": ["admin", "doctor", "receptionist"],
  "doctors:view": ["admin", "doctor", "receptionist"],
  "doctors:manage": ["admin"],
  // Horario de cualquier doctor; un doctor edita además el suyo (ODON-142).
  "availability:manage": ["admin", "receptionist"],
  "users:manage": ["admin"],
  "clinic:view": ["admin", "doctor", "receptionist"],
  // Historia médica (ODON-150): recepción la consulta, no la edita.
  "medical_history:view": ["admin", "doctor", "receptionist"],
  "medical_history:edit": ["admin", "doctor"],
  // Consultas clínicas (ODON-154): recepción no accede. Editar o anular
  // además exige ser quien la registró o administración (visitFormData).
  "visits:view": ["admin", "doctor"],
  "visits:create": ["admin", "doctor"],
  // Plan de tratamiento (ODON-158): cualquier doctor o admin lo gestiona.
  "treatments:view": ["admin", "doctor"],
  "treatments:manage": ["admin", "doctor"],
  // Historial cronológico (ODON-162): incluye consultas, así que sin recepción.
  "timeline:view": ["admin", "doctor"],
  // Imágenes clínicas y su consentimiento (ODON-8): recepción no accede.
  "images:view": ["admin", "doctor"],
  "images:upload": ["admin", "doctor"],
  // Periodontograma (ODON-9): recepción no accede. Editar, finalizar o anular
  // además exige ser quien lo registró o administración (canEditExam).
  "periodontal:view": ["admin", "doctor"],
  "periodontal:create": ["admin", "doctor"],
  // Reportes (ODON-206): todos consultan datos agregados; solo administración exporta.
  "reports:view": ["admin", "doctor", "receptionist"],
  "reports:export": ["admin"],
  "clinic:manage": ["admin"],
} as const satisfies Record<string, readonly Role[]>;

export type Permission = keyof typeof PERMISSIONS;

export function hasPermission(
  role: Role | null | undefined,
  permission: Permission,
): boolean {
  if (!role) return false;

  return (PERMISSIONS[permission] as readonly Role[]).includes(role);
}
