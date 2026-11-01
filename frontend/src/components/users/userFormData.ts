import type { CreateUserDTO, UpdateUserDTO, User } from "../../types/user";

export const MIN_PASSWORD_LENGTH = 8;

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
