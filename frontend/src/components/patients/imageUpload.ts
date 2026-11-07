import type { CurrentUser } from "../../types/auth";
import type {
  ImageMetadata,
  ImageOrigin,
  ImageView,
  PatientImage,
} from "../../types/patientImage";

/**
 * Reglas de la subida de imágenes (ODON-170). Son solo una ayuda para el
 * usuario: el backend valida el contenido real del archivo.
 */
export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const ACCEPTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
// Espejo de IMAGE_MAX_MB del backend.
export const MAX_IMAGE_MB = 10;

/** Mensaje de error para el archivo elegido, o null si se puede subir. */
export function validateImageFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_IMAGE_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return "Tipo de imagen no permitido. Usa JPEG, PNG o WebP.";
  }
  if (file.size === 0) {
    return "La imagen está vacía.";
  }
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
    return `La imagen supera el máximo de ${MAX_IMAGE_MB} MB.`;
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const photoConsentKey = (patientId: number) =>
  ["patients", patientId, "photo-consent"] as const;

/** Fecha de hoy (YYYY-MM-DD) en la zona horaria del navegador. */
export function todayLocal(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Contenido de un archivo o Blob como data URL, para vistas previas. */
export function readAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export const patientImagesKey = (patientId: number) =>
  ["patients", patientId, "images"] as const;

// Miniaturas que se piden de una vez en la galería; el resto, con «Ver más».
export const GALLERY_PAGE_SIZE = 24;

// Espejo de IMAGE_ORIGINS e IMAGE_VIEWS del backend (ODON-178).
export const IMAGE_ORIGIN_LABELS: Record<ImageOrigin, string> = {
  intraoral_camera: "Cámara intraoral",
  phone: "Celular",
  camera: "Cámara fotográfica",
  external: "Documento u otra clínica",
};

export const IMAGE_VIEW_LABELS: Record<ImageView, string> = {
  frontal: "Frontal",
  right_lateral: "Lateral derecha",
  left_lateral: "Lateral izquierda",
  upper_occlusal: "Oclusal superior",
  lower_occlusal: "Oclusal inferior",
  detail: "Detalle",
  other: "Otra",
};

/** Corrige o anula quien la subió o administración, si no está anulada. */
export function canModifyImage(
  image: PatientImage,
  user: CurrentUser | null,
): boolean {
  if (!user || image.voided_at) return false;
  return user.role === "admin" || image.uploaded_by.id === user.id;
}

/** Estado de los campos de metadatos en los formularios (todo como texto). */
export interface ImageMetadataForm {
  origin: ImageOrigin | "";
  view: ImageView | "";
  taken_on: string;
  clinical_visit_id: string;
  tooth: number | null;
}

export const EMPTY_IMAGE_METADATA: ImageMetadataForm = {
  origin: "",
  view: "",
  taken_on: "",
  clinical_visit_id: "",
  tooth: null,
};

export function imageMetadataForm(image: PatientImage): ImageMetadataForm {
  return {
    origin: image.origin ?? "",
    view: image.view ?? "",
    taken_on: image.taken_on ?? "",
    clinical_visit_id: image.clinical_visit
      ? String(image.clinical_visit.id)
      : "",
    tooth: image.tooth,
  };
}

/** Metadatos listos para la API, o null si falta el origen. */
export function toImageMetadata(form: ImageMetadataForm): ImageMetadata | null {
  if (!form.origin) return null;
  return {
    origin: form.origin,
    view: form.view || null,
    taken_on: form.taken_on || null,
    clinical_visit_id: form.clinical_visit_id
      ? Number(form.clinical_visit_id)
      : null,
    tooth: form.tooth,
  };
}
