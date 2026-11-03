import { useState } from "react";
import clsx from "clsx";

import { TOOTH_CHART, dentitionOf, type Dentition } from "./toothChartLayout";

interface ToothChartProps {
  /** Pieza seleccionada (FDI) o null. */
  value: number | null;
  onChange: (tooth: number | null) => void;
  disabled?: boolean;
}

/**
 * Odontograma para elegir una pieza dental (ODON-260). Cada pieza es un
 * botón con su número; tocar la seleccionada la quita. Complementa el campo
 * de texto, no lo reemplaza.
 */
export default function ToothChart({
  value,
  onChange,
  disabled = false,
}: ToothChartProps) {
  const [dentition, setDentition] = useState<Dentition>(() =>
    dentitionOf(value),
  );
  // Si escriben una pieza de la otra dentición, se muestra esa dentición.
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    if (value !== null && dentitionOf(value) !== dentition) {
      setDentition(dentitionOf(value));
    }
  }

  const rows = TOOTH_CHART[dentition];

  const tooth = (number: number) => {
    const selected = number === value;
    return (
      <button
        key={number}
        type="button"
        disabled={disabled}
        aria-pressed={selected}
        aria-label={`Pieza ${number}`}
        onClick={() => onChange(selected ? null : number)}
        className={clsx(
          "h-9 min-w-0 flex-1 rounded-md border text-xs font-medium transition",
          "focus:outline-none focus:ring-2 focus:ring-gray-900 disabled:opacity-50",
          selected
            ? "bg-gray-900 text-white border-gray-900"
            : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100",
        )}
      >
        {number}
      </button>
    );
  };

  const half = (teeth: number[], side: "right" | "left") => (
    <div
      className={clsx(
        "flex flex-1 gap-1",
        side === "right" ? "pr-1 border-r border-gray-300" : "pl-1",
      )}
    >
      {teeth.map(tooth)}
    </div>
  );

  return (
    <div className="flex flex-col gap-2" role="group" aria-label="Odontograma">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Odontograma</span>
        <div
          className="flex rounded-lg border border-gray-300 overflow-hidden text-xs"
          role="radiogroup"
          aria-label="Dentición"
        >
          {(["permanent", "deciduous"] as Dentition[]).map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={dentition === option}
              disabled={disabled}
              onClick={() => setDentition(option)}
              className={clsx(
                "px-3 py-1",
                dentition === option
                  ? "bg-gray-900 text-white"
                  : "bg-white text-gray-700 hover:bg-gray-100",
              )}
            >
              {option === "permanent" ? "Permanente" : "Temporal"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1 rounded-xl border border-gray-200 p-2">
        <p className="text-[10px] uppercase tracking-wide text-gray-400 text-center">
          Superior
        </p>
        <div className="flex">
          {half(rows.upper[0], "right")}
          {half(rows.upper[1], "left")}
        </div>
        <div className="border-t border-dashed border-gray-300 my-1" />
        <div className="flex">
          {half(rows.lower[0], "right")}
          {half(rows.lower[1], "left")}
        </div>
        <p className="text-[10px] uppercase tracking-wide text-gray-400 text-center">
          Inferior
        </p>
      </div>
      <p className="text-xs text-gray-500">
        Toca una pieza para elegirla; tócala de nuevo para quitarla. También
        puedes escribir el número.
      </p>
    </div>
  );
}
