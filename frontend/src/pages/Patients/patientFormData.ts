import type { Patient, UpdatePatientDTO } from "../../types/patient";

export interface PatientFormData {
  first_name: string;
  last_name: string;
  birth_date: string;
  phone: string;
  email: string;
  address: string;
  /** "" = sin doctor. */
  doctor_id: string;
}

const TEXT_FIELDS = ["first_name", "last_name", "birth_date", "phone", "email", "address"] as const;

export function initialPatientData(patient: Patient): PatientFormData {
  return {
    first_name: patient.first_name,
    last_name: patient.last_name,
    birth_date: patient.birth_date ?? "",
    phone: patient.phone ?? "",
    email: patient.email ?? "",
    address: patient.address ?? "",
    doctor_id: patient.doctor_id ? String(patient.doctor_id) : "",
  };
}

/** Campos modificados; un texto vaciado se envía como "" y "sin doctor" como null. */
export function buildPatientChanges(patient: Patient, data: PatientFormData): UpdatePatientDTO {
  const changes: UpdatePatientDTO = {};

  for (const field of TEXT_FIELDS) {
    const value = data[field].trim();
    if (value !== (patient[field] ?? "")) changes[field] = value;
  }

  const doctorId = data.doctor_id ? Number(data.doctor_id) : null;
  if (doctorId !== (patient.doctor_id ?? null)) changes.doctor_id = doctorId;

  return changes;
}

/** Edad en años cumplidos, o null sin fecha. */
export function ageFrom(birthDate: string | null | undefined, today = new Date()): number | null {
  if (!birthDate) return null;

  const [year, month, day] = birthDate.split("-").map(Number);
  const age = today.getFullYear() - year;
  const beforeBirthday =
    today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day);

  return beforeBirthday ? age - 1 : age;
}
