import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import clsx from "clsx";
import { ArrowLeft, Plus } from "lucide-react";

import Button from "../basic/Button";
import Card from "../basic/Card";
import ConfirmDialog from "../basic/ConfirmDialog";
import LoadingSpinner from "../basic/LoadingSpinner";
import { getApiErrorMessage } from "../../services/apiError";
import {
  createPeriodontalExam,
  getPeriodontalExam,
  getPeriodontalExams,
} from "../../services/periodontalService";
import PeriodontalEditor from "./PeriodontalEditor";
import { periodontalExamKey, periodontalExamsKey, statusLabel } from "./periodontalExam";
import { today } from "./periodontalChart";

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

  const close = () => {
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

  const create = useMutation({
    mutationFn: () => createPeriodontalExam(patientId, { exam_date: today(), clinical_visit_id: null, notes: null, teeth: [] }),
    onSuccess: (created) => {
      queryClient.setQueryData(periodontalExamKey(patientId, created.id), created);
      queryClient.invalidateQueries({ queryKey: periodontalExamsKey(patientId), exact: true });
      setOpenId(created.id);
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "No se pudo crear el periodontograma")),
  });

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
        {canCreate && !isArchived && (
          <Button onClick={() => create.mutate()} disabled={create.isPending} className="inline-flex items-center gap-2">
            <Plus size={18} /> {create.isPending ? "Creando..." : "Nuevo periodontograma"}
          </Button>
        )}
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
    </Card>
  );
}
