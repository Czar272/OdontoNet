import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import PatientForm from "./PatientForm";

vi.mock("../../services/doctorService", () => ({
  getDoctors: vi.fn(async () => [
    {
      id: 1,
      user_id: 11,
      specialization: null,
      license_number: null,
      phone: null,
      clinic_id: 1,
      user: { id: 11, name: "Dra. Activa", email: "a@x.com", role: "doctor", clinic_id: 1, is_active: true },
    },
  ]),
}));

vi.mock("../../services/patientService", () => ({ createPatient: vi.fn() }));

const { getDoctors } = await import("../../services/doctorService");

describe("PatientForm", () => {
  it("solo ofrece doctores activos para asignar", async () => {
    renderWithAuth(<PatientForm />, "receptionist");

    expect(await screen.findByRole("option", { name: "Dra. Activa" })).toBeInTheDocument();
    expect(getDoctors).toHaveBeenCalledWith({ active: true });
  });
});
