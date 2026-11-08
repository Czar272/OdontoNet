import type { CreateUserDTO, UpdateUserDTO, User } from "../../types/user";

// Igual que el backend (ODON-230): 10 caracteres; el backend además rechaza las
// contraseñas filtradas más comunes y su mensaje se muestra tal cual.
export const MIN_PASSWORD_LENGTH = 10;

export function initialUserData(user?: User): CreateUserDTO {
  return {
    name: user?.name ?? "",
    email: user?.email ?? "",
    password: "",
    role: user?.role ?? "doctor",
  };
}

/** Campos modificados respecto al usuario original; la contraseña solo si se escribió. */
export function buildUserChanges(user: User, data: CreateUserDTO): UpdateUserDTO {
  const changes: UpdateUserDTO = {};

  if (data.name.trim() !== user.name) changes.name = data.name.trim();
  if (data.email.trim() !== user.email) changes.email = data.email.trim();
  if (data.role !== user.role) changes.role = data.role;
  if (data.password) changes.password = data.password;

  return changes;
}
