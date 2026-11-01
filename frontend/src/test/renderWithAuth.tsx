import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

/**
 * Renderiza con una sesión simulada y un QueryClient propio (sin reintentos).
 * Las llamadas a la API se simulan en cada prueba con vi.mock.
 */
export function renderWithAuth(ui: React.ReactElement, role: Role | null) {
  const value: AuthContextType = {
    status: role ? "authenticated" : "unauthenticated",
    user: role ? fakeUser(role) : null,
    loggedOutManually: false,
    login: async () => true,
    logout: () => {},
  };

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={value}>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}
