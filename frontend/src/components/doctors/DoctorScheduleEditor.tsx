import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus, Trash2 } from "lucide-react";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import { getApiErrorMessage } from "../../services/apiError";
import { updateDoctorAvailability } from "../../services/doctorService";
import {
  WEEKDAY_NAMES,
  type DoctorAvailability,
} from "../../types/availability";
import type { Doctor } from "../../types/doctor";
import {
  DEFAULT_RANGE,
  blocksToWeek,
  copyMondayToWeekdays,
  describeDay,
  validateWeek,
  weekToBlocks,
  type WeekSchedule,
} from "./scheduleData";

interface DoctorScheduleEditorProps {
  doctor: Doctor;
  availability: DoctorAvailability | undefined;
  canEdit: boolean;
  onClose: () => void;
}

const timeInput =
  "border rounded-lg px-2 py-1 outline-none focus:ring-2 focus:ring-gray-900 disabled:bg-gray-100";

/** Horario semanal del doctor (ODON-145): uno o más bloques por día. */
export default function DoctorScheduleEditor({
  doctor,
  availability,
  canEdit,
  onClose,
}: DoctorScheduleEditorProps) {
  const queryClient = useQueryClient();
  const [week, setWeek] = useState<WeekSchedule>(() =>
    blocksToWeek(availability?.blocks ?? []),
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => updateDoctorAvailability(doctor.id, weekToBlocks(week)),
    onSuccess: () => {
      toast.success("Horario guardado");
      queryClient.invalidateQueries({ queryKey: ["availability"] });
      onClose();
    },
    onError: (err) => {
      const message = getApiErrorMessage(err, "No se pudo guardar el horario");
      setError(message);
      toast.error(message);
    },
  });

  const update = (next: WeekSchedule) => {
    setWeek(next);
    setError(null);
  };

  const setRange = (
    weekday: number,
    index: number,
    field: "start" | "end",
    value: string,
  ) =>
    update(
      week.map((day, d) =>
        d === weekday
          ? day.map((r, i) => (i === index ? { ...r, [field]: value } : r))
          : day,
      ),
    );

  const addRange = (weekday: number) =>
    update(
      week.map((day, d) => {
        if (d !== weekday) return day;
        // Después del último bloque: 14:00–18:00 si ya hay mañana.
        const next =
          day.length > 0 ? { start: "14:00", end: "18:00" } : DEFAULT_RANGE;
        return [...day, next];
      }),
    );

  const removeRange = (weekday: number, index: number) =>
    update(
      week.map((day, d) =>
        d === weekday ? day.filter((_, i) => i !== index) : day,
      ),
    );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validateWeek(week);
    if (problem) {
      setError(problem);
      return;
    }
    mutation.mutate();
  };

  const empty = week.every((day) => day.length === 0);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <p className="text-sm text-gray-600">
        Horas en la zona de la clínica (
        {availability?.timezone ?? "America/Guatemala"}). Fuera de este horario
        la agenda pide confirmar antes de agendar.
        {empty && " Sin horario registrado se puede agendar a cualquier hora."}
      </p>

      <ul className="flex flex-col divide-y border rounded-xl">
        {week.map((day, weekday) => (
          <li
            key={WEEKDAY_NAMES[weekday]}
            className="flex flex-wrap items-start gap-3 p-3"
          >
            <span className="w-24 pt-1 font-medium">
              {WEEKDAY_NAMES[weekday]}
            </span>

            <div className="flex flex-1 flex-col gap-2">
              {!canEdit || day.length === 0 ? (
                canEdit ? (
                  <span className="pt-1 text-sm text-gray-400">No atiende</span>
                ) : (
                  <span className="pt-1 text-sm">{describeDay(day)}</span>
                )
              ) : (
                day.map((range, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="time"
                      step={300}
                      aria-label={`${WEEKDAY_NAMES[weekday]}, bloque ${index + 1}, desde`}
                      value={range.start}
                      onChange={(e) =>
                        setRange(weekday, index, "start", e.target.value)
                      }
                      className={timeInput}
                      required
                    />
                    <span aria-hidden="true">–</span>
                    <input
                      type="time"
                      step={300}
                      aria-label={`${WEEKDAY_NAMES[weekday]}, bloque ${index + 1}, hasta`}
                      value={range.end}
                      onChange={(e) =>
                        setRange(weekday, index, "end", e.target.value)
                      }
                      className={timeInput}
                      required
                    />
                    <button
                      type="button"
                      onClick={() => removeRange(weekday, index)}
                      aria-label={`Quitar bloque ${index + 1} del ${WEEKDAY_NAMES[weekday].toLowerCase()}`}
                      className="p-1 rounded-lg text-gray-500 hover:bg-gray-100"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))
              )}
            </div>

            {canEdit && (
              <button
                type="button"
                onClick={() => addRange(weekday)}
                aria-label={`Agregar bloque al ${WEEKDAY_NAMES[weekday].toLowerCase()}`}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-sm text-gray-700 hover:bg-gray-100"
              >
                <Plus size={16} /> Bloque
              </button>
            )}
          </li>
        ))}
      </ul>

      {error && (
        <p
          role="alert"
          className="text-sm text-red-700 bg-red-50 rounded-xl p-3"
        >
          {error}
        </p>
      )}

      <div className="flex flex-wrap justify-between gap-3">
        {canEdit ? (
          <Button
            variant="secondary"
            onClick={() => update(copyMondayToWeekdays(week))}
          >
            <span className="flex items-center gap-2">
              <Copy size={16} /> Copiar lunes a martes–viernes
            </span>
          </Button>
        ) : (
          <span />
        )}

        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            {canEdit ? "Cancelar" : "Cerrar"}
          </Button>
          {canEdit && (
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Guardando..." : "Guardar horario"}
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}
