import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { STATUS_LABELS } from "../../types/appointment";
import type { AppointmentsReport } from "../../types/report";
import { CHART_STATUSES, bucketLabel } from "./reportFormat";

/** Citas por grupo de fechas, apiladas por estado (se carga aparte con Recharts). */
export default function AppointmentsChart({ report }: { report: AppointmentsReport }) {
  const data = report.series.map((row) => ({ ...row, label: bucketLabel(row, report.group) }));

  return (
    <div className="h-72" aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="20%">
          <CartesianGrid vertical={false} stroke="#e5e7eb" />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#6b7280" }} tickLine={false} axisLine={{ stroke: "#d1d5db" }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#6b7280" }} tickLine={false} axisLine={false} width={32} />
          <Tooltip cursor={{ fill: "rgba(17, 24, 39, 0.05)" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {CHART_STATUSES.map(({ status, color }, index) => (
            <Bar
              key={status}
              dataKey={status}
              name={STATUS_LABELS[status]}
              stackId="status"
              fill={color}
              stroke="#ffffff"
              strokeWidth={1}
              radius={index === CHART_STATUSES.length - 1 ? [4, 4, 0, 0] : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
