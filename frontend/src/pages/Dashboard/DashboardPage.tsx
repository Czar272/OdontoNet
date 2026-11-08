import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Button from "../../components/basic/Button";
import Card from "../../components/basic/Card";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import { useAuth } from "../../context/AuthContext";
import { getDashboard } from "../../services/dashboardService";
import { getDoctors } from "../../services/doctorService";
import { STATUS_COLORS, STATUS_LABELS } from "../../types/appointment";
import type { DashboardAgendaItem, DashboardIndicators } from "../../types/dashboard";
import {
  INDICATORS,
  PRIMARY_COUNT,
  formatIndicator,
  loadExpanded,
  saveExpanded,
} from "./dashboardIndicators";
import {
  PERIOD_PRESETS,
  formatPeriod,
  periodError,
  presetPeriod,
  type Period,
  type PeriodPreset,
} from "./dashboardPeriod";

/** "all": todos los doctores · null: aún sin elegir (se usa el valor por defecto). */
type DoctorChoice = number | "all" | null;

/**
 * Inicio (ODON-202): indicadores de la clínica en una cuadrícula de cuatro,
 * ampliable, y la agenda de hoy. Lo ven los tres roles; un doctor entra
 * enfocado en sus propios datos y puede cambiar a toda la clínica.
 */
export default function DashboardPage() {
  const { user } = useAuth();

  const [preset, setPreset] = useState<PeriodPreset | "custom">("this_month");
  const [custom, setCustom] = useState<Period>(() => presetPeriod("this_month"));
  const period = preset === "custom" ? custom : presetPeriod(preset);
  const customError = preset === "custom" ? periodError(custom) : null;

  const {
    data: doctors,
    isSuccess: doctorsLoaded,
    isError: doctorsFailed,
  } = useQuery({
    queryKey: ["doctors"],
    queryFn: () => getDoctors(),
  });
  const activeDoctors = (doctors ?? []).filter((doctor) => doctor.user.is_active);
  const ownDoctor =
    user?.role === "doctor"
      ? activeDoctors.find((doctor) => doctor.user_id === user.id)
      : undefined;

  const [doctorChoice, setDoctorChoice] = useState<DoctorChoice>(null);
  const doctorId =
    doctorChoice === "all" ? null : (doctorChoice ?? ownDoctor?.id ?? null);
  // Un doctor espera a conocer su perfil para no pedir primero toda la clínica.
  // Si la lista de doctores falla, se muestra toda la clínica en vez de quedar en blanco.
  const ready =
    user?.role !== "doctor" || doctorsLoaded || doctorsFailed || doctorChoice !== null;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", period.from, period.to, doctorId],
    queryFn: () => getDashboard({ from: period.from, to: period.to, doctorId }),
    enabled: ready && !customError,
  });

  const [expanded, setExpanded] = useState(() => loadExpanded(user?.id));
  const toggleExpanded = () => {
    saveExpanded(user?.id, !expanded);
    setExpanded(!expanded);
  };

  const visible = expanded ? INDICATORS : INDICATORS.slice(0, PRIMARY_COUNT);

  return (
    <div>
      <PageHeader
        title="Inicio"
        description={`Bienvenido a OdontoNet${user ? `, ${user.name}` : ""}. ${user?.clinic.name ?? ""}`}
      />

      <div className="flex flex-wrap items-end gap-4 mb-6">
        <div className="w-48">
          <Select
            label="Periodo"
            value={preset}
            onChange={(event) => setPreset(event.target.value as PeriodPreset | "custom")}
          >
            {PERIOD_PRESETS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            <option value="custom">Personalizado</option>
          </Select>
        </div>

        {preset === "custom" && (
          <>
            <div className="w-44">
              <Input
                label="Desde"
                type="date"
                value={custom.from}
                onChange={(event) => setCustom({ ...custom, from: event.target.value })}
              />
            </div>
            <div className="w-44">
              <Input
                label="Hasta"
                type="date"
                value={custom.to}
                onChange={(event) => setCustom({ ...custom, to: event.target.value })}
              />
            </div>
          </>
        )}

        <div className="w-64">
          <Select
            label="Doctor"
            value={doctorId === null ? "all" : String(doctorId)}
            onChange={(event) =>
              setDoctorChoice(event.target.value === "all" ? "all" : Number(event.target.value))
            }
          >
            <option value="all">Todos los doctores</option>
            {activeDoctors.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.user.name}
                {doctor.id === ownDoctor?.id ? " (yo)" : ""}
              </option>
            ))}
          </Select>
        </div>

        <p className="text-sm text-gray-500 pb-3">{formatPeriod(period)}</p>
      </div>

      {customError && (
        <p role="alert" className="text-sm text-red-600 mb-6">
          {customError}
        </p>
      )}

      {isError && (
        <p role="alert" className="text-red-600 mb-6">
          No se pudieron cargar los indicadores.
        </p>
      )}

      {isLoading && ready && !customError ? (
        <LoadingSpinner />
      ) : (
        data && (
          <>
            <IndicatorGrid indicators={data.indicators} keys={visible} />

            <div className="mt-4 mb-8">
              <Button variant="secondary" onClick={toggleExpanded} aria-expanded={expanded}>
                {expanded ? "Mostrar menos indicadores" : "Mostrar más indicadores"}
              </Button>
            </div>

            <AgendaToday items={data.agenda_today} />
          </>
        )
      )}
    </div>
  );
}

function IndicatorGrid({
  indicators,
  keys,
}: {
  indicators: DashboardIndicators;
  keys: typeof INDICATORS;
}) {
  return (
    <ul aria-label="Indicadores" className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
      {keys.map((indicator) => (
        <li key={indicator.key}>
          <Card className="h-full">
            <p className="text-sm font-medium text-gray-500">{indicator.label}</p>
            <p className="text-3xl font-bold mt-2 tabular-nums">
              {formatIndicator(indicators[indicator.key], indicator.percent)}
            </p>
            <p className="text-xs text-gray-400 mt-2">{indicator.hint}</p>
          </Card>
        </li>
      ))}
    </ul>
  );
}

function AgendaToday({ items }: { items: DashboardAgendaItem[] }) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Agenda de hoy</h2>
        <Link to="/agenda" className="text-sm font-medium underline">
          Ir a la agenda
        </Link>
      </div>

      {items.length === 0 ? (
        <p className="text-gray-500">No hay citas para hoy.</p>
      ) : (
        <ul className="divide-y" aria-label="Citas de hoy">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
              <span className="w-14 font-semibold tabular-nums">
                {new Date(item.starts_at).toLocaleTimeString("es-GT", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <Link to={`/patients/${item.patient.id}`} className="font-medium hover:underline">
                {item.patient.name}
              </Link>
              <span className="text-sm text-gray-500">{item.doctor.name}</span>
              <span
                className="ml-auto text-xs font-medium px-2 py-1 rounded-full text-white"
                style={{ backgroundColor: STATUS_COLORS[item.status] }}
              >
                {STATUS_LABELS[item.status]}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
