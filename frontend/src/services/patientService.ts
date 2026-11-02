import type { CreatePatientDTO, Patient, PatientPage, UpdatePatientDTO } from "../types/patient";
import api from "./api";

export interface PatientFilters {
  /** false (por defecto): solo activos · true: solo archivados. */
  archived?: boolean;
  /** Nombre y apellidos (sin tildes ni mayúsculas, en cualquier orden), correo o teléfono. */
  search?: string;
  doctorId?: number;
  page?: number;
  pageSize?: number;
}

/** Listado paginado y filtrado en el servidor (ODON-126). */
export async function getPatients(filters: PatientFilters = {}): Promise<PatientPage> {
  const params: Record<string, string | number | boolean> = {};
  if (filters.archived) params.archived = true;
  if (filters.search?.trim()) params.q = filters.search.trim();
  if (filters.doctorId) params.doctor_id = filters.doctorId;
  if (filters.page) params.page = filters.page;
  if (filters.pageSize) params.page_size = filters.pageSize;

  const response = await api.get("/patients/", { params });

  return response.data;
}

export async function createPatient(
  patient: CreatePatientDTO,
): Promise<Patient> {
  const response = await api.post("/patients/", patient);

  return response.data;
}

export async function getPatient(id: number): Promise<Patient> {
  const response = await api.get(`/patients/${id}`);

  return response.data;
}

export async function updatePatient(id: number, changes: UpdatePatientDTO): Promise<Patient> {
  const response = await api.patch(`/patients/${id}`, changes);

  return response.data;
}

export async function archivePatient(id: number): Promise<Patient> {
  const response = await api.post(`/patients/${id}/archive`);

  return response.data;
}

export async function reactivatePatient(id: number): Promise<Patient> {
  const response = await api.post(`/patients/${id}/reactivate`);

  return response.data;
}
