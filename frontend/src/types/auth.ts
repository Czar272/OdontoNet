export type Role = "admin" | "doctor" | "receptionist";

/** Roles que pueden tener perfil de doctor (igual que el backend). */
export const CLINICAL_PROFILE_ROLES: readonly Role[] = ["admin", "doctor"];

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
  /** Segundos de validez del token. */
  expires_in: number;
}
