import type { Clinic, UpdateClinicDTO } from "../../types/clinic";

export interface ClinicFormData {
  name: string;
  address: string;
  phone: string;
  email: string;
}

const FIELDS = ["name", "address", "phone", "email"] as const;

export function initialClinicData(clinic?: Clinic): ClinicFormData {
  return {
    name: clinic?.name ?? "",
    address: clinic?.address ?? "",
    phone: clinic?.phone ?? "",
    email: clinic?.email ?? "",
  };
}

/** Campos modificados (recortados); un campo vaciado se envía como "". */
export function buildClinicChanges(clinic: Clinic, data: ClinicFormData): UpdateClinicDTO {
  const changes: UpdateClinicDTO = {};

  for (const field of FIELDS) {
    const value = data[field].trim();
    if (value !== (clinic[field] ?? "")) changes[field] = value;
  }

  return changes;
}
