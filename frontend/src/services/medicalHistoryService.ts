import type {
  MedicalHistory,
  MedicalHistoryVersionSummary,
  SaveMedicalHistoryDTO,
} from "../types/medicalHistory";
import api from "./api";

const base = (patientId: number) => `/patients/${patientId}/medical-history`;

/** Versión vigente, o null si el paciente aún no tiene historia. */
export async function getMedicalHistory(
  patientId: number,
): Promise<MedicalHistory | null> {
  const response = await api.get<MedicalHistory | null>(base(patientId));

  return response.data;
}

export async function getMedicalHistoryVersions(
  patientId: number,
): Promise<MedicalHistoryVersionSummary[]> {
  const response = await api.get<MedicalHistoryVersionSummary[]>(
    `${base(patientId)}/versions`,
  );

  return response.data;
}

export async function getMedicalHistoryVersion(
  patientId: number,
  version: number,
): Promise<MedicalHistory> {
  const response = await api.get<MedicalHistory>(
    `${base(patientId)}/versions/${version}`,
  );

  return response.data;
}

/** Guarda la historia completa como una versión nueva. */
export async function saveMedicalHistory(
  patientId: number,
  data: SaveMedicalHistoryDTO,
): Promise<MedicalHistory> {
  const response = await api.post<MedicalHistory>(base(patientId), data);

  return response.data;
}
