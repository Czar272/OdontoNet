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
