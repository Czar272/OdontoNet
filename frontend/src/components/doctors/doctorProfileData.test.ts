import { describe, expect, it } from "vitest";

import type { Doctor } from "../../types/doctor";
import { buildProfileChanges, initialProfileData } from "./doctorProfileData";

const ana: Doctor = {
  id: 1,
  user_id: 11,
  specialization: "Periodoncia",
  license_number: null,
  phone: "5555-0001",
  clinic_id: 1,
  user: { id: 11, name: "Dra. Ana", email: "ana@x.com", role: "doctor", clinic_id: 1, is_active: true },
};

describe("doctorProfileData", () => {
  it("convierte null en cadenas vacías para el formulario", () => {
    expect(initialProfileData(ana)).toEqual({ specialization: "Periodoncia", license_number: "", phone: "5555-0001" });
  });

  it("sin cambios no envía nada", () => {
    expect(buildProfileChanges(ana, initialProfileData(ana))).toEqual({});
  });

  it('envía solo lo modificado y "" para borrar', () => {
    const data = { specialization: " Endodoncia ", license_number: "COL-7", phone: "" };

    expect(buildProfileChanges(ana, data)).toEqual({ specialization: "Endodoncia", license_number: "COL-7", phone: "" });
  });
});
