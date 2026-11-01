import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AuthContext, type AuthContextType } from "../context/AuthContext";
import type { CurrentUser, Role } from "../types/auth";

export function fakeUser(role: Role): CurrentUser {
  return {
    id: 1,
    name: `Usuario ${role}`,
    email: `${role}@odontonet-demo.com`,
    role,
    clinic: { id: 1, name: "Clínica Demo Norte" },
  };
}

/** Renderiza con una sesión simulada (sin llamadas a la API). */
export function renderWithAuth(ui: React.ReactElement, role: Role | null) {
  const value: AuthContextType = {
    status: role ? "authenticated" : "unauthenticated",
    user: role ? fakeUser(role) : null,
    loggedOutManually: false,
    login: async () => true,
    logout: () => {},
  };

  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter>{ui}</MemoryRouter>
    </AuthContext.Provider>,
  );
}
