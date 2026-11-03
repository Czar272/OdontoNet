import { MIN_PASSWORD_LENGTH } from "../../components/users/userFormData";

export { MIN_PASSWORD_LENGTH };

export const MAX_PASSWORD_LENGTH = 128;

/** Validación local de una contraseña nueva y su confirmación (ODON-54). */
export function validateNewPassword(
  password: string,
  confirmation: string,
): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`;
  }
  if (password.length > MAX_PASSWORD_LENGTH) {
    return `La contraseña debe tener como máximo ${MAX_PASSWORD_LENGTH} caracteres.`;
  }
  if (password !== confirmation) {
    return "Las contraseñas no coinciden.";
  }
  return null;
}
