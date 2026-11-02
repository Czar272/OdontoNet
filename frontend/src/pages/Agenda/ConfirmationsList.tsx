import { Fragment, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Phone } from "lucide-react";
import { Link } from "react-router-dom";

import Button from "../../components/basic/Button";
import ConfirmDialog from "../../components/basic/ConfirmDialog";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import Select from "../../components/basic/Select";
import Table from "../../components/basic/Table";
import { useChangeAppointmentStatus } from "../../components/appointments/useChangeAppointmentStatus";
import type { Appointment } from "../../types/appointment";
import { formatDay, formatTimeRange } from "./appointmentFormData";
import {
  CONFIRMATION_WINDOWS,
  groupByDay,
  toConfirmQuery,
  type ConfirmationWindow,
} from "./confirmations";

/**
 * Citas programadas pero no confirmadas, para que recepción llame y confirme
 * o cancele desde la misma lista (ODON-146).
 */
export default function ConfirmationsList({
  canManage,
}: {
  canManage: boolean;
}) {
  const [days, setDays] = useState<ConfirmationWindow>(7);
  const [cancelling, setCancelling] = useState<Appointment | null>(null);
  const [note, setNote] = useState("");

  const { data, isLoading, isError, isFetching } = useQuery({
    ...toConfirmQuery(days),
    placeholderData: keepPreviousData,
  });

  const mutation = useChangeAppointmentStatus(() => {
    setCancelling(null);
    setNote("");
  });

  if (isLoading) return <LoadingSpinner />;

  const appointments = data ?? [];
  // Agrupadas por día local y en orden: más fácil de llamar en secuencia.
  const groups = groupByDay(appointments);
  const columns = canManage ? 5 : 4;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <p className="text-gray-600">
          Citas programadas que aún no se confirman. Llama al paciente y
          registra su respuesta.
        </p>
        <Select
          aria-label="Periodo"
          value={days}
          onChange={(e) =>
            setDays(Number(e.target.value) as ConfirmationWindow)
          }
        >
          {CONFIRMATION_WINDOWS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <Table>
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left p-4">Hora</th>
            <th className="text-left p-4">Paciente</th>
            <th className="text-left p-4">Doctor</th>
            <th className="text-left p-4">Motivo</th>
            {canManage && <th className="text-right p-4">Acciones</th>}
          </tr>
        </thead>

        <tbody
          className={isFetching ? "opacity-60 transition-opacity" : undefined}
        >
          {groups.map((day) => (
            <Fragment key={day.key}>
              <tr className="border-t bg-gray-50">
                <th
                  colSpan={columns}
                  scope="rowgroup"
                  className="text-left px-4 py-2 text-sm font-semibold text-gray-700"
                >
                  {day.label} ·{" "}
                  {day.items.length === 1
                    ? "1 cita"
                    : `${day.items.length} citas`}
                </th>
              </tr>
              {day.items.map((appointment) => {
                const name = `${appointment.patient.first_name} ${appointment.patient.last_name}`;
                return (
                  <tr key={appointment.id} className="border-t">
                    <td className="p-4 whitespace-nowrap">
                      {formatTimeRange(
                        appointment.starts_at,
                        appointment.ends_at,
                      )}
                    </td>
                    <td className="p-4">
                      <Link
                        to={`/patients/${appointment.patient.id}`}
                        className="font-medium hover:underline"
                      >
                        {name}
                      </Link>
                      {appointment.patient.phone ? (
                        <a
                          href={`tel:${appointment.patient.phone}`}
                          className="flex items-center gap-1 text-sm text-gray-600 hover:underline"
                        >
                          <Phone size={14} aria-hidden="true" />{" "}
                          {appointment.patient.phone}
                        </a>
                      ) : (
                        <span className="block text-sm text-gray-400">
                          Sin teléfono
                        </span>
                      )}
                    </td>
                    <td className="p-4">{appointment.doctor.user.name}</td>
                    <td className="p-4">{appointment.reason ?? "—"}</td>
                    {canManage && (
                      <td className="p-4">
                        <div className="flex justify-end gap-2">
                          <Button
                            aria-label={`Confirmar cita de ${name}`}
                            onClick={() =>
                              mutation.mutate({
                                appointment,
                                status: "confirmed",
                                note: "Confirmada desde la lista de por confirmar",
                              })
                            }
                            disabled={mutation.isPending}
                          >
                            Confirmar
                          </Button>
                          <Button
                            variant="secondary"
                            aria-label={`Cancelar cita de ${name}`}
                            onClick={() => setCancelling(appointment)}
                            disabled={mutation.isPending}
                          >
                            Cancelar
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </Fragment>
          ))}

          {appointments.length === 0 && (
            <tr className="border-t">
              <td colSpan={columns} className="p-6 text-center text-gray-500">
                {isError
                  ? "No se pudieron cargar las citas."
                  : "No hay citas pendientes de confirmar en este periodo."}
              </td>
            </tr>
          )}
        </tbody>
      </Table>

      <ConfirmDialog
        isOpen={cancelling !== null}
        title="Cancelar cita"
        message={
          cancelling && (
            <div className="flex flex-col gap-4">
              <p>
                Se cancelará la cita de{" "}
                <strong>
                  {cancelling.patient.first_name} {cancelling.patient.last_name}
                </strong>{" "}
                del {formatDay(cancelling.starts_at)} (
                {formatTimeRange(cancelling.starts_at, cancelling.ends_at)}) y
                el horario quedará libre.
              </p>
              <Input
                label="Motivo de la cancelación (opcional)"
                placeholder="Ej.: El paciente no puede asistir"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={255}
              />
            </div>
          )
        }
        confirmLabel="Cancelar cita"
        variant="danger"
        isPending={mutation.isPending}
        onConfirm={() =>
          cancelling &&
          mutation.mutate({
            appointment: cancelling,
            status: "cancelled",
            note,
          })
        }
        cancelLabel="Volver"
        onCancel={() => {
          setCancelling(null);
          setNote("");
        }}
      />
    </div>
  );
}
