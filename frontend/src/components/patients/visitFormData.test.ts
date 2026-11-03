import { describe, expect, it } from "vitest";

import { fakeUser } from "../../test/renderWithAuth";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import type { Doctor } from "../../types/doctor";
import {
  buildVisitContent,
  canModifyVisit,
  defaultDoctorId,
  fromLocalInput,
  initialVisitForm,
  isVisitUnchanged,
  toLocalInput,
} from "./visitFormData";

const visit: ClinicalVisit = {
  id: 9,
  patient_id: 5,
  revision: 1,
  visit_at: "2026-11-02T16:30:00.000Z",
  doctor: { id: 3, name: "Dra. Ana" },
  reason: "Control",
  findings: "Encía inflamada",
  diagnosis: null,
  procedures: null,
  instructions: null,
  next_visit_date: "2026-12-01",
  created_by: { id: 7, name: "Dra. Ana" },
  created_at: "2026-11-02T16:31:00Z",
  updated_by: { id: 7, name: "Dra. Ana" },
  updated_at: "2026-11-02T16:31:00Z",
  voided_at: null,
  voided_by: null,
  void_reason: null,
};

function doctor(id: number, userId: number): Doctor {
  return {
    id, user_id: userId, specialization: null, license_number: null, phone: null, clinic_id: 1,
    user: { id: userId, name: `U${userId}`, email: `u${userId}@x.com`, role: "doctor", clinic_id: 1, is_active: true },
  };
}

describe("visitFormData", () => {
  it("convierte entre datetime-local y UTC sin perder la hora", () => {
    const local = toLocalInput(visit.visit_at);

    expect(fromLocalInput(local)).toBe(visit.visit_at);
  });

  it("propone el perfil de doctor del usuario actual", () => {
    expect(defaultDoctorId({ ...fakeUser("doctor"), id: 11 }, [doctor(2, 10), doctor(4, 11)])).toBe("4");
    expect(defaultDoctorId(fakeUser("admin"), [doctor(2, 10)])).toBe("");
  });

  it("arma el contenido con textos vacíos como null", () => {
    const form = { ...initialVisitForm(visit, ""), diagnosis: "  ", reason: " Control " };

    const data = buildVisitContent(form);

    expect(data).toMatchObject({ doctor_id: 3, reason: "Control", diagnosis: null, findings: "Encía inflamada", next_visit_date: "2026-12-01" });
  });

  it("una consulta nueva empieza con la hora actual y el doctor propuesto", () => {
    const now = new Date(2026, 10, 2, 9, 15);

    const form = initialVisitForm(null, "4", now);

    expect(form.visit_at).toBe("2026-11-02T09:15");
    expect(form.doctor_id).toBe("4");
    expect(form.reason).toBe("");
  });

  it("solo el autor o administración modifican, y nunca una anulada", () => {
    expect(canModifyVisit(visit, { ...fakeUser("doctor"), id: 7 })).toBe(true);
    expect(canModifyVisit(visit, { ...fakeUser("doctor"), id: 8 })).toBe(false);
    expect(canModifyVisit(visit, fakeUser("admin"))).toBe(true);
    expect(canModifyVisit({ ...visit, voided_at: "2026-11-03T00:00:00Z" }, fakeUser("admin"))).toBe(false);
    expect(canModifyVisit(visit, null)).toBe(false);
  });

  it("detecta si no hubo cambios", () => {
    const form = initialVisitForm(visit, "");

    expect(isVisitUnchanged(form, visit)).toBe(true);
    expect(isVisitUnchanged({ ...form, diagnosis: "Gingivitis" }, visit)).toBe(false);
  });
});
