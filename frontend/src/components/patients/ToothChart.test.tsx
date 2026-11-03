import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import ToothChart from "./ToothChart";
import { TOOTH_CHART, dentitionOf } from "./toothChartLayout";

function Harness({ initial = null }: { initial?: number | null }) {
  const [value, setValue] = useState<number | null>(initial);
  return (
    <>
      <input aria-label="pieza" value={value ?? ""} onChange={(e) => setValue(e.target.value ? Number(e.target.value) : null)} />
      <ToothChart value={value} onChange={setValue} />
    </>
  );
}

describe("toothChart", () => {
  it("ordena las piezas como las ve el profesional", () => {
    expect(TOOTH_CHART.permanent.upper).toEqual([
      [18, 17, 16, 15, 14, 13, 12, 11],
      [21, 22, 23, 24, 25, 26, 27, 28],
    ]);
    expect(TOOTH_CHART.permanent.lower).toEqual([
      [48, 47, 46, 45, 44, 43, 42, 41],
      [31, 32, 33, 34, 35, 36, 37, 38],
    ]);
    expect(TOOTH_CHART.deciduous.upper).toEqual([[55, 54, 53, 52, 51], [61, 62, 63, 64, 65]]);
    expect(TOOTH_CHART.deciduous.lower).toEqual([[85, 84, 83, 82, 81], [71, 72, 73, 74, 75]]);
  });

  it("elige la dentición según la pieza", () => {
    expect(dentitionOf(null)).toBe("permanent");
    expect(dentitionOf(36)).toBe("permanent");
    expect(dentitionOf(55)).toBe("deciduous");
  });
});

describe("ToothChart", () => {
  it("muestra las 32 piezas permanentes como botones", () => {
    render(<ToothChart value={null} onChange={() => {}} />);

    expect(screen.getAllByRole("button", { name: /^Pieza \d+$/ })).toHaveLength(32);
  });

  it("tocar una pieza la elige y tocarla de nuevo la quita", () => {
    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: "Pieza 36" }));
    expect(screen.getByLabelText("pieza")).toHaveValue("36");
    expect(screen.getByRole("button", { name: "Pieza 36" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Pieza 36" }));
    expect(screen.getByLabelText("pieza")).toHaveValue("");
  });

  it("refleja lo escrito en el campo, también en temporales", () => {
    render(<Harness />);

    fireEvent.change(screen.getByLabelText("pieza"), { target: { value: "54" } });

    expect(screen.getByRole("radio", { name: "Temporal" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("button", { name: "Pieza 54" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("button", { name: /^Pieza \d+$/ })).toHaveLength(20);
  });

  it("cambia entre dentición permanente y temporal", () => {
    const onChange = vi.fn();
    render(<ToothChart value={null} onChange={onChange} />);

    fireEvent.click(screen.getByRole("radio", { name: "Temporal" }));
    fireEvent.click(screen.getByRole("button", { name: "Pieza 75" }));

    expect(onChange).toHaveBeenCalledWith(75);
    expect(screen.queryByRole("button", { name: "Pieza 36" })).not.toBeInTheDocument();
  });

  it("deshabilitado no permite elegir", () => {
    const onChange = vi.fn();
    render(<ToothChart value={11} onChange={onChange} disabled />);

    fireEvent.click(screen.getByRole("button", { name: "Pieza 21" }));

    expect(onChange).not.toHaveBeenCalled();
  });
});
