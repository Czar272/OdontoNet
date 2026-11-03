import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Input from "../basic/Input";
import Select from "../basic/Select";
import PatientPicker from "./PatientPicker";
import {
  createAppointment,
  updateAppointment,
} from "../../services/appointmentService";
import { getDoctors } from "../../services/doctorService";
import type { Appointment } from "../../types/appointment";
import {
  appointmentErrorMessage,
  appointmentToFormData,
  isOutsideSchedule,
  buildAppointmentChanges,
  buildCreateAppointment,
  DURATION_OPTIONS,
  type AppointmentFormData,
} from "../../pages/Agenda/appointmentFormData";

interface AppointmentFormProps {
  /** Con cita: reprogramar. Sin cita: agendar con `initialData`. */
  appointment?: Appointment;
  initialData?: AppointmentFormData;
  onSaved: (appointment: Appointment) => void;
  onCancel: () => void;
}

export default function AppointmentForm({
  appointment,
  initialData,
  onSaved,
  onCancel,
}: AppointmentFormProps) {
  const queryClient = useQueryClient();
  const isEdit = Boolean(appointment);

  const [formData, setFormData] = useState<AppointmentFormData>(() =>
    appointment
      ? appointmentToFormData(appointment)
      : (initialData as AppointmentFormData),
  );
  const [patient, setPatient] = useState<{ id: number; name: string } | null>(
    () =>
      appointment
        ? {
            id: appointment.patient.id,
            name: `${appointment.patient.first_name} ${appointment.patient.last_name}`,
          }
        : null,
  );
  const [error, setError] = useState<string | null>(null);
  // Aviso de «fuera de horario» (ODON-142): se puede guardar de todas formas.
  const [outsideWarning, setOutsideWarning] = useState<string | null>(null);

  // Solo doctores activos; el actual se conserva aunque se haya desactivado.
  const { data: activeDoctors } = useQuery({
    queryKey: ["doctors", { active: true }],
    queryFn: () => getDoctors({ active: true }),
  });
  const doctorOptions = [...(activeDoctors ?? [])];
  if (
    appointment &&
    !doctorOptions.some((d) => d.id === appointment.doctor_id)
  ) {
    doctorOptions.push(appointment.doctor);
  }

  const durations = DURATION_OPTIONS.includes(Number(formData.duration_minutes))
    ? DURATION_OPTIONS
    : [...DURATION_OPTIONS, Number(formData.duration_minutes)].sort(
        (a, b) => a - b,
      );

  const mutation = useMutation({
    mutationFn: (allowOutsideSchedule: boolean) => {
      const confirm = allowOutsideSchedule
        ? { allow_outside_schedule: true }
        : {};
      if (appointment) {
        return updateAppointment(appointment.id, {
          ...buildAppointmentChanges(appointment, formData),
          ...confirm,
        });
      }
      const data = buildCreateAppointment({
        ...formData,
        patient_id: patient?.id ?? null,
      });
      if (!data) throw new Error("Formulario incompleto");
      return createAppointment({ ...data, ...confirm });
    },

    onSuccess: (saved) => {
      toast.success(isEdit ? "Cita reprogramada" : "Cita agendada");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      onSaved(saved);
    },

    onError: (err) => {
      if (isOutsideSchedule(err)) {
        setOutsideWarning(
          appointmentErrorMessage(err, "Fuera del horario del doctor"),
        );
        return;
      }
      const message = appointmentErrorMessage(
        err,
        isEdit
          ? "No se pudo reprogramar la cita"
          : "No se pudo agendar la cita",
      );
      setError(message);
      toast.error(message);
    },
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError(null);
    setOutsideWarning(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!patient) {
      setError("Selecciona un paciente.");
      return;
    }
    if (
      appointment &&
      Object.keys(buildAppointmentChanges(appointment, formData)).length === 0
    ) {
      toast("No hay cambios que guardar");
      return;
    }

    mutation.mutate(false);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <PatientPicker
        value={patient}
        onChange={(selected) => {
          setPatient(selected);
          setError(null);
        }}
        disabled={isEdit}
      />

      <Select
        name="doctor_id"
        label="Doctor *"
        value={formData.doctor_id}
        onChange={handleChange}
        required
      >
        <option value="">Selecciona un doctor</option>
        {doctorOptions.map((doctor) => (
          <option key={doctor.id} value={doctor.id}>
            {doctor.user.name}
            {doctor.user.is_active ? "" : " (inactivo)"}
          </option>
        ))}
      </Select>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          name="date"
          type="date"
          label="Fecha *"
          value={formData.date}
          onChange={handleChange}
          required
        />
        <Input
          name="time"
          type="time"
          label="Hora *"
          value={formData.time}
          onChange={handleChange}
          step={300}
          required
        />
        <Select
          name="duration_minutes"
          label="Duración"
          value={formData.duration_minutes}
          onChange={handleChange}
        >
          {durations.map((minutes) => (
            <option key={minutes} value={minutes}>
              {minutes} min
            </option>
          ))}
        </Select>
      </div>

      <Input
        name="reason"
        label="Motivo"
        placeholder="Limpieza, control, evaluación..."
        value={formData.reason}
        onChange={handleChange}
        maxLength={255}
      />

      {error && (
        <p
          role="alert"
          className="text-sm text-red-700 bg-red-50 rounded-xl p-3"
        >
          {error}
        </p>
      )}

      {outsideWarning && (
        <div
          role="alert"
          className="flex flex-col gap-3 text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-xl p-3"
        >
          <p>{outsideWarning}</p>
          <div className="flex justify-end">
            <Button
              variant="secondary"
              onClick={() => mutation.mutate(true)}
              disabled={mutation.isPending}
            >
              {isEdit ? "Guardar de todas formas" : "Agendar de todas formas"}
            </Button>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={onCancel}
          disabled={mutation.isPending}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending
            ? "Guardando..."
            : isEdit
              ? "Guardar cambios"
              : "Agendar cita"}
        </Button>
      </div>
    </form>
  );
}
