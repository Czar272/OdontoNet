import { describe, expect, it } from "vitest";

import type { User } from "../../types/user";
import { buildUserChanges, initialUserData } from "./userFormData";

const ana: User = {
  id: 7,
  name: "Ana López",
  email: "ana@odontonet-demo.com",
  role: "receptionist",
  clinic_id: 1,
  is_active: true,
};

describe("buildUserChanges", () => {
  it("sin cambios no envía nada", () => {
    expect(buildUserChanges(ana, initialUserData(ana))).toEqual({});
  });

  it("solo envía los campos modificados", () => {
    const data = { ...initialUserData(ana), name: "  Ana María  ", role: "admin" as const };

    expect(buildUserChanges(ana, data)).toEqual({ name: "Ana María", role: "admin" });
  });

  it("la contraseña vacía no se envía y la escrita sí", () => {
    expect(buildUserChanges(ana, initialUserData(ana))).not.toHaveProperty("password");
    expect(buildUserChanges(ana, { ...initialUserData(ana), password: "Nueva-123" })).toEqual({
      password: "Nueva-123",
    });
  });
});

describe("initialUserData", () => {
  it("un alta empieza vacía con rol doctor", () => {
    expect(initialUserData()).toEqual({ name: "", email: "", password: "", role: "doctor" });
  });
});
