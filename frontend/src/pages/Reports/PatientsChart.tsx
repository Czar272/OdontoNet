import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { PatientsReport } from "../../types/report";
import { SINGLE_SERIES_COLOR, bucketLabel } from "./reportFormat";

/** Pacientes nuevos por grupo de fechas (una sola serie, sin leyenda). */
export default function PatientsChart({ report }: { report: PatientsReport }) {
  const data = report.series.map((row) => ({ ...row, label: bucketLabel(row, report.group) }));

  return (
    <div className="h-64" aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="20%">
          <CartesianGrid vertical={false} stroke="#e5e7eb" />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#6b7280" }} tickLine={false} axisLine={{ stroke: "#d1d5db" }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#6b7280" }} tickLine={false} axisLine={false} width={32} />
          <Tooltip cursor={{ fill: "rgba(17, 24, 39, 0.05)" }} />
          <Bar dataKey="new_patients" name="Pacientes nuevos" fill={SINGLE_SERIES_COLOR} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
