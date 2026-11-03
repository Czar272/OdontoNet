import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { MedicalHistory } from "../../types/medicalHistory";
import MedicalHistoryCard from "./MedicalHistoryCard";

const empty = { present: null, detail: null };

function version(n: number, allergies: string, author = "Dra. Ana"): MedicalHistory {
  return {
    version: n,
    created_at: `2026-11-0${n}T16:00:00Z`,
    created_by: { id: n, name: author },
    conditions: {
      diabetes: { present: true, detail: "Tipo 2" },
      hypertension: empty,
      heart_disease: empty,
      bleeding_disorder: empty,
      respiratory_disease: empty,
      liver_kidney_disease: empty,
      immunosuppression: empty,
      pregnancy_lactation: empty,
    },
    other_conditions: null,
    allergies,
    current_medications: null,
    smoking_status: "never",
    cigarettes_per_day: null,
    alcohol: null,
    alcohol_detail: null,
    bruxism: null,
    chief_complaint: null,
    last_dental_visit: null,
    previous_treatments: null,
    brushing_per_day: null,
    uses_floss: null,
    gum_bleeding: null,
    notes: null,
  };
}

const v1 = version(1, "Penicilina", "Dr. Luis");
const v2 = version(2, "Penicilina y látex");

vi.mock("../../services/medicalHistoryService", () => ({
  getMedicalHistory: vi.fn(async () => v2),
  getMedicalHistoryVersions: vi.fn(async () => [
    { version: 2, created_at: v2.created_at, created_by: v2.created_by },
    { version: 1, created_at: v1.created_at, created_by: v1.created_by },
  ]),
  getMedicalHistoryVersion: vi.fn(async () => v1),
  saveMedicalHistory: vi.fn(async (_id: number, data: object) => ({
    ...v2,
    ...data,
    version: 3,
    created_by: { id: 1, name: "Usuario doctor" },
  })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const service = await import("../../services/medicalHistoryService");
const toast = (await import("react-hot-toast")).default;

beforeEach(() => vi.clearAllMocks());

describe("MedicalHistoryCard", () => {
  it("muestra la versión vigente en solo lectura con autor", async () => {
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit={false} isArchived={false} />, "receptionist");

    expect(await screen.findByLabelText("Alergias")).toHaveValue("Penicilina y látex");
    expect(screen.getByLabelText("Alergias")).toBeDisabled();
    expect(screen.getByTestId("history-version")).toHaveTextContent("Versión 2");
    expect(screen.getByTestId("history-version")).toHaveTextContent("Dra. Ana");
    expect(screen.getByLabelText("Diabetes")).toHaveValue("yes");
    expect(screen.getByText("Solo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar historia/i })).not.toBeInTheDocument();
  });

  it("permite consultar una versión anterior", async () => {
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit={false} isArchived={false} />, "receptionist");

    const selector = await screen.findByLabelText("Versión");
    fireEvent.change(selector, { target: { value: "1" } });

    expect(await screen.findByText(/versión anterior/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Alergias")).toHaveValue("Penicilina"));
    expect(service.getMedicalHistoryVersion).toHaveBeenCalledWith(5, 1);
    expect(screen.getByTestId("history-version")).toHaveTextContent("Dr. Luis");
  });

  it("guarda una versión nueva con la vigente como base", async () => {
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit isArchived={false} />, "doctor");

    fireEvent.click(await screen.findByRole("button", { name: /editar historia/i }));
    fireEvent.change(screen.getByLabelText("Alergias"), { target: { value: "Látex" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar historia" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Historia médica guardada (versión 3)"));
    expect(service.saveMedicalHistory).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ allergies: "Látex", base_version: 2 }),
    );
    expect(screen.getByLabelText("Alergias")).toBeDisabled();
  });

  it("no guarda si no hubo cambios", async () => {
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit isArchived={false} />, "doctor");

    fireEvent.click(await screen.findByRole("button", { name: /editar historia/i }));
    fireEvent.click(screen.getByRole("button", { name: "Guardar historia" }));

    expect(toast).toHaveBeenCalledWith("No hay cambios que guardar");
    expect(service.saveMedicalHistory).not.toHaveBeenCalled();
  });

  it("pide cigarrillos solo si fuma", async () => {
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit isArchived={false} />, "doctor");

    fireEvent.click(await screen.findByRole("button", { name: /editar historia/i }));
    expect(screen.queryByLabelText("Cigarrillos al día")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Tabaquismo"), { target: { value: "current" } });

    expect(screen.getByLabelText("Cigarrillos al día")).toBeInTheDocument();
  });

  it("si otra persona guardó antes, avisa y conserva lo escrito", async () => {
    vi.mocked(service.saveMedicalHistory).mockRejectedValueOnce(
      new AxiosError("409", "ERR", undefined, undefined, {
        status: 409,
        statusText: "Conflict",
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: { detail: "La historia médica cambió mientras la editabas. Revisa la versión actual antes de guardar." },
      }),
    );
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit isArchived={false} />, "doctor");

    fireEvent.click(await screen.findByRole("button", { name: /editar historia/i }));
    fireEvent.change(screen.getByLabelText("Alergias"), { target: { value: "Látex" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar historia" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("cambió mientras la editabas")));
    expect(screen.getByLabelText("Alergias")).toHaveValue("Látex");
    expect(screen.getByLabelText("Alergias")).toBeEnabled();
  });

  it("paciente sin historia: el doctor la registra desde cero", async () => {
    vi.mocked(service.getMedicalHistory).mockResolvedValueOnce(null);
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit isArchived={false} />, "doctor");

    expect(await screen.findByText(/aún no tiene historia médica/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /registrar historia/i }));
    fireEvent.change(screen.getByLabelText("Bruxismo"), { target: { value: "yes" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar historia" }));

    await waitFor(() =>
      expect(service.saveMedicalHistory).toHaveBeenCalledWith(5, expect.objectContaining({ bruxism: true, base_version: null })),
    );
  });

  it("paciente archivado: solo lectura aunque tenga permiso", async () => {
    renderWithAuth(<MedicalHistoryCard patientId={5} canEdit isArchived />, "doctor");

    expect(await screen.findByText("Archivado: solo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /editar historia/i })).not.toBeInTheDocument();
  });
});
