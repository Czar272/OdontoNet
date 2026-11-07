import type {
  ExamContentDTO,
  ExamRevision,
  ExamUpdateDTO,
  PeriodontalExam,
  PeriodontalExamListItem,
} from "../types/periodontal";
import api from "./api";

const base = (patientId: number) => `/patients/${patientId}/periodontal-exams`;

/** Exámenes del paciente, del más reciente al más antiguo, con su resumen. */
export async function getPeriodontalExams(
  patientId: number,
): Promise<PeriodontalExamListItem[]> {
  const response = await api.get<PeriodontalExamListItem[]>(base(patientId));
  return response.data;
}

export async function getPeriodontalExam(
  patientId: number,
  examId: number,
): Promise<PeriodontalExam> {
  const response = await api.get<PeriodontalExam>(`${base(patientId)}/${examId}`);
  return response.data;
}

/** Registra un examen en borrador. */
export async function createPeriodontalExam(
  patientId: number,
  data: ExamContentDTO,
): Promise<PeriodontalExam> {
  const response = await api.post<PeriodontalExam>(base(patientId), data);
  return response.data;
}

/** Guarda el borrador completo; 409 con current_revision si otra persona guardó antes. */
export async function updatePeriodontalExam(
  patientId: number,
  examId: number,
  data: ExamUpdateDTO,
): Promise<PeriodontalExam> {
  const response = await api.put<PeriodontalExam>(`${base(patientId)}/${examId}`, data);
  return response.data;
}

export async function finalizePeriodontalExam(
  patientId: number,
  examId: number,
  baseRevision: number,
): Promise<PeriodontalExam> {
  const response = await api.post<PeriodontalExam>(
    `${base(patientId)}/${examId}/finalize`,
    { base_revision: baseRevision },
  );
  return response.data;
}

export async function voidPeriodontalExam(
  patientId: number,
  examId: number,
  reason: string,
): Promise<PeriodontalExam> {
  const response = await api.post<PeriodontalExam>(
    `${base(patientId)}/${examId}/void`,
    { reason },
  );
  return response.data;
}

export async function getPeriodontalExamRevisions(
  patientId: number,
  examId: number,
): Promise<ExamRevision[]> {
  const response = await api.get<ExamRevision[]>(`${base(patientId)}/${examId}/revisions`);
  return response.data;
}
