import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { User } from "../../types/user";
import UsersPage from "./UsersPage";

const users: User[] = [
  { id: 1, name: "Usuario admin", email: "admin@odontonet-demo.com", role: "admin", clinic_id: 1, is_active: true },
  { id: 2, name: "Ana López", email: "ana@odontonet-demo.com", role: "receptionist", clinic_id: 1, is_active: true },
  { id: 3, name: "Dr. Pérez", email: "perez@odontonet-demo.com", role: "doctor", clinic_id: 1, is_active: false },
];

vi.mock("../../services/userService", () => ({
  getUsers: vi.fn(async () => users),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deactivateUser: vi.fn(async (id: number) => ({ ...users.find((u) => u.id === id), is_active: false })),
  activateUser: vi.fn(async (id: number) => ({ ...users.find((u) => u.id === id), is_active: true })),
}));

const { activateUser, deactivateUser } = await import("../../services/userService");

beforeEach(() => vi.clearAllMocks());

describe("UsersPage", () => {
  it("lista los usuarios con su rol y estado", async () => {
    renderWithAuth(<UsersPage />, "admin");

    expect(await screen.findByText("Ana López")).toBeInTheDocument();
    const anaRow = screen.getByRole("row", { name: /Ana López/ });
    expect(within(anaRow).getByText("Recepción")).toBeInTheDocument();
    expect(within(anaRow).getByText("Activo")).toBeInTheDocument();
    const perezRow = screen.getByRole("row", { name: /Dr\. Pérez/ });
    expect(within(perezRow).getByText("Inactivo")).toBeInTheDocument();
    expect(screen.queryByText(/hashed|password/i)).not.toBeInTheDocument();
  });

  it("filtra por nombre o correo y por rol", async () => {
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Ana López");

    fireEvent.change(screen.getByLabelText("Buscar usuarios"), { target: { value: "perez@" } });
    expect(screen.getByText("Dr. Pérez")).toBeInTheDocument();
    expect(screen.queryByText("Ana López")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Buscar usuarios"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Filtrar por rol"), { target: { value: "receptionist" } });
    expect(screen.getByText("Ana López")).toBeInTheDocument();
    expect(screen.queryByText("Dr. Pérez")).not.toBeInTheDocument();
  });

  it("abre el formulario de edición con los datos del usuario", async () => {
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Ana López");

    fireEvent.click(screen.getByRole("button", { name: "Editar Ana López" }));

    expect(screen.getByRole("dialog", { name: "Editar usuario" })).toBeInTheDocument();
    expect(screen.getByLabelText(/nombre completo/i)).toHaveValue("Ana López");
  });

  it("filtra por estado", async () => {
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Ana López");

    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "inactive" } });

    expect(screen.getByText("Dr. Pérez")).toBeInTheDocument();
    expect(screen.queryByText("Ana López")).not.toBeInTheDocument();
  });

  it("no ofrece desactivar la propia cuenta", async () => {
    // fakeUser (la sesión) tiene id 1, igual que "Usuario admin".
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Ana López");

    expect(screen.queryByRole("button", { name: "Desactivar Usuario admin" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Desactivar Ana López" })).toBeInTheDocument();
  });

  it("desactiva un usuario después de confirmar", async () => {
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Ana López");

    fireEvent.click(screen.getByRole("button", { name: "Desactivar Ana López" }));
    const dialog = screen.getByRole("dialog", { name: "Desactivar usuario" });
    expect(deactivateUser).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Desactivar" }));

    await waitFor(() => expect(deactivateUser).toHaveBeenCalledWith(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("cancelar no cambia el estado", async () => {
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Ana López");

    fireEvent.click(screen.getByRole("button", { name: "Desactivar Ana López" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(deactivateUser).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("reactiva a un usuario inactivo", async () => {
    renderWithAuth(<UsersPage />, "admin");
    await screen.findByText("Dr. Pérez");

    fireEvent.click(screen.getByRole("button", { name: "Activar Dr. Pérez" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "Activar usuario" })).getByRole("button", { name: "Activar" }));

    await waitFor(() => expect(activateUser).toHaveBeenCalledWith(3));
  });
});
