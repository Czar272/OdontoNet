import { describe, expect, it } from "vitest";

import {
  CEJ_Y,
  MM,
  PERMANENT_TEETH,
  apicalOf,
  attachmentLevel,
  displaySites,
  emptyChart,
  marginY,
  round,
  pocketY,
  siteLabel,
  summarize,
  toContent,
  valueError,
} from "./periodontalChart";
import { isComplete, rowKeys } from "./perioInput";

describe("piezas y sitios", () => {
  it("tiene las 32 piezas permanentes", () => {
    expect(PERMANENT_TEETH).toHaveLength(32);
    expect(new Set(PERMANENT_TEETH).size).toBe(32);
  });

  it("dibuja lo distal hacia afuera en cada cuadrante", () => {
    expect(displaySites(16, "buccal")).toEqual(["db", "b", "mb"]);
    expect(displaySites(26, "buccal")).toEqual(["mb", "b", "db"]);
    expect(displaySites(46, "lingual")).toEqual(["dl", "l", "ml"]);
    expect(displaySites(36, "lingual")).toEqual(["ml", "l", "dl"]);
  });

  it("nombra «palatino» en la arcada superior", () => {
    expect(siteLabel(16, "ml")).toBe("mesiopalatino");
    expect(siteLabel(46, "ml")).toBe("mesiolingual");
  });
});

describe("geometría", () => {
  it("enfrenta las coronas de las dos caras de cada arcada", () => {
    expect(apicalOf("upper", "buccal")).toBe(-1);
    expect(apicalOf("upper", "lingual")).toBe(1);
    expect(apicalOf("lower", "lingual")).toBe(-1);
    expect(apicalOf("lower", "buccal")).toBe(1);
  });

  it("una recesión baja el margen hacia la raíz y el sondaje parte del margen", () => {
    // Superior vestibular: la raíz está hacia arriba (y menor).
    const site = { probing_depth: 4, gingival_margin: -2, bleeding: false, suppuration: false, plaque: false };
    expect(marginY(-1, -2)).toBe(CEJ_Y - 2 * MM);
    expect(pocketY(-1, site)).toBe(CEJ_Y - 6 * MM);
    // Inferior vestibular: la raíz está hacia abajo.
    expect(marginY(1, -2)).toBe(CEJ_Y + 2 * MM);
    expect(pocketY(1, site)).toBe(CEJ_Y + 6 * MM);
    expect(attachmentLevel(site)).toBe(6);
  });
});

describe("resumen", () => {
  it("coincide con el cálculo del backend y excluye piezas ausentes", () => {
    const chart = emptyChart();
    const t16 = chart.find((t) => t.tooth === 16)!;
    t16.sites.mb = { probing_depth: 5, gingival_margin: -2, bleeding: true, suppuration: false, plaque: false };
    t16.sites.b = { probing_depth: 3, gingival_margin: 0, bleeding: false, suppuration: false, plaque: true };
    t16.sites.db = { probing_depth: 4, gingival_margin: -1, bleeding: true, suppuration: true, plaque: false };
    t16.sites.ml = { probing_depth: 2, gingival_margin: 1, bleeding: false, suppuration: false, plaque: false };
    const t21 = chart.find((t) => t.tooth === 21)!;
    t21.implant = true;
    t21.sites.b = { probing_depth: 2, gingival_margin: 0, bleeding: false, suppuration: false, plaque: false };
    chart.find((t) => t.tooth === 38)!.missing = true;

    expect(summarize(chart)).toEqual({
      present_teeth: 31,
      measured_sites: 5,
      mean_probing_depth: 3.2,
      mean_attachment_level: 3.6,
      bleeding_pct: 40,
      plaque_pct: 20,
      deep_sites_pct: 40,
    });
  });

  it("redondea los empates al par, como el backend", () => {
    expect(round(2.125, 2)).toBe(2.12);
    expect(round(2.135, 2)).toBe(2.14);
    expect(round(33.35, 1)).toBe(33.4);
    expect(round(12.5, 0)).toBe(12);
  });

  it("sin sondajes no hay promedios", () => {
    expect(summarize(emptyChart()).mean_probing_depth).toBeNull();
  });
});

describe("contenido y validación", () => {
  it("envía solo las piezas con algún dato", () => {
    const chart = emptyChart();
    chart.find((t) => t.tooth === 11)!.mobility = 1;
    const content = toContent("2026-11-07", null, "  ", chart);
    expect(content.teeth.map((t) => t.tooth)).toEqual([11]);
    expect(content.notes).toBeNull();
  });

  it("valida los rangos acordados", () => {
    expect(valueError("probing_depth", 15)).toBeNull();
    expect(valueError("probing_depth", 16)).toMatch(/0 a 15/);
    expect(valueError("gingival_margin", -15)).toBeNull();
    expect(valueError("gingival_margin", 6)).toMatch(/\+5/);
  });

  it("espera al segundo dígito cuando el valor puede crecer", () => {
    expect(isComplete("probing_depth", "1")).toBe(false);
    expect(isComplete("probing_depth", "3")).toBe(true);
    expect(isComplete("probing_depth", "12")).toBe(true);
    expect(isComplete("gingival_margin", "-")).toBe(false);
    expect(isComplete("gingival_margin", "-1")).toBe(false);
    expect(isComplete("gingival_margin", "-2")).toBe(true);
    expect(isComplete("gingival_margin", "1")).toBe(true);
  });

  it("el orden de captura salta las piezas ausentes", () => {
    const chart = emptyChart().filter((t) => [18, 17].includes(t.tooth));
    chart[0].missing = true;
    expect(rowKeys("probing_depth", "buccal", chart)).toEqual([
      "probing_depth:17:db", "probing_depth:17:b", "probing_depth:17:mb",
    ]);
  });
});
