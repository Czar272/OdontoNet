import { useState } from "react";

import {
  periodError,
  presetPeriod,
  type Period,
  type PeriodPreset,
} from "../components/dashboard/period";

export type PeriodChoice = PeriodPreset | "custom";

/** Periodo con atajos (mes en curso por defecto) o personalizado (ODON-202, ODON-206). */
export function usePeriodFilter() {
  const [preset, setPreset] = useState<PeriodChoice>("this_month");
  const [custom, setCustom] = useState<Period>(() => presetPeriod("this_month"));
  const period = preset === "custom" ? custom : presetPeriod(preset);
  const error = preset === "custom" ? periodError(custom) : null;
  return { preset, setPreset, custom, setCustom, period, error };
}
