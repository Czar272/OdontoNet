import { describe, expect, it } from "vitest";

import type { Appointment, AppointmentStatus } from "../../types/appointment";
import { actionLabel, availableTransitions } from "./appointmentStatus";

const NOW = new Date(2026, 10, 10, 12, 0);

function at(status: AppointmentStatus, startHour: number): Appointment {
  const start = new Date(2026, 10, 10, startHour, 0);
  return {
    status,
    starts_at: start.toISOString(),
    ends_at: new Date(start.getTime() + 30 * 60000).toISOString(),
  } as Appointment;
}

describe("availableTransitions", () => {
  it("una programada futura se confirma o se cancela", () => {
    expect(availableTransitions(at("scheduled", 15), NOW)).toEqual(["confirmed", "cancelled"]);
  });

  it("una confirmada futura puede perder la confirmación", () => {
    expect(availableTransitions(at("confirmed", 15), NOW)).toEqual(["scheduled", "cancelled"]);
  });

  it("una cita en curso admite todo lo que no exige que termine", () => {
    const inProgress = { ...at("scheduled", 12), starts_at: new Date(2026, 10, 10, 11, 50).toISOString() };

    expect(availableTransitions(inProgress, NOW)).toEqual(["confirmed", "completed", "no_show", "cancelled"]);
  });

  it("una cita terminada solo se cierra", () => {
    expect(availableTransitions(at("confirmed", 9), NOW)).toEqual(["completed", "no_show"]);
  });

  it("atendida y no asistió se corrigen entre sí", () => {
    expect(availableTransitions(at("completed", 9), NOW)).toEqual(["no_show"]);
    expect(availableTransitions(at("no_show", 9), NOW)).toEqual(["completed"]);
  });

  it("una cancelada se reactiva solo si aún no empieza", () => {
    expect(availableTransitions(at("cancelled", 15), NOW)).toEqual(["scheduled"]);
    expect(availableTransitions(at("cancelled", 9), NOW)).toEqual([]);
  });
});

describe("actionLabel", () => {
  it("nombra la acción según el origen", () => {
    expect(actionLabel("scheduled", "confirmed")).toBe("Confirmar");
    expect(actionLabel("confirmed", "scheduled")).toBe("Quitar confirmación");
    expect(actionLabel("cancelled", "scheduled")).toBe("Reactivar");
    expect(actionLabel("scheduled", "no_show")).toBe("Marcar no asistió");
  });
});
