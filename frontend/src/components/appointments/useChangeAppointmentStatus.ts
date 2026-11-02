import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { appointmentErrorMessage } from "../../pages/Agenda/appointmentFormData";
import { changeAppointmentStatus } from "../../services/appointmentService";
import {
  STATUS_LABELS,
  type Appointment,
  type AppointmentStatus,
} from "../../types/appointment";

interface Variables {
  appointment: Appointment;
  status: AppointmentStatus;
  note?: string;
}

/** Cambia el estado de una cita y refresca agenda, lista e historial. */
export function useChangeAppointmentStatus(
  onSuccess?: (updated: Appointment) => void,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ appointment, status, note }: Variables) =>
      changeAppointmentStatus(appointment.id, status, note),

    onSuccess: (updated) => {
      toast.success(`Cita ${STATUS_LABELS[updated.status].toLowerCase()}`);
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      onSuccess?.(updated);
    },

    onError: (error) => {
      toast.error(
        appointmentErrorMessage(
          error,
          "No se pudo cambiar el estado de la cita",
        ),
      );
    },
  });
}
