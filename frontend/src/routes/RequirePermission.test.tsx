import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RequirePermission from "./RequirePermission";
import { renderWithAuth } from "../test/renderWithAuth";

function Protected() {
  return <p>Contenido protegido</p>;
}

describe("RequirePermission", () => {
  it("muestra el contenido si el rol tiene el permiso", () => {
    renderWithAuth(
      <RequirePermission permission="users:manage">
        <Protected />
      </RequirePermission>,
      "admin",
    );

    expect(screen.getByText("Contenido protegido")).toBeInTheDocument();
  });

  it.each(["doctor", "receptionist"] as const)(
    "%s ve Acceso denegado en una ruta de administración",
    (role) => {
      renderWithAuth(
        <RequirePermission permission="users:manage">
          <Protected />
        </RequirePermission>,
        role,
      );

      expect(screen.queryByText("Contenido protegido")).not.toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Acceso denegado" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/dashboard");
    },
  );

  it.each(["admin", "doctor", "receptionist"] as const)(
    "%s accede a Pacientes",
    (role) => {
      renderWithAuth(
        <RequirePermission permission="patients:view">
          <Protected />
        </RequirePermission>,
        role,
      );

      expect(screen.getByText("Contenido protegido")).toBeInTheDocument();
    },
  );
});
