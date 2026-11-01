import type { Role } from "./auth";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  clinic_id: number;
}
