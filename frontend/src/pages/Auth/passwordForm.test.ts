import { describe, expect, it } from "vitest";

import { validateNewPassword } from "./passwordForm";

describe("validateNewPassword", () => {
  it("acepta una contraseña válida confirmada", () => {
    expect(validateNewPassword("Nueva-Clave-1", "Nueva-Clave-1")).toBeNull();
  });

  it("exige al menos 8 caracteres", () => {
    expect(validateNewPassword("corta", "corta")).toBe("La contraseña debe tener al menos 8 caracteres.");
  });

  it("limita a 128 caracteres", () => {
    const long = "a".repeat(129);
    expect(validateNewPassword(long, long)).toBe("La contraseña debe tener como máximo 128 caracteres.");
  });

  it("exige que la confirmación coincida", () => {
    expect(validateNewPassword("Nueva-Clave-1", "Nueva-Clave-2")).toBe("Las contraseñas no coinciden.");
  });
});
