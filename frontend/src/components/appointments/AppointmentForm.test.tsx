import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Appointment } from "../../types/appointment";
import type { Doctor } from "../../types/doctor";
import { newAppointmentData, toLocalIso } from "../../pages/Agenda/appointmentFormData";
import AppointmentForm from "./AppointmentForm";

function doctor(id: number, name: string, isActive = true): Doctor {
  return {
    id, user_id: id + 100, specialization: null, license_number: null, phone: null, clinic_id: 1,
    user: { id: id + 100, name, email: `d${id}@x.com`, role: "doctor", clinic_id: 1, is_active: isActive },
  };
}

const ana = doctor(1, "Dra. Ana Morales");
const retired = doctor(3, "Dr. Retirado", false);
const nine = new Date(2026, 10, 10, 9, 0);

const existing: Appointment = {
  id: 7, clinic_id: 1, patient_id: 5, doctor_id: 3,
  starts_at: toLocalIso(nine), ends_at: toLocalIso(new Date(2026, 10, 10, 9, 30)),
  duration_minutes: 30, status: "scheduled", reason: null,
  created_by_user_id: 1, created_at: "", updated_at: "",
  patient: { id: 5, first_name: "Eva", last_name: "Luna", phone: null, archived_at: null },
  doctor: retired,
};

vi.mock("../../services/patientService", () => ({
  getPatients: vi.fn(async () => ({
    items: [{ id: 5, first_name: "Eva", last_name: "Luna", phone: "5555-0000", email: null, clinic_id: 1 }],
    total: 1, page: 1, page_size: 8,
  })),
}));
vi.mock("../../services/doctorService", () => ({ getDoctors: vi.fn(async () => [ana]) }));
vi.mock("../../services/appointmentService", () => ({
  createAppointment: vi.fn(async () => existing),
  updateAppointment: vi.fn(async () => existing),
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { createAppointment, updateAppointment } = await import("../../services/appointmentService");
const { getPatients } = await import("../../services/patientService");

beforeEach(() => vi.clearAllMocks());

describe("AppointmentForm", () => {
  it("agenda buscando al paciente en el backend", async () => {
    const onSaved = vi.fn();
    renderWithAuth(
      <AppointmentForm initialData={newAppointmentData(nine, 45)} onSaved={onSaved} onCancel={() => {}} />,
      "receptionist",
    );

    fireEvent.change(screen.getByLabelText("Paciente *"), { target: { value: "luna" } });
    fireEvent.click(await screen.findByRole("button", { name: /Eva Luna/ }));
    expect(getPatients).toHaveBeenCalledWith({ search: "luna", pageSize: 8 });

    fireEvent.change(await screen.findByLabelText("Doctor *"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: " Limpieza " } });
    fireEvent.click(screen.getByRole("button", { name: "Agendar cita" }));

    await waitFor(() =>
      expect(createAppointment).toHaveBeenCalledWith({
        patient_id: 5, doctor_id: 1, starts_at: toLocalIso(nine), duration_minutes: 45, reason: "Limpieza",
      }),
    );
    expect(onSaved).toHaveBeenCalledWith(existing);
  });

  it("pide un paciente antes de enviar", async () => {
    renderWithAuth(
      <AppointmentForm initialData={newAppointmentData(nine, 30, 1)} onSaved={() => {}} onCancel={() => {}} />,
      "admin",
    );
    await screen.findByRole("option", { name: "Dra. Ana Morales" });

    fireEvent.click(screen.getByRole("button", { name: "Agendar cita" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Selecciona un paciente.");
    expect(createAppointment).not.toHaveBeenCalled();
  });

  it("muestra con qué cita choca un 409", async () => {
    vi.mocked(createAppointment).mockRejectedValueOnce(
      new AxiosError("409", "ERR", undefined, undefined, {
        status: 409, statusText: "Conflict", headers: {}, config: { headers: new AxiosHeaders() },
        data: {
          detail: "Dra. Ana Morales ya tiene una cita que se cruza con ese horario.",
          conflict: {
            appointment_id: 9, doctor_id: 1, doctor_name: "Dra. Ana Morales", patient_id: 8, patient_name: "Juan Pérez",
            starts_at: toLocalIso(nine), ends_at: toLocalIso(new Date(2026, 10, 10, 9, 30)),
          },
        },
      }),
    );
    renderWithAuth(
      <AppointmentForm initialData={newAppointmentData(nine, 30, 1)} onSaved={() => {}} onCancel={() => {}} />,
      "doctor",
    );
    fireEvent.change(screen.getByLabelText("Paciente *"), { target: { value: "eva" } });
    fireEvent.click(await screen.findByRole("button", { name: /Eva Luna/ }));
    await screen.findByRole("option", { name: "Dra. Ana Morales" });

    fireEvent.click(screen.getByRole("button", { name: "Agendar cita" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dra. Ana Morales ya tiene una cita que se cruza con ese horario. Choca con la cita de Juan Pérez (09:00 – 09:30).",
    );
  });

  it("reprograma enviando solo lo que cambió y conserva al doctor inactivo", async () => {
    renderWithAuth(<AppointmentForm appointment={existing} onSaved={() => {}} onCancel={() => {}} />, "receptionist");

    expect(screen.getByText("Eva Luna")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cambiar" })).not.toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Dr. Retirado (inactivo)" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Hora *"), { target: { value: "10:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() =>
      expect(updateAppointment).toHaveBeenCalledWith(7, { starts_at: toLocalIso(new Date(2026, 10, 10, 10, 0)) }),
    );
  });

  it("sin cambios no llama a la API", async () => {
    renderWithAuth(<AppointmentForm appointment={existing} onSaved={() => {}} onCancel={() => {}} />, "admin");

    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(updateAppointment).not.toHaveBeenCalled();
  });
});
