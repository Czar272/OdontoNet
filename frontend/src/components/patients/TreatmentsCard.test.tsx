import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import type { Treatment } from "../../types/treatment";
import TreatmentsCard from "./TreatmentsCard";

const base: Treatment = {
  id: 1,
  patient_id: 5,
  procedure: "Raspado",
  tooth: 36,
  notes: null,
  planned_date: null,
  status: "proposed",
  status_reason: null,
  status_changed_at: "2026-11-03T10:00:00Z",
  proposed_visit: null,
  completed_visit: null,
  created_by: { id: 1, name: "Dra. Ana" },
  created_at: "2026-11-03T10:00:00Z",
  updated_by: { id: 1, name: "Dra. Ana" },
  updated_at: "2026-11-03T10:00:00Z",
};

const proposed = base;
const inProgress: Treatment = { ...base, id: 2, procedure: "Endodoncia", tooth: 11, status: "in_progress" };
const cancelled: Treatment = { ...base, id: 3, procedure: "Extracción", status: "cancelled", status_reason: "Paciente no aceptó" };

const visit = (id: number, reason: string, voided = false): ClinicalVisit => ({
  id, patient_id: 5, revision: 1, visit_at: "2026-11-02T16:00:00Z", doctor: { id: 1, name: "Dra. Ana" }, reason,
  findings: null, diagnosis: null, procedures: null, instructions: null, next_visit_date: null,
  created_by: { id: 1, name: "Dra. Ana" }, created_at: "2026-11-02T16:00:00Z",
  updated_by: { id: 1, name: "Dra. Ana" }, updated_at: "2026-11-02T16:00:00Z",
  voided_at: voided ? "2026-11-02T17:00:00Z" : null, voided_by: null, void_reason: voided ? "x" : null,
});

vi.mock("../../services/treatmentService", () => ({
  getTreatments: vi.fn(async () => [inProgress, proposed, cancelled]),
  createTreatment: vi.fn(async (_p: number, data: object) => ({ ...base, ...data, id: 10 })),
  updateTreatment: vi.fn(async (_p: number, _id: number, changes: object) => ({ ...base, ...changes })),
  changeTreatmentStatus: vi.fn(async (_p: number, _id: number, data: { status: Treatment["status"] }) => ({ ...base, status: data.status })),
  getTreatmentHistory: vi.fn(async () => [
    { from_status: "proposed", to_status: "accepted", reason: null, changed_by: { id: 2, name: "Dr. Luis" }, changed_at: "2026-11-03T11:00:00Z" },
    { from_status: null, to_status: "proposed", reason: null, changed_by: { id: 1, name: "Dra. Ana" }, changed_at: "2026-11-03T10:00:00Z" },
  ]),
}));

vi.mock("../../services/clinicalVisitService", () => ({
  getVisits: vi.fn(async () => [visit(9, "Raspado cuadrante 3"), visit(8, "Consulta anulada", true)]),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const service = await import("../../services/treatmentService");

beforeEach(() => vi.clearAllMocks());

const item = (text: string) => screen.getByText(text).closest("li") as HTMLElement;

describe("TreatmentsCard", () => {
  it("separa pendientes y cerrados, con estado y motivo", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");

    const pending = await screen.findByRole("list", { name: "Tratamientos pendientes" });
    expect(within(pending).getAllByRole("listitem")).toHaveLength(2);
    const closed = screen.getByRole("list", { name: "Tratamientos cerrados" });
    expect(within(closed).getByText("Motivo: Paciente no aceptó")).toBeInTheDocument();
    expect(within(item("Endodoncia")).getByText("En curso")).toBeInTheDocument();
  });

  it("ofrece solo las transiciones permitidas", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    const buttons = (text: string) => within(item(text)).queryAllByRole("button").map((b) => b.textContent);
    expect(buttons("Raspado")).toEqual(expect.arrayContaining(["Aceptar", "Cancelar"]));
    expect(buttons("Raspado")).not.toContain("Completar");
    expect(buttons("Endodoncia")).toEqual(expect.arrayContaining(["Completar", "Cancelar"]));
    expect(within(item("Extracción")).queryByRole("button", { name: /editar/i })).not.toBeInTheDocument();
  });

  it("aceptar cambia el estado directamente", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    fireEvent.click(within(item("Raspado")).getByRole("button", { name: "Aceptar" }));

    await waitFor(() => expect(service.changeTreatmentStatus).toHaveBeenCalledWith(5, 1, { status: "accepted" }));
  });

  it("completar exige elegir una consulta vigente", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Endodoncia");

    fireEvent.click(within(item("Endodoncia")).getByRole("button", { name: "Completar" }));
    const confirm = await screen.findByRole("button", { name: "Marcar completado" });
    expect(confirm).toBeDisabled();
    const select = screen.getByLabelText("Consulta en que se realizó *");
    expect(within(select).queryByText(/Consulta anulada/)).not.toBeInTheDocument();
    fireEvent.change(select, { target: { value: "9" } });
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(service.changeTreatmentStatus).toHaveBeenCalledWith(5, 2, { status: "completed", completed_visit_id: 9 }),
    );
  });

  it("cancelar exige motivo", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    fireEvent.click(within(item("Raspado")).getByRole("button", { name: "Cancelar" }));
    const confirm = await screen.findByRole("button", { name: "Cancelar tratamiento" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Motivo de la cancelación *"), { target: { value: "Cambio de plan" } });
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(service.changeTreatmentStatus).toHaveBeenCalledWith(5, 1, { status: "cancelled", reason: "Cambio de plan" }),
    );
  });

  it("registra un tratamiento con pieza y consulta de propuesta", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    fireEvent.click(screen.getByRole("button", { name: /nuevo tratamiento/i }));
    const form = await screen.findByRole("form", { name: "Nuevo tratamiento" });
    fireEvent.change(within(form).getByLabelText("Procedimiento *"), { target: { value: "Profilaxis" } });
    fireEvent.change(within(form).getByLabelText("Pieza dental (FDI)"), { target: { value: "46" } });
    fireEvent.change(within(form).getByLabelText("Consulta en que se propuso"), { target: { value: "9" } });
    fireEvent.click(within(form).getByRole("button", { name: "Registrar tratamiento" }));

    await waitFor(() =>
      expect(service.createTreatment).toHaveBeenCalledWith(5, {
        procedure: "Profilaxis", tooth: 46, planned_date: null, proposed_visit_id: 9, notes: null,
      }),
    );
  });

  it("valida la pieza FDI antes de enviar", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    fireEvent.click(screen.getByRole("button", { name: /nuevo tratamiento/i }));
    const form = await screen.findByRole("form", { name: "Nuevo tratamiento" });
    fireEvent.change(within(form).getByLabelText("Procedimiento *"), { target: { value: "Profilaxis" } });
    fireEvent.change(within(form).getByLabelText("Pieza dental (FDI)"), { target: { value: "19" } });
    fireEvent.click(within(form).getByRole("button", { name: "Registrar tratamiento" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent("FDI");
    expect(service.createTreatment).not.toHaveBeenCalled();
  });

  it("al editar envía solo los cambios", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    fireEvent.click(screen.getByRole("button", { name: "Editar Raspado" }));
    const form = await screen.findByRole("form", { name: "Editar tratamiento" });
    fireEvent.change(within(form).getByLabelText("Notas"), { target: { value: "Bajo anestesia local" } });
    fireEvent.click(within(form).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(service.updateTreatment).toHaveBeenCalledWith(5, 1, { notes: "Bajo anestesia local" }));
  });

  it("muestra el historial de estados", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived={false} />, "doctor");
    await screen.findByText("Raspado");

    fireEvent.click(screen.getByRole("button", { name: "Historial de Raspado" }));

    expect(await screen.findByText("Propuesto → Aceptado")).toBeInTheDocument();
    expect(screen.getByText("Registrado como propuesto")).toBeInTheDocument();
  });

  it("paciente archivado: solo lectura", async () => {
    renderWithAuth(<TreatmentsCard patientId={5} canManage isArchived />, "admin");
    await screen.findByText("Raspado");

    expect(screen.queryByRole("button", { name: /nuevo tratamiento/i })).not.toBeInTheDocument();
    expect(within(item("Raspado")).queryByRole("button", { name: "Aceptar" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Historial de Raspado" })).toBeInTheDocument();
  });
});
