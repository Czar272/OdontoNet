import api from "./api";

import type { Doctor } from "../types/doctor";

export interface DoctorFilters {
  /** true: solo activos · false: solo inactivos · sin valor: todos. */
  active?: boolean;
}

export async function getDoctors(filters: DoctorFilters = {}): Promise<Doctor[]> {
  const params = filters.active === undefined ? {} : { active: filters.active };
  const response = await api.get("/doctors/", { params });

  return response.data;
}
