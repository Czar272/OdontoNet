import { afterEach, describe, expect, it } from "vitest";

import { clearToken, getToken, setToken } from "./session";

afterEach(() => {
  clearToken();
  sessionStorage.clear();
  localStorage.clear();
});

describe("session", () => {
  it("guarda el token solo en memoria", () => {
    setToken("acceso");

    expect(getToken()).toBe("acceso");
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
  });

  it("un token nuevo reemplaza al anterior", () => {
    setToken("viejo");
    setToken("nuevo");

    expect(getToken()).toBe("nuevo");
  });

  it("cerrar sesión borra el token", () => {
    setToken("acceso");

    clearToken();

    expect(getToken()).toBeNull();
  });
});

describe("tokens de versiones anteriores", () => {
  it("se eliminan del navegador al cargar la aplicación", async () => {
    const { vi } = await import("vitest");
    sessionStorage.setItem("token", "viejo-corto");
    localStorage.setItem("token", "viejo-largo");

    vi.resetModules();
    await import("./session");

    expect(sessionStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("token")).toBeNull();
  });
});

describe("respaldos clínicos de la pestaña", () => {
  it("se borran al cerrar sesión (clearToken), sin tocar otras claves", () => {
    sessionStorage.setItem("odontonet:periodontal-draft:7", "{}");
    sessionStorage.setItem("otra-clave", "x");
    clearToken();
    expect(sessionStorage.getItem("odontonet:periodontal-draft:7")).toBeNull();
    expect(sessionStorage.getItem("otra-clave")).toBe("x");
  });
});
