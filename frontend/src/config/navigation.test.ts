import { describe, expect, it } from "vitest";

import { getNavigation, NAV_ITEMS, type NavItem } from "./navigation";

const labels = (items: NavItem[]) => items.map((item) => item.label);

describe("getNavigation", () => {
  it("administración ve Inicio, Pacientes y Usuarios", () => {
    expect(labels(getNavigation("admin"))).toEqual(["Inicio", "Pacientes", "Usuarios"]);
  });

  it("doctor y recepción no ven Usuarios", () => {
    for (const role of ["doctor", "receptionist"] as const) {
      expect(labels(getNavigation(role))).toEqual(["Inicio", "Pacientes"]);
    }
  });

  it("sin sesión solo quedan opciones sin permiso", () => {
    expect(labels(getNavigation(null))).toEqual(["Inicio"]);
  });

  it("filtra opciones restringidas según el rol", () => {
    const items: NavItem[] = [
      ...NAV_ITEMS,
      { to: "/staff", label: "Personal", permission: "users:manage" },
    ];

    expect(labels(getNavigation("admin", items))).toContain("Personal");
    expect(labels(getNavigation("doctor", items))).not.toContain("Personal");
    expect(labels(getNavigation("receptionist", items))).not.toContain("Personal");
  });
});
