import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { PeriodontalExam, ToothResponse } from "../../types/periodontal";
import PeriodontalCard from "./PeriodontalCard";
import { PERMANENT_TEETH, SITES } from "./periodontalChart";

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
  // fakeUser() tiene id 1: es el autor.
  created_by: { id: 1, name: "Dra. Ana" }, created_at: "2026-11-06T15:00:00Z", updated_at: "2026-11-06T15:00:00Z",
  finalized_by: null, finalized_at: null, voided_by: null, voided_at: null, void_reason: null,
  summary: { present_teeth: 32, measured_sites: 0, mean_probing_depth: null, mean_attachment_level: null,
    bleeding_pct: null, plaque_pct: null, deep_sites_pct: null },
  teeth: PERMANENT_TEETH.map(emptyTooth),
  ...extra,
});

let current = makeExam();

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});
vi.mock("../../services/clinicalVisitService", () => ({ getVisits: vi.fn(async () => []) }));
class Conflict extends Error {
  isAxiosError = true;
  response = { status: 409, data: { detail: "El periodontograma cambió mientras lo editabas.", current_revision: 4 } };
}

vi.mock("../../services/periodontalService", () => ({
  getPeriodontalExams: vi.fn(async () => [current]),
  getPeriodontalExam: vi.fn(async () => current),
  createPeriodontalExam: vi.fn(async () => current),
  updatePeriodontalExam: vi.fn(async (_p: number, _id: number, data: { base_revision: number }) => ({
    ...current, revision: data.base_revision + 1,
  })),
}));

const service = await import("../../services/periodontalService");

beforeEach(() => {
  vi.clearAllMocks();
  current = makeExam();
});

async function openExam(role: "doctor" | "admin" = "doctor") {
  renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, role);
  fireEvent.click(await screen.findByRole("button", { name: /abrir periodontograma/i }));
  return screen.findByRole("region", { name: "Arcada superior" });
}

describe("PeriodontalCard", () => {
  it("lista los exámenes con estado, autor y resumen", async () => {
    current = makeExam({ summary: { ...makeExam().summary, measured_sites: 12, mean_probing_depth: 3.5, bleeding_pct: 25 } });
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    const list = await screen.findByRole("list", { name: "Periodontogramas del paciente" });
    expect(within(list).getByText("Borrador")).toBeInTheDocument();
    expect(within(list).getByText("Dra. Ana")).toBeInTheDocument();
    expect(within(list).getByText(/12 sitios · sondaje medio 3.5 mm · sangrado 25 %/)).toBeInTheDocument();
  });

  it("crea un borrador vacío con la fecha de hoy y lo abre", async () => {
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    fireEvent.click(await screen.findByRole("button", { name: /nuevo periodontograma/i }));
    await waitFor(() => expect(service.createPeriodontalExam).toHaveBeenCalledWith(5, expect.objectContaining({ teeth: [] })));
    expect(await screen.findByRole("region", { name: "Arcada inferior" })).toBeInTheDocument();
  });

  it("muestra las 32 piezas con sus 6 sitios y dibuja ambas caras", async () => {
    await openExam();
    expect(screen.getAllByLabelText(/^Sondaje \d\d /)).toHaveLength(32 * 6);
    expect(screen.getAllByLabelText(/^Margen gingival \d\d /)).toHaveLength(32 * 6);
    expect(screen.getByRole("img", { name: /cara vestibular de la arcada superior/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /cara palatina de la arcada superior/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /cara lingual de la arcada inferior/ })).toBeInTheDocument();
  });

  it("al escribir un sondaje salta al sitio siguiente, dibuja la bolsa y actualiza el resumen", async () => {
    await openExam();
    // 16 vestibular se lee distal → mesial: db, b, mb.
    const db = screen.getByLabelText("Sondaje 16 distovestibular");
    db.focus();
    fireEvent.change(db, { target: { value: "5" } });
    expect(screen.getByLabelText("Sondaje 16 vestibular")).toHaveFocus();
    expect(screen.getByTestId("depth-buccal-16")).toBeInTheDocument();

    const summary = screen.getByRole("region", { name: "Resumen del periodontograma" });
    expect(within(summary).getByText("5 mm")).toBeInTheDocument(); // sondaje medio
    expect(within(summary).getByText("100 %")).toBeInTheDocument(); // sitios ≥ 4 mm
  });

  it("espera el segundo dígito cuando el valor puede crecer", async () => {
    await openExam();
    const site = screen.getByLabelText("Sondaje 16 distovestibular");
    site.focus();
    fireEvent.change(site, { target: { value: "1" } });
    expect(site).toHaveFocus();
    fireEvent.change(site, { target: { value: "12" } });
    expect(screen.getByLabelText("Sondaje 16 vestibular")).toHaveFocus();

    const margin = screen.getByLabelText("Margen gingival 26 mesiovestibular");
    margin.focus();
    fireEvent.change(margin, { target: { value: "-" } });
    fireEvent.change(margin, { target: { value: "-1" } });
    expect(margin).toHaveFocus();
    fireEvent.change(margin, { target: { value: "-12" } });
    expect(screen.getByLabelText("Margen gingival 26 vestibular")).toHaveFocus();
  });

  it("las flechas y Enter mueven el foco", async () => {
    await openExam();
    const first = screen.getByLabelText("Sondaje 18 distovestibular");
    first.focus();
    fireEvent.keyDown(first, { key: "Enter" });
    expect(screen.getByLabelText("Sondaje 18 vestibular")).toHaveFocus();
    fireEvent.keyDown(screen.getByLabelText("Sondaje 18 vestibular"), { key: "ArrowUp" });
    expect(screen.getByLabelText("Margen gingival 18 vestibular")).toHaveFocus();
    fireEvent.keyDown(screen.getByLabelText("Margen gingival 18 vestibular"), { key: "ArrowLeft" });
    expect(screen.getByLabelText("Margen gingival 18 distovestibular")).toHaveFocus();
  });

  it("marca los valores fuera de rango y no deja guardar", async () => {
    await openExam();
    const margin = screen.getByLabelText("Margen gingival 11 vestibular");
    fireEvent.change(margin, { target: { value: "9" } });
    expect(margin).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Pieza 11: El margen va de -15 a +5 mm.");
    expect(screen.getByRole("button", { name: "Guardar borrador" })).toBeDisabled();
  });

  it("sangrado, supuración y placa se marcan con un clic y se dibujan", async () => {
    await openExam();
    const bleeding = screen.getByRole("button", { name: "Sangrado 21 mesiovestibular" });
    fireEvent.click(bleeding);
    expect(bleeding).toHaveAttribute("aria-pressed", "true");
    fireEvent.change(screen.getByLabelText("Sondaje 21 mesiovestibular"), { target: { value: "3" } });
    const summary = screen.getByRole("region", { name: "Resumen del periodontograma" });
    expect(within(summary).getAllByText("100 %")).toHaveLength(1); // sangrado 100 %, placa 0 %
  });

  it("una pieza ausente se vacía, se deshabilita y sale del orden de captura", async () => {
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 17 vestibular"), { target: { value: "6" } });
    fireEvent.click(screen.getAllByRole("button", { name: /^Pieza 17: marcar como ausente/ })[0]);
    const absent = screen.getByLabelText("Sondaje 17 vestibular (pieza ausente)");
    expect(absent).toHaveValue("");
    expect(absent).toHaveAttribute("readonly");
    expect(absent).toHaveAttribute("tabindex", "-1");

    const last18 = screen.getByLabelText("Sondaje 18 mesiovestibular");
    last18.focus();
    fireEvent.keyDown(last18, { key: "Enter" });
    expect(screen.getByLabelText("Sondaje 16 distovestibular")).toHaveFocus();
  });

  it("la furcación solo aparece en las entradas que existen", async () => {
    await openExam();
    expect(screen.getByLabelText("Furcación vestibular 16")).toBeInTheDocument();
    expect(screen.getByLabelText("Furcación mesiopalatina 16")).toBeInTheDocument();
    expect(screen.getByLabelText("Furcación lingual 46")).toBeInTheDocument();
    expect(screen.queryByLabelText("Furcación vestibular 15")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Furcación mesiopalatina 46")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Furcación vestibular 46"), { target: { value: "3" } });
    expect(screen.getByTestId("furcation-b-46")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Implante 46"));
    expect(screen.queryByTestId("furcation-b-46")).not.toBeInTheDocument();
  });

  it("guarda el borrador con la revisión vigente y solo las piezas con datos", async () => {
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 16 distovestibular"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Movilidad 31"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));

    await waitFor(() => expect(service.updatePeriodontalExam).toHaveBeenCalledTimes(1));
    const [, examId, body] = vi.mocked(service.updatePeriodontalExam).mock.calls[0];
    expect(examId).toBe(7);
    expect(body.base_revision).toBe(3);
    expect(body.teeth.map((t) => t.tooth)).toEqual([16, 31]);
    expect(body.teeth[0].sites.db.probing_depth).toBe(4);
    expect(await screen.findByText("Todo guardado")).toBeInTheDocument();
  });

  it("guarda con la revisión con la que empezó a editar, no con la de la caché", async () => {
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));
    await screen.findByText("Todo guardado");
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));
    await waitFor(() => expect(service.updatePeriodontalExam).toHaveBeenCalledTimes(2));
    const bases = vi.mocked(service.updatePeriodontalExam).mock.calls.map(([, , body]) => body.base_revision);
    expect(bases).toEqual([3, 4]);
  });

  it("ante un 409 avisa y permite cargar la versión vigente", async () => {
    await openExam();
    vi.mocked(service.updatePeriodontalExam).mockRejectedValueOnce(new Conflict());
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));
    const alert = await screen.findByText(/otra persona guardó, finalizó o anuló/i);
    expect(alert).toBeInTheDocument();

    const fresh = makeExam({ revision: 4 });
    fresh.teeth = fresh.teeth.map((t) => t.tooth === 11
      ? { ...t, sites: { ...t.sites, b: { ...t.sites.b, probing_depth: 6, attachment_level: null } } }
      : t);
    current = fresh;
    fireEvent.click(screen.getByRole("button", { name: "Cargar la versión actual" }));
    await waitFor(() => expect(screen.getByLabelText("Sondaje 11 vestibular")).toHaveValue("6"));
    expect(screen.queryByText(/otra persona guardó/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar borrador" }));
    await waitFor(() => expect(service.updatePeriodontalExam).toHaveBeenCalledTimes(2));
    expect(vi.mocked(service.updatePeriodontalExam).mock.calls[1][2].base_revision).toBe(4);
  });

  it("las furcaciones palatinas siguen el orden de los sitios en cada cuadrante", async () => {
    await openExam();
    const order = (tooth: number) =>
      screen.getAllByLabelText(new RegExp(`^Furcación (mesio|disto)palatina ${tooth}$`)).map((el) => el.getAttribute("aria-label"));
    expect(order(16)).toEqual(["Furcación distopalatina 16", "Furcación mesiopalatina 16"]);
    expect(order(26)).toEqual(["Furcación mesiopalatina 26", "Furcación distopalatina 26"]);
  });

  it("la nota recibe el foco y lo devuelve al cerrarse", async () => {
    await openExam();
    const opener = screen.getByRole("button", { name: "Nota de la pieza 38" });
    opener.focus();
    fireEvent.click(opener);
    const note = screen.getByRole("textbox", { name: "Nota de la pieza 38" });
    expect(note).toHaveFocus();
    fireEvent.keyDown(note, { key: "Escape" });
    expect(opener).toHaveFocus();
  });

  it("pide confirmación antes de salir con cambios sin guardar", async () => {
    await openExam();
    fireEvent.change(screen.getByLabelText("Sondaje 11 vestibular"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /periodontogramas/i }));
    expect(await screen.findByText(/se pierden los cambios/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Seguir editando" }));
    expect(screen.getByLabelText("Sondaje 11 vestibular")).toHaveValue("3");
    fireEvent.click(screen.getByRole("button", { name: /periodontogramas/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Salir sin guardar" }));
    expect(await screen.findByRole("list", { name: "Periodontogramas del paciente" })).toBeInTheDocument();
  });

  it("un doctor que no lo registró lo ve en solo lectura; administración lo edita", async () => {
    current = makeExam({ created_by: { id: 99, name: "Dr. Otro" } });
    await openExam("doctor");
    expect(screen.getByLabelText("Sondaje 11 vestibular")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Guardar borrador" })).not.toBeInTheDocument();
  });

  it("administración edita el borrador de otro", async () => {
    current = makeExam({ created_by: { id: 99, name: "Dr. Otro" } });
    await openExam("admin");
    expect(screen.getByLabelText("Sondaje 11 vestibular")).not.toHaveAttribute("readonly");
  });

  it("un examen finalizado es de solo lectura", async () => {
    current = makeExam({ status: "final", finalized_at: "2026-11-06T16:00:00Z", finalized_by: { id: 1, name: "Dra. Ana" } });
    await openExam("admin");
    expect(screen.getByLabelText("Sondaje 11 vestibular")).toHaveAttribute("readonly");
    expect(screen.getByText(/Finalizado · revisión 3/)).toBeInTheDocument();
  });

  it("paciente archivado: sin crear", async () => {
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived />, "doctor");
    await screen.findByRole("list", { name: "Periodontogramas del paciente" });
    expect(screen.queryByRole("button", { name: /nuevo periodontograma/i })).not.toBeInTheDocument();
  });
});
