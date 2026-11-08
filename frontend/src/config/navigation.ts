import { hasPermission, type Permission } from "../auth/permissions";
import type { Role } from "../types/auth";

export interface NavItem {
  to: string;
  label: string;
  /** Sin permiso: visible para cualquier usuario autenticado. */
  permission?: Permission;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Inicio" },
  { to: "/agenda", label: "Agenda", permission: "appointments:view" },
  { to: "/patients", label: "Pacientes", permission: "patients:view" },
  { to: "/doctors", label: "Doctores", permission: "doctors:view" },
  { to: "/reports", label: "Reportes", permission: "reports:view" },
  { to: "/users", label: "Usuarios", permission: "users:manage" },
  { to: "/clinic", label: "Clínica", permission: "clinic:view" },
];

/** Opciones del menú visibles para un rol. */
export function getNavigation(
  role: Role | null | undefined,
  items: NavItem[] = NAV_ITEMS,
): NavItem[] {
  return items.filter(
    (item) => !item.permission || hasPermission(role, item.permission),
  );
}
