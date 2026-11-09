import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError } from "axios";
import toast from "react-hot-toast";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { refreshSession } from "../services/api";
import { getCurrentUser, loginRequest, logoutRequest } from "../services/authService";
import { clearToken, getToken } from "../services/session";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../services/api", () => ({ refreshSession: vi.fn(), default: {} }));
vi.mock("../services/authService", () => ({
  getCurrentUser: vi.fn(),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
}));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));

function Probe() {
  const { status, login, logout } = useAuth();
  return (
    <>
      <p>estado: {status}</p>
      <button onClick={() => void login("a@b.co", "clave-larga", true)}>entrar</button>
      <button onClick={logout}>salir</button>
    </>
  );
}

function renderProvider() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const user = { id: 1, name: "Ana", email: "a@b.co", role: "admin", clinic: { id: 1, name: "C" } };

beforeEach(() => {
  vi.mocked(getCurrentUser).mockResolvedValue(user as never);
  vi.mocked(logoutRequest).mockResolvedValue({ message: "ok" });
});

afterEach(() => {
  clearToken();
  vi.clearAllMocks();
});

describe("AuthProvider", () => {
  it("restaura la sesión con la cookie al cargar", async () => {
    vi.mocked(refreshSession).mockResolvedValue("acceso");

    renderProvider();

    expect(screen.getByText("estado: loading")).toBeInTheDocument();
    expect(await screen.findByText("estado: authenticated")).toBeInTheDocument();
  });

  it("sin sesión queda sin autenticar y sin avisos", async () => {
    vi.mocked(refreshSession).mockResolvedValue(null);

    renderProvider();

    expect(await screen.findByText("estado: unauthenticated")).toBeInTheDocument();
    expect(getCurrentUser).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("avisa si el servidor no responde al cargar", async () => {
    vi.mocked(refreshSession).mockRejectedValue(new AxiosError("sin red"));

    renderProvider();

    expect(await screen.findByText("estado: unauthenticated")).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith("No se pudo conectar con el servidor.", expect.anything());
  });

  it("el login guarda el token en memoria", async () => {
    vi.mocked(refreshSession).mockResolvedValue(null);
    vi.mocked(loginRequest).mockResolvedValue({
      access_token: "nuevo", token_type: "bearer", expires_in: 900,
    });
    renderProvider();
    await screen.findByText("estado: unauthenticated");

    fireEvent.click(screen.getByRole("button", { name: "entrar" }));

    expect(await screen.findByText("estado: authenticated")).toBeInTheDocument();
    expect(loginRequest).toHaveBeenCalledWith("a@b.co", "clave-larga", true);
    expect(getToken()).toBe("nuevo");
  });

  it("cerrar sesión revoca en el servidor y borra el token", async () => {
    vi.mocked(refreshSession).mockResolvedValue("acceso");
    renderProvider();
    await screen.findByText("estado: authenticated");

    fireEvent.click(screen.getByRole("button", { name: "salir" }));

    expect(await screen.findByText("estado: unauthenticated")).toBeInTheDocument();
    expect(logoutRequest).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Sesión cerrada"));
  });

  it("avisa si el servidor no confirmó el cierre de sesión", async () => {
    vi.mocked(refreshSession).mockResolvedValue("acceso");
    vi.mocked(logoutRequest).mockRejectedValue(new AxiosError("sin red"));
    renderProvider();
    await screen.findByText("estado: authenticated");

    fireEvent.click(screen.getByRole("button", { name: "salir" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.success).not.toHaveBeenCalledWith("Sesión cerrada");
  });
});
