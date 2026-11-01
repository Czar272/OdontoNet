import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Clinic } from "../../types/clinic";
import ClinicPage from "./ClinicPage";
import { buildClinicChanges, initialClinicData } from "./clinicFormData";

const norte: Clinic = { id: 1, name: "Clínica Demo Norte", address: "Zona 1", phone: null, email: "norte@x.com" };

vi.mock("../../services/clinicService", () => ({
  getClinic: vi.fn(async () => norte),
  updateClinic: vi.fn(async (changes) => ({ ...norte, ...changes })),
}));

vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { updateClinic } = await import("../../services/clinicService");

beforeEach(() => vi.clearAllMocks());

describe("buildClinicChanges", () => {
  it("envía solo lo modificado y \"\" para borrar", () => {
    const data = { ...initialClinicData(norte), name: " Clínica Norte ", address: "" };

    expect(buildClinicChanges(norte, data)).toEqual({ name: "Clínica Norte", address: "" });
  });

  it("sin cambios no envía nada", () => {
    expect(buildClinicChanges(norte, initialClinicData(norte))).toEqual({});
  });
});

describe("ClinicPage", () => {
  it("administración edita y guarda solo los cambios", async () => {
    renderWithAuth(<ClinicPage />, "admin");

    const name = await screen.findByLabelText(/nombre de la clínica/i);
    expect(name).toHaveValue("Clínica Demo Norte");
    fireEvent.change(screen.getByLabelText(/teléfono/i), { target: { value: "2222-0000" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(updateClinic).toHaveBeenCalledWith({ phone: "2222-0000" }));
  });

  it.each(["doctor", "receptionist"] as const)("%s solo consulta", async (role) => {
    renderWithAuth(<ClinicPage />, role);

    const name = await screen.findByLabelText(/nombre de la clínica/i);
    expect(name).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Guardar cambios" })).not.toBeInTheDocument();
    expect(screen.getByText("Solo administración puede modificar los datos de la clínica.")).toBeInTheDocument();
  });
});
