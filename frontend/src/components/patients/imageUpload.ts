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
