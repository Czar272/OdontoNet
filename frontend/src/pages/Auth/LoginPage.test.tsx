import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthContext, type AuthContextType } from "../../context/AuthContext";
import LoginPage from "./LoginPage";

function renderLogin() {
  const login = vi.fn(async () => false);
  const value: AuthContextType = {
    status: "unauthenticated",
    user: null,
    loggedOutManually: false,
    login,
    logout: () => {},
    refreshUser: async () => {},
  };

  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );

  fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: "a@odontonet-demo.com" } });
  fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "Clave-123" } });

  return login;
}

describe("LoginPage", () => {
  it("Recuérdame está desmarcado por defecto", async () => {
    const login = renderLogin();

    expect(screen.getByLabelText("Recuérdame")).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("a@odontonet-demo.com", "Clave-123", false));
  });

  it("envía rememberMe al marcar Recuérdame", async () => {
    const login = renderLogin();

    fireEvent.click(screen.getByLabelText("Recuérdame"));
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("a@odontonet-demo.com", "Clave-123", true));
  });
});
