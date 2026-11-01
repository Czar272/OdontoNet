import { afterEach, describe, expect, it } from "vitest";

import { clearToken, getToken, setToken } from "./session";

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe("session", () => {
  it("sin Recuérdame guarda el token solo en sessionStorage", () => {
    setToken("corto");

    expect(sessionStorage.getItem("token")).toBe("corto");
    expect(localStorage.getItem("token")).toBeNull();
    expect(getToken()).toBe("corto");
  });

  it("con Recuérdame guarda el token solo en localStorage", () => {
    setToken("largo", true);

    expect(localStorage.getItem("token")).toBe("largo");
    expect(sessionStorage.getItem("token")).toBeNull();
    expect(getToken()).toBe("largo");
  });

  it("un nuevo login reemplaza el token anterior en ambos almacenamientos", () => {
    setToken("largo", true);
    setToken("corto");

    expect(localStorage.getItem("token")).toBeNull();
    expect(getToken()).toBe("corto");
  });

  it("cerrar sesión borra ambos", () => {
    setToken("largo", true);
    sessionStorage.setItem("token", "otro");

    clearToken();

    expect(getToken()).toBeNull();
  });
});
