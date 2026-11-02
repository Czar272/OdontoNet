import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Appointment } from "../../types/appointment";
import { toLocalIso } from "../../pages/Agenda/appointmentFormData";
import AppointmentStatusPanel from "./AppointmentStatusPanel";

const future = new Date();
future.setDate(future.getDate() + 2);
future.setHours(9, 0, 0, 0);

const scheduled = {
  id: 7, status: "scheduled",
  starts_at: toLocalIso(future), ends_at: toLocalIso(new Date(future.getTime() + 30 * 60000)),
} as Appointment;

vi.mock("../../services/appointmentService", () => ({
  getAppointmentHistory: vi.fn(async () => [
    { id: 1, from_status: null, to_status: "scheduled", note: null, changed_at: "2026-11-02T10:00:00-06:00", changed_by: { id: 1, name: "Recepción" } },
    { id: 2, from_status: "scheduled", to_status: "confirmed", note: "Confirmó por teléfono", changed_at: "2026-11-02T11:00:00-06:00", changed_by: { id: 2, name: "Dra. Ana" } },
  ]),
  changeAppointmentStatus: vi.fn(async (_id: number, status: string) => ({ ...scheduled, status })),
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { changeAppointmentStatus } = await import("../../services/appointmentService");

beforeEach(() => vi.clearAllMocks());

describe("AppointmentStatusPanel", () => {
  it("muestra solo las acciones posibles y el historial", async () => {
    renderWithAuth(<AppointmentStatusPanel appointment={scheduled} canManage onChanged={() => {}} />, "receptionist");

    expect(screen.getByRole("button", { name: "Confirmar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar cita" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Marcar atendida" })).not.toBeInTheDocument();
    expect(await screen.findByText("Creada como programada")).toBeInTheDocument();
    expect(screen.getByText(/Programada → Confirmada/)).toHaveTextContent("Confirmó por teléfono");
  });

  it("pide una nota opcional antes de cambiar el estado", async () => {
    const onChanged = vi.fn();
    renderWithAuth(<AppointmentStatusPanel appointment={scheduled} canManage onChanged={onChanged} />, "receptionist");

    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    fireEvent.change(screen.getByLabelText("Nota para «Confirmar» (opcional)"), { target: { value: "Llamada 10:05" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(changeAppointmentStatus).toHaveBeenCalledWith(7, "confirmed", "Llamada 10:05"));
    expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ status: "confirmed" }));
  });

  it("Volver descarta la acción", () => {
    renderWithAuth(<AppointmentStatusPanel appointment={scheduled} canManage onChanged={() => {}} />, "admin");

    fireEvent.click(screen.getByRole("button", { name: "Cancelar cita" }));
    fireEvent.click(screen.getByRole("button", { name: "Volver" }));

    expect(changeAppointmentStatus).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirmar" })).toBeInTheDocument();
  });

  it("sin permiso solo muestra el historial", async () => {
    renderWithAuth(<AppointmentStatusPanel appointment={scheduled} canManage={false} onChanged={() => {}} />, "receptionist");

    expect(await screen.findByText("Creada como programada")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
