import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import Input from "../basic/Input";
import Textarea from "../basic/Textarea";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import { getVisits } from "../../services/clinicalVisitService";
import { getPeriodontalExam, updatePeriodontalExam } from "../../services/periodontalService";
import type { PeriodontalExam, SiteCode, SiteData, ToothData } from "../../types/periodontal";
import PerioChart from "./PerioChart";
import { canEditExam, chartErrors, periodontalExamKey, periodontalExamsKey } from "./periodontalExam";
import type { ChartActions } from "./PerioGrid";
import PerioSummary, { PerioLegend } from "./PerioSummary";
import {
  SITES,
  chartFromExam,
  emptyFurcation,
  emptySite,
  summarize,
  toContent,
  today,
} from "./periodontalChart";

interface PeriodontalEditorProps {
  exam: PeriodontalExam;
  isArchived: boolean;
  /** Avisa si hay cambios sin guardar (para no perderlos al salir). */
  onDirtyChange?: (dirty: boolean) => void;
}

/** Editor de un examen periodontal (ODON-186): datos generales, grilla, dibujo y resumen en vivo. */
export default function PeriodontalEditor({ exam, isArchived, onDirtyChange }: PeriodontalEditorProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const editable = canEditExam(exam, user, isArchived);

  const [chart, setChart] = useState<ToothData[]>(() => chartFromExam(exam));
  const [examDate, setExamDate] = useState(exam.exam_date);
  const [visitId, setVisitId] = useState<number | null>(exam.clinical_visit?.id ?? null);
  const [notes, setNotes] = useState(exam.notes ?? "");
  const [noteTooth, setNoteTooth] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  // Revisión sobre la que se está editando. No sigue a la caché: si otra
  // persona guarda y la consulta se recarga, el siguiente guardado debe dar
  // 409 en vez de pisar sus cambios. Se actualiza al guardar o al recargar.
  const [baseRevision, setBaseRevision] = useState(exam.revision);
  const [conflict, setConflict] = useState(false);
  const noteOpener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const { data: allVisits = [] } = useQuery({
    queryKey: ["patients", exam.patient_id, "visits"],
    queryFn: () => getVisits(exam.patient_id),
    enabled: editable,
  });
  // Se conserva la consulta ya vinculada aunque se haya anulado después.
  const visits = allVisits.filter((visit) => !visit.voided_at || visit.id === exam.clinical_visit?.id);

  const summary = useMemo(() => summarize(chart), [chart]);
  const errors = useMemo(() => chartErrors(chart), [chart]);

  const change = (fn: (tooth: ToothData) => ToothData, number: number) => {
    setChart((current) => current.map((tooth) => (tooth.tooth === number ? fn(tooth) : tooth)));
    setDirty(true);
  };

  const actions: ChartActions = {
    updateSite: (number: number, site: SiteCode, patch: Partial<SiteData>) =>
      change((tooth) => ({ ...tooth, sites: { ...tooth.sites, [site]: { ...tooth.sites[site], ...patch } } }), number),
    updateTooth: (number, patch) => change((tooth) => ({ ...tooth, ...patch }), number),
    // Marcar ausente vacía la pieza: una pieza ausente no lleva mediciones.
    toggleMissing: (number) =>
      change(
        (tooth) =>
          tooth.missing
            ? { ...tooth, missing: false }
            : {
                ...tooth,
                missing: true,
                implant: false,
                mobility: null,
                furcation: emptyFurcation(),
                sites: Object.fromEntries(SITES.map((site) => [site, emptySite()])) as Record<SiteCode, SiteData>,
              },
        number,
      ),
    openNote: (number) => {
      noteOpener.current = document.activeElement as HTMLElement | null;
      setNoteTooth(number);
    },
  };

  const save = useMutation({
    mutationFn: () =>
      updatePeriodontalExam(exam.patient_id, exam.id, {
        ...toContent(examDate, visitId, notes, chart),
        base_revision: baseRevision,
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(periodontalExamKey(exam.patient_id, exam.id), saved);
      queryClient.invalidateQueries({ queryKey: periodontalExamsKey(exam.patient_id), exact: true });
      setBaseRevision(saved.revision);
      setDirty(false);
      toast.success("Borrador guardado");
    },
    onError: (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        // Otra persona guardó, finalizó o anuló: se muestra cómo cargar la versión vigente.
        setConflict(true);
        queryClient.invalidateQueries({ queryKey: periodontalExamKey(exam.patient_id, exam.id), exact: true });
      }
      toast.error(getApiErrorMessage(error, "No se pudo guardar el periodontograma"));
    },
  });

  const reload = useMutation({
    mutationFn: () => getPeriodontalExam(exam.patient_id, exam.id),
    onSuccess: (fresh) => {
      queryClient.setQueryData(periodontalExamKey(exam.patient_id, exam.id), fresh);
      setChart(chartFromExam(fresh));
      setExamDate(fresh.exam_date);
      setVisitId(fresh.clinical_visit?.id ?? null);
      setNotes(fresh.notes ?? "");
      setBaseRevision(fresh.revision);
      setConflict(false);
      setDirty(false);
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "No se pudo cargar la versión actual")),
  });

  const closeNote = () => {
    setNoteTooth(null);
    noteOpener.current?.focus();
  };

  const noteValue = noteTooth === null ? "" : chart.find((tooth) => tooth.tooth === noteTooth)?.note ?? "";

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 md:grid-cols-[180px_1fr_1fr]">
        <Input
          type="date"
          label="Fecha del examen"
          value={examDate}
          disabled={!editable}
          max={today()}
          onChange={(event) => {
            setExamDate(event.target.value);
            setDirty(true);
          }}
        />
        <div className="flex flex-col gap-2">
          <label htmlFor="perio-visit" className="text-sm font-medium">Consulta (opcional)</label>
          <select
            id="perio-visit"
            disabled={!editable}
            value={visitId ?? ""}
            onChange={(event) => {
              setVisitId(event.target.value === "" ? null : Number(event.target.value));
              setDirty(true);
            }}
            className="rounded-xl border p-3 disabled:bg-gray-100"
          >
            <option value="">Sin consulta</option>
            {(editable ? visits : exam.clinical_visit ? [exam.clinical_visit] : []).map((visit) => (
              <option key={visit.id} value={visit.id}>
                {new Date(visit.visit_at).toLocaleDateString("es")} · {visit.reason}
              </option>
            ))}
          </select>
        </div>
        <Textarea
          label="Notas generales"
          rows={2}
          value={notes}
          disabled={!editable}
          maxLength={4000}
          onChange={(event) => {
            setNotes(event.target.value);
            setDirty(true);
          }}
        />
      </div>

      {conflict && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900">
          <p>Otra persona guardó, finalizó o anuló este periodontograma mientras lo editabas. Tus cambios no se guardaron.</p>
          <Button variant="secondary" onClick={() => reload.mutate()} disabled={reload.isPending}>
            {reload.isPending ? "Cargando..." : "Cargar la versión actual"}
          </Button>
        </div>
      )}

      <PerioSummary summary={summary} />
      <PerioLegend />

      {noteTooth !== null && (
        <div role="dialog" aria-label={`Nota de la pieza ${noteTooth}`} className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <Textarea
            label={`Nota de la pieza ${noteTooth}`}
            autoFocus
            onKeyDown={(event) => {
              if (event.key === "Escape") closeNote();
            }}
            rows={2}
            maxLength={500}
            value={noteValue}
            disabled={!editable}
            onChange={(event) =>
              actions.updateTooth(noteTooth, { note: event.target.value === "" ? null : event.target.value })
            }
          />
          <div className="flex justify-end">
            <Button variant="secondary" onClick={closeNote}>Cerrar</Button>
          </div>
        </div>
      )}

      <PerioChart chart={chart} readOnly={!editable} actions={actions} />

      {editable && (
        <div className="flex flex-wrap items-center justify-end gap-3">
          {errors.length > 0 && (
            <p role="alert" className="mr-auto text-sm text-red-700">
              {errors.length === 1 ? errors[0] : `${errors.length} valores fuera de rango (marcados en rojo).`}
            </p>
          )}
          <span className="text-sm text-slate-500">{dirty ? "Cambios sin guardar" : "Todo guardado"}</span>
          <Button onClick={() => save.mutate()} disabled={save.isPending || errors.length > 0 || !dirty}>
            {save.isPending ? "Guardando..." : "Guardar borrador"}
          </Button>
        </div>
      )}
    </div>
  );
}
