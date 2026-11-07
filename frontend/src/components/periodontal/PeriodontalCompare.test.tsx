import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { PeriodontalExam, ToothResponse } from "../../types/periodontal";
import PeriodontalCard from "./PeriodontalCard";
import { compareExams } from "./compareExams";
import { PERMANENT_TEETH, SITES } from "./periodontalChart";

const emptyTooth = (tooth: number): ToothResponse => ({
  tooth, missing: false, implant: false, mobility: null,
  furcation: { b: null, mp: null, dp: null, l: null }, note: null,
  sites: Object.fromEntries(SITES.map((site) => [site, {
    probing_depth: null, gingival_margin: null, attachment_level: null,
    bleeding: false, suppuration: false, plaque: false,
  }])) as ToothResponse["sites"],
});

type SiteValues = { pd: number; gm: number; bop?: boolean };

function exam(id: number, date: string, values: Record<string, SiteValues>, extra: Partial<PeriodontalExam> = {}): PeriodontalExam {
  const teeth = PERMANENT_TEETH.map(emptyTooth).map((tooth) => {
    const sites = { ...tooth.sites };
    for (const site of SITES) {
      const value = values[`${tooth.tooth}${site}`];
      if (value) {
        sites[site] = {
          probing_depth: value.pd, gingival_margin: value.gm, attachment_level: value.pd - value.gm,
          bleeding: value.bop ?? false, suppuration: false, plaque: false,
        };
      }
    }
    return { ...tooth, sites };
  });
  return {
    id, patient_id: 5, exam_date: date, clinical_visit: null, notes: null, status: "final", revision: 2,
    created_by: { id: 1, name: "Dra. Ana" }, created_at: `${date}T15:00:00Z`, updated_at: `${date}T15:00:00Z`,
    finalized_by: { id: 1, name: "Dra. Ana" }, finalized_at: `${date}T16:00:00Z`,
    voided_by: null, voided_at: null, void_reason: null,
    summary: { present_teeth: 32, measured_sites: 2, mean_probing_depth: 3, mean_attachment_level: 3,
      bleeding_pct: 50, plaque_pct: 0, deep_sites_pct: 50 },
    teeth, ...extra,
  };
}

const older = exam(1, "2026-05-01", { "16mb": { pd: 3, gm: 0 }, "16b": { pd: 2, gm: 0, bop: true }, "36db": { pd: 4, gm: -1 } });
const newer = exam(2, "2026-11-01", { "16mb": { pd: 6, gm: -1, bop: true }, "16b": { pd: 2, gm: 0 }, "36db": { pd: 3, gm: -1 } },
  { summary: { present_teeth: 31, measured_sites: 3, mean_probing_depth: 3.67, mean_attachment_level: 4,
    bleeding_pct: 33.3, plaque_pct: 0, deep_sites_pct: 33.3 } });
newer.teeth = newer.teeth.map((t) => (t.tooth === 48 ? { ...t, missing: true } : t));

describe("compareExams", () => {
  it("lista los sitios con cambios y resalta los de 2 mm o más", () => {
    const result = compareExams(older, newer);
    expect(result.changes.map((c) => `${c.tooth}${c.site}`)).toEqual(["16mb", "16b", "36db"]);
    const mb = result.changes[0];
    expect(mb.probingDelta).toBe(3);
    expect(mb.attachmentDelta).toBe(4); // NIC 3 → 7
    expect(mb.significant).toBe(true);
    expect(result.changes[1].probingDelta).toBe(0); // solo cambió el sangrado
    expect(result.changes[2].significant).toBe(false); // −1 mm
    expect([...result.highlighted]).toEqual([16]);
  });

  it("informa los cambios de estado de las piezas y las diferencias del resumen", () => {
    const result = compareExams(older, newer);
    expect(result.toothChanges).toEqual([{ tooth: 48, change: "lost" }]);
    expect(result.summaryDelta.mean_probing_depth).toBe(0.67);
    expect(result.summaryDelta.bleeding_pct).toBe(-16.7);
  });

  it("ordena por fecha aunque se pasen al revés", () => {
    const result = compareExams(newer, older);
    expect(result.changes[0].probingDelta).toBe(3);
    expect(result.toothChanges).toEqual([{ tooth: 48, change: "lost" }]);
  });

  it("una pieza que pasa a implante no compara sus sitios", () => {
    const implanted = { ...newer, teeth: newer.teeth.map((t) => (t.tooth === 16 ? { ...t, implant: true } : t)) };
    const result = compareExams(older, implanted);
    expect(result.toothChanges).toContainEqual({ tooth: 16, change: "implant" });
    expect(result.changes.some((c) => c.tooth === 16)).toBe(false);
  });

  it("dos exámenes iguales no tienen cambios", () => {
    const result = compareExams(older, older);
    expect(result.changes).toEqual([]);
    expect(result.highlighted.size).toBe(0);
  });
});

let list = [newer, older];

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});
vi.mock("../../services/periodontalService", () => ({
  getPeriodontalExams: vi.fn(async () => list),
  getPeriodontalExam: vi.fn(async (_p: number, id: number) => (id === 1 ? older : newer)),
}));

beforeEach(() => {
  list = [newer, older];
});

describe("vista de comparación", () => {
  it("compara los dos exámenes más recientes y resalta los cambios", async () => {
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    fireEvent.click(await screen.findByRole("button", { name: "Comparar" }));

    const table = await screen.findByRole("region", { name: "Sitios con cambios" });
    expect(within(table).getByRole("heading")).toHaveTextContent("Sitios con cambios (3; 1 de 2 mm o más)");
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("16mesiovestibular3 → 6 (+3)");
    // El cambio de 2 mm o más se indica con texto, no solo con color.
    expect(within(rows[1]).getAllByRole("cell").at(-1)).toHaveTextContent("Sí");
    expect(within(rows[3]).getAllByRole("cell").at(-1)).toHaveTextContent("");
    expect(screen.getByText("Pieza 48: ausente en el examen reciente")).toBeInTheDocument();
    expect(screen.getByText(/no constituye diagnóstico/i)).toBeInTheDocument();
    expect(screen.getByText(/Piezas con cambios de 2 mm o más \(resaltadas\): 16\./)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /cara vestibular de la arcada superior; piezas resaltadas: 16/ })).toBeInTheDocument();
  });

  it("aunque se elijan al revés, compara del más antiguo al más reciente", async () => {
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    fireEvent.click(await screen.findByRole("button", { name: "Comparar" }));
    fireEvent.change(await screen.findByLabelText("Primer examen"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Segundo examen"), { target: { value: "1" } });
    const table = await screen.findByRole("region", { name: "Sitios con cambios" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("3 → 6 (+3)");
  });

  it("solo compara exámenes finalizados", async () => {
    list = [newer, { ...older, status: "draft", finalized_at: null, finalized_by: null }];
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByRole("list", { name: "Periodontogramas del paciente" });
    expect(screen.queryByRole("button", { name: "Comparar" })).not.toBeInTheDocument();
  });

  it("no ofrece comparar con menos de dos exámenes vigentes", async () => {
    list = [newer, { ...older, voided_at: "2026-11-02T10:00:00Z", voided_by: { id: 1, name: "Dra. Ana" }, void_reason: "x" }];
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    await screen.findByRole("list", { name: "Periodontogramas del paciente" });
    expect(screen.queryByRole("button", { name: "Comparar" })).not.toBeInTheDocument();
  });

  it("al elegir el mismo examen pide dos distintos", async () => {
    renderWithAuth(<PeriodontalCard patientId={5} canCreate isArchived={false} />, "doctor");
    fireEvent.click(await screen.findByRole("button", { name: "Comparar" }));
    fireEvent.change(await screen.findByLabelText("Primer examen"), { target: { value: "2" } });
    await waitFor(() => expect(screen.getByText("Elige dos exámenes distintos.")).toBeInTheDocument());
  });
});
