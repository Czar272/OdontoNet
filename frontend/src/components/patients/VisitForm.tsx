import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Input from "../basic/Input";
import Select from "../basic/Select";
import Textarea from "../basic/Textarea";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import { createVisit, updateVisit } from "../../services/clinicalVisitService";
import { getDoctors } from "../../services/doctorService";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import {
  buildVisitContent,
  defaultDoctorId,
  initialVisitForm,
  isVisitUnchanged,
  toLocalInput,
  type VisitFormData,
} from "./visitFormData";

interface VisitFormProps {
  patientId: number;
  /** null = nueva consulta. */
  visit: ClinicalVisit | null;
  onSaved: (visit: ClinicalVisit) => void;
  onCancel: () => void;
  /** 409: otra persona guardó antes; el formulario conserva lo escrito. */
  onConflict: () => void;
}

export default function VisitForm({
  patientId,
  visit,
  onSaved,
  onCancel,
  onConflict,
}: VisitFormProps) {
  const { user } = useAuth();
  const isEdit = visit !== null;

  const { data: activeDoctors = [] } = useQuery({
    queryKey: ["doctors", { active: true }],
    queryFn: () => getDoctors({ active: true }),
  });

  // El doctor de la consulta se conserva aunque hoy esté inactivo.
  const doctorOptions = [
    ...activeDoctors.map((d) => ({ id: d.id, name: d.user.name })),
  ];
  if (visit && !doctorOptions.some((d) => d.id === visit.doctor.id)) {
    doctorOptions.push({
      ...visit.doctor,
      name: `${visit.doctor.name} (inactivo)`,
    });
  }

  const [form, setForm] = useState<VisitFormData>(() =>
    initialVisitForm(visit, ""),
  );
  // El doctor propuesto se completa cuando llega la lista de doctores.
  const doctorId =
    form.doctor_id || (isEdit ? "" : defaultDoctorId(user, activeDoctors));

  const mutation = useMutation({
    mutationFn: () => {
      const data = buildVisitContent({ ...form, doctor_id: doctorId });
      return visit
        ? updateVisit(patientId, visit.id, {
            ...data,
            base_revision: visit.revision,
          })
        : createVisit(patientId, data);
    },
    onSuccess: (saved) => {
      toast.success(isEdit ? "Consulta actualizada" : "Consulta registrada");
      onSaved(saved);
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "No se pudo guardar la consulta"));
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        onConflict();
      }
    },
  });

  const set =
    (field: keyof VisitFormData) =>
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >,
    ) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (visit && isVisitUnchanged({ ...form, doctor_id: doctorId }, visit)) {
      toast("No hay cambios que guardar");
      return;
    }
    mutation.mutate();
  };

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={isEdit ? "Editar consulta" : "Nueva consulta"}
    >
      <fieldset disabled={mutation.isPending} className="flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Fecha y hora de atención *"
            type="datetime-local"
            max={toLocalInput(new Date())}
            value={form.visit_at}
            onChange={set("visit_at")}
            required
          />

          <Select
            label="Doctor *"
            value={doctorId}
            onChange={set("doctor_id")}
            required
          >
            <option value="">Selecciona un doctor</option>
            {doctorOptions.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.name}
              </option>
            ))}
          </Select>
        </div>

        <Input
          label="Motivo de la consulta *"
          maxLength={500}
          value={form.reason}
          onChange={set("reason")}
          required
        />
        <Textarea
          label="Hallazgos / examen"
          maxLength={4000}
          rows={3}
          value={form.findings}
          onChange={set("findings")}
        />
        <Textarea
          label="Diagnóstico profesional"
          maxLength={4000}
          value={form.diagnosis}
          onChange={set("diagnosis")}
        />
        <Textarea
          label="Procedimientos realizados"
          maxLength={4000}
          value={form.procedures}
          onChange={set("procedures")}
        />
        <Textarea
          label="Indicaciones"
          maxLength={4000}
          value={form.instructions}
          onChange={set("instructions")}
        />
        <div className="sm:w-1/2">
          <Input
            label="Próxima cita sugerida"
            type="date"
            value={form.next_visit_date}
            onChange={set("next_visit_date")}
          />
        </div>
      </fieldset>

      <div className="mt-6 flex justify-end gap-3">
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
              : "Registrar consulta"}
        </Button>
      </div>
    </form>
  );
}
