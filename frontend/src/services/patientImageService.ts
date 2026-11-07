import type {
  ImageAccess,
  ImageUpdateDTO,
  ImageUploadData,
  PatientImage,
  PatientImageRevision,
  PhotoConsent,
  PhotoConsentDTO,
  PhotoConsentStatus,
} from "../types/patientImage";
import api from "./api";

const consentUrl = (patientId: number) =>
  `/patients/${patientId}/photo-consent`;
const imagesUrl = (patientId: number) => `/patients/${patientId}/images`;

export async function getPhotoConsent(
  patientId: number,
): Promise<PhotoConsentStatus> {
  const response = await api.get<PhotoConsentStatus>(consentUrl(patientId));

  return response.data;
}

export async function recordPhotoConsent(
  patientId: number,
  data: PhotoConsentDTO,
): Promise<PhotoConsent> {
  const response = await api.post<PhotoConsent>(consentUrl(patientId), data);

  return response.data;
}

/** Sube una fotografía; onProgress recibe de 0 a 100. */
export async function uploadPatientImage(
  patientId: number,
  data: ImageUploadData,
  onProgress?: (percent: number) => void,
): Promise<PatientImage> {
  const form = new FormData();
  form.append("file", data.file);
  form.append("origin", data.origin);
  if (data.view !== null) form.append("view", data.view);
  if (data.taken_on !== null) form.append("taken_on", data.taken_on);
  if (data.clinical_visit_id !== null) {
    form.append("clinical_visit_id", String(data.clinical_visit_id));
  }
  if (data.tooth !== null) {
    form.append("tooth", String(data.tooth));
  }

  const response = await api.post<PatientImage>(imagesUrl(patientId), form, {
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });

  return response.data;
}

/** Archivo de la imagen como Blob: se pide con el token, nunca por URL pública. */
export async function getPatientImageFile(
  patientId: number,
  imageId: number,
): Promise<Blob> {
  const response = await api.get<Blob>(
    `${imagesUrl(patientId)}/${imageId}/file`,
    { responseType: "blob" },
  );

  return response.data;
}

/** Imágenes del paciente (solo metadatos), la más reciente primero. */
export async function getPatientImages(
  patientId: number,
): Promise<PatientImage[]> {
  const response = await api.get<PatientImage[]>(imagesUrl(patientId));

  return response.data;
}

/** Miniatura JPEG (lado mayor 320 px), pedida con el token. */
export async function getPatientImageThumbnail(
  patientId: number,
  imageId: number,
): Promise<Blob> {
  const response = await api.get<Blob>(
    `${imagesUrl(patientId)}/${imageId}/thumbnail`,
    { responseType: "blob" },
  );

  return response.data;
}

/** Corrige los metadatos (409 con current_revision si cambió). */
export async function updatePatientImage(
  patientId: number,
  imageId: number,
  data: ImageUpdateDTO,
): Promise<PatientImage> {
  const response = await api.patch<PatientImage>(
    `${imagesUrl(patientId)}/${imageId}`,
    data,
  );

  return response.data;
}

export async function voidPatientImage(
  patientId: number,
  imageId: number,
  reason: string,
): Promise<PatientImage> {
  const response = await api.post<PatientImage>(
    `${imagesUrl(patientId)}/${imageId}/void`,
    { reason },
  );

  return response.data;
}

export async function getPatientImageRevisions(
  patientId: number,
  imageId: number,
): Promise<PatientImageRevision[]> {
  const response = await api.get<PatientImageRevision[]>(
    `${imagesUrl(patientId)}/${imageId}/revisions`,
  );

  return response.data;
}

/** Aperturas del original (solo administración). */
export async function getPatientImageAccessLog(
  patientId: number,
  imageId: number,
): Promise<ImageAccess[]> {
  const response = await api.get<ImageAccess[]>(
    `${imagesUrl(patientId)}/${imageId}/access-log`,
  );

  return response.data;
}
