import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboard } from "../../services/dashboardService";
import { getDoctors } from "../../services/doctorService";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { Role } from "../../types/auth";
import type { Dashboard } from "../../types/dashboard";
import type { Doctor } from "../../types/doctor";
import DashboardPage from "./DashboardPage";
import { presetPeriod } from "./dashboardPeriod";

function doctor(id: number, userId: number, name: string, isActive = true): Doctor {
  return {
    id,
    user_id: userId,
    specialization: null,
    license_number: null,
    phone: null,
    clinic_id: 1,
    user: { id: userId, name, email: `d${id}@odontonet-demo.com`, role: "doctor", clinic_id: 1, is_active: isActive },
  };
}

// fakeUser tiene id 1: el doctor 7 es el usuario de la sesión cuando entra un doctor.
const doctors = [
  doctor(7, 1, "Dra. Ana Morales"),
  doctor(8, 2, "Dr. Luis Herrera"),
  doctor(9, 3, "Dr. Retirado", false),
];

const dashboard: Dashboard = {
  date_from: "2026-03-01",
  date_to: "2026-03-31",
  timezone: "America/Guatemala",
  doctor_id: null,
  indicators: {
    patients_active: 120,
    patients_new: 8,
    appointments_today: 5,
    appointments_week: 22,
    appointments_period: 90,
    attendance_rate: 87.5,
    no_show_rate: 12.5,
    cancellation_rate: null,
    visits_registered: 60,
    treatments_completed: 14,
    periodontal_finalized: 3,
    images_uploaded: 11,
    occupancy_rate: 64.2,
  },
  agenda_today: [
    {
      id: 1,
      starts_at: "2026-03-11T15:00:00Z",
      duration_minutes: 30,
      status: "confirmed",
      patient: { id: 40, name: "Paciente Demo" },
      doctor: { id: 7, name: "Dra. Ana Morales" },
    },
  ],
};

vi.mock("../../services/doctorService", () => ({
  getDoctors: vi.fn(async () => doctors),
}));

vi.mock("../../services/dashboardService", () => ({
  getDashboard: vi.fn(async () => dashboard),
}));

const mockedGetDashboard = vi.mocked(getDashboard);

beforeEach(() => {
  localStorage.clear();
  mockedGetDashboard.mockClear();
});

afterEach(() => localStorage.clear());

const ROLES: Role[] = ["admin", "doctor", "receptionist"];

describe("DashboardPage", () => {
  it.each(ROLES)("%s ve cuatro indicadores y la agenda de hoy", async (role) => {
    renderWithAuth(<DashboardPage />, role);

    const grid = await screen.findByRole("list", { name: "Indicadores" });
    expect(within(grid).getAllByRole("listitem")).toHaveLength(4);
    expect(within(grid).getByText("Citas de hoy")).toBeInTheDocument();
    expect(within(grid).getByText("87.5 %")).toBeInTheDocument();
    expect(within(grid).queryByText("Pacientes activos")).not.toBeInTheDocument();

    const agenda = screen.getByRole("list", { name: "Citas de hoy" });
    expect(within(agenda).getByRole("link", { name: "Paciente Demo" })).toHaveAttribute("href", "/patients/40");
    expect(within(agenda).getByText("Confirmada")).toBeInTheDocument();
  });

  it("pide el mes en curso por defecto", async () => {
    renderWithAuth(<DashboardPage />, "admin");
    await screen.findByRole("list", { name: "Indicadores" });
    const { from, to } = presetPeriod("this_month");
    expect(mockedGetDashboard).toHaveBeenCalledWith({ from, to, doctorId: null });
  });

  it("un doctor entra enfocado en sus propios datos y puede ver toda la clínica", async () => {
    renderWithAuth(<DashboardPage />, "doctor");
    await screen.findByRole("list", { name: "Indicadores" });

    // La primera consulta ya va filtrada: no pide antes toda la clínica.
    expect(mockedGetDashboard).toHaveBeenCalledTimes(1);
    expect(mockedGetDashboard.mock.calls[0][0].doctorId).toBe(7);
    const select = screen.getByLabelText("Doctor") as HTMLSelectElement;
    expect(select.value).toBe("7");
    expect(screen.getByRole("option", { name: "Dra. Ana Morales (yo)" })).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "all" } });
    await waitFor(() => expect(mockedGetDashboard.mock.lastCall?.[0].doctorId).toBeNull());
  });

  it("administración entra con todos los doctores y ve solo los activos", async () => {
    renderWithAuth(<DashboardPage />, "admin");
    await screen.findByRole("list", { name: "Indicadores" });
    expect((screen.getByLabelText("Doctor") as HTMLSelectElement).value).toBe("all");
    await screen.findByRole("option", { name: "Dr. Luis Herrera" });
    expect(screen.queryByRole("option", { name: "Dr. Retirado" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Doctor"), { target: { value: "8" } });
    await waitFor(() => expect(mockedGetDashboard.mock.lastCall?.[0].doctorId).toBe(8));
  });

  it("muestra más indicadores debajo y recuerda la preferencia del usuario", async () => {
    const { unmount } = renderWithAuth(<DashboardPage />, "receptionist");
    await screen.findByRole("list", { name: "Indicadores" });

    fireEvent.click(screen.getByRole("button", { name: "Mostrar más indicadores" }));
    const grid = screen.getByRole("list", { name: "Indicadores" });
    expect(within(grid).getAllByRole("listitem")).toHaveLength(13);
    expect(within(grid).getByText("Pacientes activos")).toBeInTheDocument();
    // Tasa sin base: guion, no 0 %.
    expect(within(grid).getByText("—")).toBeInTheDocument();
    unmount();

    renderWithAuth(<DashboardPage />, "receptionist");
    const again = await screen.findByRole("list", { name: "Indicadores" });
    expect(within(again).getAllByRole("listitem")).toHaveLength(13);
    fireEvent.click(screen.getByRole("button", { name: "Mostrar menos indicadores" }));
    expect(within(screen.getByRole("list", { name: "Indicadores" })).getAllByRole("listitem")).toHaveLength(4);
  });

  it("cambia el periodo con los atajos y valida el personalizado", async () => {
    renderWithAuth(<DashboardPage />, "admin");
    await screen.findByRole("list", { name: "Indicadores" });

    fireEvent.change(screen.getByLabelText("Periodo"), { target: { value: "last_month" } });
    const lastMonth = presetPeriod("last_month");
    await waitFor(() =>
      expect(mockedGetDashboard.mock.lastCall?.[0]).toMatchObject({ from: lastMonth.from, to: lastMonth.to }),
    );

    fireEvent.change(screen.getByLabelText("Periodo"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-03-10" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-03-01" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("anterior a la inicial");
    expect(mockedGetDashboard.mock.lastCall?.[0].to).not.toBe("2026-03-01");

    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-03-20" } });
    await waitFor(() =>
      expect(mockedGetDashboard.mock.lastCall?.[0]).toMatchObject({ from: "2026-03-10", to: "2026-03-20" }),
    );
  });

  it("si no carga la lista de doctores, un doctor ve toda la clínica", async () => {
    vi.mocked(getDoctors).mockRejectedValueOnce(new Error("red"));
    renderWithAuth(<DashboardPage />, "doctor");
    await screen.findByRole("list", { name: "Indicadores" });
    expect(mockedGetDashboard.mock.calls[0][0].doctorId).toBeNull();
  });

  it("avisa cuando no hay citas hoy", async () => {
    mockedGetDashboard.mockResolvedValueOnce({ ...dashboard, agenda_today: [] });
    renderWithAuth(<DashboardPage />, "admin");
    expect(await screen.findByText("No hay citas para hoy.")).toBeInTheDocument();
  });
});
