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

/** PDF de un examen finalizado (ODON-198); el nombre de archivo lo da el backend. */
export async function getPeriodontalReport(
  patientId: number,
  examId: number,
): Promise<{ blob: Blob; filename: string }> {
  let response;
  try {
    response = await api.get<Blob>(`${base(patientId)}/${examId}/report.pdf`, { responseType: "blob" });
  } catch (error) {
    // Con responseType "blob" el error también llega como Blob: se lee como JSON
    // para mostrar el mensaje del backend (p. ej. «El periodontograma está anulado.»).
    const data = (error as { response?: { data?: unknown } }).response?.data;
    if (data instanceof Blob) {
      try {
        (error as { response: { data: unknown } }).response.data = JSON.parse(await data.text());
      } catch {
        // No era JSON: queda el mensaje genérico.
      }
    }
    throw error;
  }
  const disposition = String(response.headers["content-disposition"] ?? "");
  const match = /filename="([^"]+)"/.exec(disposition);
  return { blob: response.data, filename: match?.[1] ?? `periodontograma-${examId}.pdf` };
}

