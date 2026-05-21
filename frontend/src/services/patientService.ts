import type { CreatePatientDTO, Patient } from "../types/patient";
import api from "./api";

export async function getPatients(): Promise<Patient[]> {
  const response = await api.get("/patients");

  return response.data;
}

export async function createPatient(
  patient: CreatePatientDTO,
): Promise<Patient> {
  const response = await api.post("/patients", patient);

  return response.data;
}
