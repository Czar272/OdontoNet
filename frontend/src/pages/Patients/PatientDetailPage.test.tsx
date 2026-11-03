import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError, AxiosHeaders } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext, type AuthContextType } from "../../context/AuthContext";
import { fakeUser } from "../../test/renderWithAuth";
import type { Role } from "../../types/auth";
import type { Doctor } from "../../types/doctor";
import type { Patient } from "../../types/patient";
import PatientDetailPage from "./PatientDetailPage";

function doctor(id: number, name: string, isActive = true): Doctor {
  return {
    id, user_id: id + 100, specialization: null, license_number: null, phone: null, clinic_id: 1,
    user: { id: id + 100, name, email: `d${id}@x.com`, role: "doctor", clinic_id: 1, is_active: isActive },
  };
}

const retired = doctor(3, "Dr. Retirado", false);
const ana = doctor(1, "Dra. Ana Morales");

const eva: Patient = {
  id: 5, first_name: "Eva", last_name: "Luna", birth_date: null, phone: "5555-0000",
  email: null, address: null, doctor_id: 3, doctor: retired, clinic_id: 1,
};

const archivedAt = "2026-11-02T16:00:00Z";
const rosa: Patient = { ...eva, id: 6, first_name: "Rosa", last_name: "Archivada", archived_at: archivedAt };

vi.mock("../../services/patientService", () => ({
  getPatient: vi.fn(async (id: number) => {
    if (id === 5) return eva;
    if (id === 6) return rosa;
    throw new AxiosError("404", "ERR", undefined, undefined, {
      status: 404, statusText: "Not Found", data: { detail: "Paciente no encontrado." },
      headers: {}, config: { headers: new AxiosHeaders() },
    });
  }),
  updatePatient: vi.fn(async (_id: number, changes: object) => ({ ...eva, ...changes })),
  archivePatient: vi.fn(async () => ({ ...eva, archived_at: archivedAt })),
  reactivatePatient: vi.fn(async () => ({ ...rosa, archived_at: null })),
}));

vi.mock("../../services/doctorService", () => ({ getDoctors: vi.fn(async () => [ana]) }));

vi.mock("../../services/clinicalVisitService", () => ({
  getVisits: vi.fn(async () => []),
  createVisit: vi.fn(),
  updateVisit: vi.fn(),
  voidVisit: vi.fn(),
  getVisitRevisions: vi.fn(async () => []),
}));

vi.mock("../../services/medicalHistoryService", () => ({
  getMedicalHistory: vi.fn(async () => null),
  getMedicalHistoryVersions: vi.fn(async () => []),
  getMedicalHistoryVersion: vi.fn(),
  saveMedicalHistory: vi.fn(),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { archivePatient, reactivatePatient, updatePatient } = await import(
  "../../services/patientService"
);

function renderAt(path: string, role: Role = "receptionist") {
  const value: AuthContextType = {
    status: "authenticated", user: fakeUser(role), loggedOutManually: false,
    login: async () => true, logout: () => {}, refreshUser: async () => {},
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={value}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/patients/:patientId" element={<PatientDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("PatientDetailPage", () => {
  it("muestra la ficha bloqueada con el doctor actual aunque esté inactivo", async () => {
    renderAt("/patients/5");

    expect(await screen.findByRole("heading", { name: "Eva Luna" })).toBeInTheDocument();
    expect(screen.getByLabelText(/nombres/i)).toBeDisabled();
    expect(screen.getByLabelText(/doctor asignado/i)).toHaveDisplayValue("Dr. Retirado (inactivo)");
    expect(screen.getByText("Historial clínico")).toBeInTheDocument();
  });

  it("recepción edita en dos pasos y reasigna doctor", async () => {
    renderAt("/patients/5");
    await screen.findByRole("heading", { name: "Eva Luna" });

    fireEvent.click(screen.getByRole("button", { name: /editar datos/i }));
    await screen.findByRole("option", { name: "Dra. Ana Morales" });
    expect(screen.getByRole("option", { name: "Dr. Retirado (inactivo)" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/teléfono/i), { target: { value: "5555-1111" } });
    fireEvent.change(screen.getByLabelText(/doctor asignado/i), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(updatePatient).toHaveBeenCalledWith(5, { phone: "5555-1111", doctor_id: 1 }));
  });

  it("Cancelar descarta los cambios", async () => {
    renderAt("/patients/5", "doctor");
    await screen.findByRole("heading", { name: "Eva Luna" });

    fireEvent.click(screen.getByRole("button", { name: /editar datos/i }));
    fireEvent.change(screen.getByLabelText(/nombres/i), { target: { value: "Otra" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(screen.getByLabelText(/nombres/i)).toHaveValue("Eva");
    expect(updatePatient).not.toHaveBeenCalled();
  });

  it.each(["/patients/999", "/patients/abc"])("%s muestra Paciente no encontrado", async (path) => {
    renderAt(path, "admin");

    expect(await screen.findByRole("heading", { name: "Paciente no encontrado" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a pacientes" })).toHaveAttribute("href", "/patients");
  });

  it("archiva con confirmación y la ficha queda en solo lectura", async () => {
    renderAt("/patients/5", "receptionist");
    await screen.findByRole("heading", { name: "Eva Luna" });

    fireEvent.click(screen.getByRole("button", { name: /archivar paciente/i }));
    expect(screen.getByText(/no se borra ningún dato/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Archivar" }));

    await waitFor(() => expect(archivePatient).toHaveBeenCalledWith(5));
    expect(await screen.findByRole("status")).toHaveTextContent(/paciente archivado el/i);
    expect(screen.queryByRole("button", { name: /editar datos/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reactivar paciente/i })).toBeInTheDocument();
  });

  it("cancelar el diálogo no archiva", async () => {
    renderAt("/patients/5", "doctor");
    await screen.findByRole("heading", { name: "Eva Luna" });

    fireEvent.click(screen.getByRole("button", { name: /archivar paciente/i }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(archivePatient).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /editar datos/i })).toBeInTheDocument();
  });

  it("un paciente archivado muestra el aviso, conserva sus datos y se reactiva", async () => {
    renderAt("/patients/6", "admin");
    await screen.findByRole("heading", { name: "Rosa Archivada" });

    expect(screen.getByRole("status")).toHaveTextContent(/sus datos e historial se conservan/i);
    expect(screen.getByText("Archivado: solo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar datos/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/teléfono/i)).toHaveValue("5555-0000");

    fireEvent.click(screen.getByRole("button", { name: /reactivar paciente/i }));
    fireEvent.click(screen.getByRole("button", { name: "Reactivar" }));

    await waitFor(() => expect(reactivatePatient).toHaveBeenCalledWith(6));
    expect(await screen.findByRole("button", { name: /editar datos/i })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("muestra la historia médica a recepción sin opción de editarla", async () => {
    renderAt("/patients/5", "receptionist");

    expect(await screen.findByText("Historia médica y odontológica")).toBeInTheDocument();
    expect(await screen.findByText(/aún no tiene historia médica/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /registrar historia/i })).not.toBeInTheDocument();
  });

  it("el doctor puede registrar la historia", async () => {
    renderAt("/patients/5", "doctor");

    expect(await screen.findByRole("button", { name: /registrar historia/i })).toBeInTheDocument();
  });

  it("las consultas clínicas no se muestran a recepción", async () => {
    renderAt("/patients/5", "receptionist");

    await screen.findByText("Historia médica y odontológica");
    expect(screen.queryByText("Consultas clínicas")).not.toBeInTheDocument();
  });

  it("el doctor ve las consultas y puede registrar una", async () => {
    renderAt("/patients/5", "doctor");

    expect(await screen.findByText("Consultas clínicas")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /nueva consulta/i })).toBeInTheDocument();
  });
});
