import { fireEvent, screen } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getToken, setToken } from "../../services/session";
import { renderWithAuth } from "../../test/renderWithAuth";
import ChangePasswordPage from "./ChangePasswordPage";

vi.mock("../../services/authService", () => ({
  changePasswordRequest: vi.fn(async () => ({ access_token: "token-nuevo", token_type: "bearer", expires_in: 900, user_id: 1 })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { changePasswordRequest } = await import("../../services/authService");
const toast = (await import("react-hot-toast")).default;

function fill(current: string, password: string, confirmation = password) {
  fireEvent.change(screen.getByLabelText("Contraseña actual"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("Nueva contraseña"), { target: { value: password } });
  fireEvent.change(screen.getByLabelText("Confirmar contraseña"), { target: { value: confirmation } });
  fireEvent.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
}

beforeEach(() => vi.clearAllMocks());

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe("ChangePasswordPage", () => {
  it("cambia la contraseña y guarda el token nuevo en memoria", async () => {
    setToken("token-viejo", 1);
    renderWithAuth(<ChangePasswordPage />, "doctor");

    fill("Actual-123", "Nueva-Clave-456");

    await vi.waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(changePasswordRequest).toHaveBeenCalledWith("Actual-123", "Nueva-Clave-456");
    expect(getToken()).toBe("token-nuevo");
    expect(localStorage.getItem("token")).toBeNull();
    expect(screen.getByLabelText("Contraseña actual")).toHaveValue("");
  });

  it("valida la confirmación antes de llamar a la API", () => {
    renderWithAuth(<ChangePasswordPage />, "receptionist");

    fill("Actual-123", "Nueva-Clave-456", "otra");

    expect(screen.getByRole("alert")).toHaveTextContent("Las contraseñas no coinciden.");
    expect(changePasswordRequest).not.toHaveBeenCalled();
  });

  it("muestra el error si la contraseña actual es incorrecta y conserva el token", async () => {
    setToken("token-viejo", 1);
    vi.mocked(changePasswordRequest).mockRejectedValueOnce(
      new AxiosError("error", "ERR", undefined, undefined, {
        status: 400,
        statusText: "",
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: { detail: "La contraseña actual no es correcta." },
      }),
    );
    renderWithAuth(<ChangePasswordPage />, "admin");

    fill("incorrecta", "Nueva-Clave-456");

    expect(await screen.findByRole("alert")).toHaveTextContent("La contraseña actual no es correcta.");
    expect(getToken()).toBe("token-viejo");
  });
});
