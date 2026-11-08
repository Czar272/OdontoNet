import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { presetPeriod } from "../../components/dashboard/period";
import {
  downloadReportCsv,
  getAppointmentsReport,
  getPatientsReport,
} from "../../services/reportService";
import { renderWithAuth } from "../../test/renderWithAuth";
import type { Role } from "../../types/auth";
import type { Doctor } from "../../types/doctor";
import type { AppointmentsReport, PatientsReport } from "../../types/report";
import { saveBlob } from "../../utils/saveBlob";
import ReportsPage from "./ReportsPage";

function doctor(id: number, userId: number, name: string): Doctor {
  return {
    id,
    user_id: userId,
    specialization: null,
    license_number: null,
    phone: null,
    clinic_id: 1,
    user: { id: userId, name, email: `d${id}@odontonet-demo.com`, role: "doctor", clinic_id: 1, is_active: true },
  };
}

const counts = { scheduled: 0, confirmed: 0, cancelled: 0, attendance_rate: 75, no_show_rate: 25 };

const appointmentsReport: AppointmentsReport = {
  date_from: "2026-03-01",
  date_to: "2026-03-31",
  timezone: "America/Guatemala",
  group: "day",
  doctor_id: null,
  series: [
    { period_start: "2026-03-02", period_end: "2026-03-02", partial: false, ...counts, completed: 3, no_show: 1, total: 4 },
    { period_start: "2026-03-03", period_end: "2026-03-03", partial: false, ...counts, completed: 0, no_show: 0, total: 0, attendance_rate: null, no_show_rate: null },
  ],
  by_doctor: [{ doctor: { id: 7, name: "Dra. Ana Morales" }, ...counts, completed: 3, no_show: 1, total: 4 }],
  totals: { ...counts, completed: 3, no_show: 1, total: 4 },
};

const patientsReport: PatientsReport = {
  date_from: "2026-03-01",
  date_to: "2026-03-31",
  timezone: "America/Guatemala",
  group: "day",
  doctor_id: null,
  series: [
    { period_start: "2026-03-02", period_end: "2026-03-02", partial: false, new_patients: 2 },
    { period_start: "2026-03-03", period_end: "2026-03-03", partial: false, new_patients: 0 },
  ],
  total_new: 2,
  without_registration_date: 5,
};

vi.mock("../../services/doctorService", () => ({
  getDoctors: vi.fn(async () => [doctor(7, 1, "Dra. Ana Morales"), doctor(8, 2, "Dr. Luis Herrera")]),
}));
vi.mock("../../services/reportService", () => ({
  getAppointmentsReport: vi.fn(async () => appointmentsReport),
  getPatientsReport: vi.fn(async () => patientsReport),
  downloadReportCsv: vi.fn(async () => ({ blob: new Blob(["a,b"]), filename: "reporte-citas-2026-03-01-2026-03-31.csv" })),
}));
vi.mock("../../utils/saveBlob", () => ({ saveBlob: vi.fn() }));
// Recharts necesita medidas reales del DOM: aquí basta con saber que se dibuja.
vi.mock("./AppointmentsChart", () => ({ default: () => <div data-testid="appointments-chart" /> }));
vi.mock("./PatientsChart", () => ({ default: () => <div data-testid="patients-chart" /> }));

beforeEach(() => vi.clearAllMocks());

const ROLES: Role[] = ["admin", "doctor", "receptionist"];

describe("ReportsPage", () => {
  it.each(ROLES)("%s ve los reportes con gráfico y tabla equivalente", async (role) => {
    renderWithAuth(<ReportsPage />, role);

    const table = await screen.findByRole("table", { name: "Citas por periodo y estado" });
    expect(screen.getByTestId("appointments-chart")).toBeInTheDocument();
    const firstRow = within(table).getAllByRole("row")[1];
    expect(within(firstRow).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      expect.stringContaining("2"), "3", "1", "0", "0", "0", "4",
    ]);
    expect(screen.getByText(/4 citas · asistencia 75 %/)).toBeInTheDocument();

    const doctors = screen.getByRole("table", { name: "Citas e inasistencias por doctor" });
    expect(within(doctors).getByText("Dra. Ana Morales")).toBeInTheDocument();
    expect(within(doctors).getByText("25 %")).toBeInTheDocument();

    expect(await screen.findByRole("table", { name: "Pacientes nuevos por periodo" })).toBeInTheDocument();
    expect(screen.getByText(/5 pacientes registrados antes/)).toBeInTheDocument();
  });

  it.each([
    ["admin", 2],
    ["doctor", 0],
    ["receptionist", 0],
  ] as const)("%s ve %i botones de Exportar CSV (solo administración)", async (role, expected) => {
    renderWithAuth(<ReportsPage />, role);
    await screen.findByRole("table", { name: "Citas por periodo y estado" });
    expect(screen.queryAllByRole("button", { name: "Exportar CSV" })).toHaveLength(expected);
  });

  it("exporta el CSV con los filtros vigentes", async () => {
    renderWithAuth(<ReportsPage />, "admin");
    await screen.findByRole("table", { name: "Citas por periodo y estado" });
    fireEvent.change(screen.getByLabelText("Agrupar"), { target: { value: "month" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Exportar CSV" })[0]);

    const { from, to } = presetPeriod("this_month");
    await waitFor(() =>
      expect(downloadReportCsv).toHaveBeenCalledWith("appointments", { from, to, doctorId: null, group: "month" }),
    );
    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), "reporte-citas-2026-03-01-2026-03-31.csv"));
  });

  it("un doctor entra filtrado en sí mismo y puede cambiar el agrupamiento", async () => {
    renderWithAuth(<ReportsPage />, "doctor");
    await screen.findByRole("table", { name: "Citas por periodo y estado" });
    expect(vi.mocked(getAppointmentsReport).mock.calls[0][0].doctorId).toBe(7);
    expect(vi.mocked(getPatientsReport).mock.calls[0][0].doctorId).toBe(7);

    fireEvent.change(screen.getByLabelText("Agrupar"), { target: { value: "week" } });
    await waitFor(() => expect(vi.mocked(getAppointmentsReport).mock.lastCall?.[0].group).toBe("week"));
  });

  it("sin datos no dibuja gráficos vacíos", async () => {
    vi.mocked(getAppointmentsReport).mockResolvedValueOnce({
      ...appointmentsReport, series: [], by_doctor: [], totals: { ...appointmentsReport.totals, total: 0 },
    });
    vi.mocked(getPatientsReport).mockResolvedValueOnce({ ...patientsReport, series: [], total_new: 0, without_registration_date: 0 });
    renderWithAuth(<ReportsPage />, "admin");
    expect(await screen.findAllByText("No hay citas en el periodo.")).toHaveLength(2);
    expect(await screen.findByText("No hay pacientes nuevos en el periodo.")).toBeInTheDocument();
    expect(screen.queryByTestId("appointments-chart")).not.toBeInTheDocument();
  });
});
