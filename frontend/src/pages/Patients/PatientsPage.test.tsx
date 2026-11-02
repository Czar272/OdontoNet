import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PatientFilters } from "../../services/patientService";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { Doctor } from "../../types/doctor";
import type { Patient, PatientPage } from "../../types/patient";
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

const ALL = [
  patient(1, "José", "Pérez", ana),
  patient(2, "María", "López", luis),
  patient(3, "Carlos", "Ruiz", null),
];

// El backend filtra y pagina: el mock responde según la prueba y se verifica
// qué parámetros se le enviaron.
const state = vi.hoisted(() => ({
  respond: (() => null) as (filters: PatientFilters) => unknown,
}));

vi.mock("../../services/patientService", () => ({
  getPatients: vi.fn(async (filters: PatientFilters) => state.respond(filters)),
  createPatient: vi.fn(),
}));

vi.mock("../../services/doctorService", () => ({
  getDoctors: vi.fn(async () => [ana, luis]),
}));

const { getPatients } = await import("../../services/patientService");

function page(items: Patient[], total = items.length, pageNumber = 1): PatientPage {
  return { items, total, page: pageNumber, page_size: 20 };
}

function lastFilters(): PatientFilters {
  const calls = vi.mocked(getPatients).mock.calls;
  return calls[calls.length - 1][0] as PatientFilters;
}

beforeEach(() => {
  vi.clearAllMocks();
  state.respond = (f) => page(ALL, ALL.length, f.page);
});

describe("PatientsPage", () => {
  it("pide la primera página de activos y muestra el total", async () => {
    renderWithAuth(<PatientsPage />, "receptionist");

    expect(await screen.findByText("José Pérez")).toBeInTheDocument();
    expect(screen.getByText("3 pacientes · Página 1 de 1")).toBeInTheDocument();
    expect(getPatients).toHaveBeenCalledWith({
      archived: false, search: "", doctorId: undefined, page: 1, pageSize: 20,
    });
  });

  it("envía la búsqueda al backend cuando se deja de escribir", async () => {
    renderWithAuth(<PatientsPage />, "receptionist");
    await screen.findByText("José Pérez");

    state.respond = () => page([ALL[0]]);
    fireEvent.change(screen.getByLabelText("Buscar pacientes"), { target: { value: "  perez jose " } });

    await waitFor(() => expect(lastFilters()).toMatchObject({ search: "perez jose", page: 1 }));
    await waitFor(() => expect(screen.queryByText("María López")).not.toBeInTheDocument());
    expect(screen.getByText("José Pérez")).toBeInTheDocument();
    // Una sola consulta por la búsqueda completa, no una por tecla.
    expect(vi.mocked(getPatients).mock.calls.filter(([f]) => (f as PatientFilters).search)).toHaveLength(1);
  });

  it("filtra por doctor en el backend y marca a los inactivos", async () => {
    renderWithAuth(<PatientsPage />, "doctor");
    await screen.findByText("José Pérez");

    expect(await screen.findByRole("option", { name: "Dr. Luis Herrera (inactivo)" })).toBeInTheDocument();
    state.respond = () => page([ALL[1]]);
    fireEvent.change(screen.getByLabelText("Filtrar por doctor"), { target: { value: "2" } });

    await waitFor(() => expect(lastFilters()).toMatchObject({ doctorId: 2, page: 1 }));
    expect(await screen.findByText("1 paciente · Página 1 de 1")).toBeInTheDocument();
    expect(screen.queryByText("José Pérez")).not.toBeInTheDocument();
  });

  it("pagina con Anterior y Siguiente", async () => {
    state.respond = (f) => page(f.page === 2 ? [ALL[2]] : [ALL[0], ALL[1]], 45, f.page);
    renderWithAuth(<PatientsPage />, "admin");
    await screen.findByText("45 pacientes · Página 1 de 3");

    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));

    expect(await screen.findByText("45 pacientes · Página 2 de 3")).toBeInTheDocument();
    expect(await screen.findByText("Carlos Ruiz")).toBeInTheDocument();
    expect(lastFilters()).toMatchObject({ page: 2 });
    expect(screen.getByRole("button", { name: "Anterior" })).toBeEnabled();
  });

  it("cambiar un filtro vuelve a la primera página", async () => {
    state.respond = (f) => page(ALL, 45, f.page);
    renderWithAuth(<PatientsPage />, "admin");
    await screen.findByText("45 pacientes · Página 1 de 3");
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByText("45 pacientes · Página 2 de 3");

    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "archived" } });

    await waitFor(() => expect(lastFilters()).toMatchObject({ archived: true, page: 1 }));
  });

  it("sin paginación cuando no hay resultados", async () => {
    state.respond = () => page([]);
    renderWithAuth(<PatientsPage />, "admin");

    expect(await screen.findByText("Todavía no hay pacientes registrados en la clínica.")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Paginación de pacientes" })).not.toBeInTheDocument();
  });

  it("estado vacío por búsqueda sin resultados, con opción de limpiar", async () => {
    renderWithAuth(<PatientsPage />, "admin");
    await screen.findByText("José Pérez");

    state.respond = (f) => (f.search ? page([]) : page(ALL));
    fireEvent.change(screen.getByLabelText("Buscar pacientes"), { target: { value: "zzz" } });
    expect(await screen.findByText(/No hay pacientes que coincidan/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }));

    expect(await screen.findByText("Carlos Ruiz")).toBeInTheDocument();
    expect(screen.getByLabelText("Buscar pacientes")).toHaveValue("");
  });

  it("muestra los archivados al cambiar el estado, pidiéndolos al backend", async () => {
    renderWithAuth(<PatientsPage />, "receptionist");
    await screen.findByText("José Pérez");
    expect(screen.queryByText("Archivado")).not.toBeInTheDocument();

    state.respond = () => page([{ ...patient(9, "Rosa", "Archivada", ana), archived_at: "2026-11-02T10:00:00Z" }]);
    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "archived" } });

    expect(await screen.findByText("Rosa Archivada")).toBeInTheDocument();
    expect(screen.getByText("Archivado")).toBeInTheDocument();
    expect(screen.queryByText("José Pérez")).not.toBeInTheDocument();
    expect(lastFilters()).toMatchObject({ archived: true });
  });

  it("estado vacío propio cuando no hay archivados", async () => {
    renderWithAuth(<PatientsPage />, "admin");
    await screen.findByText("José Pérez");

    state.respond = () => page([]);
    fireEvent.change(screen.getByLabelText("Filtrar por estado"), { target: { value: "archived" } });

    expect(await screen.findByText("No hay pacientes archivados.")).toBeInTheDocument();
  });
});
