import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Doctor } from "../../types/doctor";
import type { Patient } from "../../types/patient";
import PatientsPage from "./PatientsPage";

function doctor(id: number, name: string, isActive = true): Doctor {
  return {
    id,
    user_id: id + 100,
    specialization: null,
    license_number: null,
    phone: null,
    clinic_id: 1,
    user: { id: id + 100, name, email: `d${id}@x.com`, role: "doctor", clinic_id: 1, is_active: isActive },
  };
}

const ana = doctor(1, "Dra. Ana Morales");
const luis = doctor(2, "Dr. Luis Herrera", false);

const patient = (id: number, first: string, last: string, doc: Doctor | null): Patient => ({
  id,
  first_name: first,
  last_name: last,
  email: null,
  phone: null,
  clinic_id: 1,
  doctor_id: doc?.id ?? null,
  doctor: doc,
});

const state = vi.hoisted(() => ({ patients: [] as unknown[], archived: [] as unknown[] }));

vi.mock("../../services/patientService", () => ({
  getPatients: vi.fn(async (filters?: { archived?: boolean }) =>
    filters?.archived ? state.archived : state.patients,
  ),
  createPatient: vi.fn(),
}));

vi.mock("../../services/doctorService", () => ({
  getDoctors: vi.fn(async () => [ana, luis]),
}));

const ALL = [
  patient(1, "José", "Pérez", ana),
  patient(2, "María", "López", luis),
  patient(3, "Carlos", "Ruiz", null),
];

const { getPatients } = await import("../../services/patientService");

describe("PatientsPage", () => {
  it("busca por nombre o apellido sin importar tildes ni orden", async () => {
    state.patients = ALL;
    renderWithAuth(<PatientsPage />, "receptionist");
    await screen.findByText("José Pérez");

    fireEvent.change(screen.getByLabelText("Buscar pacientes"), { target: { value: "perez jose" } });

    expect(screen.getByText("José Pérez")).toBeInTheDocument();
    expect(screen.queryByText("María López")).not.toBeInTheDocument();
  });

  it("filtra por doctor de la clínica y marca a los inactivos", async () => {
    state.patients = ALL;
    renderWithAuth(<PatientsPage />, "doctor");
    await screen.findByText("José Pérez");

    expect(await screen.findByRole("option", { name: "Dr. Luis Herrera (inactivo)" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filtrar por doctor"), { target: { value: "2" } });

    expect(screen.getByText("María López")).toBeInTheDocument();
    expect(screen.queryByText("José Pérez")).not.toBeInTheDocument();
    expect(screen.queryByText("Carlos Ruiz")).not.toBeInTheDocument();
  });

  it("estado vacío por búsqueda sin resultados, con opción de limpiar", async () => {
    state.patients = ALL;
    renderWithAuth(<PatientsPage />, "admin");
    await screen.findByText("José Pérez");

    fireEvent.change(screen.getByLabelText("Buscar pacientes"), { target: { value: "zzz" } });
    expect(screen.getByText(/No hay pacientes que coincidan/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }));
    expect(screen.getByText("Carlos Ruiz")).toBeInTheDocument();
  });

  it("estado vacío cuando la clínica no tiene pacientes", async () => {
    state.patients = [];
    renderWithAuth(<PatientsPage />, "admin");

    expect(await screen.findByText("Todavía no hay pacientes registrados en la clínica.")).toBeInTheDocument();
  });

  it("muestra los archivados al cambiar el estado, pidiéndolos al backend", async () => {
    state.patients = ALL;
    state.archived = [{ ...patient(9, "Rosa", "Archivada", ana), archived_at: "2026-11-02T10:00:00Z" }];
    renderWithAuth(<PatientsPage />, "receptionist");
    await screen.findByText("José Pérez");
    expect(screen.queryByText("Archivado")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "archived" } });

    expect(await screen.findByText("Rosa Archivada")).toBeInTheDocument();
    expect(screen.getByText("Archivado")).toBeInTheDocument();
    expect(screen.queryByText("José Pérez")).not.toBeInTheDocument();
    expect(getPatients).toHaveBeenLastCalledWith({ archived: true });
  });

  it("estado vacío propio cuando no hay archivados", async () => {
    state.patients = ALL;
    state.archived = [];
    renderWithAuth(<PatientsPage />, "admin");
    await screen.findByText("José Pérez");

    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "archived" } });

    expect(await screen.findByText("No hay pacientes archivados.")).toBeInTheDocument();
  });
});
