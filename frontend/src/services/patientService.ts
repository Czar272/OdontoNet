import type { CreatePatientDTO, Patient, UpdatePatientDTO } from "../types/patient";
import api from "./api";

export async function getPatients(): Promise<Patient[]> {
  const response = await api.get("/patients/");

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
