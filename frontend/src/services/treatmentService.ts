import type {
  Treatment,
  TreatmentDTO,
  TreatmentStatusChange,
  TreatmentStatusDTO,
} from "../types/treatment";
import api from "./api";

const base = (patientId: number) => `/patients/${patientId}/treatments`;

/** Tratamientos del paciente: pendientes primero y después los cerrados. */
export async function getTreatments(patientId: number): Promise<Treatment[]> {
  const response = await api.get<Treatment[]>(base(patientId));

  return response.data;
}

export async function createTreatment(
  patientId: number,
  data: TreatmentDTO,
): Promise<Treatment> {
  const response = await api.post<Treatment>(base(patientId), data);

  return response.data;
}

export async function updateTreatment(
  patientId: number,
  treatmentId: number,
  changes: Partial<TreatmentDTO>,
): Promise<Treatment> {
  const response = await api.patch<Treatment>(
    `${base(patientId)}/${treatmentId}`,
    changes,
  );

  return response.data;
}

export async function changeTreatmentStatus(
  patientId: number,
  treatmentId: number,
  data: TreatmentStatusDTO,
): Promise<Treatment> {
  const response = await api.post<Treatment>(
    `${base(patientId)}/${treatmentId}/status`,
    data,
  );

  return response.data;
}

export async function getTreatmentHistory(
  patientId: number,
  treatmentId: number,
): Promise<TreatmentStatusChange[]> {
  const response = await api.get<TreatmentStatusChange[]>(
    `${base(patientId)}/${treatmentId}/history`,
  );

  return response.data;
}
