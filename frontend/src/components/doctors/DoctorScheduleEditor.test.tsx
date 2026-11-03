import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { DoctorAvailability } from "../../types/availability";
import type { Doctor } from "../../types/doctor";
import DoctorScheduleEditor from "./DoctorScheduleEditor";

const ana: Doctor = {
  id: 1, user_id: 101, specialization: null, license_number: null, phone: null, clinic_id: 1,
  user: { id: 101, name: "Dra. Ana", email: "a@x.com", role: "doctor", clinic_id: 1, is_active: true },
};

const availability: DoctorAvailability = {
  doctor_id: 1,
  timezone: "America/Guatemala",
  blocks: [
    { weekday: 0, start_time: "08:00:00", end_time: "12:00:00" },
    { weekday: 0, start_time: "14:00:00", end_time: "18:00:00" },
  ],
};

vi.mock("../../services/doctorService", () => ({
  updateDoctorAvailability: vi.fn(async () => availability),
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { updateDoctorAvailability } = await import("../../services/doctorService");

beforeEach(() => vi.clearAllMocks());

describe("DoctorScheduleEditor", () => {
  it("copia el lunes a martes–viernes y guarda la semana", async () => {
    const onClose = vi.fn();
    renderWithAuth(
      <DoctorScheduleEditor doctor={ana} availability={availability} canEdit onClose={onClose} />,
      "receptionist",
    );

    expect(screen.getByLabelText("Lunes, bloque 2, desde")).toHaveValue("14:00");
    fireEvent.click(screen.getByRole("button", { name: /Copiar lunes/ }));
    fireEvent.click(screen.getByRole("button", { name: "Guardar horario" }));

    await waitFor(() => expect(updateDoctorAvailability).toHaveBeenCalled());
    const blocks = vi.mocked(updateDoctorAvailability).mock.calls[0][1];
    expect(blocks).toHaveLength(10);
    expect(blocks).toContainEqual({ weekday: 4, start_time: "14:00", end_time: "18:00" });
    expect(blocks.some((b) => b.weekday >= 5)).toBe(false);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("valida en el navegador que la hora de fin sea posterior", async () => {
    renderWithAuth(
      <DoctorScheduleEditor doctor={ana} availability={availability} canEdit onClose={() => {}} />,
      "admin",
    );

    fireEvent.change(screen.getByLabelText("Lunes, bloque 1, hasta"), { target: { value: "07:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar horario" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("posterior");
    expect(updateDoctorAvailability).not.toHaveBeenCalled();
  });

  it("agrega y quita bloques; vaciar la semana se puede guardar", async () => {
    renderWithAuth(
      <DoctorScheduleEditor doctor={ana} availability={availability} canEdit onClose={() => {}} />,
      "admin",
    );

    fireEvent.click(screen.getByRole("button", { name: "Agregar bloque al sábado" }));
    expect(screen.getByLabelText("Sábado, bloque 1, desde")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Quitar bloque 1 del sábado" }));
    fireEvent.click(screen.getByRole("button", { name: "Quitar bloque 2 del lunes" }));
    fireEvent.click(screen.getByRole("button", { name: "Quitar bloque 1 del lunes" }));
    expect(screen.getByText(/Sin horario registrado/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Guardar horario" }));
    await waitFor(() => expect(updateDoctorAvailability).toHaveBeenCalledWith(1, []));
  });

  it("muestra el error del backend", async () => {
    vi.mocked(updateDoctorAvailability).mockRejectedValueOnce(
      new AxiosError("403", "ERR", undefined, undefined, {
        status: 403, statusText: "Forbidden", headers: {}, config: { headers: new AxiosHeaders() },
        data: { detail: "Solo puedes editar tu propio horario." },
      }),
    );
    renderWithAuth(
      <DoctorScheduleEditor doctor={ana} availability={availability} canEdit onClose={() => {}} />,
      "doctor",
    );

    fireEvent.click(screen.getByRole("button", { name: "Guardar horario" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Solo puedes editar tu propio horario.");
  });

  it("en solo lectura describe el horario sin controles", () => {
    renderWithAuth(
      <DoctorScheduleEditor doctor={ana} availability={availability} canEdit={false} onClose={() => {}} />,
      "doctor",
    );

    expect(screen.getByText("08:00–12:00 y 14:00–18:00")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Guardar horario" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Lunes, bloque 1, desde")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cerrar" })).toBeInTheDocument();
  });
});
