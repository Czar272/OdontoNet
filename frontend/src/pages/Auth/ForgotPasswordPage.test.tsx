import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ForgotPasswordPage from "./ForgotPasswordPage";

const GENERIC = "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.";

vi.mock("../../services/authService", () => ({
  requestPasswordReset: vi.fn(async () => ({ message: GENERIC })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { requestPasswordReset } = await import("../../services/authService");
const toast = (await import("react-hot-toast")).default;

function renderPage() {
  render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("ForgotPasswordPage", () => {
  it("envía el correo y muestra el mensaje genérico del servidor", async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: "ana@odontonet-demo.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar enlace" }));

    expect(await screen.findByRole("status")).toHaveTextContent(GENERIC);
    expect(requestPasswordReset).toHaveBeenCalledWith("ana@odontonet-demo.com");
    expect(screen.queryByRole("button", { name: "Enviar enlace" })).not.toBeInTheDocument();
  });

  it("si la API falla avisa y deja el formulario", async () => {
    vi.mocked(requestPasswordReset).mockRejectedValueOnce(new Error("caída"));
    renderPage();

    fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: "ana@odontonet-demo.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar enlace" }));

    await vi.waitFor(() => expect(toast.error).toHaveBeenCalledWith("No se pudo enviar la solicitud."));
    expect(screen.getByRole("button", { name: "Enviar enlace" })).toBeEnabled();
  });

  it("enlaza de vuelta al inicio de sesión", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "Volver a iniciar sesión" })).toHaveAttribute("href", "/");
  });
});
