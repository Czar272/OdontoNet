export interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  birth_date?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  assigned_doctor?: string | null;
}

export interface CreatePatientDTO {
  first_name: string;
  last_name: string;
  birth_date?: string;
  phone?: string;
  email?: string;
  address?: string;
  assigned_doctor?: string | null;
}
