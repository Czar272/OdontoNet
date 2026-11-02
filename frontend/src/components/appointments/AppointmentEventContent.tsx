import clsx from "clsx";

import {
  doctorInitials,
  doctorShortName,
} from "../../pages/Agenda/agendaColors";
import {
  STATUS_COLORS,
  STATUS_LABELS,
  type Appointment,
} from "../../types/appointment";

interface AppointmentEventContentProps {
  appointment: Appointment;
  doctorColor: string;
  timeText: string;
  /** Vista de mes: una sola línea. */
  compact?: boolean;
  /** Vista de semana: columnas angostas, «Dra. Morales» en vez del nombre completo. */
  shortDoctorName?: boolean;
}

/**
 * Contenido de una cita en el calendario (ODON-257): arriba el doctor con su
 * color, luego el paciente y abajo la hora y el estado. El doctor no se
 * identifica solo por el color: su nombre siempre está escrito.
 */
export default function AppointmentEventContent({
  appointment,
  doctorColor,
  timeText,
  compact = false,
  shortDoctorName = false,
}: AppointmentEventContentProps) {
  const patient = `${appointment.patient.first_name} ${appointment.patient.last_name}`;
  const status = STATUS_LABELS[appointment.status];

  if (compact) {
    return (
      <div
        className="flex items-center gap-1 overflow-hidden text-xs text-gray-900"
        title={`${timeText} · ${patient} · ${appointment.doctor.user.name} · ${status}`}
      >
        <span
          aria-hidden="true"
          className="w-2 h-2 shrink-0 rounded-full"
          style={{ backgroundColor: doctorColor }}
        />
        <span className="font-medium">{timeText}</span>
        <span className="truncate">{patient}</span>
      </div>
    );
  }

  return (
    <div
      className="odn-event-body flex flex-col h-full overflow-hidden px-1 py-0.5 leading-tight text-gray-900"
      title={`${patient} · ${appointment.doctor.user.name} · ${timeText} · ${status}`}
    >
      {/* En columnas muy angostas el CSS cambia el nombre por las iniciales. */}
      <span
        className="odn-doc-name truncate text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: doctorColor }}
      >
        {shortDoctorName
          ? doctorShortName(appointment.doctor.user.name)
          : appointment.doctor.user.name}
      </span>
      <span
        className="odn-doc-initials self-start rounded px-1 text-[10px] font-bold text-white"
        style={{ backgroundColor: doctorColor }}
        aria-hidden="true"
      >
        {doctorInitials(appointment.doctor.user.name)}
      </span>
      <span
        className={clsx(
          "truncate text-xs font-medium",
          appointment.status === "cancelled" && "line-through",
        )}
      >
        {patient}
      </span>
      <span className="flex items-center gap-1 truncate text-[11px] text-gray-600">
        <span
          aria-hidden="true"
          className="w-2 h-2 shrink-0 rounded-full"
          style={{ backgroundColor: STATUS_COLORS[appointment.status] }}
        />
        {timeText} · {status}
      </span>
    </div>
  );
}
