import { describe, expect, it } from "vitest";

import type { MedicalHistory } from "../../types/medicalHistory";
import {
  CONDITIONS,
  buildMedicalHistoryData,
  buildSaveMedicalHistory,
  initialMedicalHistoryForm,
  isUnchanged,
} from "./medicalHistoryForm";

const empty = { present: null, detail: null };

const history: MedicalHistory = {
  version: 2,
  created_at: "2026-11-02T20:00:00Z",
  created_by: { id: 1, name: "Dra. Ana" },
  conditions: {
    diabetes: { present: true, detail: "Tipo 2" },
    hypertension: { present: false, detail: null },
    heart_disease: empty,
    bleeding_disorder: empty,
    respiratory_disease: empty,
    liver_kidney_disease: empty,
    immunosuppression: empty,
    pregnancy_lactation: empty,
  },
  other_conditions: null,
  allergies: "Penicilina",
  current_medications: null,
  smoking_status: "current",
  cigarettes_per_day: 10,
  alcohol: null,
  alcohol_detail: null,
  bruxism: true,
  chief_complaint: null,
  last_dental_visit: null,
  previous_treatments: null,
  brushing_per_day: 2,
  uses_floss: false,
  gum_bleeding: null,
  notes: null,
};

describe("medicalHistoryForm", () => {
  it("sin historia, todo empieza sin dato", () => {
    const form = initialMedicalHistoryForm(null);

    expect(Object.keys(form.conditions)).toEqual(CONDITIONS.map((c) => c.key));
    expect(form.conditions.diabetes).toEqual({ present: "", detail: "" });
    expect(buildSaveMedicalHistory(form, null).base_version).toBeNull();
    expect(buildMedicalHistoryData(form).allergies).toBeNull();
  });

  it("ida y vuelta conserva los datos de la versión", () => {
    const form = initialMedicalHistoryForm(history);

    expect(form.conditions.diabetes).toEqual({ present: "yes", detail: "Tipo 2" });
    expect(form.conditions.hypertension.present).toBe("no");
    expect(form.cigarettes_per_day).toBe("10");
    expect(form.uses_floss).toBe("no");

    const data = buildMedicalHistoryData(form);
    expect({ ...history, ...data }).toEqual(history);
    expect(Object.keys(data)).not.toContain("version");
  });

  it("envía la versión vigente como base", () => {
    expect(buildSaveMedicalHistory(initialMedicalHistoryForm(history), history).base_version).toBe(2);
  });

  it("los textos en blanco se envían como sin dato", () => {
    const form = { ...initialMedicalHistoryForm(history), allergies: "   ", notes: "" };

    const data = buildMedicalHistoryData(form);
    expect(data.allergies).toBeNull();
    expect(data.notes).toBeNull();
  });

  it("los cigarrillos solo se envían si fuma actualmente", () => {
    const form = { ...initialMedicalHistoryForm(history), smoking_status: "former" as const };

    expect(buildMedicalHistoryData(form).cigarettes_per_day).toBeNull();
  });

  it("detecta si no hubo cambios", () => {
    const form = initialMedicalHistoryForm(history);

    expect(isUnchanged(form, history)).toBe(true);
    expect(isUnchanged({ ...form, allergies: "Látex" }, history)).toBe(false);
    expect(isUnchanged({ ...form, allergies: " Penicilina " }, history)).toBe(true);
  });
});
