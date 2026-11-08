import type { Dashboard, DashboardParams } from "../types/dashboard";
import api from "./api";

/** Indicadores del periodo y agenda de hoy de la clínica (ODON-202). */
export async function getDashboard({
  from,
  to,
  doctorId,
}: DashboardParams): Promise<Dashboard> {
  const params: Record<string, string | number> = { from, to };
  if (doctorId) params.doctor_id = doctorId;

  const response = await api.get<Dashboard>("/dashboard", { params });

  return response.data;
}
