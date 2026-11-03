import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import type { Doctor } from "../../types/doctor";
import ClinicalVisitsCard from "./ClinicalVisitsCard";

// renderWithAuth usa el usuario id 1.
const own: ClinicalVisit = {
  id: 9,
  patient_id: 5,
  revision: 2,
  visit_at: "2026-11-02T16:30:00.000Z",
  doctor: { id: 3, name: "Dra. Ana" },
  reason: "Sangrado de encías",
  findings: "Inflamación generalizada",
  diagnosis: "Gingivitis",
  procedures: null,
  instructions: null,
  next_visit_date: "2026-12-01",
  created_by: { id: 1, name: "Usuario doctor" },
  created_at: "2026-11-02T16:31:00Z",
  updated_by: { id: 1, name: "Usuario doctor" },
  updated_at: "2026-11-02T17:00:00Z",
  voided_at: null,
  voided_by: null,
  void_reason: null,
};

const othersVisit: ClinicalVisit = {
  ...own,
  id: 8,
  revision: 1,
  visit_at: "2026-10-01T16:30:00.000Z",
  reason: "Control anual",
  created_by: { id: 2, name: "Dr. Luis" },
  updated_by: { id: 2, name: "Dr. Luis" },
};

const voided: ClinicalVisit = {
  ...own,
  id: 7,
  revision: 1,
  reason: "Consulta duplicada",
  voided_at: "2026-11-02T18:00:00Z",
  voided_by: { id: 1, name: "Usuario doctor" },
  void_reason: "Registrada dos veces",
};

const ana: Doctor = {
  id: 3, user_id: 1, specialization: null, license_number: null, phone: null, clinic_id: 1,
  user: { id: 1, name: "Dra. Ana", email: "ana@x.com", role: "doctor", clinic_id: 1, is_active: true },
};

vi.mock("../../services/clinicalVisitService", () => ({
  getVisits: vi.fn(async () => [own, othersVisit, voided]),
  createVisit: vi.fn(async (_p: number, data: object) => ({ ...own, ...data, id: 10, revision: 1 })),
  updateVisit: vi.fn(async (_p: number, _id: number, data: object) => ({ ...own, ...data, revision: 3 })),
  voidVisit: vi.fn(async () => ({ ...own, voided_at: "2026-11-03T00:00:00Z" })),
  getVisitRevisions: vi.fn(async () => [
    { ...own, revision: 2, edited_by: { id: 1, name: "Usuario doctor" }, edited_at: own.updated_at },
    { ...own, revision: 1, diagnosis: "Sin diagnóstico", edited_by: { id: 1, name: "Usuario doctor" }, edited_at: own.created_at },
  ]),
}));

vi.mock("../../services/doctorService", () => ({ getDoctors: vi.fn(async () => [ana]) }));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const service = await import("../../services/clinicalVisitService");
const toast = (await import("react-hot-toast")).default;

beforeEach(() => vi.clearAllMocks());

function item(reason: string) {
  return screen.getByText(new RegExp(reason)).closest("li") as HTMLElement;
}

describe("ClinicalVisitsCard", () => {
  it("lista las consultas con doctor, autor y contenido", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");

    const first = await screen.findByText(/Sangrado de encías/);
    const row = first.closest("li") as HTMLElement;
    expect(within(row).getByText(/registrada por Usuario doctor/)).toBeInTheDocument();
    expect(within(row).getByText("Gingivitis")).toBeInTheDocument();
    expect(within(row).getByText(/editada por/)).toBeInTheDocument();
  });

  it("solo ofrece editar y anular las consultas propias", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByText(/Sangrado de encías/);

    expect(within(item("Sangrado de encías")).getByRole("button", { name: /editar/i })).toBeInTheDocument();
    expect(within(item("Control anual")).queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
    expect(within(item("Control anual")).queryByRole("button", { name: /anular/i })).not.toBeInTheDocument();
  });

  it("administración puede modificar consultas de otros", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "admin");
    await screen.findByText(/Control anual/);

    expect(within(item("Control anual")).getByRole("button", { name: /editar/i })).toBeInTheDocument();
  });

  it("muestra la anulada con su motivo y sin acciones", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "admin");
    await screen.findByText(/Consulta duplicada/);

    const row = item("Consulta duplicada");
    expect(within(row).getByRole("note")).toHaveTextContent("Motivo: Registrada dos veces");
    expect(within(row).queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
  });

  it("registra una consulta nueva con el doctor propuesto", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");

    fireEvent.click(await screen.findByRole("button", { name: /nueva consulta/i }));
    const form = await screen.findByRole("form", { name: "Nueva consulta" });
    await waitFor(() => expect(within(form).getByLabelText("Doctor *")).toHaveValue("3"));
    fireEvent.change(within(form).getByLabelText("Motivo de la consulta *"), { target: { value: "Dolor molar" } });
    fireEvent.click(within(form).getByRole("button", { name: "Registrar consulta" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Consulta registrada"));
    expect(service.createVisit).toHaveBeenCalledWith(5, expect.objectContaining({ reason: "Dolor molar", doctor_id: 3 }));
  });

  it("edita enviando la revisión vigente", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByText(/Sangrado de encías/);

    fireEvent.click(within(item("Sangrado de encías")).getByRole("button", { name: /editar/i }));
    const form = await screen.findByRole("form", { name: "Editar consulta" });
    fireEvent.change(within(form).getByLabelText("Diagnóstico profesional"), { target: { value: "Periodontitis" } });
    fireEvent.click(within(form).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() =>
      expect(service.updateVisit).toHaveBeenCalledWith(5, 9, expect.objectContaining({ diagnosis: "Periodontitis", base_revision: 2 })),
    );
  });

  it("ante un 409 conserva lo escrito y recarga la lista", async () => {
    vi.mocked(service.updateVisit).mockRejectedValueOnce(
      new AxiosError("409", "ERR", undefined, undefined, {
        status: 409, statusText: "Conflict", headers: {}, config: { headers: new AxiosHeaders() },
        data: { detail: "La consulta cambió mientras la editabas. Revisa la versión actual antes de guardar." },
      }),
    );
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByText(/Sangrado de encías/);

    fireEvent.click(within(item("Sangrado de encías")).getByRole("button", { name: /editar/i }));
    const form = await screen.findByRole("form", { name: "Editar consulta" });
    fireEvent.change(within(form).getByLabelText("Indicaciones"), { target: { value: "Enjuague" } });
    fireEvent.click(within(form).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("cambió mientras la editabas")));
    expect(within(form).getByLabelText("Indicaciones")).toHaveValue("Enjuague");
    await waitFor(() => expect(service.getVisits).toHaveBeenCalledTimes(2));
  });

  it("anula pidiendo un motivo", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByText(/Sangrado de encías/);

    fireEvent.click(within(item("Sangrado de encías")).getByRole("button", { name: /anular/i }));
    const confirm = await screen.findByRole("button", { name: "Anular consulta" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Motivo de la anulación *"), { target: { value: "Paciente equivocado" } });
    fireEvent.click(confirm);

    await waitFor(() => expect(service.voidVisit).toHaveBeenCalledWith(5, 9, "Paciente equivocado"));
  });

  it("muestra el historial de cambios", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByText(/Sangrado de encías/);

    fireEvent.click(within(item("Sangrado de encías")).getByRole("button", { name: /cambios/i }));

    expect(await screen.findByText(/Revisión 1 \(registro\)/)).toBeInTheDocument();
    expect(screen.getByText("Sin diagnóstico")).toBeInTheDocument();
  });

  it("paciente archivado: sin registrar ni modificar", async () => {
    renderWithAuth(<ClinicalVisitsCard patientId={5} canCreate isArchived />, "admin");
    await screen.findByText(/Sangrado de encías/);

    expect(screen.queryByRole("button", { name: /nueva consulta/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^editar$/i })).not.toBeInTheDocument();
  });
});
