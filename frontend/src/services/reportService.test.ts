import { beforeEach, describe, expect, it, vi } from "vitest";

// `get` es una función simple y no un vi.fn: el espía de Vitest encadena la
// promesa que devuelve el mock y un rechazo esperado quedaba como «sin manejar».
const api = vi.hoisted(() => ({
  calls: [] as unknown[][],
  impl: (async () => ({ data: {} })) as (...args: unknown[]) => Promise<unknown>,
}));

vi.mock("./api", () => ({
  default: {
    get: (...args: unknown[]) => {
      api.calls.push(args);
      return api.impl(...args);
    },
  },
}));

const { downloadReportCsv, getAppointmentsReport } = await import("./reportService");
const { getApiErrorMessage } = await import("./apiError");

const params = { from: "2026-03-01", to: "2026-03-31", group: "week" as const };

beforeEach(() => {
  api.calls = [];
  api.impl = async () => ({ data: {} });
});

describe("reportService", () => {
  it("envía los filtros y omite el doctor cuando es toda la clínica", async () => {
    await getAppointmentsReport({ ...params, doctorId: null });
    await getAppointmentsReport({ ...params, doctorId: 7 });
    expect(api.calls).toEqual([
      ["/reports/appointments", { params }],
      ["/reports/appointments", { params: { ...params, doctor_id: 7 } }],
    ]);
  });

  it("toma el nombre del archivo de Content-Disposition", async () => {
    const blob = new Blob(["a,b"]);
    api.impl = async () => ({
      data: blob,
      headers: { "content-disposition": 'attachment; filename="reporte-citas-x.csv"' },
    });
    await expect(downloadReportCsv("appointments", params)).resolves.toEqual({
      blob,
      filename: "reporte-citas-x.csv",
    });
  });

  it("un error llega como Blob y se convierte para mostrar el mensaje del backend", async () => {
    const error = Object.assign(new Error("Request failed"), {
      isAxiosError: true,
      response: { status: 403, data: new Blob([JSON.stringify({ detail: "No tienes permiso." })]) as unknown },
    });
    api.impl = async () => {
      throw error;
    };
    const failure = await downloadReportCsv("patients", params).then(
      () => null,
      (caught: unknown) => caught,
    );
    expect(failure).toBe(error);
    expect(error.response.data).toEqual({ detail: "No tienes permiso." });
    expect(getApiErrorMessage(failure, "No se pudo exportar el reporte")).toBe("No tienes permiso.");
  });
});
