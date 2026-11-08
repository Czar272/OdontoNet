import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";

import Button from "../../components/basic/Button";
import Card from "../../components/basic/Card";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import PeriodDoctorFilters from "../../components/dashboard/PeriodDoctorFilters";
import { useDoctorFilter } from "../../hooks/useDoctorFilter";
import { usePeriodFilter } from "../../hooks/usePeriodFilter";
import { usePermission } from "../../hooks/usePermission";
import { getApiErrorMessage } from "../../services/apiError";
import {
  downloadReportCsv,
  getAppointmentsReport,
  getPatientsReport,
} from "../../services/reportService";
import { STATUS_LABELS } from "../../types/appointment";
import type {
  AppointmentsReport,
  PatientsReport,
  ReportGrouping,
  ReportKind,
  ReportParams,
} from "../../types/report";
import { saveBlob } from "../../utils/saveBlob";
import AppointmentsChart from "./AppointmentsChart";
import PatientsChart from "./PatientsChart";
import { CHART_STATUSES, GROUP_OPTIONS, bucketLabel, formatRate } from "./reportFormat";

/**
 * Reportes de citas y pacientes (ODON-206): series por día, semana o mes en
 * la zona de la clínica, con filtro de periodo y doctor. Cada gráfico tiene
 * su tabla equivalente. Solo administración exporta a CSV.
 */
export default function ReportsPage() {
  const periodFilter = usePeriodFilter();
  const { period, error: periodError } = periodFilter;
  const { activeDoctors, ownDoctor, doctorId, setDoctorChoice, ready } = useDoctorFilter();
  const [group, setGroup] = useState<ReportGrouping>("day");
  const canExport = usePermission("reports:export");

  const params: ReportParams = { from: period.from, to: period.to, doctorId, group };
  const enabled = ready && !periodError;

  const appointments = useQuery({
    queryKey: ["reports", "appointments", params],
    queryFn: () => getAppointmentsReport(params),
    enabled,
  });
  const patients = useQuery({
    queryKey: ["reports", "patients", params],
    queryFn: () => getPatientsReport(params),
    enabled,
  });

  const exportCsv = useMutation({
    mutationFn: (kind: ReportKind) => downloadReportCsv(kind, params),
    onSuccess: ({ blob, filename }) => saveBlob(blob, filename),
    onError: (error) => toast.error(getApiErrorMessage(error, "No se pudo exportar el reporte")),
  });

  const exportButton = (kind: ReportKind) =>
    canExport && (
      <Button
        variant="secondary"
        onClick={() => exportCsv.mutate(kind)}
        disabled={exportCsv.isPending || !enabled}
      >
        Exportar CSV
      </Button>
    );

  return (
    <div>
      <PageHeader
        title="Reportes"
        description="Tendencias de citas y pacientes de la clínica. Solo datos agregados."
      />

      <PeriodDoctorFilters
        periodFilter={periodFilter}
        doctors={activeDoctors}
        ownDoctorId={ownDoctor?.id}
        doctorId={doctorId}
        onDoctorChange={setDoctorChoice}
      >
        <div className="w-40">
          <Select
            label="Agrupar"
            value={group}
            onChange={(event) => setGroup(event.target.value as ReportGrouping)}
          >
            {GROUP_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </PeriodDoctorFilters>

      <div className="flex flex-col gap-6">
        <Card>
          <SectionHeader title="Citas por periodo y estado" action={exportButton("appointments")} />
          <QueryState isLoading={enabled && appointments.isLoading} isError={appointments.isError} />
          {appointments.data && <AppointmentsSection report={appointments.data} />}
        </Card>

        <Card>
          <SectionHeader title="Citas e inasistencias por doctor" />
          <QueryState isLoading={enabled && appointments.isLoading} isError={appointments.isError} />
          {appointments.data && <DoctorsTable report={appointments.data} />}
        </Card>

        <Card>
          <SectionHeader title="Pacientes nuevos" action={exportButton("patients")} />
          <QueryState isLoading={enabled && patients.isLoading} isError={patients.isError} />
          {patients.data && <PatientsSection report={patients.data} />}
        </Card>
      </div>
    </div>
  );
}

function SectionHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
      <h2 className="text-xl font-semibold">{title}</h2>
      {action}
    </div>
  );
}

function QueryState({ isLoading, isError }: { isLoading: boolean; isError: boolean }) {
  if (isLoading) return <LoadingSpinner />;
  if (isError)
    return (
      <p role="alert" className="text-red-600">
        No se pudo cargar el reporte.
      </p>
    );
  return null;
}

function AppointmentsSection({ report }: { report: AppointmentsReport }) {
  const { totals } = report;
  return (
    <>
      <p className="text-sm text-gray-600 mb-4">
        {totals.total} citas · asistencia {formatRate(totals.attendance_rate)} · inasistencia{" "}
        {formatRate(totals.no_show_rate)}
      </p>
      {totals.total === 0 ? (
        <p className="text-gray-500">No hay citas en el periodo.</p>
      ) : (
        <AppointmentsChart report={report} />
      )}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium">Ver como tabla</summary>
        <div className="overflow-x-auto mt-3">
          <table className="min-w-full text-sm" aria-label="Citas por periodo y estado">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="py-2 pr-4 font-medium">Periodo</th>
                {CHART_STATUSES.map(({ status }) => (
                  <th key={status} className="py-2 pr-4 font-medium text-right">
                    {STATUS_LABELS[status]}
                  </th>
                ))}
                <th className="py-2 pr-4 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {report.series.map((row) => (
                <tr key={row.period_start}>
                  <td className="py-2 pr-4">{bucketLabel(row, report.group)}</td>
                  {CHART_STATUSES.map(({ status }) => (
                    <td key={status} className="py-2 pr-4 text-right tabular-nums">
                      {row[status]}
                    </td>
                  ))}
                  <td className="py-2 pr-4 text-right tabular-nums font-medium">{row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}

function DoctorsTable({ report }: { report: AppointmentsReport }) {
  if (report.by_doctor.length === 0) return <p className="text-gray-500">No hay citas en el periodo.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm" aria-label="Citas e inasistencias por doctor">
        <thead>
          <tr className="text-left text-gray-500">
            <th className="py-2 pr-4 font-medium">Doctor</th>
            <th className="py-2 pr-4 font-medium text-right">Citas</th>
            <th className="py-2 pr-4 font-medium text-right">Atendidas</th>
            <th className="py-2 pr-4 font-medium text-right">No asistió</th>
            <th className="py-2 pr-4 font-medium text-right">Inasistencia</th>
            <th className="py-2 pr-4 font-medium text-right">Canceladas</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {report.by_doctor.map((row) => (
            <tr key={row.doctor.id}>
              <td className="py-2 pr-4">{row.doctor.name}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{row.total}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{row.completed}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{row.no_show}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{formatRate(row.no_show_rate)}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{row.cancelled}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PatientsSection({ report }: { report: PatientsReport }) {
  return (
    <>
      <p className="text-sm text-gray-600 mb-4">
        {report.total_new} pacientes nuevos en el periodo.
        {report.without_registration_date > 0 &&
          ` ${report.without_registration_date} pacientes registrados antes de que existiera la fecha de alta no se incluyen.`}
      </p>
      {report.total_new === 0 ? (
        <p className="text-gray-500">No hay pacientes nuevos en el periodo.</p>
      ) : (
        <PatientsChart report={report} />
      )}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium">Ver como tabla</summary>
        <div className="overflow-x-auto mt-3">
          <table className="min-w-full text-sm" aria-label="Pacientes nuevos por periodo">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="py-2 pr-4 font-medium">Periodo</th>
                <th className="py-2 pr-4 font-medium text-right">Pacientes nuevos</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {report.series.map((row) => (
                <tr key={row.period_start}>
                  <td className="py-2 pr-4">{bucketLabel(row, report.group)}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{row.new_patients}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
