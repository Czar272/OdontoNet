import type { User } from "./user";

/** Perfil clínico de un doctor; los datos de acceso viven en `user`. */
export interface Doctor {
  id: number;
  user_id: number;
  specialization: string | null;
  license_number: string | null;
  phone: string | null;
  user: User;
  clinic_id: number;
}

/** Campos editables del perfil. "" o null borran el dato. */
export interface DoctorProfileDTO {
  specialization?: string | null;
  license_number?: string | null;
  phone?: string | null;
}

/** Alta de perfil para un usuario con rol doctor de la clínica. */
export interface CreateDoctorDTO extends DoctorProfileDTO {
  user_id: number;
}
