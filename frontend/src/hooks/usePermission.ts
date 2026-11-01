import { hasPermission, type Permission } from "../auth/permissions";
import { useAuth } from "../context/AuthContext";

/** true si el usuario autenticado tiene el permiso indicado. */
export function usePermission(permission: Permission): boolean {
  const { user } = useAuth();

  return hasPermission(user?.role, permission);
}
