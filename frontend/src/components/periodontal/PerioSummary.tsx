import type { ExamSummary } from "../../types/periodontal";
import { DEEP_SITE_MM } from "./periodontalChart";

const number = new Intl.NumberFormat("es", { maximumFractionDigits: 2 });

/** Resumen descriptivo del examen. No constituye diagnóstico ni estadio. */
export default function PerioSummary({ summary }: { summary: ExamSummary }) {
  const items: [string, string][] = [
    ["Sondaje medio", summary.mean_probing_depth === null ? "–" : `${number.format(summary.mean_probing_depth)} mm`],
    ["NIC medio", summary.mean_attachment_level === null ? "–" : `${number.format(summary.mean_attachment_level)} mm`],
    ["Sangrado al sondaje", summary.bleeding_pct === null ? "–" : `${number.format(summary.bleeding_pct)} %`],
    ["Placa", summary.plaque_pct === null ? "–" : `${number.format(summary.plaque_pct)} %`],
    [`Sitios ≥ ${DEEP_SITE_MM} mm`, summary.deep_sites_pct === null ? "–" : `${number.format(summary.deep_sites_pct)} %`],
    ["Sitios medidos", String(summary.measured_sites)],
    ["Piezas presentes", String(summary.present_teeth)],
    ["Predeterminados", String(summary.default_sites ?? 0)],
  ];
  return (
    <section aria-label="Resumen del periodontograma" className="rounded-xl bg-teal-50/60 p-4">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4 lg:grid-cols-8">
        {items.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="text-lg font-semibold tabular-nums text-slate-900">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        Estadística descriptiva sobre los sitios con sondaje de las piezas presentes. No constituye diagnóstico.
        {(summary.default_sites ?? 0) > 0 &&
          ` ${summary.default_sites} sitios tienen un valor predeterminado sin editar (gris cursiva): revísalos antes de finalizar.`}
      </p>
    </section>
  );
}

export function PerioLegend() {
  return (
    <ul aria-label="Leyenda" className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
      <li className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-red-600" />Margen gingival</li>
      <li className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-blue-600" />Fondo de la bolsa</li>
      <li className="flex items-center gap-1.5"><span className="h-3 w-5 rounded-sm bg-blue-600/20" />Bolsa</li>
      <li className="flex items-center gap-1.5"><span className="h-px w-5 border-t border-dashed border-slate-400" />UAC</li>
      <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-600" />Sangrado</li>
      <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-yellow-500" />Supuración</li>
      <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-sky-500" />Placa</li>
      <li className="italic text-slate-400">Gris cursiva = valor predeterminado sin editar</li>
      <li>Margen: negativo = recesión · NIC = sondaje − margen</li>
    </ul>
  );
}
