export interface Clinic {
  id: number;
  name: string;
  address: string | null;
  phone: string | null;
  email: string | null;
}

/** Edición parcial. "" en dirección, teléfono o correo borra el dato. */
export interface UpdateClinicDTO {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
}
