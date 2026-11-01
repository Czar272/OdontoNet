import type { Clinic, UpdateClinicDTO } from "../types/clinic";
import api from "./api";

/** Clínica de la sesión: no recibe id, el backend la toma del token. */
export async function getClinic(): Promise<Clinic> {
  const response = await api.get("/clinic");

  return response.data;
}

export async function updateClinic(changes: UpdateClinicDTO): Promise<Clinic> {
  const response = await api.patch("/clinic", changes);

  return response.data;
}
