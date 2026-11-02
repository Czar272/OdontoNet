import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Appointment } from "../../types/appointment";
import { toLocalIso } from "./appointmentFormData";
import ConfirmationsList from "./ConfirmationsList";

const start = new Date();
start.setDate(start.getDate() + 1);
start.setHours(10, 0, 0, 0);

function appointment(id: number, first: string, phone: string | null): Appointment {
  return {
    id, clinic_id: 1, patient_id: id, doctor_id: 1,
    starts_at: toLocalIso(start), ends_at: toLocalIso(new Date(start.getTime() + 30 * 60000)),
    duration_minutes: 30, status: "scheduled", reason: "Limpieza", created_by_user_id: 1, created_at: "", updated_at: "",
    patient: { id, first_name: first, last_name: "Ruiz", phone, archived_at: null },
    doctor: {
      id: 1, user_id: 9, specialization: null, license_number: null, phone: null, clinic_id: 1,
      user: { id: 9, name: "Dra. Ana", email: "a@x.com", role: "doctor", clinic_id: 1, is_active: true },
    },
  };
}

const state = vi.hoisted(() => ({ items: [] as unknown[] }));

vi.mock("../../services/appointmentService", () => ({
  getAppointments: vi.fn(async () => state.items),
  changeAppointmentStatus: vi.fn(async (id: number, status: string) => ({ ...(state.items[0] as object), id, status })),
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { getAppointments, changeAppointmentStatus } = await import("../../services/appointmentService");

beforeEach(() => {
  vi.clearAllMocks();
  state.items = [appointment(1, "Lucía", "5555-0101"), appointment(2, "Mario", null)];
});

describe("ConfirmationsList", () => {
  it("lista las programadas de los próximos 7 días con teléfono para llamar", async () => {
    renderWithAuth(<ConfirmationsList canManage />, "receptionist");

    expect(await screen.findByText("Lucía Ruiz")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /5555-0101/ })).toHaveAttribute("href", "tel:5555-0101");
    expect(screen.getByText("Sin teléfono")).toBeInTheDocument();
    expect(getAppointments).toHaveBeenCalledWith(expect.objectContaining({ statuses: ["scheduled"] }));
  });

  it("confirma con un clic", async () => {
    renderWithAuth(<ConfirmationsList canManage />, "receptionist");

    fireEvent.click(await screen.findByRole("button", { name: "Confirmar cita de Lucía Ruiz" }));

    await waitFor(() =>
      expect(changeAppointmentStatus).toHaveBeenCalledWith(1, "confirmed", "Confirmada desde la lista de por confirmar"),
    );
  });

  it("cancela con motivo opcional y permite volver sin cancelar", async () => {
    renderWithAuth(<ConfirmationsList canManage />, "receptionist");

    fireEvent.click(await screen.findByRole("button", { name: "Cancelar cita de Mario Ruiz" }));
    const dialog = screen.getByRole("dialog", { name: "Cancelar cita" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Volver" }));
    expect(changeAppointmentStatus).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Cancelar cita de Mario Ruiz" }));
    fireEvent.change(screen.getByLabelText("Motivo de la cancelación (opcional)"), { target: { value: "De viaje" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancelar cita" }));

    await waitFor(() => expect(changeAppointmentStatus).toHaveBeenCalledWith(2, "cancelled", "De viaje"));
  });

  it("cambiar el periodo vuelve a consultar", async () => {
    renderWithAuth(<ConfirmationsList canManage />, "admin");
    await screen.findByText("Lucía Ruiz");

    fireEvent.change(screen.getByLabelText("Periodo"), { target: { value: "1" } });

    await waitFor(() => expect(getAppointments).toHaveBeenCalledTimes(2));
  });

  it("estado vacío", async () => {
    state.items = [];
    renderWithAuth(<ConfirmationsList canManage />, "receptionist");

    expect(await screen.findByText("No hay citas pendientes de confirmar en este periodo.")).toBeInTheDocument();
  });

  it("sin permiso de gestión no muestra acciones", async () => {
    renderWithAuth(<ConfirmationsList canManage={false} />, "receptionist");
    await screen.findByText("Lucía Ruiz");

    expect(screen.queryByRole("button", { name: /Confirmar cita/ })).not.toBeInTheDocument();
  });
});
