import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Clinic } from "../../types/clinic";
import ClinicPage from "./ClinicPage";
import { buildClinicChanges, initialClinicData, timezoneOptions } from "./clinicFormData";

const norte: Clinic = {
  id: 1, name: "Clínica Demo Norte", address: "Zona 1", phone: null, email: "norte@x.com",
  timezone: "America/Guatemala",
};

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

describe("timezoneOptions", () => {
  it("ofrece las zonas de América y conserva la actual aunque sea de otra región", () => {
    const options = timezoneOptions("Europe/Madrid");

    expect(options).toContain("America/Guatemala");
    expect(options).toContain("Europe/Madrid");
    expect(options).not.toContain("Asia/Tokyo");
    expect(options).toEqual([...options].sort());
  });
});

describe("ClinicPage", () => {
  it("administración ve los campos bloqueados hasta pulsar Editar datos", async () => {
    renderWithAuth(<ClinicPage />, "admin");

    const name = await screen.findByLabelText(/nombre de la clínica/i);
    expect(name).toHaveValue("Clínica Demo Norte");
    expect(name).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Guardar cambios" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /editar datos/i }));

    expect(name).toBeEnabled();
    expect(screen.queryByRole("button", { name: /editar datos/i })).not.toBeInTheDocument();
  });

  it("guarda solo los cambios y vuelve a bloquear", async () => {
    renderWithAuth(<ClinicPage />, "admin");
    await screen.findByLabelText(/nombre de la clínica/i);

    fireEvent.click(screen.getByRole("button", { name: /editar datos/i }));
    fireEvent.change(screen.getByLabelText(/teléfono/i), { target: { value: "2222-0000" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(updateClinic).toHaveBeenCalledWith({ phone: "2222-0000" }));
    await waitFor(() => expect(screen.getByLabelText(/teléfono/i)).toBeDisabled());
  });

  it("cambia la zona horaria de la clínica", async () => {
    renderWithAuth(<ClinicPage />, "admin");
    await screen.findByLabelText(/nombre de la clínica/i);

    fireEvent.click(screen.getByRole("button", { name: /editar datos/i }));
    fireEvent.change(screen.getByLabelText(/zona horaria/i), { target: { value: "America/Mexico_City" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(updateClinic).toHaveBeenCalledWith({ timezone: "America/Mexico_City" }));
  });

  it("Cancelar descarta los cambios y bloquea de nuevo", async () => {
    renderWithAuth(<ClinicPage />, "admin");
    await screen.findByLabelText(/nombre de la clínica/i);

    fireEvent.click(screen.getByRole("button", { name: /editar datos/i }));
    fireEvent.change(screen.getByLabelText(/nombre de la clínica/i), { target: { value: "Otro nombre" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(screen.getByLabelText(/nombre de la clínica/i)).toHaveValue("Clínica Demo Norte");
    expect(screen.getByLabelText(/nombre de la clínica/i)).toBeDisabled();
    expect(updateClinic).not.toHaveBeenCalled();
  });

  it.each(["doctor", "receptionist"] as const)("%s solo consulta", async (role) => {
    renderWithAuth(<ClinicPage />, role);

    const name = await screen.findByLabelText(/nombre de la clínica/i);
    expect(name).toBeDisabled();
    expect(screen.queryByRole("button", { name: /editar datos/i })).not.toBeInTheDocument();
    expect(screen.getByText("Solo administración puede modificar los datos de la clínica.")).toBeInTheDocument();
  });
});
