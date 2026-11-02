import { AxiosError, AxiosHeaders } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Appointment } from "../../types/appointment";
import {
  appointmentErrorMessage,
  appointmentToFormData,
  buildAppointmentChanges,
  buildCreateAppointment,
  durationBetween,
  newAppointmentData,
  toLocalIso,
} from "./appointmentFormData";

// Fechas construidas en la hora local: las pruebas valen en cualquier zona.
const nine = new Date(2026, 10, 10, 9, 0);

function appointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: 7, clinic_id: 1, patient_id: 3, doctor_id: 2,
    starts_at: toLocalIso(nine), ends_at: toLocalIso(new Date(2026, 10, 10, 9, 30)),
    duration_minutes: 30, status: "scheduled", reason: "Limpieza",
    created_by_user_id: 1, created_at: "", updated_at: "",
    patient: { id: 3, first_name: "Eva", last_name: "Luna", archived_at: null },
    doctor: {
      id: 2, user_id: 9, specialization: null, license_number: null, phone: null, clinic_id: 1,
      user: { id: 9, name: "Dra. Ana", email: "a@x.com", role: "doctor", clinic_id: 1, is_active: true },
    },
    ...overrides,
  };
}

afterEach(() => vi.restoreAllMocks());

describe("toLocalIso", () => {
  it("conserva el instante e incluye la zona del navegador", () => {
    const iso = toLocalIso(nine);

    expect(iso).toMatch(/^2026-11-10T09:00:00[+-]\d{2}:\d{2}$/);
    expect(new Date(iso).getTime()).toBe(nine.getTime());
  });

  it.each([
    [360, "-06:00"],
    [-330, "+05:30"],
    [0, "+00:00"],
  ])("offset %i → %s", (offset, suffix) => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(offset);

    expect(toLocalIso(nine).endsWith(suffix)).toBe(true);
  });
});

describe("durationBetween", () => {
  it("calcula minutos y respeta los límites del backend", () => {
    expect(durationBetween(nine, new Date(2026, 10, 10, 10, 15))).toBe(75);
    expect(durationBetween(nine, nine)).toBe(5);
    expect(durationBetween(nine, new Date(2026, 10, 11, 9, 0))).toBe(480);
  });
});

describe("buildCreateAppointment", () => {
  it("arma la cita con fecha local y omite el motivo vacío", () => {
    const data = { ...newAppointmentData(nine, 45, 2), patient_id: 3 };

    expect(buildCreateAppointment(data)).toEqual({
      patient_id: 3, doctor_id: 2, starts_at: toLocalIso(nine), duration_minutes: 45,
    });
  });

  it("devuelve null si falta el paciente, el doctor o la hora", () => {
    const base = { ...newAppointmentData(nine, 30, 2), patient_id: 3 };

    expect(buildCreateAppointment({ ...base, patient_id: null })).toBeNull();
    expect(buildCreateAppointment({ ...base, doctor_id: "" })).toBeNull();
    expect(buildCreateAppointment({ ...base, time: "" })).toBeNull();
  });
});

describe("buildAppointmentChanges", () => {
  it("sin cambios no envía nada", () => {
    const current = appointment();

    expect(buildAppointmentChanges(current, appointmentToFormData(current))).toEqual({});
  });

  it("envía solo lo que cambió", () => {
    const current = appointment();
    const form = { ...appointmentToFormData(current), time: "10:30", duration_minutes: "60", reason: "" };

    expect(buildAppointmentChanges(current, form)).toEqual({
      starts_at: toLocalIso(new Date(2026, 10, 10, 10, 30)),
      duration_minutes: 60,
      reason: "",
    });
  });
});

describe("appointmentErrorMessage", () => {
  function conflictError() {
    return new AxiosError("409", "ERR", undefined, undefined, {
      status: 409, statusText: "Conflict", headers: {}, config: { headers: new AxiosHeaders() },
      data: {
        detail: "Dra. Ana ya tiene una cita que se cruza con ese horario.",
        conflict: {
          appointment_id: 1, doctor_id: 2, doctor_name: "Dra. Ana", patient_id: 4, patient_name: "Juan Pérez",
          starts_at: toLocalIso(nine), ends_at: toLocalIso(new Date(2026, 10, 10, 9, 30)),
        },
      },
    });
  }

  it("agrega con qué cita choca, en hora local de 24 horas", () => {
    expect(appointmentErrorMessage(conflictError(), "x")).toBe(
      "Dra. Ana ya tiene una cita que se cruza con ese horario. Choca con la cita de Juan Pérez (09:00 – 09:30).",
    );
  });

  it("sin conflicto usa el detalle o el mensaje por defecto", () => {
    expect(appointmentErrorMessage(new Error("red"), "No se pudo agendar la cita")).toBe(
      "No se pudo agendar la cita",
    );
  });
});
