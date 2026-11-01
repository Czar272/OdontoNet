import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Doctor } from "../../types/doctor";
import type { User } from "../../types/user";
import DoctorProfileForm from "./DoctorProfileForm";

vi.mock("../../services/doctorService", () => ({
  createDoctor: vi.fn(async (data) => ({ id: 9, ...data })),
  updateDoctor: vi.fn(async (id, changes) => ({ id, ...changes })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { createDoctor, updateDoctor } = await import("../../services/doctorService");

const luis: User = { id: 12, name: "Dr. Luis", email: "luis@x.com", role: "doctor", clinic_id: 1, is_active: true };

const ana: Doctor = {
  id: 1,
  user_id: 11,
  specialization: "Periodoncia",
  license_number: "COL-1",
  phone: null,
  clinic_id: 1,
  user: { id: 11, name: "Dra. Ana", email: "ana@x.com", role: "doctor", clinic_id: 1, is_active: true },
};

beforeEach(() => vi.clearAllMocks());

describe("DoctorProfileForm", () => {
  it("crea el perfil para el usuario elegido", async () => {
    const onSuccess = vi.fn();
    renderWithAuth(<DoctorProfileForm candidates={[luis]} onSuccess={onSuccess} />, "admin");

    fireEvent.change(screen.getByLabelText(/usuario/i), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText(/especialidad/i), { target: { value: "Ortodoncia" } });
    fireEvent.change(screen.getByLabelText(/colegiado/i), { target: { value: "COL-2" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear perfil" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(createDoctor).toHaveBeenCalledWith({ user_id: 12, specialization: "Ortodoncia", license_number: "COL-2", phone: "" });
  });

  it("sin usuarios disponibles explica qué hacer", () => {
    renderWithAuth(<DoctorProfileForm candidates={[]} />, "admin");

    expect(screen.getByText(/ya tienen perfil/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Crear perfil" })).not.toBeInTheDocument();
  });

  it("al editar envía solo lo que cambió", async () => {
    const onSuccess = vi.fn();
    renderWithAuth(<DoctorProfileForm doctor={ana} onSuccess={onSuccess} />, "admin");

    expect(screen.getByLabelText("Doctor")).toHaveValue("Dra. Ana");
    fireEvent.change(screen.getByLabelText(/teléfono/i), { target: { value: "5555-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(updateDoctor).toHaveBeenCalledWith(1, { phone: "5555-1234" });
  });

  it("sin cambios no llama a la API", () => {
    renderWithAuth(<DoctorProfileForm doctor={ana} />, "admin");

    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(updateDoctor).not.toHaveBeenCalled();
  });
});
