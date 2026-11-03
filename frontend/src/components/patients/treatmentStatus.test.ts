import { describe, expect, it } from "vitest";

import type { Treatment, TreatmentStatus } from "../../types/treatment";
import {
  TREATMENT_TRANSITIONS,
  buildTreatmentChanges,
  buildTreatmentDTO,
  initialTreatmentForm,
  isClosed,
  isValidTooth,
  validateTreatmentForm,
} from "./treatmentStatus";

const treatment: Treatment = {
  id: 4,
  patient_id: 5,
  procedure: "Raspado",
  tooth: 36,
  notes: null,
  planned_date: "2026-12-15",
  status: "proposed",
  status_reason: null,
  status_changed_at: "2026-11-03T10:00:00Z",
  proposed_visit: { id: 9, visit_at: "2026-11-02T16:00:00Z", reason: "Evaluación", voided: false },
  completed_visit: null,
  created_by: { id: 1, name: "Dra. Ana" },
  created_at: "2026-11-03T10:00:00Z",
  updated_by: { id: 1, name: "Dra. Ana" },
  updated_at: "2026-11-03T10:00:00Z",
};

describe("treatmentStatus", () => {
  // Debe coincidir con TREATMENT_TRANSITIONS del backend.
  it.each<[TreatmentStatus, TreatmentStatus[]]>([
    ["proposed", ["accepted", "cancelled"]],
    ["accepted", ["in_progress", "completed", "cancelled"]],
    ["in_progress", ["completed", "cancelled"]],
    ["completed", []],
    ["cancelled", []],
  ])("%s → %j", (from, to) => {
    expect(TREATMENT_TRANSITIONS[from]).toEqual(to);
    expect(isClosed(from)).toBe(to.length === 0);
  });

  it.each([11, 18, 21, 48, 51, 55, 85])("pieza %i es válida", (tooth) => {
    expect(isValidTooth(tooth)).toBe(true);
  });

  it.each([0, 10, 19, 49, 56, 90, 36.5])("pieza %s es inválida", (tooth) => {
    expect(isValidTooth(tooth)).toBe(false);
  });

  it("valida procedimiento y pieza", () => {
    const form = initialTreatmentForm(null);

    expect(validateTreatmentForm(form)).toBe("Indica el procedimiento.");
    expect(validateTreatmentForm({ ...form, procedure: "Raspado", tooth: "19" })).toMatch(/FDI/);
    expect(validateTreatmentForm({ ...form, procedure: "Raspado", tooth: "" })).toBeNull();
  });

  it("arma el alta con vacíos como null", () => {
    const dto = buildTreatmentDTO({ procedure: " Raspado ", tooth: "", planned_date: "", proposed_visit_id: "", notes: "  " });

    expect(dto).toEqual({ procedure: "Raspado", tooth: null, planned_date: null, proposed_visit_id: null, notes: null });
  });

  it("al editar envía solo lo que cambió", () => {
    const form = initialTreatmentForm(treatment);

    expect(buildTreatmentChanges(treatment, form)).toEqual({});
    expect(buildTreatmentChanges(treatment, { ...form, tooth: "46", proposed_visit_id: "" })).toEqual({
      tooth: 46,
      proposed_visit_id: null,
    });
  });
});
