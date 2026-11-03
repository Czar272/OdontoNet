import { fireEvent, render, screen } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResetPasswordPage from "./ResetPasswordPage";

vi.mock("../../services/authService", () => ({
  confirmPasswordReset: vi.fn(async () => ({ message: "Tu contraseña se actualizó. Inicia sesión con la nueva." })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { confirmPasswordReset } = await import("../../services/authService");
const toast = (await import("react-hot-toast")).default;

function Location() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname + location.search}</p>;
}

function renderPage(url = "/reset-password?token=abc123") {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/" element={<p>Pantalla de login</p>} />
      </Routes>
      <Location />
    </MemoryRouter>,
  );
}

function fill(password: string, confirmation = password) {
  fireEvent.change(screen.getByLabelText("Nueva contraseña"), { target: { value: password } });
  fireEvent.change(screen.getByLabelText("Confirmar contraseña"), { target: { value: confirmation } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));
}

function apiError(status: number, detail: string) {
  return new AxiosError("error", "ERR", undefined, undefined, {
    status,
    statusText: "",
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { detail },
  });
}

beforeEach(() => vi.clearAllMocks());

describe("ResetPasswordPage", () => {
  it("quita el token de la barra de direcciones", async () => {
    renderPage();

    expect(await screen.findByTestId("location")).toHaveTextContent(/^\/reset-password$/);
  });

  it("guarda la contraseña con el token y vuelve al login", async () => {
    renderPage();

    fill("Nueva-Clave-456");

    expect(await screen.findByText("Pantalla de login")).toBeInTheDocument();
    expect(confirmPasswordReset).toHaveBeenCalledWith("abc123", "Nueva-Clave-456");
    expect(toast.success).toHaveBeenCalledWith("Tu contraseña se actualizó. Inicia sesión con la nueva.");
  });

  it("valida la confirmación antes de llamar a la API", () => {
    renderPage();

    fill("Nueva-Clave-456", "Otra-Clave-789");

    expect(screen.getByRole("alert")).toHaveTextContent("Las contraseñas no coinciden.");
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it("muestra el error del servidor si el enlace expiró", async () => {
    vi.mocked(confirmPasswordReset).mockRejectedValueOnce(
      apiError(400, "El enlace no es válido o ya expiró. Solicita uno nuevo."),
    );
    renderPage();

    fill("Nueva-Clave-456");

    expect(await screen.findByRole("alert")).toHaveTextContent("El enlace no es válido o ya expiró.");
    expect(screen.getByRole("link", { name: "Solicitar un enlace nuevo" })).toHaveAttribute("href", "/forgot-password");
  });

  it("sin token avisa y ofrece pedir un enlace nuevo", () => {
    renderPage("/reset-password");

    expect(screen.getByRole("alert")).toHaveTextContent("El enlace no es válido o ya expiró.");
    expect(screen.queryByLabelText("Nueva contraseña")).not.toBeInTheDocument();
  });
});
