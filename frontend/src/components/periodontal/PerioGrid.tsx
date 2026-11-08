import { useState, type KeyboardEvent, type MutableRefObject } from "react";
import clsx from "clsx";

import type { FurcationEntrance, SiteCode, SiteData, ToothData } from "../../types/periodontal";
import {
  FURCATION_GRADES,
  MOBILITY_RANGE,
  FURCATION_LABELS,
  TOOTH_WIDTH,
  attachmentLevel,
  displayEntrances,
  displaySites,
  innerFaceLabel,
  siteLabel,
  valueError,
  type Arch,
  type Face,
} from "./periodontalChart";
import { LABEL_WIDTH, inputKey, isComplete, rowKeys, type NumericField } from "./perioInput";

type ToggleField = "bleeding" | "suppuration" | "plaque";

export interface ChartActions {
  updateSite: (tooth: number, site: SiteCode, patch: Partial<SiteData>) => void;
  updateTooth: (tooth: number, patch: Partial<ToothData>) => void;
  toggleMissing: (tooth: number) => void;
  openNote: (tooth: number) => void;
}

interface PerioGridProps {
  arch: Arch;
  face: Face;
  teeth: ToothData[];
  readOnly: boolean;
  actions: ChartActions;
  /** Registro de campos para mover el foco con el teclado. */
  inputs: MutableRefObject<Map<string, HTMLInputElement>>;
}

const TEXT_PATTERN = /^-?\d{0,2}$/;

function SiteInput({
  field, tooth, site, value, readOnly, missing, isDefault, onValue, inputs, row,
}: {
  field: NumericField;
  tooth: number;
  site: SiteCode;
  value: number | null;
  readOnly: boolean;
  missing: boolean;
  /** Valor predeterminado aún no editado: se muestra en gris cursiva. */
  isDefault: boolean;
  onValue: (value: number | null) => void;
  inputs: MutableRefObject<Map<string, HTMLInputElement>>;
  row: string[];
}) {
  const key = inputKey(field, tooth, site);
  const [text, setText] = useState(value === null ? "" : String(value));
  const [focused, setFocused] = useState(false);
  // Si el valor cambia desde fuera (cargar, copiar, ausente), se refleja.
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    if (!focused) setText(value === null ? "" : String(value));
  }

  const move = (offset: number) => {
    const index = row.indexOf(key);
    const target = inputs.current.get(row[index + offset]);
    if (target) {
      target.focus();
      target.select();
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const other = field === "probing_depth" ? "gingival_margin" : "probing_depth";
    if (event.key === "Enter" || event.key === "ArrowRight") {
      event.preventDefault();
      move(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      move(-1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      inputs.current.get(inputKey(other, tooth, site))?.focus();
    }
  };

  const error = valueError(field, value);
  const label = `${field === "probing_depth" ? "Sondaje" : "Margen gingival"} ${tooth} ${siteLabel(tooth, site)}${missing ? " (pieza ausente)" : ""}${isDefault && value !== null ? " (predeterminado)" : ""}`;

  return (
    <input
      ref={(el) => {
        if (el) inputs.current.set(key, el);
        else inputs.current.delete(key);
      }}
      aria-label={label}
      aria-invalid={error ? true : undefined}
      title={error ?? label}
      inputMode="numeric"
      readOnly={readOnly}
      tabIndex={missing ? -1 : undefined}
      value={text}
      onFocus={(event) => {
        setFocused(true);
        event.target.select();
      }}
      onBlur={() => setFocused(false)}
      onKeyDown={onKeyDown}
      onChange={(event) => {
        const next = event.target.value.trim();
        if (!TEXT_PATTERN.test(next)) return;
        setText(next);
        onValue(next === "" || next === "-" ? null : Number(next));
        if (isComplete(field, next)) move(1);
      }}
      className={clsx(
        "h-6 w-full min-w-0 rounded-[4px] border text-center text-[11px] tabular-nums outline-none",
        "focus:border-teal-600 focus:ring-1 focus:ring-teal-600",
        error ? "border-red-500 bg-red-50 text-red-700" : "border-slate-200 bg-white",
        field === "gingival_margin" && value !== null && value < 0 && !error && "text-red-700",
        // Predeterminado gana sobre el estilo de «profundo»: un valor no editado nunca parece medido.
        isDefault && value !== null && !error
          ? "italic text-slate-400"
          : field === "probing_depth" && value !== null && value >= 4 && !error && "font-semibold text-blue-700",
        readOnly && "bg-slate-50",
      )}
    />
  );
}

function RowLabel({ children }: { children: string }) {
  return <div className="flex items-center pr-2 text-[11px] font-medium text-slate-500">{children}</div>;
}

const TOGGLE_STYLE: Record<ToggleField, { on: string; label: string }> = {
  bleeding: { on: "bg-red-600 border-red-600", label: "Sangrado" },
  suppuration: { on: "bg-yellow-500 border-yellow-500", label: "Supuración" },
  plaque: { on: "bg-sky-500 border-sky-500", label: "Placa" },
};

/**
 * Grilla de captura de una cara de una arcada (ODON-186), alineada columna a
 * columna con su dibujo. En la cara vestibular van además los datos por pieza.
 */
export default function PerioGrid({ arch, face, teeth, readOnly, actions, inputs }: PerioGridProps) {
  const faceLabel = face === "buccal" ? "Vestibular" : innerFaceLabel(arch);
  const columns = { gridTemplateColumns: `${LABEL_WIDTH}px repeat(${teeth.length}, ${TOOTH_WIDTH}px)` };
  const rows: Record<NumericField, string[]> = {
    gingival_margin: rowKeys("gingival_margin", face, teeth),
    probing_depth: rowKeys("probing_depth", face, teeth),
  };

  const perTooth = (render: (tooth: ToothData) => React.ReactNode) =>
    teeth.map((tooth) => (
      <div key={tooth.tooth} className={clsx("flex items-center justify-center gap-px px-0.5", tooth.missing && "opacity-30")}>
        {render(tooth)}
      </div>
    ));

  const perSite = (render: (tooth: ToothData, site: SiteCode) => React.ReactNode) =>
    perTooth((tooth) => displaySites(tooth.tooth, face).map((site) => (
      <div key={site} className="flex flex-1 justify-center">{render(tooth, site)}</div>
    )));

  const entrances = (tooth: number): FurcationEntrance[] => displayEntrances(tooth, face);

  const toggleRow = (field: ToggleField) => (
    <>
      <RowLabel>{TOGGLE_STYLE[field].label}</RowLabel>
      {perSite((tooth, site) => {
        const on = tooth.sites[site][field];
        return (
          <button
            type="button"
            disabled={readOnly || tooth.missing}
            aria-pressed={on}
            aria-label={`${TOGGLE_STYLE[field].label} ${tooth.tooth} ${siteLabel(tooth.tooth, site)}`}
            onClick={() => actions.updateSite(tooth.tooth, site, { [field]: !on })}
            className={clsx(
              "h-3.5 w-3.5 rounded-full border transition",
              on ? TOGGLE_STYLE[field].on : "border-slate-300 bg-white hover:border-slate-500",
              "disabled:cursor-default",
            )}
          />
        );
      })}
    </>
  );

  const numericRow = (field: NumericField, label: string) => (
    <>
      <RowLabel>{label}</RowLabel>
      {perSite((tooth, site) => (
        <SiteInput
          field={field}
          tooth={tooth.tooth}
          site={site}
          value={tooth.sites[site][field]}
          readOnly={readOnly || tooth.missing}
          missing={tooth.missing}
          isDefault={tooth.sites[site].source === "default"}
          onValue={(value) => actions.updateSite(tooth.tooth, site, { [field]: value })}
          inputs={inputs}
          row={rows[field]}
        />
      ))}
    </>
  );

  return (
    <div role="group" aria-label={`Captura ${faceLabel.toLowerCase()} arcada ${arch === "upper" ? "superior" : "inferior"}`}
      className="grid gap-y-1 py-1" style={columns}>
      <div className="flex items-center text-xs font-semibold uppercase tracking-wide text-teal-700">{faceLabel}</div>
      {teeth.map((tooth) => (
        <button
          key={tooth.tooth}
          type="button"
          disabled={readOnly}
          aria-pressed={tooth.missing}
          aria-label={`Pieza ${tooth.tooth}${tooth.missing ? " (ausente)" : ""}: marcar como ${tooth.missing ? "presente" : "ausente"}`}
          title={tooth.missing ? "Pieza ausente. Toca para marcarla presente." : "Toca para marcar la pieza como ausente."}
          onClick={() => actions.toggleMissing(tooth.tooth)}
          className={clsx(
            "mx-0.5 rounded-md py-0.5 text-xs font-semibold tabular-nums transition",
            tooth.missing ? "bg-slate-200 text-slate-400 line-through" : "bg-teal-50 text-teal-800 hover:bg-teal-100",
            "disabled:cursor-default",
          )}
        >
          {tooth.tooth}
        </button>
      ))}

      {face === "buccal" && (
        <>
          <RowLabel>Implante</RowLabel>
          {perTooth((tooth) => (
            <input
              type="checkbox"
              aria-label={`Implante ${tooth.tooth}`}
              disabled={readOnly || tooth.missing}
              checked={tooth.implant}
              onChange={(event) => actions.updateTooth(tooth.tooth, {
                implant: event.target.checked,
                ...(event.target.checked ? { furcation: { b: null, mp: null, dp: null, l: null } } : {}),
              })}
              className="h-3.5 w-3.5 accent-teal-700"
            />
          ))}
          <RowLabel>Movilidad</RowLabel>
          {perTooth((tooth) => (
            <select
              aria-label={`Movilidad ${tooth.tooth}${tooth.source === "default" && tooth.mobility !== null ? " (predeterminado)" : ""}`}
              disabled={readOnly || tooth.missing}
              value={tooth.mobility ?? ""}
              onChange={(event) =>
                actions.updateTooth(tooth.tooth, { mobility: event.target.value === "" ? null : Number(event.target.value) })
              }
              className={clsx(
                "h-6 w-full rounded-[4px] border border-slate-200 bg-white text-center text-[11px]",
                tooth.source === "default" && tooth.mobility !== null && "italic text-slate-400",
              )}
            >
              <option value="">–</option>
              {Array.from({ length: MOBILITY_RANGE[1] - MOBILITY_RANGE[0] + 1 }, (_, i) => MOBILITY_RANGE[0] + i).map((grade) => (
                <option key={grade} value={grade}>{grade}</option>
              ))}
            </select>
          ))}
          <RowLabel>Nota</RowLabel>
          {perTooth((tooth) => (
            <button
              type="button"
              aria-label={`Nota de la pieza ${tooth.tooth}${tooth.note ? ": " + tooth.note : ""}`}
              title={tooth.note ?? "Agregar nota"}
              onClick={() => actions.openNote(tooth.tooth)}
              className={clsx("h-5 w-5 rounded text-[11px]", tooth.note ? "bg-amber-100 text-amber-800" : "text-slate-400 hover:bg-slate-100")}
            >
              ✎
            </button>
          ))}
        </>
      )}

      <RowLabel>Furcación</RowLabel>
      {perTooth((tooth) =>
        entrances(tooth.tooth).map((entrance) => (
          <select
            key={entrance}
            aria-label={`Furcación ${FURCATION_LABELS[entrance].toLowerCase()} ${tooth.tooth}`}
            title={`Furcación ${FURCATION_LABELS[entrance].toLowerCase()}`}
            disabled={readOnly || tooth.missing || tooth.implant}
            value={tooth.furcation[entrance] ?? ""}
            onChange={(event) =>
              actions.updateTooth(tooth.tooth, {
                furcation: { ...tooth.furcation, [entrance]: event.target.value === "" ? null : Number(event.target.value) },
              })
            }
            className="h-6 min-w-0 flex-1 rounded-[4px] border border-slate-200 bg-white text-center text-[11px]"
          >
            <option value="">–</option>
            {FURCATION_GRADES.map((grade) => <option key={grade} value={grade}>{["I", "II", "III"][grade - 1]}</option>)}
          </select>
        )),
      )}

      {toggleRow("bleeding")}
      {toggleRow("suppuration")}
      {toggleRow("plaque")}
      {numericRow("gingival_margin", "Margen gingival")}
      {numericRow("probing_depth", "Sondaje")}

      <RowLabel>NIC</RowLabel>
      {perSite((tooth, site) => {
        const level = attachmentLevel(tooth.sites[site]);
        return (
          <span aria-label={`NIC ${tooth.tooth} ${siteLabel(tooth.tooth, site)}`}
            className="text-[11px] tabular-nums text-slate-500">
            {level ?? ""}
          </span>
        );
      })}
    </div>
  );
}
