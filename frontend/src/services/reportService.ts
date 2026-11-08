import type {
  AppointmentsReport,
  PatientsReport,
  ReportKind,
  ReportParams,
} from "../types/report";
import api from "./api";

function toQuery({ from, to, doctorId, group }: ReportParams) {
  const params: Record<string, string | number> = { from, to, group };
  if (doctorId) params.doctor_id = doctorId;
  return params;
}

export async function getAppointmentsReport(params: ReportParams): Promise<AppointmentsReport> {
  const response = await api.get<AppointmentsReport>("/reports/appointments", { params: toQuery(params) });
  return response.data;
}

export async function getPatientsReport(params: ReportParams): Promise<PatientsReport> {
  const response = await api.get<PatientsReport>("/reports/patients", { params: toQuery(params) });
  return response.data;
}

/** CSV agregado del reporte (solo administración). */
export async function downloadReportCsv(
  kind: ReportKind,
  params: ReportParams,
): Promise<{ blob: Blob; filename: string }> {
  let response;
  try {
    response = await api.get<Blob>(`/reports/${kind}.csv`, {
      params: toQuery(params),
      responseType: "blob",
    });
  } catch (error) {
    // Con responseType "blob" el error llega como Blob: se lee como JSON para
    // mostrar el mensaje del backend.
    const data = (error as { response?: { data?: unknown } }).response?.data;
    if (data instanceof Blob) {
      try {
        (error as { response: { data: unknown } }).response.data = JSON.parse(await data.text());
      } catch {
        // No era JSON: queda el mensaje genérico.
      }
    }
    throw error;
  }
  const disposition = String(response.headers["content-disposition"] ?? "");
  const match = /filename="([^"]+)"/.exec(disposition);
  return { blob: response.data, filename: match?.[1] ?? `reporte-${kind}.csv` };
}
