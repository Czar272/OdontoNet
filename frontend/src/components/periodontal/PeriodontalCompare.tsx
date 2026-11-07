import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";

import LoadingSpinner from "../basic/LoadingSpinner";
import { getPeriodontalExam } from "../../services/periodontalService";
import type { ExamSummary, PeriodontalExamListItem } from "../../types/periodontal";
import PerioChart from "./PerioChart";
import type { ChartActions } from "./PerioGrid";
import { chronological, compareExams } from "./compareExams";
import { DEEP_SITE_MM, SIGNIFICANT_CHANGE_MM, chartFromExam, siteLabel } from "./periodontalChart";
import { periodontalExamKey } from "./periodontalExam";

const dateFormat = new Intl.DateTimeFormat("es", { dateStyle: "medium", timeZone: "UTC" });
const number = new Intl.NumberFormat("es", { maximumFractionDigits: 2, signDisplay: "exceptZero" });
const plain = new Intl.NumberFormat("es", { maximumFractionDigits: 2 });
const value = (amount: number | null | undefined, unit: string) =>
  amount === null || amount === undefined ? "–" : `${plain.format(amount)} ${unit}`;

const READ_ONLY: ChartActions = {
  updateSite: () => {},
  updateTooth: () => {},
  toggleMissing: () => {},
  openNote: () => {},
};

const ROWS: [keyof ExamSummary, string, string][] = [
  ["mean_probing_depth", "Sondaje medio", "mm"],
  ["mean_attachment_level", "NIC medio", "mm"],
  ["bleeding_pct", "Sangrado al sondaje", "%"],
  ["plaque_pct", "Placa", "%"],
  ["deep_sites_pct", `Sitios ≥ ${DEEP_SITE_MM} mm`, "%"],
];

const TOOTH_CHANGE_LABELS = {
  lost: "ausente en el examen reciente",
  implant: "ahora implante",
  natural: "registrada como pieza natural (antes implante)",
  restored: "presente de nuevo",
};

interface PeriodontalCompareProps {
  patientId: number;
  /** Exámenes finalizados y no anulados, del más reciente al más antiguo. */
  exams: PeriodontalExamListItem[];
}

const label = (exam: PeriodontalExamListItem) =>
  `${dateFormat.format(new Date(exam.exam_date))} · ${exam.status === "final" ? "finalizado" : "borrador"} · ${exam.created_by.name}`;

/** Comparación de dos periodontogramas (ODON-194). Describe cambios; no diagnostica. */
export default function PeriodontalCompare({ patientId, exams }: PeriodontalCompareProps) {
  const [secondId, setSecondId] = useState(exams[0].id);
  const [firstId, setFirstId] = useState(exams[1].id);

  const load = (id: number) => ({
    queryKey: periodontalExamKey(patientId, id),
    queryFn: () => getPeriodontalExam(patientId, id),
  });
  const { data: first } = useQuery(load(firstId));
  const { data: second } = useQuery(load(secondId));
  // Se muestran siempre del más antiguo al más reciente, aunque se elijan al revés.
  const [before, after] = first && second ? chronological(first, second) : [undefined, undefined];

  const comparison = useMemo(
    () => (before && after && before.id !== after.id ? compareExams(before, after) : null),
    [before, after],
  );

  const select = (id: string, value: number, onChange: (id: number) => void, text: string) => (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium">{text}</label>
      <select id={id} value={value} onChange={(event) => onChange(Number(event.target.value))} className="rounded-xl border p-3">
        {exams.map((exam) => <option key={exam.id} value={exam.id}>{label(exam)}</option>)}
      </select>
    </div>
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 md:grid-cols-2">
        {select("perio-first", firstId, setFirstId, "Primer examen")}
        {select("perio-second", secondId, setSecondId, "Segundo examen")}
      </div>

      {firstId === secondId ? (
        <p className="text-slate-500">Elige dos exámenes distintos.</p>
      ) : !before || !after || !comparison ? (
        <LoadingSpinner />
      ) : (
        <>
          <section aria-label="Resumen comparado" className="overflow-x-auto rounded-xl bg-teal-50/60 p-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1 font-medium">Indicador</th>
                  <th className="py-1 font-medium">{dateFormat.format(new Date(before.exam_date))}</th>
                  <th className="py-1 font-medium">{dateFormat.format(new Date(after.exam_date))}</th>
                  <th className="py-1 font-medium">Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {ROWS.map(([key, text, unit]) => {
                  const diff = comparison.summaryDelta[key];
                  return (
                    <tr key={key}>
                      <td className="py-1">{text}</td>
                      <td className="py-1 tabular-nums">{value(before.summary[key], unit)}</td>
                      <td className="py-1 tabular-nums">{value(after.summary[key], unit)}</td>
                      <td className="py-1 tabular-nums">{diff === null || diff === undefined ? "–" : `${number.format(diff)} ${unit}`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-slate-500">
              Se resaltan las piezas con cambios de sondaje de {SIGNIFICANT_CHANGE_MM} mm o más. Describe diferencias entre
              registros; no constituye diagnóstico.
            </p>
          </section>

          {comparison.toothChanges.length > 0 && (
            <ul aria-label="Cambios por pieza" className="flex flex-wrap gap-2 text-sm">
              {comparison.toothChanges.map((change) => (
                <li key={change.tooth} className="rounded-full bg-slate-100 px-3 py-1">
                  Pieza {change.tooth}: {TOOTH_CHANGE_LABELS[change.change]}
                </li>
              ))}
            </ul>
          )}

          <p className="text-sm text-slate-600">
            Dibujo del examen del {dateFormat.format(new Date(after.exam_date))}.{" "}
            {comparison.highlighted.size > 0
              ? `Piezas con cambios de ${SIGNIFICANT_CHANGE_MM} mm o más (resaltadas): ${[...comparison.highlighted].join(", ")}.`
              : `Ninguna pieza cambió ${SIGNIFICANT_CHANGE_MM} mm o más.`}
          </p>
          <PerioChart chart={chartFromExam(after)} readOnly actions={READ_ONLY} highlighted={comparison.highlighted} />

          <section aria-label="Sitios con cambios">
            <h3 className="mb-2 font-semibold">
              Sitios con cambios ({comparison.changes.length}; {comparison.significant.length} de {SIGNIFICANT_CHANGE_MM} mm o más)
            </h3>
            {comparison.changes.length === 0 ? (
              <p className="text-slate-500">No hay diferencias de sondaje, margen ni sangrado entre los dos exámenes.</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-slate-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">Pieza</th>
                      <th className="px-3 py-2 font-medium">Sitio</th>
                      <th className="px-3 py-2 font-medium">Sondaje</th>
                      <th className="px-3 py-2 font-medium">Margen</th>
                      <th className="px-3 py-2 font-medium">NIC</th>
                      <th className="px-3 py-2 font-medium">Sangrado</th>
                      <th className="px-3 py-2 font-medium">≥ {SIGNIFICANT_CHANGE_MM} mm</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.changes.map((change) => (
                      <tr key={`${change.tooth}-${change.site}`}
                        className={clsx("border-t", change.significant && "bg-amber-50 font-medium")}>
                        <td className="px-3 py-1.5 tabular-nums">{change.tooth}</td>
                        <td className="px-3 py-1.5">{siteLabel(change.tooth, change.site)}</td>
                        <td className="px-3 py-1.5 tabular-nums">
                          {change.before.probing_depth ?? "–"} → {change.after.probing_depth ?? "–"}
                          {change.probingDelta !== null && change.probingDelta !== 0 && ` (${number.format(change.probingDelta)})`}
                        </td>
                        <td className="px-3 py-1.5 tabular-nums">{change.before.gingival_margin ?? "–"} → {change.after.gingival_margin ?? "–"}</td>
                        <td className="px-3 py-1.5 tabular-nums">
                          {change.before.attachment_level ?? "–"} → {change.after.attachment_level ?? "–"}
                          {change.attachmentDelta !== null && change.attachmentDelta !== 0 && ` (${number.format(change.attachmentDelta)})`}
                        </td>
                        <td className="px-3 py-1.5">{change.before.bleeding ? "sí" : "no"} → {change.after.bleeding ? "sí" : "no"}</td>
                        <td className="px-3 py-1.5">{change.significant ? "Sí" : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
