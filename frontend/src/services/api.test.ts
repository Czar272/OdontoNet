import type { AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";
import { AxiosError } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api, { refreshSession } from "./api";
import { clearToken, getToken, setToken, setUnauthorizedHandler } from "./session";

type Answer = { status: number; data?: unknown } | Error;

let calls: { url: string; authorization: unknown }[];
let answers: Record<string, Answer[]>;
const unauthorized = vi.fn();

function respond(config: InternalAxiosRequestConfig) {
  const url = config.url ?? "";
  calls.push({ url, authorization: config.headers.Authorization });
  const answer = answers[url]?.shift() ?? { status: 200, data: {} };

  if (answer instanceof Error) return Promise.reject(answer);

  const response = { data: undefined, ...answer, statusText: "", headers: {}, config };
  if (answer.status >= 400) {
    return Promise.reject(new AxiosError("error", undefined, config, undefined, response));
  }
  return Promise.resolve(response);
}

const newToken = { status: 200, data: { access_token: "renovado", user_id: 1 } };

beforeEach(() => {
  calls = [];
  answers = {};
  api.defaults.adapter = respond as AxiosRequestConfig["adapter"];
  setUnauthorizedHandler(unauthorized);
  setToken("vencido", 1);
});

afterEach(() => {
  clearToken();
  setUnauthorizedHandler(null);
  unauthorized.mockReset();
});

const urls = () => calls.map((call) => call.url);

describe("renovación de la sesión", () => {
  it("usa /api en el mismo origen por defecto", () => {
    expect(api.defaults.baseURL).toBe("/api");
  });

  it("ante un 401 renueva el token y repite la petición con el nuevo", async () => {
    answers["/patients"] = [{ status: 401 }, { status: 200, data: { ok: true } }];
    answers["/auth/refresh"] = [newToken];

    const response = await api.get("/patients");

    expect(response.data).toEqual({ ok: true });
    expect(urls()).toEqual(["/patients", "/auth/refresh", "/patients"]);
    expect(calls[2].authorization).toBe("Bearer renovado");
    expect(unauthorized).not.toHaveBeenCalled();
  });

  it("varias peticiones simultáneas comparten una sola renovación", async () => {
    answers["/a"] = [{ status: 401 }, { status: 200 }];
    answers["/b"] = [{ status: 401 }, { status: 200 }];
    answers["/auth/refresh"] = [newToken];

    await Promise.all([api.get("/a"), api.get("/b")]);

    expect(urls().filter((url) => url === "/auth/refresh")).toHaveLength(1);
  });

  it("si la sesión ya no es válida, avisa y rechaza", async () => {
    answers["/patients"] = [{ status: 401 }];
    answers["/auth/refresh"] = [{ status: 401 }];

    await expect(api.get("/patients")).rejects.toBeInstanceOf(AxiosError);

    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it("no sigue trabajando si la cookie ya es de otra cuenta", async () => {
    answers["/patients"] = [{ status: 401 }];
    answers["/auth/refresh"] = [{ status: 200, data: { access_token: "de-otra", user_id: 2 } }];

    await expect(api.get("/patients")).rejects.toBeInstanceOf(AxiosError);

    expect(unauthorized).toHaveBeenCalledTimes(1);
    expect(getToken()).toBe("vencido");
    expect(urls()).toEqual(["/patients", "/auth/refresh"]);
  });

  it("no reintenta en bucle si el token nuevo también es rechazado", async () => {
    answers["/patients"] = [{ status: 401 }, { status: 401 }];
    answers["/auth/refresh"] = [newToken];

    await expect(api.get("/patients")).rejects.toBeInstanceOf(AxiosError);

    expect(urls()).toEqual(["/patients", "/auth/refresh", "/patients"]);
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it("con el servidor inalcanzable no cierra la sesión", async () => {
    answers["/patients"] = [{ status: 401 }];
    answers["/auth/refresh"] = [new Error("sin red")];

    await expect(api.get("/patients")).rejects.toBeInstanceOf(AxiosError);

    expect(unauthorized).not.toHaveBeenCalled();
    expect(getToken()).toBe("vencido");
  });

  it.each(["/auth/login", "/auth/logout"])("%s no dispara una renovación", async (url) => {
    answers[url] = [{ status: 401 }];

    await expect(api.post(url)).rejects.toBeInstanceOf(AxiosError);

    expect(urls()).toEqual([url]);
    expect(unauthorized).not.toHaveBeenCalled();
  });

  it("refreshSession guarda el token y devuelve null sin sesión", async () => {
    answers["/auth/refresh"] = [newToken, { status: 401 }];

    await expect(refreshSession()).resolves.toBe("renovado");
    expect(getToken()).toBe("renovado");
    await expect(refreshSession()).resolves.toBeNull();
  });

  it("otros errores del refresh se propagan", async () => {
    answers["/auth/refresh"] = [{ status: 500 }];

    await expect(refreshSession()).rejects.toBeInstanceOf(AxiosError);
  });
});
