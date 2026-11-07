import { afterEach, describe, expect, it } from "vitest";

import {
  clearToken,
  getToken,
  isRememberedSession,
  replaceToken,
  setToken,
} from "./session";

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

  it("replaceToken conserva una sesión con Recuérdame en localStorage", () => {
    setToken("largo", true);

    expect(isRememberedSession()).toBe(true);
    replaceToken("nuevo-largo");

    expect(localStorage.getItem("token")).toBe("nuevo-largo");
    expect(sessionStorage.getItem("token")).toBeNull();
  });

  it("replaceToken conserva una sesión corta en sessionStorage", () => {
    setToken("corto");

    expect(isRememberedSession()).toBe(false);
    replaceToken("nuevo-corto");

    expect(sessionStorage.getItem("token")).toBe("nuevo-corto");
    expect(localStorage.getItem("token")).toBeNull();
  });
});

describe("respaldos clínicos de la pestaña", () => {
  it("se borran al cerrar sesión (clearToken), sin tocar otras claves", async () => {
    const { clearToken } = await import("./session");
    sessionStorage.setItem("odontonet:periodontal-draft:7", "{}");
    sessionStorage.setItem("otra-clave", "x");
    clearToken();
    expect(sessionStorage.getItem("odontonet:periodontal-draft:7")).toBeNull();
    expect(sessionStorage.getItem("otra-clave")).toBe("x");
  });
});
