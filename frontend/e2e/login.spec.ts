import { expect, test } from "@playwright/test";

import {
  CLINICA_NORTE,
  USUARIOS,
  crearPacienteApi,
  iniciarSesion,
  menu,
  sufijoUnico,
} from "./support/helpers";

test.describe("Inicio de sesión", () => {
  test("administración inicia sesión y ve Inicio con su clínica", async ({ page }) => {
    await iniciarSesion(page, USUARIOS.adminNorte);

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByTestId("clinic-name")).toHaveText(CLINICA_NORTE);
    await expect(page.getByTestId("current-user")).toContainText("Administración");
    for (const opcion of ["Agenda", "Pacientes", "Usuarios", "Auditoría"]) {
      await expect(menu(page).getByRole("link", { name: opcion })).toBeVisible();
    }
  });

  test("la sesión sobrevive a una recarga sin dejar tokens legibles y cerrarla la revoca", async ({
    page,
    context,
  }) => {
    await iniciarSesion(page, USUARIOS.doctorNorte);

    const almacenado = await page.evaluate(() => ({
      local: localStorage.getItem("token"),
      sesion: sessionStorage.getItem("token"),
    }));
    expect(almacenado).toEqual({ local: null, sesion: null });
    const [cookie] = (await context.cookies()).filter((c) => c.name === "odontonet_session");
    expect(cookie).toMatchObject({ httpOnly: true, sameSite: "Strict", path: "/api/auth" });

    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "Inicio" })).toBeVisible();

    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    await expect(page.getByRole("button", { name: "Iniciar sesión" })).toBeVisible();

    // La cookie copiada antes de cerrar ya no sirve.
    await context.addCookies([cookie]);
    await page.goto("/dashboard");
    await expect(page.getByRole("button", { name: "Iniciar sesión" })).toBeVisible();
  });

  test("cerrar sesión en una pestaña también la cierra en las demás", async ({ page, context }) => {
    await iniciarSesion(page, USUARIOS.doctorNorte);
    const otra = await context.newPage();
    await otra.goto("/dashboard");
    await expect(otra.getByRole("heading", { level: 1, name: "Inicio" })).toBeVisible();

    await otra.getByRole("button", { name: "Cerrar sesión" }).click();

    await expect(otra.getByRole("button", { name: "Iniciar sesión" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Iniciar sesión" })).toBeVisible();
  });

  test("una contraseña incorrecta muestra el error en español", async ({ page }) => {
    // Un solo fallo por corrida, en una cuenta que ninguna otra prueba usa para iniciar sesión por la interfaz:
    // lejos del límite de 7 fallos por cuenta.
    await page.goto("/");
    await page.getByLabel("Correo electrónico").fill(USUARIOS.recepcionSur);
    await page.getByLabel("Contraseña", { exact: true }).fill("Incorrecta-123456");
    await page.getByRole("button", { name: "Iniciar sesión" }).click();

    await expect(page.getByText("Credenciales inválidas.")).toBeVisible();
    await expect(page).toHaveURL(/\/$/);
    // El formulario sigue disponible y la contraseña se borra.
    await expect(page.getByLabel("Contraseña", { exact: true })).toHaveValue("");
  });

  test("recepción no ve opciones ni pestañas clínicas", async ({ page }, testInfo) => {
    const apellido = `Recepcion ${sufijoUnico(testInfo)}`;
    const pacienteId = await crearPacienteApi(USUARIOS.adminNorte, {
      first_name: "Paciente",
      last_name: apellido,
    });

    await iniciarSesion(page, USUARIOS.recepcionNorte);
    await expect(page.getByTestId("current-user")).toContainText("Recepción");

    // Menú según docs/PERMISSIONS.md: sin Usuarios ni Auditoría.
    for (const opcion of ["Inicio", "Agenda", "Pacientes", "Doctores", "Reportes", "Clínica"]) {
      await expect(menu(page).getByRole("link", { name: opcion })).toBeVisible();
    }
    for (const opcion of ["Usuarios", "Auditoría"]) {
      await expect(menu(page).getByRole("link", { name: opcion })).toHaveCount(0);
    }

    // Ficha del paciente: solo datos generales e historia médica (lectura).
    await page.goto(`/patients/${pacienteId}`);
    await expect(page.getByRole("heading", { level: 1, name: `Paciente ${apellido}` })).toBeVisible();
    const pestanas = page.getByRole("tablist", { name: "Secciones del expediente" });
    await expect(pestanas.getByRole("tab")).toHaveText(["Datos generales", "Historia médica"]);
    for (const clinica of ["Consultas", "Tratamientos", "Imágenes", "Periodontograma", "Historial"]) {
      await expect(pestanas.getByRole("tab", { name: clinica })).toHaveCount(0);
    }
  });

  test("cerrar sesión vuelve al login y protege las rutas", async ({ page }) => {
    await iniciarSesion(page, USUARIOS.adminNorte);

    await page.getByRole("button", { name: "Cerrar sesión" }).click();

    await expect(page.getByRole("button", { name: "Iniciar sesión" })).toBeVisible();
    await expect(page.getByText("Sesión cerrada")).toBeVisible();

    // Sin sesión, una ruta protegida lleva al login.
    await page.goto("/patients");
    await expect(page.getByRole("button", { name: "Iniciar sesión" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Pacientes" })).toHaveCount(0);
  });
});
