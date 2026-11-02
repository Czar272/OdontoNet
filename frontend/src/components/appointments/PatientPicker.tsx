import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { getPatients } from "../../services/patientService";

interface SelectedPatient {
  id: number;
  name: string;
}

interface PatientPickerProps {
  value: SelectedPatient | null;
  onChange: (patient: SelectedPatient | null) => void;
  disabled?: boolean;
}

/** Búsqueda de pacientes activos en el backend (nombre, correo o teléfono). */
export default function PatientPicker({ value, onChange, disabled }: PatientPickerProps) {
  const inputId = useId();
  const [search, setSearch] = useState("");
  const term = useDebouncedValue(search.trim(), 300);

  const { data, isFetching } = useQuery({
    queryKey: ["patients", "list", { archived: false, search: term, picker: true }],
    queryFn: () => getPatients({ search: term, pageSize: 8 }),
    enabled: !value && term.length > 0,
  });

  if (value) {
    return (
      <div className="flex flex-col gap-2">
        <span className="font-medium text-sm">Paciente *</span>
        <div className="flex items-center justify-between border rounded-xl p-3 bg-gray-50">
          <span className="font-medium">{value.name}</span>
          {!disabled && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className="text-sm underline text-gray-600 hover:text-gray-900"
            >
              Cambiar
            </button>
          )}
        </div>
      </div>
    );
  }

  const results = data?.items ?? [];

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="font-medium text-sm">
        Paciente *
      </label>
      <input
        id={inputId}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Buscar por nombre, correo o teléfono..."
        maxLength={100}
        disabled={disabled}
        autoComplete="off"
        className="border rounded-xl p-3 outline-none focus:ring-2 focus:ring-gray-900"
      />

      {term && (
        <ul
          aria-label="Resultados de pacientes"
          className="border rounded-xl divide-y max-h-56 overflow-y-auto"
        >
          {results.map((patient) => (
            <li key={patient.id}>
              <button
                type="button"
                onClick={() => {
                  onChange({ id: patient.id, name: `${patient.first_name} ${patient.last_name}` });
                  setSearch("");
                }}
                className="w-full text-left p-3 hover:bg-gray-50"
              >
                <span className="font-medium">
                  {patient.first_name} {patient.last_name}
                </span>
                <span className="block text-xs text-gray-500">
                  {[patient.phone, patient.email].filter(Boolean).join(" · ") || "Sin contacto"}
                </span>
              </button>
            </li>
          ))}

          {!isFetching && results.length === 0 && (
            <li className="p-3 text-sm text-gray-500">
              No hay pacientes activos que coincidan.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
