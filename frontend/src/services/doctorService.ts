import api from "./api";

import type { Doctor } from "../types/doctor";

export async function getDoctors(): Promise<Doctor[]> {
  const response = await api.get("/doctors");

  return response.data;
}
