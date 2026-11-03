import api from "./api";

import type { AvailabilityBlock, DoctorAvailability } from "../types/availability";
import type { CreateDoctorDTO, Doctor, DoctorProfileDTO } from "../types/doctor";

export interface DoctorFilters {
  /** true: solo activos · false: solo inactivos · sin valor: todos. */
  active?: boolean;
}

export async function getDoctors(filters: DoctorFilters = {}): Promise<Doctor[]> {
  const params = filters.active === undefined ? {} : { active: filters.active };
  const response = await api.get("/doctors/", { params });

  return response.data;
}

export async function createDoctor(doctor: CreateDoctorDTO): Promise<Doctor> {
  const response = await api.post("/doctors/", doctor);

  return response.data;
}

export async function updateDoctor(id: number, changes: DoctorProfileDTO): Promise<Doctor> {
  const response = await api.patch(`/doctors/${id}`, changes);

  return response.data;
}

/** Horario semanal de todos los doctores de la clínica (ODON-142). */
export async function getClinicAvailability(): Promise<DoctorAvailability[]> {
  const response = await api.get("/doctors/availability");

  return response.data;
}

/** Reemplaza el horario completo del doctor; [] lo borra. */
export async function updateDoctorAvailability(
  doctorId: number,
  blocks: AvailabilityBlock[],
): Promise<DoctorAvailability> {
  const response = await api.put(`/doctors/${doctorId}/availability`, { blocks });

  return response.data;
}
