import { describe, expect, it } from "vitest";

import { STATUS_COLORS } from "../../types/appointment";
import {
  DOCTOR_PALETTE,
  doctorColor,
  doctorColorMap,
  doctorInitials,
  doctorShortName,
  lighten,
} from "./agendaColors";

describe("doctorColorMap", () => {
  it("asigna colores distintos por orden de id, sin importar el orden recibido", () => {
    const colors = doctorColorMap([{ id: 7 }, { id: 2 }, { id: 4 }]);

    expect(colors.get(2)).toBe(DOCTOR_PALETTE[0]);
    expect(colors.get(4)).toBe(DOCTOR_PALETTE[1]);
    expect(colors.get(7)).toBe(DOCTOR_PALETTE[2]);
  });

  it("un doctor nuevo no cambia el color de los existentes", () => {
    const before = doctorColorMap([{ id: 1 }, { id: 2 }]);
    const after = doctorColorMap([{ id: 1 }, { id: 2 }, { id: 9 }]);

    expect(after.get(1)).toBe(before.get(1));
    expect(after.get(2)).toBe(before.get(2));
  });

  it("usa un color de respaldo para un doctor que no está en la lista", () => {
    expect(DOCTOR_PALETTE).toContain(doctorColor(new Map(), 13));
  });

  it("no repite los colores de estado", () => {
    const statusColors = Object.values(STATUS_COLORS);
    expect(DOCTOR_PALETTE.some((color) => statusColors.includes(color))).toBe(false);
  });
});

describe("lighten", () => {
  it("mezcla con blanco y devuelve un color opaco", () => {
    expect(lighten("#6d28d9", 0)).toBe("#ffffff");
    expect(lighten("#6d28d9", 1)).toBe("#6d28d9");
    expect(lighten("#000000", 0.5)).toBe("#808080");
  });
});

describe("doctorShortName", () => {
  it.each([
    ["Dra. Ana Morales", "Dra. Morales"],
    ["Dr. Luis Herrera García", "Dr. García"],
    ["Luis Herrera López", "L. López"],
    ["Ana Morales", "Ana Morales"],
    ["Recepción", "Recepción"],
  ])("%s → %s", (name, short) => {
    expect(doctorShortName(name)).toBe(short);
  });
});

describe("doctorInitials", () => {
  it.each([
    ["Dra. Ana Morales", "AM"],
    ["Dr. Luis Herrera García", "LG"],
    ["Luis", "L"],
  ])("%s → %s", (name, initials) => {
    expect(doctorInitials(name)).toBe(initials);
  });
});
