import type { Role } from "./auth";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  clinic_id: number;
  is_active: boolean;
}

/** Alta por administración. La clínica la asigna el backend. */
export interface CreateUserDTO {
  name: string;
  email: string;
  password: string;
  role: Role;
}

/** Edición parcial: solo se envían los campos que cambian. */
export type UpdateUserDTO = Partial<CreateUserDTO>;
