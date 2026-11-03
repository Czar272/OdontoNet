import type {
  ClinicalVisit,
  ClinicalVisitRevision,
  UpdateVisitDTO,
  VisitContent,
} from "../types/clinicalVisit";
import api from "./api";

const base = (patientId: number) => `/patients/${patientId}/visits`;

/** Consultas del paciente, de la más reciente a la más antigua. */
export async function getVisits(patientId: number): Promise<ClinicalVisit[]> {
  const response = await api.get<ClinicalVisit[]>(base(patientId));

  return response.data;
}

export async function createVisit(
  patientId: number,
  data: VisitContent,
): Promise<ClinicalVisit> {
  const response = await api.post<ClinicalVisit>(base(patientId), data);

  return response.data;
}

export async function updateVisit(
  patientId: number,
  visitId: number,
  data: UpdateVisitDTO,
): Promise<ClinicalVisit> {
  const response = await api.put<ClinicalVisit>(
    `${base(patientId)}/${visitId}`,
    data,
  );

  return response.data;
}

export async function voidVisit(
  patientId: number,
  visitId: number,
  reason: string,
): Promise<ClinicalVisit> {
  const response = await api.post<ClinicalVisit>(
    `${base(patientId)}/${visitId}/void`,
    { reason },
  );

  return response.data;
}

export async function getVisitRevisions(
  patientId: number,
  visitId: number,
): Promise<ClinicalVisitRevision[]> {
  const response = await api.get<ClinicalVisitRevision[]>(
    `${base(patientId)}/${visitId}/revisions`,
  );

  return response.data;
}
