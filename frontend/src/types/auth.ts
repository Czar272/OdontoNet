export type Role = "admin" | "doctor" | "receptionist";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administración",
  doctor: "Doctor",
  receptionist: "Recepción",
};

export interface CurrentUser {
  id: number;
  name: string;
  email: string;
  role: Role;
  clinic: {
    id: number;
    name: string;
  };
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}
