export interface Doctor {
  id: number;
  user_id: number;
  specialization?: string | null;
  license_number?: string | null;
  phone?: string | null;
}
