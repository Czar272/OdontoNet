import Input from "../basic/Input";
import Select from "../basic/Select";
import type { Doctor } from "../../types/doctor";
import type { PeriodChoice, usePeriodFilter } from "../../hooks/usePeriodFilter";
import { PERIOD_PRESETS, formatPeriod } from "./period";

interface PeriodDoctorFiltersProps {
  periodFilter: ReturnType<typeof usePeriodFilter>;
  doctors: Doctor[];
  ownDoctorId?: number;
  doctorId: number | null;
  onDoctorChange: (choice: number | "all") => void;
  /** Controles extra al final de la fila (p. ej. la agrupación). */
  children?: React.ReactNode;
}

/** Filtros compartidos del panel de inicio y los reportes. */
export default function PeriodDoctorFilters({
  periodFilter,
  doctors,
  ownDoctorId,
  doctorId,
  onDoctorChange,
  children,
}: PeriodDoctorFiltersProps) {
  const { preset, setPreset, custom, setCustom, period, error } = periodFilter;

  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-48">
          <Select
            label="Periodo"
            value={preset}
            onChange={(event) => setPreset(event.target.value as PeriodChoice)}
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
              onDoctorChange(event.target.value === "all" ? "all" : Number(event.target.value))
            }
          >
            <option value="all">Todos los doctores</option>
            {doctors.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.user.name}
                {doctor.id === ownDoctorId ? " (yo)" : ""}
              </option>
            ))}
          </Select>
        </div>

        {children}

        <p className="text-sm text-gray-500 pb-3">{formatPeriod(period)}</p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-600 mt-3">
          {error}
        </p>
      )}
    </div>
  );
}
