export interface Clinic {
  id: number;
  name: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  /** Zona IANA; los horarios de los doctores son hora local de la clínica (ODON-142). */
  timezone: string;
}

/** Edición parcial. "" en dirección, teléfono o correo borra el dato. */
export interface UpdateClinicDTO {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
  timezone?: string;
}
