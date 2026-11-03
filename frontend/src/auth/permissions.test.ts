import { describe, expect, it } from "vitest";

import { hasPermission, PERMISSIONS, type Permission } from "./permissions";
import type { Role } from "../types/auth";

// Debe coincidir con docs/PERMISSIONS.md y con require_roles del backend.
const EXPECTED: Record<Permission, Record<Role, boolean>> = {
  "patients:view": { admin: true, doctor: true, receptionist: true },
  "patients:create": { admin: true, doctor: true, receptionist: true },
  "patients:edit": { admin: true, doctor: true, receptionist: true },
  "patients:archive": { admin: true, doctor: true, receptionist: true },
  "appointments:view": { admin: true, doctor: true, receptionist: true },
  "appointments:manage": { admin: true, doctor: true, receptionist: true },
  "doctors:view": { admin: true, doctor: true, receptionist: true },
  "availability:manage": { admin: true, doctor: false, receptionist: true },
  "doctors:manage": { admin: true, doctor: false, receptionist: false },
  "users:manage": { admin: true, doctor: false, receptionist: false },
  "clinic:view": { admin: true, doctor: true, receptionist: true },
  "medical_history:view": { admin: true, doctor: true, receptionist: true },
  "medical_history:edit": { admin: true, doctor: true, receptionist: false },
  "visits:view": { admin: true, doctor: true, receptionist: false },
  "visits:create": { admin: true, doctor: true, receptionist: false },
  "treatments:view": { admin: true, doctor: true, receptionist: false },
  "treatments:manage": { admin: true, doctor: true, receptionist: false },
  "timeline:view": { admin: true, doctor: true, receptionist: false },
  "clinic:manage": { admin: true, doctor: false, receptionist: false },
};

describe("hasPermission", () => {
  const cases = Object.entries(EXPECTED).flatMap(([permission, roles]) =>
    Object.entries(roles).map(([role, allowed]) => ({
      permission: permission as Permission,
      role: role as Role,
      allowed,
    })),
  );

  it.each(cases)("$role → $permission = $allowed", ({ role, permission, allowed }) => {
    expect(hasPermission(role, permission)).toBe(allowed);
  });

  it("deniega sin rol", () => {
    expect(hasPermission(null, "patients:view")).toBe(false);
    expect(hasPermission(undefined, "patients:view")).toBe(false);
  });

  it("la tabla esperada cubre todos los permisos definidos", () => {
    expect(Object.keys(EXPECTED).sort()).toEqual(Object.keys(PERMISSIONS).sort());
  });
});
