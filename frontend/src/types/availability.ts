/** Un bloque del horario semanal (ODON-142). weekday: 0 = lunes … 6 = domingo. */
export interface AvailabilityBlock {
  weekday: number;
  /** "08:00:00" desde la API; se acepta "08:00" al enviar. */
  start_time: string;
  end_time: string;
}

export interface DoctorAvailability {
  doctor_id: number;
  /** Zona de la clínica: las horas son hora local de la clínica. */
  timezone: string;
  /** Vacío: sin horario registrado, se agenda libremente. */
  blocks: AvailabilityBlock[];
}

export const WEEKDAY_NAMES = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];
