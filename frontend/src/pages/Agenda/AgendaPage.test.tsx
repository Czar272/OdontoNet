import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/renderWithAuth";
import type { Appointment, AppointmentStatus } from "../../types/appointment";
import type { Doctor } from "../../types/doctor";
import { toLocalIso } from "./appointmentFormData";
import AgendaPage from "./AgendaPage";

// FullCalendar no se dibuja en jsdom: se reemplaza por un doble que lista los
// eventos y deja invocar los callbacks como lo haría el calendario.
const calendar = vi.hoisted(() => ({ props: {} as Record<string, (...args: unknown[]) => unknown> & { events?: unknown[] } }));

vi.mock("@fullcalendar/react", async () => {
  const React = await import("react");
  function FakeCalendar(props: Record<string, unknown>) {
    calendar.props = props as typeof calendar.props;
    const datesSet = React.useRef(props.datesSet as (arg: unknown) => void);
    // Como el calendario real: anuncia el rango visible al montarse (una vez).
    React.useEffect(() => {
      datesSet.current({ start: new Date(2026, 10, 9), end: new Date(2026, 10, 16) });
    }, []);
    const events = (props.events as { id: string; title: string; editable: boolean }[]) ?? [];
      return React.createElement(
        "ul",
        { "aria-label": "Calendario" },
        events.map((event) =>
          React.createElement("li", { key: event.id, "data-editable": String(event.editable) }, event.title),
        ),
      );
  }
  return { default: FakeCalendar };
});
vi.mock("@fullcalendar/core/locales/es", () => ({ default: {} }));
vi.mock("@fullcalendar/daygrid", () => ({ default: {} }));
vi.mock("@fullcalendar/timegrid", () => ({ default: {} }));
vi.mock("@fullcalendar/interaction", () => ({ default: {} }));

function doctor(id: number, name: string): Doctor {
  return {
    id, user_id: id + 100, specialization: null, license_number: null, phone: null, clinic_id: 1,
    user: { id: id + 100, name, email: `d${id}@x.com`, role: "doctor", clinic_id: 1, is_active: true },
  };
}

const ana = doctor(1, "Dra. Ana");
const future = new Date();
future.setDate(future.getDate() + 3);
future.setHours(9, 0, 0, 0);

function appointment(id: number, first: string, status: AppointmentStatus, start = future): Appointment {
  const end = new Date(start.getTime() + 30 * 60000);
  return {
    id, clinic_id: 1, patient_id: id, doctor_id: 1, starts_at: toLocalIso(start), ends_at: toLocalIso(end),
    duration_minutes: 30, status, reason: "Control", created_by_user_id: 1, created_at: "", updated_at: "",
    patient: { id, first_name: first, last_name: "Paz", archived_at: null }, doctor: ana,
  };
}

const past = new Date(2020, 0, 6, 9, 0);
const APPOINTMENTS = [
  appointment(1, "Ana", "scheduled"),
  appointment(2, "Beto", "confirmed"),
  appointment(3, "Ciro", "completed", past),
  appointment(4, "Dora", "cancelled"),
  appointment(5, "Eli", "no_show", past),
];

vi.mock("../../services/appointmentService", () => ({
  getAppointments: vi.fn(async () => APPOINTMENTS),
  updateAppointment: vi.fn(async () => APPOINTMENTS[0]),
  createAppointment: vi.fn(),
}));
vi.mock("../../services/doctorService", () => ({ getDoctors: vi.fn(async () => [ana]) }));
vi.mock("../../services/patientService", () => ({ getPatients: vi.fn() }));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast };
});

const { getAppointments, updateAppointment } = await import("../../services/appointmentService");

const titles = () => screen.queryAllByRole("listitem").map((item) => item.textContent);

beforeEach(() => vi.clearAllMocks());

describe("AgendaPage", () => {
  it("pide al backend las citas del rango visible", async () => {
    renderWithAuth(<AgendaPage />, "receptionist");

    await screen.findByText("Ana Paz · Dra. Ana");
    expect(getAppointments).toHaveBeenCalledWith({
      start: toLocalIso(new Date(2026, 10, 9)), end: toLocalIso(new Date(2026, 10, 16)), doctorId: undefined,
    });
  });

  it("oculta canceladas y No asistió hasta activarlas en la leyenda", async () => {
    renderWithAuth(<AgendaPage />, "doctor");
    await screen.findByText("Ana Paz · Dra. Ana");

    expect(titles()).toEqual(["Ana Paz · Dra. Ana", "Beto Paz · Dra. Ana", "Ciro Paz · Dra. Ana"]);

    fireEvent.click(screen.getByRole("button", { name: "Cancelada" }));
    fireEvent.click(screen.getByRole("button", { name: "Atendida" }));

    expect(screen.getByRole("button", { name: "Cancelada" })).toHaveAttribute("aria-pressed", "true");
    expect(titles()).toEqual(["Ana Paz · Dra. Ana", "Beto Paz · Dra. Ana", "Dora Paz · Dra. Ana"]);
  });

  it("filtra por doctor en el backend", async () => {
    renderWithAuth(<AgendaPage />, "admin");
    await screen.findByRole("option", { name: "Dra. Ana" });

    fireEvent.change(screen.getByLabelText("Filtrar por doctor"), { target: { value: "1" } });

    await waitFor(() => expect(getAppointments).toHaveBeenLastCalledWith(expect.objectContaining({ doctorId: 1 })));
  });

  it("solo las citas pendientes y futuras se pueden arrastrar", async () => {
    renderWithAuth(<AgendaPage />, "receptionist");
    await screen.findByText("Ana Paz · Dra. Ana");

    const editable = screen.getAllByRole("listitem").map((item) => item.getAttribute("data-editable"));
    expect(editable).toEqual(["true", "true", "false"]);
  });

  it("abre el detalle al hacer clic y permite reprogramar una pendiente", async () => {
    renderWithAuth(<AgendaPage />, "receptionist");
    await screen.findByText("Ana Paz · Dra. Ana");

    calendar.props.eventClick({ event: { extendedProps: { appointment: APPOINTMENTS[0] } } });

    expect(await screen.findByRole("dialog", { name: "Detalle de la cita" })).toHaveTextContent("Programada");
    fireEvent.click(screen.getByRole("button", { name: "Reprogramar" }));
    expect(await screen.findByRole("dialog", { name: "Reprogramar cita" })).toBeInTheDocument();
  });

  it("una cita atendida no ofrece reprogramar", async () => {
    renderWithAuth(<AgendaPage />, "admin");
    await screen.findByText("Ana Paz · Dra. Ana");

    calendar.props.eventClick({ event: { extendedProps: { appointment: APPOINTMENTS[2] } } });

    await screen.findByRole("dialog", { name: "Detalle de la cita" });
    expect(screen.queryByRole("button", { name: "Reprogramar" })).not.toBeInTheDocument();
  });

  it("seleccionar un horario abre Nueva cita con esa hora y duración", async () => {
    renderWithAuth(<AgendaPage />, "receptionist");
    await screen.findByText("Ana Paz · Dra. Ana");
    const start = new Date(future.getTime() + 2 * 3600000);

    calendar.props.select({
      start, end: new Date(start.getTime() + 45 * 60000), allDay: false,
      view: { calendar: { unselect: vi.fn(), changeView: vi.fn() } },
    });

    expect(await screen.findByRole("dialog", { name: "Nueva cita" })).toBeInTheDocument();
    expect(screen.getByLabelText("Hora *")).toHaveValue("11:00");
    expect(screen.getByLabelText("Duración")).toHaveValue("45");
  });

  it("arrastrar guarda el nuevo horario y lo revierte si el backend lo rechaza", async () => {
    vi.mocked(updateAppointment).mockRejectedValueOnce(new Error("409"));
    renderWithAuth(<AgendaPage />, "receptionist");
    await screen.findByText("Ana Paz · Dra. Ana");
    const start = new Date(future.getTime() + 3600000);
    const revert = vi.fn();

    calendar.props.eventDrop({
      event: { start, end: new Date(start.getTime() + 30 * 60000), extendedProps: { appointment: APPOINTMENTS[0] } },
      revert,
    });

    await waitFor(() => expect(updateAppointment).toHaveBeenCalledWith(1, { starts_at: toLocalIso(start) }));
    await waitFor(() => expect(revert).toHaveBeenCalled());
  });

  it("en la vista de mes, elegir un día abre la vista de ese día", async () => {
    renderWithAuth(<AgendaPage />, "receptionist");
    await screen.findByText("Ana Paz · Dra. Ana");
    const changeView = vi.fn();

    calendar.props.select({ start: future, end: future, allDay: true, view: { calendar: { unselect: vi.fn(), changeView } } });

    expect(changeView).toHaveBeenCalledWith("timeGridDay", future);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
