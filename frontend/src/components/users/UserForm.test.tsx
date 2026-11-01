import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { User } from "../../types/user";
import UserForm from "./UserForm";

vi.mock("../../services/userService", () => ({
  createUser: vi.fn(async (data) => ({ id: 99, clinic_id: 1, is_active: true, ...data })),
  updateUser: vi.fn(async (id, changes) => ({ id, clinic_id: 1, is_active: true, ...changes })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { createUser, updateUser } = await import("../../services/userService");

const ana: User = {
  id: 7,
  name: "Ana López",
  email: "ana@odontonet-demo.com",
  role: "receptionist",
  clinic_id: 1,
  is_active: true,
};

function type(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

beforeEach(() => vi.clearAllMocks());

describe("UserForm", () => {
  it("crea un usuario con todos los datos", async () => {
    const onSuccess = vi.fn();
    renderWithAuth(<UserForm onSuccess={onSuccess} />, "admin");

    type(/nombre completo/i, "Dr. Pérez");
    type(/correo/i, "perez@odontonet-demo.com");
    type(/contraseña/i, "Segura-123");
    fireEvent.click(screen.getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(createUser).toHaveBeenCalledWith({
      name: "Dr. Pérez",
      email: "perez@odontonet-demo.com",
      password: "Segura-123",
      role: "doctor",
    });
  });

  it("en alta la contraseña es obligatoria con mínimo 8 caracteres", () => {
    renderWithAuth(<UserForm />, "admin");

    const password = screen.getByLabelText(/contraseña/i);
    expect(password).toBeRequired();
    expect(password).toHaveAttribute("minLength", "8");
  });

  it("al editar solo envía lo que cambió", async () => {
    const onSuccess = vi.fn();
    renderWithAuth(<UserForm user={ana} onSuccess={onSuccess} />, "admin");

    expect(screen.getByLabelText(/nueva contraseña/i)).not.toBeRequired();
    type(/nombre completo/i, "Ana María López");
    fireEvent.change(screen.getByLabelText(/rol/i), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(updateUser).toHaveBeenCalledWith(7, { name: "Ana María López", role: "admin" });
  });

  it("sin cambios no llama a la API", () => {
    renderWithAuth(<UserForm user={ana} />, "admin");

    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(updateUser).not.toHaveBeenCalled();
  });

  it("no permite cambiar el rol propio", () => {
    // fakeUser tiene id 1: editar ese usuario es editarse a sí mismo.
    renderWithAuth(<UserForm user={{ ...ana, id: 1, role: "admin" }} />, "admin");

    expect(screen.getByLabelText(/rol/i)).toBeDisabled();
    expect(screen.getByText("No puedes cambiar tu propio rol.")).toBeInTheDocument();
  });

  it("el rol de otro usuario sí se puede cambiar", () => {
    renderWithAuth(<UserForm user={ana} />, "admin");

    expect(screen.getByLabelText(/rol/i)).toBeEnabled();
  });
});
