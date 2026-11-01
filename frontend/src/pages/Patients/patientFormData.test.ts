import { describe, expect, it } from "vitest";

import type { Patient } from "../../types/patient";
import { ageFrom, buildPatientChanges, initialPatientData } from "./patientFormData";

const eva: Patient = {
  id: 1,
  first_name: "Eva",
  last_name: "Luna",
  birth_date: "1990-06-15",
  phone: "5555-0000",
  email: null,
  address: null,
  doctor_id: 3,
  doctor: null,
  clinic_id: 1,
};

describe("buildPatientChanges", () => {
  it("sin cambios no envía nada", () => {
    expect(buildPatientChanges(eva, initialPatientData(eva))).toEqual({});
  });

  it("envía solo lo modificado; texto vacío borra y sin doctor es null", () => {
    const data = { ...initialPatientData(eva), first_name: " Eva María ", phone: "", doctor_id: "" };

    expect(buildPatientChanges(eva, data)).toEqual({ first_name: "Eva María", phone: "", doctor_id: null });
  });

  it("reasigna doctor como número", () => {
    expect(buildPatientChanges(eva, { ...initialPatientData(eva), doctor_id: "7" })).toEqual({ doctor_id: 7 });
  });
});

describe("ageFrom", () => {
  const today = new Date(2026, 10, 1); // 1 de noviembre de 2026

  it("cuenta años cumplidos", () => {
    expect(ageFrom("1990-06-15", today)).toBe(36);
    expect(ageFrom("1990-11-02", today)).toBe(35);
    expect(ageFrom("1990-11-01", today)).toBe(36);
  });

  it("sin fecha devuelve null", () => {
    expect(ageFrom(null, today)).toBeNull();
  });
});
