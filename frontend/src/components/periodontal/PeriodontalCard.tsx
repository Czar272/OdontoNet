import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import clsx from "clsx";
import { ArrowLeft, GitCompare, Plus } from "lucide-react";

import Button from "../basic/Button";
import Card from "../basic/Card";
import ConfirmDialog from "../basic/ConfirmDialog";
import Modal from "../basic/Modal";
import LoadingSpinner from "../basic/LoadingSpinner";
import { getApiErrorMessage } from "../../services/apiError";
import {
  createPeriodontalExam,
  getPeriodontalExam,
  getPeriodontalExams,
} from "../../services/periodontalService";
import PeriodontalCompare from "./PeriodontalCompare";
import PeriodontalEditor from "./PeriodontalEditor";
import { clearBackup, periodontalExamKey, periodontalExamsKey, statusLabel } from "./periodontalExam";
import { toContent, today } from "./periodontalChart";
import { COPY_LABELS, DEFAULT_COPY, copyChart, type CopyOptions } from "./copyExam";

interface PeriodontalCardProps {
  patientId: number;
  canCreate: boolean;
  isArchived: boolean;
}

const dateFormat = new Intl.DateTimeFormat("es", { dateStyle: "medium", timeZone: "UTC" });

/** Pestaña «Periodontograma» de la ficha (ODON-9): exámenes del paciente y su editor. */
export default function PeriodontalCard({ patientId, canCreate, isArchived }: PeriodontalCardProps) {
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [copyFrom, setCopyFrom] = useState<number | null>(null);
  const [copyOptions, setCopyOptions] = useState<CopyOptions>(DEFAULT_COPY);

  const close = () => {
    // «Salir sin guardar» descarta también el respaldo de la pestaña.
    if (openId !== null) clearBackup(openId);
    setConfirmLeave(false);
    setDirty(false);
    setOpenId(null);
  };

  const { data: exams = [], isLoading } = useQuery({
    queryKey: periodontalExamsKey(patientId),
    queryFn: () => getPeriodontalExams(patientId),
  });

  const { data: exam, isLoading: loadingExam } = useQuery({
    queryKey: periodontalExamKey(patientId, openId ?? 0),
    queryFn: () => getPeriodontalExam(patientId, openId as number),
    enabled: openId !== null,
  });

  // Se puede partir del examen vigente más reciente (no anulado), como en la referencia.
  const previous = exams.find((item) => !item.voided_at) ?? null;

  const create = useMutation({
    mutationFn: async (source: number | null) => {
      if (source === null) {
        return createPeriodontalExam(patientId, { exam_date: today(), clinical_visit_id: null, notes: null, teeth: [] });
      }
      const base = await getPeriodontalExam(patientId, source);
      return createPeriodontalExam(patientId, toContent(today(), null, "", copyChart(base, copyOptions)));
    },
    onSuccess: (created) => {
      setChoosing(false);
      setCopyFrom(null);
      queryClient.setQueryData(periodontalExamKey(patientId, created.id), created);
      queryClient.invalidateQueries({ queryKey: periodontalExamsKey(patientId), exact: true });
      setOpenId(created.id);
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "No se pudo crear el periodontograma")),
  });

  // Se comparan registros previos: finalizados y no anulados (un borrador aún puede cambiar).
  const comparable = exams.filter((item) => item.status === "final" && !item.voided_at);

  if (comparing && comparable.length >= 2) {
    return (
      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <button type="button" onClick={() => setComparing(false)}
            className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900">
            <ArrowLeft size={16} /> Periodontogramas
          </button>
          <h2 className="text-lg font-semibold">Comparar periodontogramas</h2>
        </div>
        <PeriodontalCompare patientId={patientId} exams={comparable} />
      </Card>
    );
  }

  if (openId !== null) {
    return (
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <button type="button" onClick={() => (dirty ? setConfirmLeave(true) : close())}
            className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900">
            <ArrowLeft size={16} /> Periodontogramas
          </button>
          {exam && (
            <span className={clsx("rounded-full px-3 py-1 text-xs font-medium", statusLabel(exam).className)}>
              {statusLabel(exam).text} · revisión {exam.revision} · {exam.created_by.name}
            </span>
          )}
        </div>
        {loadingExam || !exam ? <LoadingSpinner /> : (
          <PeriodontalEditor key={exam.id} exam={exam} isArchived={isArchived} onDirtyChange={setDirty} />
        )}
        <ConfirmDialog
          isOpen={confirmLeave}
          title="Cambios sin guardar"
          message="Si vuelves a la lista se pierden los cambios que no guardaste."
          confirmLabel="Salir sin guardar"
          cancelLabel="Seguir editando"
          variant="danger"
          onConfirm={close}
          onCancel={() => setConfirmLeave(false)}
        />
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Periodontograma</h2>
          <p className="text-sm text-slate-500">Registro manual por pieza y sitio. Los resúmenes no constituyen diagnóstico.</p>
        </div>
        <div className="flex flex-wrap gap-3">
        {comparable.length >= 2 && (
          <Button variant="secondary" onClick={() => setComparing(true)} className="inline-flex items-center gap-2">
            <GitCompare size={18} /> Comparar
          </Button>
        )}
        {canCreate && !isArchived && (
          <Button
            onClick={() => {
              setCopyFrom(null);
              if (previous) setChoosing(true);
              else create.mutate(null);
            }}
            disabled={create.isPending || isLoading}
            className="inline-flex items-center gap-2"
          >
            <Plus size={18} /> {create.isPending ? "Creando..." : "Nuevo periodontograma"}
          </Button>
        )}
        </div>
      </div>

      {isLoading ? <LoadingSpinner /> : exams.length === 0 ? (
        <p className="text-slate-500">Aún no hay periodontogramas de este paciente.</p>
      ) : (
        <ul aria-label="Periodontogramas del paciente" className="divide-y rounded-xl border">
          {exams.map((item) => {
            const status = statusLabel(item);
            const { summary } = item;
            return (
              <li key={item.id}>
                <button type="button" onClick={() => setOpenId(item.id)}
                  aria-label={`Abrir periodontograma del ${dateFormat.format(new Date(item.exam_date))}`}
                  className="flex w-full flex-wrap items-center gap-x-6 gap-y-1 p-4 text-left hover:bg-slate-50">
                  <span className="font-medium">{dateFormat.format(new Date(item.exam_date))}</span>
                  <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-medium", status.className)}>{status.text}</span>
                  <span className="text-sm text-slate-500">{item.created_by.name}</span>
                  <span className="ml-auto text-sm tabular-nums text-slate-600">
                    {summary.measured_sites} sitios
                    {summary.mean_probing_depth !== null && ` · sondaje medio ${summary.mean_probing_depth} mm`}
                    {summary.bleeding_pct !== null && ` · sangrado ${summary.bleeding_pct} %`}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <Modal isOpen={choosing} onClose={() => setChoosing(false)} title="Nuevo periodontograma">
        <form
          aria-label="Nuevo periodontograma"
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate(copyFrom);
          }}
        >
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">¿Cómo empezar?</legend>
            <label className="flex items-center gap-2">
              <input type="radio" name="perio-start" checked={copyFrom === null} onChange={() => setCopyFrom(null)} />
              En blanco
            </label>
            {previous && (
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="perio-start"
                  checked={copyFrom === previous.id}
                  onChange={() => setCopyFrom(previous.id)}
                />
                A partir del examen del {dateFormat.format(new Date(previous.exam_date))}
              </label>
            )}
          </fieldset>
          {copyFrom !== null && (
            <fieldset className="flex flex-col gap-2 rounded-xl bg-slate-50 p-3">
              <legend className="text-sm font-medium">Copiar</legend>
              {(Object.keys(COPY_LABELS) as (keyof CopyOptions)[]).map((key) => (
                <label key={key} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={copyOptions[key]}
                    onChange={(event) => setCopyOptions({ ...copyOptions, [key]: event.target.checked })}
                  />
                  {COPY_LABELS[key]}
                </label>
              ))}
              <p className="text-xs text-slate-500">Las notas no se copian. Revisa cada valor copiado antes de finalizar.</p>
            </fieldset>
          )}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setChoosing(false)}>Cancelar</Button>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creando..." : "Crear"}</Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
}
