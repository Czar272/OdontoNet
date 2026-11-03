import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, History, Pencil, Plus, Stethoscope } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

import Button from "../basic/Button";
import Card from "../basic/Card";
import LoadingSpinner from "../basic/LoadingSpinner";
import Modal from "../basic/Modal";
import Textarea from "../basic/Textarea";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import {
  getVisitRevisions,
  getVisits,
  voidVisit,
} from "../../services/clinicalVisitService";
import type { ClinicalVisit } from "../../types/clinicalVisit";
import VisitForm from "./VisitForm";
import { canModifyVisit } from "./visitFormData";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "long",
  timeStyle: "short",
});
const dateOnly = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "long",
  timeZone: "UTC",
});

function formatDate(value: string) {
  return dateOnly.format(new Date(`${value}T00:00:00Z`));
}

const SECTIONS: { key: keyof ClinicalVisit; label: string }[] = [
  { key: "findings", label: "Hallazgos / examen" },
  { key: "diagnosis", label: "Diagnóstico profesional" },
  { key: "procedures", label: "Procedimientos realizados" },
  { key: "instructions", label: "Indicaciones" },
];

function VisitBody({
  visit,
}: {
  visit: Pick<
    ClinicalVisit,
    "findings" | "diagnosis" | "procedures" | "instructions" | "next_visit_date"
  >;
}) {
  return (
    <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
      {SECTIONS.map(({ key, label }) => {
        const value = visit[key as keyof typeof visit];
        return value ? (
          <div key={key}>
            <dt className="font-medium text-gray-700">{label}</dt>
            <dd className="text-gray-900 whitespace-pre-line">{value}</dd>
          </div>
        ) : null;
      })}
      {visit.next_visit_date && (
        <div>
          <dt className="font-medium text-gray-700">Próxima cita sugerida</dt>
          <dd className="text-gray-900">{formatDate(visit.next_visit_date)}</dd>
        </div>
      )}
    </dl>
  );
}

function RevisionsModal({
  patientId,
  visit,
  onClose,
}: {
  patientId: number;
  visit: ClinicalVisit;
  onClose: () => void;
}) {
  const { data: revisions, isLoading } = useQuery({
    queryKey: ["patients", patientId, "visits", visit.id, "revisions"],
    queryFn: () => getVisitRevisions(patientId, visit.id),
  });

  return (
    <Modal isOpen onClose={onClose} title="Historial de cambios">
      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <ol className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
          {revisions?.map((rev) => (
            <li key={rev.revision} className="rounded-xl border p-4">
              <p className="text-sm font-semibold">
                Revisión {rev.revision}
                {rev.revision === 1 ? " (registro)" : ""} ·{" "}
                {dateTime.format(new Date(rev.edited_at))} ·{" "}
                {rev.edited_by.name}
              </p>
              <p className="text-sm text-gray-600 mt-1 mb-3">
                {dateTime.format(new Date(rev.visit_at))} · {rev.doctor.name} ·{" "}
                {rev.reason}
              </p>
              <VisitBody visit={rev} />
            </li>
          ))}
        </ol>
      )}
    </Modal>
  );
}

interface ClinicalVisitsCardProps {
  patientId: number;
  canCreate: boolean;
  isArchived: boolean;
}

/**
 * Consultas clínicas del paciente en orden cronológico (ODON-154). Cada
 * cambio queda en el historial; una consulta se anula con motivo, no se borra.
 */
export default function ClinicalVisitsCard({
  patientId,
  canCreate,
  isArchived,
}: ClinicalVisitsCardProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const visitsKey = ["patients", patientId, "visits"];

  // undefined = cerrado; null = nueva; consulta = edición.
  const [editing, setEditing] = useState<ClinicalVisit | null | undefined>(
    undefined,
  );
  const [voiding, setVoiding] = useState<ClinicalVisit | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [showingRevisions, setShowingRevisions] =
    useState<ClinicalVisit | null>(null);

  const { data: visits, isLoading } = useQuery({
    queryKey: visitsKey,
    queryFn: () => getVisits(patientId),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: visitsKey });

  const voidMutation = useMutation({
    mutationFn: () =>
      voidVisit(patientId, (voiding as ClinicalVisit).id, voidReason),
    onSuccess: () => {
      toast.success("Consulta anulada");
      setVoiding(null);
      setVoidReason("");
      refresh();
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "No se pudo anular la consulta"));
    },
  });

  const writable = !isArchived;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Stethoscope size={20} /> Consultas clínicas
        </h2>
        {canCreate && writable && (
          <Button onClick={() => setEditing(null)}>
            <span className="flex items-center gap-2">
              <Plus size={16} /> Nueva consulta
            </span>
          </Button>
        )}
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : !visits || visits.length === 0 ? (
        <p className="text-gray-500 text-sm">
          Este paciente aún no tiene consultas registradas.
        </p>
      ) : (
        <ol className="flex flex-col gap-4" aria-label="Consultas">
          {visits.map((visit) => {
            const voided = Boolean(visit.voided_at);
            const canModify = writable && canModifyVisit(visit, user);
            return (
              <li
                key={visit.id}
                className={clsx(
                  "rounded-xl border p-4",
                  voided ? "bg-gray-50 border-gray-200" : "border-gray-200",
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <div className={clsx(voided && "text-gray-500")}>
                    <p
                      className={clsx(
                        "font-semibold",
                        voided && "line-through",
                      )}
                    >
                      {dateTime.format(new Date(visit.visit_at))} ·{" "}
                      {visit.reason}
                    </p>
                    <p className="text-sm text-gray-600">
                      {visit.doctor.name} · registrada por{" "}
                      {visit.created_by.name}
                      {visit.revision > 1 &&
                        ` · editada por ${visit.updated_by.name} el ${dateTime.format(new Date(visit.updated_at))}`}
                    </p>
                  </div>

                  <div className="flex gap-2">
                    {visit.revision > 1 && (
                      <Button
                        variant="secondary"
                        className="px-3 py-2 text-sm"
                        onClick={() => setShowingRevisions(visit)}
                      >
                        <span className="flex items-center gap-1">
                          <History size={14} /> Cambios
                        </span>
                      </Button>
                    )}
                    {canModify && (
                      <>
                        <Button
                          variant="secondary"
                          className="px-3 py-2 text-sm"
                          onClick={() => setEditing(visit)}
                        >
                          <span className="flex items-center gap-1">
                            <Pencil size={14} /> Editar
                          </span>
                        </Button>
                        <Button
                          variant="secondary"
                          className="px-3 py-2 text-sm"
                          onClick={() => setVoiding(visit)}
                        >
                          <span className="flex items-center gap-1">
                            <Ban size={14} /> Anular
                          </span>
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {voided && (
                  <p
                    role="note"
                    className="mb-3 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800"
                  >
                    Anulada por {visit.voided_by?.name}{" "}
                    {`(${dateTime.format(new Date(visit.voided_at as string))}).`}{" "}
                    Motivo: {visit.void_reason}
                  </p>
                )}

                <div className={clsx(voided && "opacity-60")}>
                  <VisitBody visit={visit} />
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <Modal
        isOpen={editing !== undefined}
        onClose={() => setEditing(undefined)}
        title={editing ? "Editar consulta" : "Nueva consulta"}
      >
        {editing !== undefined && (
          <VisitForm
            key={editing?.id ?? "new"}
            patientId={patientId}
            visit={editing}
            onSaved={() => {
              setEditing(undefined);
              refresh();
            }}
            onCancel={() => setEditing(undefined)}
            onConflict={refresh}
          />
        )}
      </Modal>

      <Modal
        isOpen={voiding !== null}
        onClose={() => setVoiding(null)}
        title="Anular consulta"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            voidMutation.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <p className="text-gray-700 text-sm">
            La consulta no se borra: queda visible como anulada, con tu nombre,
            la fecha y el motivo.
          </p>
          <Textarea
            label="Motivo de la anulación *"
            maxLength={500}
            value={voidReason}
            onChange={(e) => setVoidReason(e.target.value)}
            required
          />
          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={() => setVoiding(null)}
              disabled={voidMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="danger"
              disabled={voidMutation.isPending || !voidReason.trim()}
            >
              {voidMutation.isPending ? "Guardando..." : "Anular consulta"}
            </Button>
          </div>
        </form>
      </Modal>

      {showingRevisions && (
        <RevisionsModal
          patientId={patientId}
          visit={showingRevisions}
          onClose={() => setShowingRevisions(null)}
        />
      )}
    </Card>
  );
}
