import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../basic/Button";
import ConfirmDialog from "../basic/ConfirmDialog";
import Modal from "../basic/Modal";
import Input from "../basic/Input";
import Textarea from "../basic/Textarea";
import { useAuth } from "../../context/AuthContext";
import { getApiErrorMessage } from "../../services/apiError";
import { getVisits } from "../../services/clinicalVisitService";
import {
  finalizePeriodontalExam,
  getPeriodontalExam,
  getPeriodontalExamRevisions,
  getPeriodontalReport,
  updatePeriodontalExam,
  voidPeriodontalExam,
} from "../../services/periodontalService";
import type { PeriodontalExam, SiteCode, SiteData, ToothData } from "../../types/periodontal";
import PerioChart from "./PerioChart";
import { timelineKey } from "../patients/timelineEvents";
import {
  AUTOSAVE_MS,
  canEditExam,
  canExportExam,
  canVoidExam,
  chartErrors,
  clearBackup,
  periodontalExamKey,
  periodontalExamsKey,
  readBackup,
  saveBlob,
  writeBackup,
  type DraftBackup,
} from "./periodontalExam";
import type { ChartActions } from "./PerioGrid";
import PerioSummary, { PerioLegend } from "./PerioSummary";
import {
  SITES,
  chartFromExam,
  emptyFurcation,
  emptySite,
  DEFAULT_HEALTHY,
  HEALTHY_MARGIN_OPTIONS,
  HEALTHY_PROBING_OPTIONS,
  fillHealthy,
  summarize,
  toContent,
  today,
  type HealthyValues,
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
  const [saveFailed, setSaveFailed] = useState(false);
  const [confirmFinalize, setConfirmFinalize] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const [showRevisions, setShowRevisions] = useState(false);
  // Respaldo de la sesión que quedó sin guardar (corte de red, pestaña recargada).
  const [recovery, setRecovery] = useState<DraftBackup | null>(() => {
    const backup = editable && user ? readBackup(exam.id, user.id) : null;
    if (backup && backup.baseRevision === exam.revision) return backup;
    // De otra revisión u otro usuario: ya no aplica y no debe quedar en el navegador.
    if (backup || (user && readBackup(exam.id, null))) clearBackup(exam.id);
    return null;
  });
  const noteOpener = useRef<HTMLElement | null>(null);
  const [fillOpen, setFillOpen] = useState(false);
  const [healthy, setHealthy] = useState<HealthyValues>(DEFAULT_HEALTHY);
  // Contenido anterior al último llenado, para poder deshacerlo.
  const [undoChart, setUndoChart] = useState<ToothData[] | null>(null);
  const [lastFilled, setLastFilled] = useState(0);
  // Cuenta las ediciones: un guardado solo deja el examen «limpio» si no hubo
  // cambios mientras viajaba la petición.
  const editSeq = useRef(0);

  const touch = () => {
    editSeq.current += 1;
    setSaveFailed(false);
    setDirty(true);
    // «Deshacer el llenado» solo vale hasta la siguiente edición: después
    // restauraría una copia vieja y borraría lo escrito o lo recargado.
    setUndoChart(null);
  };

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
  const hasProbing = summary.measured_sites > 0 || chart.some((tooth) =>
    SITES.some((site) => tooth.sites[site].probing_depth !== null));
  const errors = useMemo(() => chartErrors(chart), [chart]);

  const change = (fn: (tooth: ToothData) => ToothData, number: number) => {
    setChart((current) => current.map((tooth) => (tooth.tooth === number ? fn(tooth) : tooth)));
    touch();
  };

  const actions: ChartActions = {
    // Cualquier edición de un sitio lo vuelve «manual»: ya lo decidió el profesional.
    updateSite: (number: number, site: SiteCode, patch: Partial<SiteData>) =>
      change(
        (tooth) => ({ ...tooth, sites: { ...tooth.sites, [site]: { ...tooth.sites[site], ...patch, source: "manual" } } }),
        number,
      ),
    updateTooth: (number, patch) =>
      change((tooth) => ({ ...tooth, ...patch, ...("mobility" in patch ? { source: "manual" as const } : {}) }), number),
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

  const content = () => toContent(examDate, visitId, notes, chart);

  const afterSave = (saved: PeriodontalExam) => {
    queryClient.setQueryData(periodontalExamKey(exam.patient_id, exam.id), saved);
    queryClient.invalidateQueries({ queryKey: periodontalExamsKey(exam.patient_id), exact: true });
    setBaseRevision(saved.revision);
  };

  const onSaveError = (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      // Otra persona guardó, finalizó o anuló: se muestra cómo cargar la versión vigente.
      setConflict(true);
      queryClient.invalidateQueries({ queryKey: periodontalExamKey(exam.patient_id, exam.id), exact: true });
    } else {
      setSaveFailed(true);
    }
    toast.error(getApiErrorMessage(error, "No se pudo guardar el periodontograma"));
  };

  // seq: edición al momento de enviar; auto: autoguardado (sin aviso).
  const save = useMutation<PeriodontalExam, unknown, { seq: number; auto: boolean }>({
    mutationFn: () =>
      updatePeriodontalExam(exam.patient_id, exam.id, { ...content(), base_revision: baseRevision }),
    onSuccess: (saved, { seq, auto }) => {
      afterSave(saved);
      setSaveFailed(false);
      if (seq === editSeq.current) {
        setDirty(false);
        clearBackup(exam.id);
      }
      if (!auto) toast.success("Borrador guardado");
    },
    onError: onSaveError,
    onSettled: () => {
      saveInFlight.current = false;
    },
  });
  const { mutate, isPending: saving } = save;
  // Marcas síncronas: `saving` y `saveFailed` llegan con el siguiente render, y
  // con el hilo ocupado el temporizador del autoguardado podía dispararse antes
  // y enviar una segunda petición con la misma revisión base. Un guardado en
  // curso bloquea otro, y un temporizador queda sin efecto si algún guardado
  // empezó después de programarlo.
  const saveInFlight = useRef(false);
  const saveStarts = useRef(0);
  const saveDraft = (variables: { seq: number; auto: boolean }) => {
    if (saveInFlight.current) return;
    saveInFlight.current = true;
    saveStarts.current += 1;
    mutate(variables);
  };
  const saveDraftRef = useRef(saveDraft);
  useEffect(() => {
    saveDraftRef.current = saveDraft;
  });

  const finalize = useMutation({
    mutationFn: async () => {
      let revision = baseRevision;
      if (dirty) {
        const seq = editSeq.current;
        let saved: PeriodontalExam;
        try {
          saved = await updatePeriodontalExam(exam.patient_id, exam.id, { ...content(), base_revision: revision });
        } catch (error) {
          throw { step: "save", error };
        }
        afterSave(saved);
        if (seq === editSeq.current) {
          setDirty(false);
          clearBackup(exam.id);
        }
        revision = saved.revision;
      }
      try {
        return await finalizePeriodontalExam(exam.patient_id, exam.id, revision);
      } catch (error) {
        throw { step: "finalize", error };
      }
    },
    onSuccess: (finalized) => {
      afterSave(finalized);
      queryClient.invalidateQueries({ queryKey: timelineKey(exam.patient_id) });
      setDirty(false);
      clearBackup(exam.id);
      setConfirmFinalize(false);
      toast.success("Periodontograma finalizado");
    },
    onError: (failure) => {
      setConfirmFinalize(false);
      const { step, error } = failure as unknown as { step: "save" | "finalize"; error: unknown };
      if (step === "save") {
        onSaveError(error);
      } else if (axios.isAxiosError(error) && error.response?.status === 409) {
        onSaveError(error);
      } else {
        // Los datos ya están guardados; solo falló finalizar (p. ej. sin sondajes).
        toast.error(getApiErrorMessage(error, "No se pudo finalizar el periodontograma"));
      }
    },
  });
  const finalizing = finalize.isPending;

  const voidExam = useMutation({
    mutationFn: () => voidPeriodontalExam(exam.patient_id, exam.id, voidReason.trim()),
    onSuccess: (voided) => {
      afterSave(voided);
      queryClient.invalidateQueries({ queryKey: timelineKey(exam.patient_id) });
      setDirty(false);
      clearBackup(exam.id);
      setVoiding(false);
      toast.success("Periodontograma anulado");
    },
    onError: (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        // Otra persona lo anuló o cambió: se muestra el estado vigente.
        setVoiding(false);
        queryClient.invalidateQueries({ queryKey: periodontalExamKey(exam.patient_id, exam.id), exact: true });
      }
      toast.error(getApiErrorMessage(error, "No se pudo anular el periodontograma"));
    },
  });
  const voidPending = voidExam.isPending;

  const closeVoid = () => {
    setVoiding(false);
    setVoidReason("");
  };

  // Autoguardado: unos segundos después del último cambio válido.
  useEffect(() => {
    // En pausa mientras se decide la recuperación o se finaliza o anula: así no
    // viajan dos peticiones con la misma revisión base (409 falso).
    if (!editable || !dirty || conflict || saveFailed || saving || errors.length > 0) return;
    if (recovery || confirmFinalize || finalizing || voiding || voidPending) return;
    const startsWhenScheduled = saveStarts.current;
    const timer = setTimeout(() => {
      if (saveStarts.current !== startsWhenScheduled) return;
      saveDraftRef.current({ seq: editSeq.current, auto: true });
    }, AUTOSAVE_MS);
    return () => clearTimeout(timer);
  }, [chart, examDate, visitId, notes, editable, dirty, conflict, saveFailed, saving, errors.length,
    recovery, confirmFinalize, finalizing, voiding, voidPending]);

  // Respaldo en esta pestaña mientras haya cambios sin guardar.
  useEffect(() => {
    // Con el aviso de recuperación visible no se pisa el respaldo pendiente.
    if (!editable || !dirty || recovery || !user) return;
    writeBackup(exam.id, {
      userId: user.id, baseRevision, examDate, visitId, notes, chart, savedAt: new Date().toISOString(),
    });
  }, [exam.id, user, editable, dirty, recovery, baseRevision, examDate, visitId, notes, chart]);

  const exportPdf = useMutation({
    mutationFn: () => getPeriodontalReport(exam.patient_id, exam.id),
    onSuccess: ({ blob, filename }) => saveBlob(blob, filename),
    onError: (error) => toast.error(getApiErrorMessage(error, "No se pudo generar el PDF")),
  });

  const { data: revisions = [], isLoading: loadingRevisions, isError: revisionsError } = useQuery({
    queryKey: [...periodontalExamKey(exam.patient_id, exam.id), "revisions", exam.revision],
    queryFn: () => getPeriodontalExamRevisions(exam.patient_id, exam.id),
    enabled: showRevisions,
  });

  const recover = (backup: DraftBackup) => {
    setChart(backup.chart);
    setExamDate(backup.examDate);
    setVisitId(backup.visitId);
    setNotes(backup.notes);
    setRecovery(null);
    touch();
  };

  const applyHealthy = () => {
    const { chart: next, filled, mobilityFilled } = fillHealthy(chart, healthy);
    setFillOpen(false);
    if (filled === 0 && mobilityFilled === 0) {
      toast("No hay sitios vacíos ni movilidad por llenar.");
      return;
    }
    setChart(next);
    touch();
    setUndoChart(chart);
    setLastFilled(filled);
  };

  const undoHealthy = () => {
    const previous = undoChart;
    touch();
    if (previous) setChart(previous);
  };

  const discardRecovery = () => {
    clearBackup(exam.id);
    setRecovery(null);
  };

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
      setSaveFailed(false);
      setDirty(false);
      setUndoChart(null);
      clearBackup(exam.id);
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
            touch();
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
              touch();
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
            touch();
          }}
        />
      </div>

      {recovery && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sky-300 bg-sky-50 p-4 text-sky-900">
          <p>
            Hay cambios de esta sesión que no se llegaron a guardar. Mientras no elijas, no se autoguarda (respaldo de las 
            {new Date(recovery.savedAt).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}).
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={discardRecovery}>Descartar</Button>
            <Button onClick={() => recover(recovery)}>Recuperar cambios</Button>
          </div>
        </div>
      )}

      {conflict && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900">
          <p>Otra persona guardó, finalizó o anuló este periodontograma mientras lo editabas. Tus cambios no se guardaron.</p>
          <Button variant="secondary" onClick={() => reload.mutate()} disabled={reload.isPending}>
            {reload.isPending ? "Cargando..." : "Cargar la versión actual"}
          </Button>
        </div>
      )}

      {editable && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={() => setFillOpen(true)}>Llenar con valores de salud</Button>
          {undoChart && (
            <p role="status" className="flex items-center gap-2 text-sm text-slate-600">
              Se llenaron {lastFilled} sitios vacíos con valores predeterminados. Deshacer vale hasta la próxima edición.
              <button type="button" onClick={undoHealthy} className="font-medium text-teal-700 underline">Deshacer</button>
            </p>
          )}
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

      <div className="flex flex-wrap items-center justify-end gap-3">
        {errors.length > 0 && editable && (
          <p role="alert" className="mr-auto text-sm text-red-700">
            {errors.length === 1 ? errors[0] : `${errors.length} valores fuera de rango (marcados en rojo).`}
          </p>
        )}
        <Button variant="secondary" onClick={() => setShowRevisions((open) => !open)} aria-expanded={showRevisions}>
          {showRevisions ? "Ocultar guardados" : "Ver guardados"}
        </Button>
        {canExportExam(exam) && (
          <Button variant="secondary" onClick={() => exportPdf.mutate()} disabled={exportPdf.isPending}>
            {exportPdf.isPending ? "Generando PDF..." : "Descargar PDF"}
          </Button>
        )}
        {canVoidExam(exam, user, isArchived) && (
          <Button variant="danger" onClick={() => setVoiding(true)} disabled={saving}>Anular</Button>
        )}
        {editable && (
          <>
            <span role="status" className="text-sm text-slate-500">
              {saving
                ? "Guardando..."
                : saveFailed
                  ? "No se pudo guardar. Tus cambios siguen respaldados en esta pestaña."
                  : dirty
                    ? "Cambios sin guardar"
                    : "Todo guardado"}
            </span>
            <Button
              variant="secondary"
              onClick={() => saveDraft({ seq: editSeq.current, auto: false })}
              disabled={saving || errors.length > 0 || !dirty}
            >
              {saving ? "Guardando..." : saveFailed ? "Reintentar" : "Guardar borrador"}
            </Button>
            <Button
              onClick={() => setConfirmFinalize(true)}
              disabled={errors.length > 0 || finalizing || conflict || saving || !hasProbing || recovery !== null}
              title={hasProbing ? undefined : "Registra al menos un sondaje para finalizar."}
            >
              Finalizar
            </Button>
          </>
        )}
      </div>

      {showRevisions && (
        <section aria-label="Guardados del periodontograma" className="rounded-xl border p-4">
          <h3 className="mb-2 text-sm font-semibold">Guardados</h3>
          <ol className="flex flex-col gap-1 text-sm text-slate-600">
            {loadingRevisions && <li>Cargando...</li>}
            {revisionsError && <li className="text-red-700">No se pudieron cargar los guardados.</li>}
            {revisions.map((revision) => (
              <li key={revision.revision}>
                Revisión {revision.revision} · {revision.edited_by.name} ·{" "}
                {new Date(revision.edited_at).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" })}
              </li>
            ))}
          </ol>
        </section>
      )}

      <Modal isOpen={fillOpen} onClose={() => setFillOpen(false)} title="Llenar con valores de salud">
        <form
          aria-label="Llenar con valores de salud"
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            applyHealthy();
          }}
        >
          <p className="text-sm text-slate-600">
            Llena solo los sitios vacíos de las piezas presentes (no implantes) con los valores elegidos; no cambia lo
            que ya escribiste. Quedan en gris cursiva como predeterminados hasta que edites el sitio. Referencia: salud
            periodontal según el World Workshop 2017 (sondaje de 3 mm o menos y sangrado en menos del 10 % de los
            sitios, sin pérdida de inserción ni ósea). La decisión clínica es tuya: revisa y corrige las piezas que lo
            necesiten.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label htmlFor="healthy-pd" className="text-sm font-medium">Sondaje (mm)</label>
              <select id="healthy-pd" value={healthy.probingDepth} className="rounded-xl border p-3"
                onChange={(event) => setHealthy({ ...healthy, probingDepth: Number(event.target.value) })}>
                {HEALTHY_PROBING_OPTIONS.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="healthy-gm" className="text-sm font-medium">Margen gingival (mm)</label>
              <select id="healthy-gm" value={healthy.gingivalMargin} className="rounded-xl border p-3"
                onChange={(event) => setHealthy({ ...healthy, gingivalMargin: Number(event.target.value) })}>
                {HEALTHY_MARGIN_OPTIONS.map((value) => (
                  <option key={value} value={value}>{value > 0 ? `+${value}` : value}</option>
                ))}
              </select>
            </div>
          </div>
          <p role="note" className={clsx(
            "rounded-lg p-2 text-sm",
            healthy.probingDepth - healthy.gingivalMargin > 0 ? "bg-amber-50 text-amber-900" : "bg-teal-50 text-teal-900",
          )}>
            NIC resultante en cada sitio llenado: {healthy.probingDepth - healthy.gingivalMargin} mm (sondaje − margen).
            {healthy.probingDepth - healthy.gingivalMargin > 0 &&
              " Con el margen en la UAC (0) el NIC no es 0: si la encía está sana y coronal a la UAC, usa un margen positivo igual al sondaje."}
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={healthy.mobility}
              onChange={(event) => setHealthy({ ...healthy, mobility: event.target.checked })} />
            Movilidad 0 en las piezas sin movilidad registrada
          </label>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setFillOpen(false)}>Cancelar</Button>
            <Button type="submit">Llenar sitios vacíos</Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        isOpen={confirmFinalize}
        title="Finalizar periodontograma"
        message="Al finalizarlo queda guardado tal como está y ya no se puede modificar. Si después encuentras un error, tendrás que anularlo y registrar otro."
        confirmLabel="Finalizar"
        isPending={finalize.isPending}
        onConfirm={() => finalize.mutate()}
        onCancel={() => setConfirmFinalize(false)}
      />

      <Modal isOpen={voiding} onClose={closeVoid} title="Anular periodontograma">
        <form
          aria-label="Anular periodontograma"
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            voidExam.mutate();
          }}
        >
          <p className="text-sm text-slate-600">No se borra: queda en el historial como anulado, con el motivo.</p>
          <Textarea
            label="Motivo"
            rows={3}
            maxLength={500}
            value={voidReason}
            onChange={(event) => setVoidReason(event.target.value)}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={closeVoid}>Cancelar</Button>
            <Button type="submit" variant="danger" disabled={!voidReason.trim() || voidExam.isPending}>
              {voidExam.isPending ? "Anulando..." : "Anular periodontograma"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
