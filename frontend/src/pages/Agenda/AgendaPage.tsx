import { useMemo, useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import FullCalendar from "@fullcalendar/react";
import type {
  DateSelectArg,
  DatesSetArg,
  EventClickArg,
  EventDropArg,
  EventInput,
} from "@fullcalendar/core";
import esLocale from "@fullcalendar/core/locales/es";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, {
  type EventResizeDoneArg,
} from "@fullcalendar/interaction";
import timeGridPlugin from "@fullcalendar/timegrid";
import clsx from "clsx";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Modal from "../../components/basic/Modal";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import AppointmentForm from "../../components/appointments/AppointmentForm";
import AppointmentStatusPanel from "../../components/appointments/AppointmentStatusPanel";
import { usePermission } from "../../hooks/usePermission";
import {
  getAppointments,
  updateAppointment,
} from "../../services/appointmentService";
import { getDoctors } from "../../services/doctorService";
import {
  APPOINTMENT_STATUSES,
  PENDING_STATUSES,
  STATUS_COLORS,
  STATUS_LABELS,
  type Appointment,
  type AppointmentStatus,
  type UpdateAppointmentDTO,
} from "../../types/appointment";
import {
  appointmentErrorMessage,
  durationBetween,
  formatDay,
  formatTimeRange,
  newAppointmentData,
  toLocalIso,
  type AppointmentFormData,
} from "./appointmentFormData";
import ConfirmationsList from "./ConfirmationsList";
import { toConfirmQuery } from "./confirmations";

// Canceladas y No asistió se ocultan por defecto: no ocupan el horario.
const DEFAULT_VISIBLE: AppointmentStatus[] = [
  "scheduled",
  "confirmed",
  "completed",
];

type ModalState =
  | { kind: "create"; data: AppointmentFormData }
  | { kind: "detail"; appointment: Appointment }
  | { kind: "edit"; appointment: Appointment }
  | null;

function currentMinute(): Date {
  const now = new Date();
  now.setSeconds(0, 0);
  return now;
}

function isReschedulable(appointment: Appointment): boolean {
  return (
    PENDING_STATUSES.includes(appointment.status) &&
    new Date(appointment.starts_at) >= currentMinute()
  );
}

function AppointmentDetail({
  appointment,
  canManage,
  onEdit,
  onChanged,
}: {
  appointment: Appointment;
  canManage: boolean;
  onEdit: () => void;
  onChanged: (updated: Appointment) => void;
}) {
  const rows: [string, React.ReactNode][] = [
    [
      "Paciente",
      <Link
        to={`/patients/${appointment.patient.id}`}
        className="font-medium underline hover:text-gray-700"
      >
        {appointment.patient.first_name} {appointment.patient.last_name}
      </Link>,
    ],
    ["Doctor", appointment.doctor.user.name],
    ["Fecha", formatDay(appointment.starts_at)],
    [
      "Horario",
      `${formatTimeRange(appointment.starts_at, appointment.ends_at)} (${appointment.duration_minutes} min)`,
    ],
    ["Motivo", appointment.reason ?? "—"],
  ];

  return (
    <div>
      <span
        className="inline-block mb-4 px-3 py-1 rounded-full text-sm text-white"
        style={{ backgroundColor: STATUS_COLORS[appointment.status] }}
      >
        {STATUS_LABELS[appointment.status]}
      </span>

      <dl className="grid grid-cols-[auto,1fr] gap-x-6 gap-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-gray-500">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      {canManage && isReschedulable(appointment) && (
        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={onEdit}>
            Reprogramar
          </Button>
        </div>
      )}

      <AppointmentStatusPanel
        appointment={appointment}
        canManage={canManage}
        onChanged={onChanged}
      />
    </div>
  );
}

/** Agenda compartida de la clínica (ODON-138). */
export default function AgendaPage() {
  const queryClient = useQueryClient();
  const canManage = usePermission("appointments:manage");

  const [range, setRange] = useState<{ start: string; end: string } | null>(
    null,
  );
  const [doctorFilter, setDoctorFilter] = useState<number | undefined>();
  const [visible, setVisible] = useState<AppointmentStatus[]>(DEFAULT_VISIBLE);
  const [modal, setModal] = useState<ModalState>(null);
  const [tab, setTab] = useState<"calendar" | "to-confirm">("calendar");

  // Contador de la pestaña «Por confirmar» (próximos 7 días).
  const { data: toConfirm } = useQuery(toConfirmQuery(7));

  // Todos los doctores, incluidos inactivos: sus citas siguen en la agenda.
  const { data: doctors } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });

  // El rango lo decide la vista del calendario (semana, día o mes).
  const {
    data: appointments,
    isError,
    isFetching,
  } = useQuery({
    queryKey: ["appointments", "range", { ...range, doctorFilter }],
    queryFn: () =>
      getAppointments({
        start: range?.start,
        end: range?.end,
        doctorId: doctorFilter,
      }),
    enabled: range !== null,
    placeholderData: keepPreviousData,
  });

  const events: EventInput[] = useMemo(
    () =>
      (appointments ?? [])
        .filter((a) => visible.includes(a.status))
        .map((a) => ({
          id: String(a.id),
          title: `${a.patient.first_name} ${a.patient.last_name} · ${a.doctor.user.name}`,
          start: a.starts_at,
          end: a.ends_at,
          backgroundColor: STATUS_COLORS[a.status],
          borderColor: STATUS_COLORS[a.status],
          editable: canManage && isReschedulable(a),
          classNames:
            a.status === "cancelled" ? ["line-through", "opacity-70"] : [],
          extendedProps: { appointment: a },
        })),
    [appointments, visible, canManage],
  );

  const moveMutation = useMutation({
    mutationFn: ({
      id,
      changes,
    }: {
      id: number;
      changes: UpdateAppointmentDTO;
      revert: () => void;
    }) => updateAppointment(id, changes),
    onSuccess: () => {
      toast.success("Cita reprogramada");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (error, { revert }) => {
      revert();
      toast.error(
        appointmentErrorMessage(error, "No se pudo reprogramar la cita"),
      );
    },
  });

  const handleDatesSet = (arg: DatesSetArg) => {
    setRange({ start: toLocalIso(arg.start), end: toLocalIso(arg.end) });
  };

  const handleSelect = (arg: DateSelectArg) => {
    arg.view.calendar.unselect();
    if (arg.allDay) {
      // En la vista de mes, elegir un día abre ese día con sus horas.
      arg.view.calendar.changeView("timeGridDay", arg.start);
      return;
    }
    setModal({
      kind: "create",
      data: newAppointmentData(
        arg.start,
        durationBetween(arg.start, arg.end),
        doctorFilter,
      ),
    });
  };

  const handleEventClick = (arg: EventClickArg) => {
    setModal({
      kind: "detail",
      appointment: arg.event.extendedProps.appointment as Appointment,
    });
  };

  const handleMove = (arg: EventDropArg | EventResizeDoneArg) => {
    const appointment = arg.event.extendedProps.appointment as Appointment;
    const { start, end } = arg.event;
    if (!start || !end) {
      arg.revert();
      return;
    }
    const changes: UpdateAppointmentDTO = {};
    if (start.getTime() !== new Date(appointment.starts_at).getTime()) {
      changes.starts_at = toLocalIso(start);
    }
    const minutes = durationBetween(start, end);
    if (minutes !== appointment.duration_minutes)
      changes.duration_minutes = minutes;

    moveMutation.mutate({ id: appointment.id, changes, revert: arg.revert });
  };

  const toggleStatus = (status: AppointmentStatus) => {
    setVisible((current) =>
      current.includes(status)
        ? current.filter((s) => s !== status)
        : [...current, status],
    );
  };

  const openCreate = () => {
    // Próxima media hora como sugerencia.
    const start = currentMinute();
    start.setMinutes(start.getMinutes() < 30 ? 30 : 60, 0, 0);
    setModal({
      kind: "create",
      data: newAppointmentData(start, undefined, doctorFilter),
    });
  };

  const closeModal = () => setModal(null);

  return (
    <div>
      <PageHeader
        title="Agenda"
        description="Citas de la clínica en tu hora local"
        action={canManage && <Button onClick={openCreate}>Nueva cita</Button>}
      />

      <div
        role="tablist"
        aria-label="Vistas de la agenda"
        className="flex gap-2 mb-6"
      >
        {(
          [
            ["calendar", "Calendario"],
            ["to-confirm", "Por confirmar"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition",
              tab === value
                ? "bg-gray-900 text-white"
                : "bg-white text-gray-700 hover:bg-gray-100",
            )}
          >
            {label}
            {value === "to-confirm" && (toConfirm?.length ?? 0) > 0 && (
              <span
                aria-label={`${toConfirm?.length} por confirmar en 7 días`}
                className={clsx(
                  "px-2 py-0.5 rounded-full text-xs",
                  tab === value
                    ? "bg-white text-gray-900"
                    : "bg-amber-100 text-amber-800",
                )}
              >
                {toConfirm?.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "to-confirm" && <ConfirmationsList canManage={canManage} />}

      <div hidden={tab !== "calendar"}>
        <div className="flex flex-wrap items-end gap-4 mb-4">
          <Select
            aria-label="Filtrar por doctor"
            value={doctorFilter ?? ""}
            onChange={(e) =>
              setDoctorFilter(
                e.target.value ? Number(e.target.value) : undefined,
              )
            }
          >
            <option value="">Todos los doctores</option>
            {doctors?.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.user.name}
                {doctor.user.is_active ? "" : " (inactivo)"}
              </option>
            ))}
          </Select>

          <div
            role="group"
            aria-label="Estados visibles"
            className="flex flex-wrap gap-2"
          >
            {APPOINTMENT_STATUSES.map((status) => {
              const active = visible.includes(status);
              return (
                <button
                  key={status}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleStatus(status)}
                  className={clsx(
                    "flex items-center gap-2 px-3 py-2 rounded-full border text-sm transition",
                    active
                      ? "bg-white border-gray-300"
                      : "bg-gray-100 border-transparent text-gray-400",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className="w-3 h-3 rounded-full"
                    style={{
                      backgroundColor: active
                        ? STATUS_COLORS[status]
                        : "#d1d5db",
                    }}
                  />
                  {STATUS_LABELS[status]}
                </button>
              );
            })}
          </div>

          {isFetching && (
            <span className="text-sm text-gray-500">Actualizando…</span>
          )}
        </div>

        {isError && (
          <p
            role="alert"
            className="mb-4 text-sm text-red-700 bg-red-50 rounded-xl p-3"
          >
            No se pudieron cargar las citas.
          </p>
        )}

        <div className="bg-white rounded-2xl shadow-sm p-4">
          <FullCalendar
            plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
            locale={esLocale}
            initialView="timeGridWeek"
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: "dayGridMonth,timeGridWeek,timeGridDay",
            }}
            firstDay={1}
            allDaySlot={false}
            slotMinTime="07:00:00"
            slotMaxTime="21:00:00"
            scrollTime="08:00:00"
            slotDuration="00:15:00"
            slotLabelInterval="01:00"
            nowIndicator
            height="auto"
            events={events}
            datesSet={handleDatesSet}
            selectable={canManage}
            selectMirror
            selectAllow={(info) => info.allDay || info.start >= currentMinute()}
            select={handleSelect}
            eventClick={handleEventClick}
            eventAllow={(info) => info.start >= currentMinute()}
            eventDrop={handleMove}
            eventResize={handleMove}
            eventTimeFormat={{
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }}
          />
        </div>
      </div>

      <Modal
        isOpen={modal !== null}
        onClose={closeModal}
        title={
          modal?.kind === "create"
            ? "Nueva cita"
            : modal?.kind === "edit"
              ? "Reprogramar cita"
              : "Detalle de la cita"
        }
      >
        {modal?.kind === "create" && (
          <AppointmentForm
            initialData={modal.data}
            onSaved={closeModal}
            onCancel={closeModal}
          />
        )}
        {modal?.kind === "edit" && (
          <AppointmentForm
            appointment={modal.appointment}
            onSaved={closeModal}
            onCancel={closeModal}
          />
        )}
        {modal?.kind === "detail" && (
          <AppointmentDetail
            appointment={modal.appointment}
            canManage={canManage}
            onEdit={() =>
              setModal({ kind: "edit", appointment: modal.appointment })
            }
            onChanged={(updated) =>
              setModal({ kind: "detail", appointment: updated })
            }
          />
        )}
      </Modal>
    </div>
  );
}
