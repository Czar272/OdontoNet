import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { PeriodontalExam, ToothResponse } from "../../types/periodontal";
import PeriodontalCard from "./PeriodontalCard";
import { copyChart, DEFAULT_COPY } from "./copyExam";
import { PERMANENT_TEETH, SITES, emptyChart } from "./periodontalChart";
import { AUTOSAVE_MS, writeBackup } from "./periodontalExam";

const emptyTooth = (tooth: number): ToothResponse => ({
  tooth, missing: false, implant: false, mobility: null,
  furcation: { b: null, mp: null, dp: null, l: null }, note: null,
  sites: Object.fromEntries(SITES.map((site) => [site, {
    probing_depth: null, gingival_margin: null, attachment_level: null,
    bleeding: false, suppuration: false, plaque: false,
  }])) as ToothResponse["sites"],
});

const makeExam = (extra: Partial<PeriodontalExam> = {}): PeriodontalExam => ({
  id: 7, patient_id: 5, exam_date: "2026-11-06", clinical_visit: null, notes: null,
  status: "draft", revision: 3,
  created_by: { id: 1, name: "Dra. Ana" }, created_at: "2026-11-06T15:00:00Z", updated_at: "2026-11-06T15:00:00Z",
  finalized_by: null, finalized_at: null, voided_by: null, voided_at: null, void_reason: null,
  summary: { present_teeth: 32, measured_sites: 0, mean_probing_depth: null, mean_attachment_level: null,
    bleeding_pct: null, plaque_pct: null, deep_sites_pct: null },
  teeth: PERMANENT_TEETH.map(emptyTooth),
  ...extra,
});

/** Examen anterior: 18 ausente, 21 implante, 16 con movilidad, furcación y mediciones. */
function previousExam(): PeriodontalExam {
  const exam = makeExam({ id: 3, status: "final", exam_date: "2026-05-01", finalized_at: "2026-05-01T10:00:00Z",
    finalized_by: { id: 1, name: "Dra. Ana" } });
  exam.teeth = exam.teeth.map((tooth) => {
    if (tooth.tooth === 18) return { ...tooth, missing: true };
    if (tooth.tooth === 21) return { ...tooth, implant: true };
    if (tooth.tooth === 16) {
      return {
        ...tooth, mobility: 2, furcation: { ...tooth.furcation, b: 2 }, note: "Control",
        sites: { ...tooth.sites, mb: { ...tooth.sites.mb, probing_depth: 6, gingival_margin: -2, bleeding: true } },
      };
    }
    return tooth;
  });
  return exam;
}

let current = makeExam();
let list: PeriodontalExam[] = [];

class NetworkError extends Error {
  isAxiosError = true;
  response = undefined;
}

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});
vi.mock("../../services/clinicalVisitService", () => ({ getVisits: vi.fn(async () => []) }));
vi.mock("../../services/periodontalService", () => ({
  getPeriodontalExams: vi.fn(async () => list),
  getPeriodontalExam: vi.fn(async (_p: number, id: number) => (id === 3 ? previousExam() : current)),
  createPeriodontalExam: vi.fn(async () => current),
  updatePeriodontalExam: vi.fn(async (_p: number, _id: number, data: { base_revision: number }) => ({
    ...current, revision: data.base_revision + 1,
  })),
  finalizePeriodontalExam: vi.fn(async (_p: number, _id: number, revision: number) => ({
    ...current, revision, status: "final", finalized_at: "2026-11-07T10:00:00Z", finalized_by: { id: 1, name: "Dra. Ana" },
  })),
  voidPeriodontalExam: vi.fn(async (_p: number, _id: number, reason: string) => ({
    ...current, voided_at: "2026-11-07T10:00:00Z", voided_by: { id: 1, name: "Dra. Ana" }, void_reason: reason,
  })),
  getPeriodontalExamRevisions: vi.fn(async () => [
    { revision: 3, edited_by: { id: 1, name: "Dra. Ana" }, edited_at: "2026-11-06T16:00:00Z" },
    { revision: 1, edited_by: { id: 1, name: "Dra. Ana" }, edited_at: "2026-11-06T15:00:00Z" },
  ]),
}));

const service = await import("../../services/periodontalService");

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  current = makeExam();
  list = [current];
});

async function openExam(role: "doctor" | "admin" = "doctor") {
  renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, role);
  fireEvent.click(await screen.findByRole("button", { name: /abrir periodontograma/i }));
  return screen.findByRole("region", { name: "Arcada superior" });
}

describe("guardado y recuperación (ODON-190)", () => {
  it("autoguarda unos segundos después del último cambio", async () => {
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    expect(service.updatePeriodontalExam).not.toHaveBeenCalled();
    await waitFor(() => expect(service.updatePeriodontalExam).toHaveBeenCalledTimes(1), { timeout: AUTOSAVE_MS + 2000 });
    expect(await screen.findByText("Todo guardado")).toBeInTheDocument();
    expect(sessionStorage.length).toBe(0);
  });

  it("si falla la red, avisa, conserva el respaldo y permite reintentar", async () => {
    await openExam();
    vi.mocked(service.updatePeriodontalExam).mockRejectedValueOnce(new NetworkError("Network Error"));
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));

    expect(await screen.findByText(/no se pudo guardar\. tus cambios siguen respaldados/i)).toBeInTheDocument();
    const backup = JSON.parse(sessionStorage.getItem("odontonet:periodontal-draft:7") as string);
    expect(backup.baseRevision).toBe(3);
    expect(backup.chart.find((t: { tooth: number }) => t.tooth === 11).sites.b.probing_depth).toBe(4);

    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Todo guardado")).toBeInTheDocument();
    expect(sessionStorage.getItem("odontonet:periodontal-draft:7")).toBeNull();
  });

  it("al volver a abrir ofrece recuperar lo que no se guardó", async () => {
    const chart = emptyChart();
    chart.find((t) => t.tooth === 11)!.sites.b.probing_depth = 5;
    writeBackup(7, { userId: 1, baseRevision: 3, examDate: "2026-11-06", visitId: null, notes: "", chart,
      savedAt: "2026-11-07T15:30:00Z" });
    await openExam();

    expect(screen.getByText(/cambios de esta sesión que no se llegaron a guardar/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Recuperar cambios" }));
    expect(screen.getByLabelText("Sondaje 11 vestibular")).toHaveValue("5");
    expect(screen.getByText("Cambios sin guardar")).toBeInTheDocument();
  });

  it("no ofrece un respaldo de una revisión vieja", async () => {
    writeBackup(7, { userId: 1, baseRevision: 2, examDate: "2026-11-06", visitId: null, notes: "", chart: emptyChart(),
      savedAt: "2026-11-07T15:30:00Z" });
    await openExam();
    expect(screen.queryByText(/no se llegaron a guardar/i)).not.toBeInTheDocument();
  });

  it("finalizar guarda antes los cambios pendientes y deja el examen en solo lectura", async () => {
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Finalizar" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/ya no se puede modificar/i)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Finalizar" }));

    await waitFor(() => expect(service.finalizePeriodontalExam).toHaveBeenCalledWith(5, 7, 4));
    expect(service.updatePeriodontalExam).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByLabelText("Sondaje 11 vestibular")).toHaveAttribute("readonly"));
    expect(screen.queryByRole("button", { name: "Finalizar" })).not.toBeInTheDocument();
  });

  it("anula con motivo", async () => {
    await openExam();
    fireEvent.click(screen.getByRole("button", { name: "Anular" }));
    const form = await screen.findByRole("form", { name: "Anular periodontograma" });
    const submit = within(form).getByRole("button", { name: "Anular periodontograma" });
    expect(submit).toBeDisabled();
    fireEvent.change(within(form).getByLabelText("Motivo"), { target: { value: " Paciente equivocado " } });
    fireEvent.click(submit);
    await waitFor(() => expect(service.voidPeriodontalExam).toHaveBeenCalledWith(5, 7, "Paciente equivocado"));
  });

  it("un examen finalizado se puede anular pero no editar", async () => {
    current = makeExam({ status: "final", finalized_at: "2026-11-06T16:00:00Z", finalized_by: { id: 1, name: "Dra. Ana" } });
    list = [current];
    await openExam();
    expect(screen.getByRole("button", { name: "Anular" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Guardar borrador" })).not.toBeInTheDocument();
  });

  it("muestra los guardados con autor y fecha", async () => {
    await openExam();
    fireEvent.click(screen.getByRole("button", { name: "Ver guardados" }));
    const section = await screen.findByRole("region", { name: "Guardados del periodontograma" });
    expect(await within(section).findByText(/Revisión 3 · Dra. Ana/)).toBeInTheDocument();
    expect(within(section).getByText(/Revisión 1 · Dra. Ana/)).toBeInTheDocument();
  });

  it("crea un examen nuevo copiando lo elegido del anterior", async () => {
    list = [previousExam()];
    current = makeExam({ id: 8 });
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByRole("list", { name: "Periodontogramas del paciente" });
    fireEvent.click(screen.getByRole("button", { name: /nuevo periodontograma/i }));
    const form = await screen.findByRole("form", { name: "Nuevo periodontograma" });
    fireEvent.click(within(form).getByLabelText(/a partir del examen/i));
    fireEvent.click(within(form).getByLabelText("Sondajes y márgenes gingivales"));
    fireEvent.click(within(form).getByRole("button", { name: "Crear" }));

    await waitFor(() => expect(service.createPeriodontalExam).toHaveBeenCalledTimes(1));
    const [, body] = vi.mocked(service.createPeriodontalExam).mock.calls[0];
    const t16 = body.teeth.find((t) => t.tooth === 16)!;
    expect(body.teeth.find((t) => t.tooth === 18)?.missing).toBe(true);
    expect(body.teeth.find((t) => t.tooth === 21)?.implant).toBe(true);
    expect(t16.sites.mb.probing_depth).toBe(6);
    expect(t16.sites.mb.bleeding).toBe(false); // sangrado no elegido
    expect(t16.mobility).toBeNull(); // movilidad no elegida
    expect(t16.note).toBeNull();
  });

  it("sin examen previo crea directamente uno en blanco", async () => {
    list = [];
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByText(/aún no hay periodontogramas/i);
    fireEvent.click(screen.getByRole("button", { name: /nuevo periodontograma/i }));
    await waitFor(() => expect(service.createPeriodontalExam).toHaveBeenCalledWith(5, expect.objectContaining({ teeth: [] })));
  });
});

describe("copyChart", () => {
  it("por defecto copia solo el estado dental", () => {
    const chart = copyChart(previousExam(), DEFAULT_COPY);
    expect(chart.find((t) => t.tooth === 18)?.missing).toBe(true);
    expect(chart.find((t) => t.tooth === 21)?.implant).toBe(true);
    const t16 = chart.find((t) => t.tooth === 16)!;
    expect(t16.mobility).toBeNull();
    expect(t16.furcation.b).toBeNull();
    expect(t16.sites.mb.probing_depth).toBeNull();
  });

  it("con todo marcado copia movilidad, furcación, medidas e indicadores", () => {
    const t16 = copyChart(previousExam(), {
      dentalStatus: true, mobilityAndFurcation: true, measurements: true, indicators: true,
    }).find((t) => t.tooth === 16)!;
    expect(t16.mobility).toBe(2);
    expect(t16.furcation.b).toBe(2);
    expect(t16.sites.mb).toEqual({ probing_depth: 6, gingival_margin: -2, bleeding: true, suppuration: false, plaque: false });
  });
});

describe("carreras y privacidad (revisión de ODON-190)", () => {
  it("con el aviso de recuperación visible no se autoguarda ni se pisa el respaldo", async () => {
    const chart = emptyChart();
    chart.find((t) => t.tooth === 11)!.sites.b.probing_depth = 5;
    writeBackup(7, { userId: 1, baseRevision: 3, examDate: "2026-11-06", visitId: null, notes: "", chart,
      savedAt: "2026-11-07T15:30:00Z" });
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 12 vestibular"), { target: { value: "2" } });
    await new Promise((resolve) => setTimeout(resolve, AUTOSAVE_MS + 500));
    expect(service.updatePeriodontalExam).not.toHaveBeenCalled();
    const kept = JSON.parse(sessionStorage.getItem("odontonet:periodontal-draft:7") as string);
    expect(kept.chart.find((t: { tooth: number }) => t.tooth === 11).sites.b.probing_depth).toBe(5);
    expect(screen.getByRole("button", { name: "Finalizar" })).toBeDisabled();
  }, 10000);

  it("no ofrece el respaldo de otro usuario y lo borra", async () => {
    writeBackup(7, { userId: 99, baseRevision: 3, examDate: "2026-11-06", visitId: null, notes: "nota de otro",
      chart: emptyChart(), savedAt: "2026-11-07T15:30:00Z" });
    await openExam();
    expect(screen.queryByText(/no se llegaron a guardar/i)).not.toBeInTheDocument();
    expect(sessionStorage.getItem("odontonet:periodontal-draft:7")).toBeNull();
  });

  it("Finalizar se deshabilita sin sondajes y mientras se guarda", async () => {
    await openExam();
    expect(screen.getByRole("button", { name: "Finalizar" })).toBeDisabled();
    let resolveSave: (value: PeriodontalExam) => void = () => {};
    vi.mocked(service.updatePeriodontalExam).mockImplementationOnce(
      () => new Promise((resolve) => { resolveSave = resolve; }),
    );
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    expect(screen.getByRole("button", { name: "Finalizar" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Finalizar" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Anular" })).toBeDisabled();
    resolveSave({ ...current, revision: 4 });
    await waitFor(() => expect(screen.getByRole("button", { name: "Finalizar" })).toBeEnabled());
  });

  it("si falla solo el paso de finalizar, no se presenta como fallo de guardado", async () => {
    await openExam();
    vi.mocked(service.finalizePeriodontalExam).mockRejectedValueOnce(
      Object.assign(new Error("422"), { isAxiosError: true, response: { status: 422, data: { detail: "Registra al menos una profundidad de sondaje antes de finalizar." } } }),
    );
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Finalizar" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Finalizar" }));
    await waitFor(() => expect(service.finalizePeriodontalExam).toHaveBeenCalled());
    expect(await screen.findByText("Todo guardado")).toBeInTheDocument();
    expect(screen.queryByText(/no se pudo guardar/i)).not.toBeInTheDocument();
    expect(sessionStorage.getItem("odontonet:periodontal-draft:7")).toBeNull();
  });

  it("un doctor que no lo registró no puede anularlo; administración sí", async () => {
    current = makeExam({ created_by: { id: 99, name: "Dr. Otro" } });
    list = [current];
    await openExam("doctor");
    expect(screen.queryByRole("button", { name: "Anular" })).not.toBeInTheDocument();
  });

  it("administración anula el examen de otro", async () => {
    current = makeExam({ created_by: { id: 99, name: "Dr. Otro" } });
    list = [current];
    await openExam("admin");
    expect(screen.getByRole("button", { name: "Anular" })).toBeInTheDocument();
  });

  it("al volver a crear, el modal empieza en blanco", async () => {
    list = [previousExam()];
    current = makeExam({ id: 8 });
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByRole("list", { name: "Periodontogramas del paciente" });
    fireEvent.click(screen.getByRole("button", { name: /nuevo periodontograma/i }));
    let form = await screen.findByRole("form", { name: "Nuevo periodontograma" });
    fireEvent.click(within(form).getByLabelText(/a partir del examen/i));
    fireEvent.click(within(form).getByRole("button", { name: "Cancelar" }));
    fireEvent.click(screen.getByRole("button", { name: /nuevo periodontograma/i }));
    form = await screen.findByRole("form", { name: "Nuevo periodontograma" });
    expect(within(form).getByLabelText("En blanco")).toBeChecked();
    expect(within(form).queryByText("Copiar")).not.toBeInTheDocument();
  });
});
