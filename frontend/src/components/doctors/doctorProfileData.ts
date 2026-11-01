import type { Doctor, DoctorProfileDTO } from "../../types/doctor";

export interface DoctorProfileFormData {
  specialization: string;
  license_number: string;
  phone: string;
}

export function initialProfileData(doctor?: Doctor): DoctorProfileFormData {
  return {
    specialization: doctor?.specialization ?? "",
    license_number: doctor?.license_number ?? "",
    phone: doctor?.phone ?? "",
  };
}

/** Campos que cambiaron; un campo vaciado se envía como "" y el backend lo borra. */
export function buildProfileChanges(
  doctor: Doctor,
  data: DoctorProfileFormData,
): DoctorProfileDTO {
  const changes: DoctorProfileDTO = {};
  const fields = ["specialization", "license_number", "phone"] as const;

  for (const field of fields) {
    const value = data[field].trim();
    if (value !== (doctor[field] ?? "")) changes[field] = value;
  }

  return changes;
}
