import { useRef } from "react";

import type { ToothData } from "../../types/periodontal";
import PerioGrid, { type ChartActions } from "./PerioGrid";
import { LABEL_WIDTH } from "./perioInput";
import ToothFace from "./ToothFace";
import { LOWER_TEETH, UPPER_TEETH, type Arch, type Face } from "./periodontalChart";

interface PerioChartProps {
  chart: ToothData[];
  readOnly: boolean;
  actions: ChartActions;
  highlighted?: Set<number>;
}

/**
 * Periodontograma completo (ODON-186): por arcada, la grilla y el dibujo de
 * cada cara, con las coronas enfrentadas. Superior: vestibular arriba y
 * palatina abajo. Inferior: lingual arriba y vestibular abajo.
 */
export default function PerioChart({ chart, readOnly, actions, highlighted }: PerioChartProps) {
  const inputs = useRef(new Map<string, HTMLInputElement>());
  const byTooth = new Map(chart.map((tooth) => [tooth.tooth, tooth]));
  const teethOf = (arch: Arch) => (arch === "upper" ? UPPER_TEETH : LOWER_TEETH).map((n) => byTooth.get(n)!);

  const face = (arch: Arch, side: Face) => (
    <div style={{ paddingLeft: LABEL_WIDTH }}>
      <ToothFace arch={arch} face={side} teeth={teethOf(arch)} highlighted={highlighted} />
    </div>
  );
  const grid = (arch: Arch, side: Face) => (
    <PerioGrid arch={arch} face={side} teeth={teethOf(arch)} readOnly={readOnly} actions={actions} inputs={inputs} />
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <div className="inline-block min-w-full p-3">
        <section aria-label="Arcada superior" className="border-b border-dashed border-slate-200 pb-3">
          <h3 className="mb-1 text-sm font-semibold text-slate-700">Arcada superior</h3>
          {grid("upper", "buccal")}
          {face("upper", "buccal")}
          {face("upper", "lingual")}
          {grid("upper", "lingual")}
        </section>
        <section aria-label="Arcada inferior" className="pt-3">
          <h3 className="mb-1 text-sm font-semibold text-slate-700">Arcada inferior</h3>
          {grid("lower", "lingual")}
          {face("lower", "lingual")}
          {face("lower", "buccal")}
          {grid("lower", "buccal")}
        </section>
      </div>
    </div>
  );
}
