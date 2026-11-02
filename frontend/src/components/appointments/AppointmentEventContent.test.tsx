import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Appointment } from "../../types/appointment";
import AppointmentEventContent from "./AppointmentEventContent";

const appointment = {
  status: "confirmed",
  patient: { first_name: "Eva", last_name: "Luna" },
  doctor: { user: { name: "Dra. Ana Morales" } },
} as Appointment;

describe("AppointmentEventContent", () => {
  it("muestra doctor arriba, paciente y hora con estado", () => {
    render(<AppointmentEventContent appointment={appointment} doctorColor="#6d28d9" timeText="09:00 - 09:30" />);

    expect(screen.getByText("Dra. Ana Morales")).toHaveStyle({ color: "#6d28d9" });
    expect(screen.getByText("Eva Luna")).toBeInTheDocument();
    expect(screen.getByText("09:00 - 09:30 · Confirmada")).toBeInTheDocument();
    // Las iniciales existen para columnas angostas; el CSS decide cuál se ve.
    expect(screen.getByText("AM")).toBeInTheDocument();
  });

  it("en la vista de semana usa el nombre corto", () => {
    render(
      <AppointmentEventContent appointment={appointment} doctorColor="#6d28d9" timeText="09:00" shortDoctorName />,
    );

    expect(screen.getByText("Dra. Morales")).toBeInTheDocument();
  });

  it("en la vista de mes es una sola línea con el doctor en el título", () => {
    const { container } = render(
      <AppointmentEventContent appointment={appointment} doctorColor="#6d28d9" timeText="09:00" compact />,
    );

    expect(screen.getByText("Eva Luna")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute("title", "09:00 · Eva Luna · Dra. Ana Morales · Confirmada");
  });

  it("tacha al paciente de una cita cancelada", () => {
    render(
      <AppointmentEventContent appointment={{ ...appointment, status: "cancelled" }} doctorColor="#6d28d9" timeText="09:00" />,
    );

    expect(screen.getByText("Eva Luna")).toHaveClass("line-through");
  });
});
