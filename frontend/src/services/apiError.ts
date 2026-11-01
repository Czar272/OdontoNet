import axios from "axios";

/**
 * Extrae un mensaje legible de un error de la API.
 * El backend responde { detail: string } en errores de negocio y
 * { detail: [...] } en errores de validación de FastAPI.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) return "Revisa los datos del formulario.";
  }

  return fallback;
}
