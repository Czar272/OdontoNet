import { describe, expect, it } from "vitest";

import { formatBytes, todayLocal, validateImageFile } from "./imageUpload";

const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

describe("validateImageFile", () => {
  it.each(["foto.jpg", "FOTO.JPEG", "foto.png", "foto.webp"])("acepta %s", (name) => {
    expect(validateImageFile(file(name, 10))).toBeNull();
  });

  it.each(["foto.gif", "foto.bmp", "foto", "foto.jpg.exe"])("rechaza %s", (name) => {
    expect(validateImageFile(file(name, 10))).toMatch(/JPEG, PNG o WebP/);
  });

  it("rechaza archivos vacíos o de más de 10 MB", () => {
    expect(validateImageFile(file("foto.jpg", 0))).toMatch(/vacía/);
    expect(validateImageFile(file("foto.jpg", 10 * 1024 * 1024))).toBeNull();
    expect(validateImageFile(file("foto.jpg", 10 * 1024 * 1024 + 1))).toMatch(/10 MB/);
  });
});

describe("formatBytes y todayLocal", () => {
  it("formatea tamaños", () => {
    expect(formatBytes(200)).toBe("1 KB");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(3.5 * 1024 * 1024)).toBe("3.5 MB");
  });

  it("usa la fecha local", () => {
    expect(todayLocal(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});
