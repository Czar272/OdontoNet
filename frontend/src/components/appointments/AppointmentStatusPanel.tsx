import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Button from "../basic/Button";
import Input from "../basic/Input";
import {
  actionLabel,
  availableTransitions,
} from "../../pages/Agenda/appointmentStatus";
import { getAppointmentHistory } from "../../services/appointmentService";
import {
  STATUS_LABELS,
  type Appointment,
  type AppointmentStatus,
} from "../../types/appointment";
import { useChangeAppointmentStatus } from "./useChangeAppointmentStatus";

const dateTimeFormat = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
  hour12: false,
});

interface AppointmentStatusPanelProps {
  appointment: Appointment;
  canManage: boolean;
  onChanged: (updated: Appointment) => void;
}

/** Acciones de estado con nota opcional e historial de la cita (ODON-148). */
export default function AppointmentStatusPanel({
  appointment,
  canManage,
  onChanged,
}: AppointmentStatusPanelProps) {
  const [pending, setPending] = useState<AppointmentStatus | null>(null);
  const [note, setNote] = useState("");

  const mutation = useChangeAppointmentStatus((updated) => {
    setPending(null);
    setNote("");
    onChanged(updated);
  });

  const { data: history } = useQuery({
    queryKey: ["appointments", appointment.id, "history"],
    queryFn: () => getAppointmentHistory(appointment.id),
  });

  const actions = canManage ? availableTransitions(appointment) : [];

  return (
    <div className="mt-6 border-t pt-6 flex flex-col gap-6">
      {actions.length > 0 && (
        <section aria-label="Cambiar estado">
          <h3 className="font-semibold mb-3">Cambiar estado</h3>

          {pending === null ? (
            <div className="flex flex-wrap gap-2">
              {actions.map((target) => (
                <Button
                  key={target}
                  variant={
                    target === "cancelled"
                      ? "danger"
                      : target === "confirmed"
                        ? "primary"
                        : "secondary"
                  }
                  onClick={() => setPending(target)}
                >
                  {actionLabel(appointment.status, target)}
                </Button>
              ))}
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                mutation.mutate({ appointment, status: pending, note });
              }}
              className="flex flex-col gap-3"
            >
              <Input
                label={`Nota para «${actionLabel(appointment.status, pending)}» (opcional)`}
                placeholder="Ej.: Confirmó por teléfono"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={255}
                autoFocus
              />
              <div className="flex justify-end gap-3">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPending(null);
                    setNote("");
                  }}
                  disabled={mutation.isPending}
                >
                  Volver
                </Button>
                <Button
                  type="submit"
                  variant={pending === "cancelled" ? "danger" : "primary"}
                  disabled={mutation.isPending}
                >
                  {mutation.isPending
                    ? "Guardando..."
                    : actionLabel(appointment.status, pending)}
                </Button>
              </div>
            </form>
          )}
        </section>
      )}

      <section aria-label="Historial de estados">
        <h3 className="font-semibold mb-3">Historial</h3>
        {history && history.length > 0 ? (
          <ol className="flex flex-col gap-2 text-sm">
            {history.map((entry) => (
              <li key={entry.id} className="flex flex-col">
                <span>
                  {entry.from_status
                    ? `${STATUS_LABELS[entry.from_status]} → ${STATUS_LABELS[entry.to_status]}`
                    : `Creada como ${STATUS_LABELS[entry.to_status].toLowerCase()}`}
                  {entry.note && (
                    <span className="text-gray-600"> · {entry.note}</span>
                  )}
                </span>
                <span className="text-xs text-gray-500">
                  {entry.changed_by.name} ·{" "}
                  {dateTimeFormat.format(new Date(entry.changed_at))}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-gray-500">Sin cambios registrados.</p>
        )}
      </section>
    </div>
  );
}
