import type { Doctor } from "./doctor";

export interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  birth_date?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  doctor_id?: number | null;
  doctor?: Doctor | null;
  clinic_id: number;
}

/** Edición parcial: "" borra los opcionales y doctor_id null quita el doctor. */
export interface UpdatePatientDTO {
  first_name?: string;
  last_name?: string;
  birth_date?: string;
  phone?: string;
  email?: string;
  address?: string;
  doctor_id?: number | null;
}

export interface CreatePatientDTO {
  first_name: string;
  last_name: string;
  birth_date?: string;
  phone?: string;
  email?: string;
  address?: string;
  doctor_id?: number | null;
}
