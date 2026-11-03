import type { Clinic, UpdateClinicDTO } from "../../types/clinic";

export interface ClinicFormData {
  name: string;
  address: string;
  phone: string;
  email: string;
  timezone: string;
}

const FIELDS = ["name", "address", "phone", "email", "timezone"] as const;

/** Zonas de América (más la actual si es de otra región), por nombre. */
export function timezoneOptions(current: string): string[] {
  const all =
    typeof Intl.supportedValuesOf === "function"
      ? Intl.supportedValuesOf("timeZone")
      : ["America/Guatemala"];
  const america = all.filter((zone) => zone.startsWith("America/"));
  return [...new Set([current, ...america])].filter(Boolean).sort();
}

export function initialClinicData(clinic?: Clinic): ClinicFormData {
  return {
    name: clinic?.name ?? "",
    address: clinic?.address ?? "",
    phone: clinic?.phone ?? "",
    email: clinic?.email ?? "",
    timezone: clinic?.timezone ?? "America/Guatemala",
  };
}

/** Campos modificados (recortados); un campo vaciado se envía como "". */
export function buildClinicChanges(
  clinic: Clinic,
  data: ClinicFormData,
): UpdateClinicDTO {
  const changes: UpdateClinicDTO = {};

  for (const field of FIELDS) {
    const value = data[field].trim();
    if (value !== (clinic[field] ?? "")) changes[field] = value;
  }

  return changes;
}
