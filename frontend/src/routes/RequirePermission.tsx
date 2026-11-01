import type { Permission } from "../auth/permissions";
import { usePermission } from "../hooks/usePermission";
import ForbiddenPage from "../pages/Errors/ForbiddenPage";

/**
 * Protege una ruta por permiso. Va dentro de ProtectedRoute (sesión ya verificada).
 * Es una ayuda de interfaz: la API vuelve a validar el rol en cada petición.
 */
export default function RequirePermission({
  permission,
  children,
}: {
  permission: Permission;
  children: React.ReactNode;
}) {
  const allowed = usePermission(permission);

  if (!allowed) {
    return <ForbiddenPage />;
  }

  return children;
}
