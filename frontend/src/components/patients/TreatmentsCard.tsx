import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, History, Pencil, Plus } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

import Button from "../basic/Button";
import Card from "../basic/Card";
import Input from "../basic/Input";
import LoadingSpinner from "../basic/LoadingSpinner";
import Modal from "../basic/Modal";
import Select from "../basic/Select";
import Textarea from "../basic/Textarea";
import { getApiErrorMessage } from "../../services/apiError";
import { getVisits } from "../../services/clinicalVisitService";
import {
  changeTreatmentStatus,
  createTreatment,
  getTreatmentHistory,
  getTreatments,
  updateTreatment,
} from "../../services/treatmentService";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import type { Treatment, TreatmentStatus } from "../../types/treatment";
import {
  TRANSITION_ACTIONS,
  TREATMENT_STATUS_LABELS,
  TREATMENT_STATUS_STYLES,
  TREATMENT_TRANSITIONS,
  buildTreatmentChanges,
  buildTreatmentDTO,
  initialTreatmentForm,
  isClosed,
  validateTreatmentForm,
  type TreatmentFormData,
} from "./treatmentStatus";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeStyle: "short",
});
const dateOnly = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "medium",
  timeZone: "UTC",
});

const formatDate = (value: string) =>
  dateOnly.format(new Date(`${value}T00:00:00Z`));

const visitLabel = (visit: { visit_at: string; reason: string }) =>
  `${dateTime.format(new Date(visit.visit_at))} · ${visit.reason}`;

function VisitSelect({
  label,
  visits,
  value,
  onChange,
  required = false,
}: {
  label: string;
  visits: ClinicalVisit[];
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <Select
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required={required}
    >
      <option value="">
        {required ? "Selecciona una consulta" : "Sin consulta"}
      </option>
      {visits.map((visit) => (
        <option key={visit.id} value={visit.id}>
          {visitLabel(visit)}
        </option>
      ))}
    </Select>
  );
}

function TreatmentForm({
  patientId,
  treatment,
  visits,
  onDone,
}: {
  patientId: number;
  treatment: Treatment | null;
  visits: ClinicalVisit[];
  onDone: () => void;
}) {
  const [form, setForm] = useState<TreatmentFormData>(() =>
    initialTreatmentForm(treatment),
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      treatment
        ? updateTreatment(
            patientId,
            treatment.id,
            buildTreatmentChanges(treatment, form),
          )
        : createTreatment(patientId, buildTreatmentDTO(form)),
    onSuccess: () => {
      toast.success(
        treatment ? "Tratamiento actualizado" : "Tratamiento registrado",
      );
      onDone();
    },
    onError: (err) =>
      setError(getApiErrorMessage(err, "No se pudo guardar el tratamiento")),
  });

  const set =
    (field: keyof TreatmentFormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const invalid = validateTreatmentForm(form);
    setError(invalid);
    if (invalid) return;
    if (
      treatment &&
      Object.keys(buildTreatmentChanges(treatment, form)).length === 0
    ) {
      toast("No hay cambios que guardar");
      return;
    }
    mutation.mutate();
  };

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={treatment ? "Editar tratamiento" : "Nuevo tratamiento"}
      className="flex flex-col gap-4"
    >
      <fieldset disabled={mutation.isPending} className="flex flex-col gap-4">
        <Input
          label="Procedimiento *"
          maxLength={300}
          value={form.procedure}
          onChange={set("procedure")}
          required
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Pieza dental (FDI)"
            inputMode="numeric"
            placeholder="Ej. 36"
            value={form.tooth}
            onChange={set("tooth")}
          />
          <Input
            label="Fecha estimada"
            type="date"
            value={form.planned_date}
            onChange={set("planned_date")}
          />
        </div>
        <VisitSelect
          label="Consulta en que se propuso"
          visits={visits}
          value={form.proposed_visit_id}
          onChange={(value) =>
            setForm((prev) => ({ ...prev, proposed_visit_id: value }))
          }
        />
        <Textarea
          label="Notas"
          maxLength={2000}
          value={form.notes}
          onChange={set("notes")}
        />
      </fieldset>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={onDone}
          disabled={mutation.isPending}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending
            ? "Guardando..."
            : treatment
              ? "Guardar cambios"
              : "Registrar tratamiento"}
        </Button>
      </div>
    </form>
  );
}

function StatusDialog({
  patientId,
  treatment,
  target,
  visits,
  onDone,
}: {
  patientId: number;
  treatment: Treatment;
  target: "completed" | "cancelled";
  visits: ClinicalVisit[];
  onDone: () => void;
}) {
  const [visitId, setVisitId] = useState("");
  const [reason, setReason] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      changeTreatmentStatus(
        patientId,
        treatment.id,
        target === "completed"
          ? { status: target, completed_visit_id: Number(visitId) }
          : { status: target, reason: reason.trim() },
      ),
    onSuccess: () => {
      toast.success(
        target === "completed"
          ? "Tratamiento completado"
          : "Tratamiento cancelado",
      );
      onDone();
    },
    onError: (err) =>
      toast.error(getApiErrorMessage(err, "No se pudo cambiar el estado")),
  });

  const ready =
    target === "completed" ? Boolean(visitId) : Boolean(reason.trim());

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
      className="flex flex-col gap-4"
    >
      <p className="text-sm text-gray-700">
        <strong>{treatment.procedure}</strong>
        {treatment.tooth ? ` · pieza ${treatment.tooth}` : ""}
      </p>

      {target === "completed" ? (
        visits.length === 0 ? (
          <p role="alert" className="text-sm text-amber-800">
            Registra primero la consulta en que se realizó el tratamiento.
          </p>
        ) : (
          <VisitSelect
            label="Consulta en que se realizó *"
            visits={visits}
            value={visitId}
            onChange={setVisitId}
            required
          />
        )
      ) : (
        <Textarea
          label="Motivo de la cancelación *"
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          required
        />
      )}

      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={onDone}
          disabled={mutation.isPending}
        >
          Volver
        </Button>
        <Button
          type="submit"
          variant={target === "cancelled" ? "danger" : "primary"}
          disabled={mutation.isPending || !ready}
        >
          {mutation.isPending
            ? "Guardando..."
            : target === "completed"
              ? "Marcar completado"
              : "Cancelar tratamiento"}
        </Button>
      </div>
    </form>
  );
}

function HistoryList({
  patientId,
  treatment,
}: {
  patientId: number;
  treatment: Treatment;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["patients", patientId, "treatments", treatment.id, "history"],
    queryFn: () => getTreatmentHistory(patientId, treatment.id),
  });

  if (isLoading) return <LoadingSpinner />;

  return (
    <ol className="flex flex-col gap-3">
      {data?.map((change, index) => (
        <li key={index} className="text-sm border-l-2 border-gray-200 pl-3">
          <p className="font-medium">
            {change.from_status
              ? `${TREATMENT_STATUS_LABELS[change.from_status]} → ${TREATMENT_STATUS_LABELS[change.to_status]}`
              : "Registrado como propuesto"}
          </p>
          <p className="text-gray-600">
            {dateTime.format(new Date(change.changed_at))} ·{" "}
            {change.changed_by.name}
          </p>
          {change.reason && (
            <p className="text-gray-700">Motivo: {change.reason}</p>
          )}
        </li>
      ))}
    </ol>
  );
}

type Dialog =
  | { kind: "form"; treatment: Treatment | null }
  | { kind: "status"; treatment: Treatment; target: "completed" | "cancelled" }
  | { kind: "history"; treatment: Treatment };

interface TreatmentsCardProps {
  patientId: number;
  canManage: boolean;
  isArchived: boolean;
}

/**
 * Plan de tratamiento del paciente (ODON-158): pendientes y cerrados, con
 * cambios de estado e historial. Completar exige la consulta en que se realizó.
 */
export default function TreatmentsCard({
  patientId,
  canManage,
  isArchived,
}: TreatmentsCardProps) {
  const queryClient = useQueryClient();
  const treatmentsKey = ["patients", patientId, "treatments"];
  const [dialog, setDialog] = useState<Dialog | null>(null);

  const { data: treatments, isLoading } = useQuery({
    queryKey: treatmentsKey,
    queryFn: () => getTreatments(patientId),
  });

  // Las mismas consultas que muestra la tarjeta de consultas; solo las vigentes.
  const { data: allVisits = [] } = useQuery({
    queryKey: ["patients", patientId, "visits"],
    queryFn: () => getVisits(patientId),
  });
  const visits = allVisits.filter((visit) => !visit.voided_at);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: treatmentsKey });
  };

  const close = () => setDialog(null);
  const closeAndRefresh = () => {
    setDialog(null);
    refresh();
  };

  const quickStatus = useMutation({
    mutationFn: ({
      treatment,
      target,
    }: {
      treatment: Treatment;
      target: TreatmentStatus;
    }) => changeTreatmentStatus(patientId, treatment.id, { status: target }),
    onSuccess: (updated) => {
      toast.success(
        `Tratamiento: ${TREATMENT_STATUS_LABELS[updated.status].toLowerCase()}`,
      );
      refresh();
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, "No se pudo cambiar el estado"));
      refresh();
    },
  });

  const writable = canManage && !isArchived;
  const pending = treatments?.filter((t) => !isClosed(t.status)) ?? [];
  const closed = treatments?.filter((t) => isClosed(t.status)) ?? [];

  const renderItem = (treatment: Treatment) => (
    <li key={treatment.id} className="rounded-xl border border-gray-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p
            className={clsx(
              "font-semibold",
              treatment.status === "cancelled" && "line-through text-gray-500",
            )}
          >
            {treatment.procedure}
            {treatment.tooth ? (
              <span className="font-normal text-gray-600">
                {" "}
                · pieza {treatment.tooth}
              </span>
            ) : null}
          </p>
          <p className="text-sm text-gray-600 mt-1">
            <span
              className={clsx(
                "inline-block rounded-full px-2 py-0.5 text-xs font-medium mr-2",
                TREATMENT_STATUS_STYLES[treatment.status],
              )}
            >
              {TREATMENT_STATUS_LABELS[treatment.status]}
            </span>
            {treatment.planned_date &&
              `Fecha estimada: ${formatDate(treatment.planned_date)} · `}
            Propuesto por {treatment.created_by.name}
          </p>
          {treatment.proposed_visit && (
            <p className="text-sm text-gray-600">
              Indicado en: {visitLabel(treatment.proposed_visit)}
            </p>
          )}
          {treatment.completed_visit && (
            <p className="text-sm text-gray-600">
              Realizado en: {visitLabel(treatment.completed_visit)}
            </p>
          )}
          {treatment.status === "cancelled" && treatment.status_reason && (
            <p className="text-sm text-red-700">
              Motivo: {treatment.status_reason}
            </p>
          )}
          {treatment.notes && (
            <p className="text-sm text-gray-800 mt-1 whitespace-pre-line">
              {treatment.notes}
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {writable &&
            TREATMENT_TRANSITIONS[treatment.status].map((target) => (
              <Button
                key={target}
                variant={target === "cancelled" ? "secondary" : "primary"}
                className="px-3 py-2 text-sm"
                disabled={quickStatus.isPending}
                onClick={() =>
                  target === "completed" || target === "cancelled"
                    ? setDialog({ kind: "status", treatment, target })
                    : quickStatus.mutate({ treatment, target })
                }
              >
                {TRANSITION_ACTIONS[target]}
              </Button>
            ))}
          {writable && !isClosed(treatment.status) && (
            <Button
              variant="secondary"
              className="px-3 py-2 text-sm"
              aria-label={`Editar ${treatment.procedure}`}
              onClick={() => setDialog({ kind: "form", treatment })}
            >
              <Pencil size={14} />
            </Button>
          )}
          <Button
            variant="secondary"
            className="px-3 py-2 text-sm"
            aria-label={`Historial de ${treatment.procedure}`}
            onClick={() => setDialog({ kind: "history", treatment })}
          >
            <History size={14} />
          </Button>
        </div>
      </div>
    </li>
  );

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <ClipboardList size={20} /> Plan de tratamiento
        </h2>
        {writable && (
          <Button onClick={() => setDialog({ kind: "form", treatment: null })}>
            <span className="flex items-center gap-2">
              <Plus size={16} /> Nuevo tratamiento
            </span>
          </Button>
        )}
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : !treatments || treatments.length === 0 ? (
        <p className="text-gray-500 text-sm">
          Este paciente aún no tiene tratamientos registrados.
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          <section>
            <h3 className="font-semibold text-gray-700 mb-3">
              Pendientes ({pending.length})
            </h3>
            {pending.length === 0 ? (
              <p className="text-sm text-gray-500">
                No hay tratamientos pendientes.
              </p>
            ) : (
              <ol
                className="flex flex-col gap-3"
                aria-label="Tratamientos pendientes"
              >
                {pending.map(renderItem)}
              </ol>
            )}
          </section>
          {closed.length > 0 && (
            <section>
              <h3 className="font-semibold text-gray-700 mb-3">
                Completados y cancelados ({closed.length})
              </h3>
              <ol
                className="flex flex-col gap-3"
                aria-label="Tratamientos cerrados"
              >
                {closed.map(renderItem)}
              </ol>
            </section>
          )}
        </div>
      )}

      <Modal
        isOpen={dialog !== null}
        onClose={close}
        title={
          dialog?.kind === "form"
            ? dialog.treatment
              ? "Editar tratamiento"
              : "Nuevo tratamiento"
            : dialog?.kind === "status"
              ? dialog.target === "completed"
                ? "Completar tratamiento"
                : "Cancelar tratamiento"
              : "Historial del tratamiento"
        }
      >
        {dialog?.kind === "form" && (
          <TreatmentForm
            patientId={patientId}
            treatment={dialog.treatment}
            visits={visits}
            onDone={closeAndRefresh}
          />
        )}
        {dialog?.kind === "status" && (
          <StatusDialog
            patientId={patientId}
            treatment={dialog.treatment}
            target={dialog.target}
            visits={visits}
            onDone={closeAndRefresh}
          />
        )}
        {dialog?.kind === "history" && (
          <HistoryList patientId={patientId} treatment={dialog.treatment} />
        )}
      </Modal>
    </Card>
  );
}
