import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Doctor } from "../../types/doctor";
import DoctorsPage from "./DoctorsPage";

function doctor(id: number, name: string, specialization: string | null, isActive = true): Doctor {
  return {
    id,
    user_id: id + 100,
    specialization,
    license_number: `COL-${id}`,
    phone: null,
    clinic_id: 1,
    user: { id: id + 100, name, email: `d${id}@odontonet-demo.com`, role: "doctor", clinic_id: 1, is_active: isActive },
  };
}

const doctors = [
  doctor(1, "Dra. Ana Morales", "Periodoncia"),
  doctor(2, "Dr. Luis Herrera", null),
  doctor(3, "Dr. Carlos Retirado", "Endodoncia", false),
];

vi.mock("../../services/doctorService", () => ({
  getDoctors: vi.fn(async () => doctors),
  createDoctor: vi.fn(),
  updateDoctor: vi.fn(),
}));

const sinPerfil = { id: 200, name: "Dr. Sin Perfil", email: "sp@odontonet-demo.com", role: "doctor" as const, clinic_id: 1, is_active: true };

vi.mock("../../services/userService", () => ({
  // Los tres doctores con perfil, uno sin perfil, un admin sin perfil y una recepcionista.
  getUsers: vi.fn(async () => [
    ...doctors.map((d) => d.user),
    sinPerfil,
    { ...sinPerfil, id: 201, name: "Admin Clínico", role: "admin" as const },
    { ...sinPerfil, id: 202, name: "Recepción", role: "receptionist" as const },
  ]),
}));

const { getUsers } = await import("../../services/userService");

describe("DoctorsPage", () => {
  it("muestra nombre y especialidad; por defecto solo activos", async () => {
    renderWithAuth(<DoctorsPage />, "receptionist");

    const row = (await screen.findByText("Dra. Ana Morales")).closest("tr") as HTMLElement;
    expect(within(row).getByText("Periodoncia")).toBeInTheDocument();
    expect(within(screen.getByText("Dr. Luis Herrera").closest("tr") as HTMLElement).getByText("General")).toBeInTheDocument();
    expect(screen.queryByText("Dr. Carlos Retirado")).not.toBeInTheDocument();
  });

  it("permite ver inactivos y todos", async () => {
    renderWithAuth(<DoctorsPage />, "doctor");
    await screen.findByText("Dra. Ana Morales");

    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "inactive" } });
    expect(screen.getByText("Dr. Carlos Retirado")).toBeInTheDocument();
    expect(screen.queryByText("Dra. Ana Morales")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "" } });
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("busca por especialidad", async () => {
    renderWithAuth(<DoctorsPage />, "admin");
    await screen.findByText("Dra. Ana Morales");

    fireEvent.change(screen.getByLabelText("Buscar doctores"), { target: { value: "perio" } });

    expect(screen.getByText("Dra. Ana Morales")).toBeInTheDocument();
    expect(screen.queryByText("Dr. Luis Herrera")).not.toBeInTheDocument();
  });

  it("administración puede crear y editar perfiles", async () => {
    renderWithAuth(<DoctorsPage />, "admin");
    await screen.findByText("Dra. Ana Morales");

    fireEvent.click(screen.getByRole("button", { name: "Editar perfil de Dra. Ana Morales" }));
    expect(screen.getByRole("dialog", { name: "Editar perfil" })).toBeInTheDocument();
    expect(screen.getByLabelText(/especialidad/i)).toHaveValue("Periodoncia");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));

    fireEvent.click(screen.getByRole("button", { name: "Nuevo perfil" }));
    const options = await screen.findAllByRole("option", { name: /Dr\. Sin Perfil|Admin Clínico/ });
    expect(options).toHaveLength(2);
    expect(screen.queryByRole("option", { name: /Recepción/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Dra\. Ana Morales/ })).not.toBeInTheDocument();
  });

  it.each(["doctor", "receptionist"] as const)("%s solo consulta", async (role) => {
    vi.mocked(getUsers).mockClear();
    renderWithAuth(<DoctorsPage />, role);
    await screen.findByText("Dra. Ana Morales");

    expect(screen.queryByRole("button", { name: "Nuevo perfil" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Editar perfil/ })).not.toBeInTheDocument();
    expect(getUsers).not.toHaveBeenCalled();
  });
});
