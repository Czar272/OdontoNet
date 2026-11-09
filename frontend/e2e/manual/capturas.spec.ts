/**
 * Capturas del manual de usuario (ODON-242): recorre las pantallas de cada
 * rol y guarda las imágenes en docs/manual/img/. Trabaja sobre la base E2E
 * con el seed sintético; los datos clínicos de ejemplo se crean aquí por la
 * API y las fotografías son imágenes generadas, nunca reales.
 *
 * No es una prueba de regresión: se ejecuta aparte con `npm run manual:capturas`.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import {
  expect,
  request,
  test,
  type APIRequestContext,
  type Browser,
  type Locator,
  type Page,
} from "@playwright/test";

import { API_URL, FRONTEND_DIR, SEED_PASSWORD } from "../support/entorno";
import { DOCTORA_NORTE, USUARIOS, iniciarSesion, menu } from "../support/helpers";

const IMG_DIR = path.resolve(FRONTEND_DIR, "..", "docs", "manual", "img");
const ZONA_CLINICA = "America/Guatemala";
const DESPLAZAMIENTO_CLINICA = "-06:00";
const DIA_MS = 24 * 60 * 60 * 1000;
const HORA_CITA_DETALLE = "08:00";

interface Paciente {
  id: number;
  first_name: string;
  last_name: string;
}

interface Doctor {
  id: number;
  user: { name: string };
}

/** Datos preparados antes de las capturas. */
let paciente: Paciente;

/** Cliente de la API con sesión de un usuario demo, solo para preparar datos. */
class ApiDemo {
  private readonly contexto: APIRequestContext;
  private readonly encabezados: Record<string, string>;

  private constructor(contexto: APIRequestContext, encabezados: Record<string, string>) {
    this.contexto = contexto;
    this.encabezados = encabezados;
  }

  static async abrir(email: string): Promise<ApiDemo> {
    const contexto = await request.newContext({ baseURL: API_URL });
    const login = await contexto.post("/auth/login", {
      data: { email, password: SEED_PASSWORD },
    });
    expect(login.ok(), "login de la API para preparar datos").toBeTruthy();
    const { access_token } = (await login.json()) as { access_token: string };
    return new ApiDemo(contexto, { Authorization: `Bearer ${access_token}` });
  }

  async get<T>(ruta: string): Promise<T> {
    const respuesta = await this.contexto.get(ruta, { headers: this.encabezados });
    expect(respuesta.ok(), `GET ${ruta}: ${respuesta.status()}`).toBeTruthy();
    return (await respuesta.json()) as T;
  }

  async post<T>(ruta: string, data: unknown): Promise<T> {
    const respuesta = await this.contexto.post(ruta, { data, headers: this.encabezados });
    expect(respuesta.ok(), `POST ${ruta}: ${respuesta.status()} ${await respuesta.text()}`).toBeTruthy();
    return (await respuesta.json()) as T;
  }

  async subirImagen(ruta: string, nombre: string, contenido: Buffer, campos: Record<string, string>): Promise<void> {
    const respuesta = await this.contexto.post(ruta, {
      headers: this.encabezados,
      multipart: { ...campos, file: { name: nombre, mimeType: "image/png", buffer: contenido } },
    });
    expect(respuesta.ok(), `subida de imagen: ${respuesta.status()} ${await respuesta.text()}`).toBeTruthy();
  }

  async cerrar(): Promise<void> {
    await this.contexto.dispose();
  }
}

/** Fecha (YYYY-MM-DD) en la zona de la clínica, desplazada en días. */
function fechaClinica(dias = 0): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: ZONA_CLINICA }).format(new Date(Date.now() + dias * DIA_MS));
}

function diaDeSemanaClinica(): string {
  return new Intl.DateTimeFormat("en-US", { timeZone: ZONA_CLINICA, weekday: "short" }).format(new Date());
}

function horaClinica(): number {
  return Number(
    new Intl.DateTimeFormat("en-US", { timeZone: ZONA_CLINICA, hour: "numeric", hourCycle: "h23" }).format(new Date()),
  );
}

/** El lunes siguiente en la zona de la clínica: la agenda demo llega hasta ahí. */
function proximoLunes(): string {
  const dias = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return fechaClinica(7 - dias.indexOf(diaDeSemanaClinica()));
}

const PIEZAS = [
  18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28,
  48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38,
];
const SITIOS = ["mb", "b", "db", "ml", "l", "dl"];
/** Piezas con bolsas en el examen inicial, que mejoran en el control. */
const PIEZAS_PROFUNDAS = new Set([16, 26, 36, 46]);

function dientesDemo(etapa: "inicial" | "control" | "borrador") {
  const piezas = etapa === "borrador" ? PIEZAS.slice(0, 16) : PIEZAS;
  return piezas.map((tooth) => {
    if (tooth === 18 || tooth === 28) return { tooth, missing: true };
    return {
      tooth,
      sites: Object.fromEntries(
        SITIOS.map((site, indice) => {
          const base = 2 + ((tooth + indice) % 2);
          const profunda = PIEZAS_PROFUNDAS.has(tooth) && (indice === 0 || indice === 2);
          const sondaje = !profunda ? base : etapa === "inicial" ? 6 : 4;
          return [
            site,
            {
              probing_depth: sondaje,
              gingival_margin: 0,
              bleeding: etapa !== "control" && profunda,
              suppuration: false,
              plaque: etapa !== "control" && indice === 1,
            },
          ];
        }),
      ),
    };
  });
}

/** Fotografía de ejemplo: un dibujo generado, sin ningún dato real. */
async function imagenDeEjemplo(browser: Browser, color: string, rotulo: string): Promise<Buffer> {
  const pagina = await browser.newPage();
  // Como texto: este proyecto de TypeScript no incluye los tipos del DOM.
  const dataUrl = await pagina.evaluate<string>(`(() => {
    const lienzo = document.createElement("canvas");
    lienzo.width = 640;
    lienzo.height = 480;
    const ctx = lienzo.getContext("2d");
    ctx.fillStyle = ${JSON.stringify(color)};
    ctx.fillRect(0, 0, 640, 480);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 36px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Imagen de ejemplo", 320, 225);
    ctx.font = "24px sans-serif";
    ctx.fillText(${JSON.stringify(rotulo)}, 320, 275);
    return lienzo.toDataURL("image/png");
  })()`);
  await pagina.close();
  return Buffer.from(dataUrl.split(",")[1], "base64");
}

/** Crea el expediente de ejemplo de un paciente del seed y deja citas para hoy. */
async function prepararDatos(browser: Browser): Promise<void> {
  const doctora = await ApiDemo.abrir(USUARIOS.doctorNorte);
  const admin = await ApiDemo.abrir(USUARIOS.adminNorte);
  try {
    const encontrados = await doctora.get<{ items: Paciente[] }>("/patients/?q=paciente02.norte");
    expect(encontrados.items).toHaveLength(1);
    paciente = encontrados.items[0];
    const base = `/patients/${paciente.id}`;

    const doctores = await doctora.get<Doctor[]>("/doctors/");
    const ana = doctores.find((doctor) => doctor.user.name === DOCTORA_NORTE) as Doctor;

    await doctora.post(`${base}/medical-history`, {
      conditions: {
        diabetes: { present: false },
        hypertension: { present: true, detail: "Controlada con medicamento" },
      },
      allergies: "Penicilina",
      current_medications: "Losartán 50 mg al día",
      smoking_status: "never",
      alcohol: false,
      bruxism: true,
      chief_complaint: "Sangrado de encías al cepillarse",
      last_dental_visit: "Hace 2 años",
      brushing_per_day: 2,
      uses_floss: false,
      gum_bleeding: true,
    });

    const consulta = async (dias: number, reason: string, extra: Record<string, string>) =>
      doctora.post<{ id: number }>(`${base}/visits`, {
        visit_at: `${fechaClinica(dias)}T10:00:00${DESPLAZAMIENTO_CLINICA}`,
        doctor_id: ana.id,
        reason,
        ...extra,
      });
    const primera = await consulta(-180, "Evaluación inicial", {
      findings: "Inflamación gingival generalizada; cálculo en sector anterior inferior.",
      diagnosis: "Criterio profesional registrado por la doctora tratante.",
      instructions: "Técnica de cepillado e hilo dental diario.",
    });
    await consulta(-30, "Control", {
      findings: "Mejor control de placa.",
      procedures: "Profilaxis.",
      instructions: "Control en 6 meses.",
    });

    const tratamiento = async (procedure: string, tooth: number | null, planned_date: string | null) =>
      doctora.post<{ id: number }>(`${base}/treatments`, { procedure, tooth, planned_date });
    await tratamiento("Resina compuesta", 36, fechaClinica(21));
    const aceptado = await tratamiento("Raspado y alisado radicular", null, fechaClinica(10));
    await doctora.post(`${base}/treatments/${aceptado.id}/status`, { status: "accepted" });
    const completado = await tratamiento("Profilaxis", null, null);
    await doctora.post(`${base}/treatments/${completado.id}/status`, { status: "accepted" });
    await doctora.post(`${base}/treatments/${completado.id}/status`, {
      status: "completed",
      completed_visit_id: primera.id,
    });

    await doctora.post(`${base}/photo-consent`, {
      granted: true,
      research_use: false,
      signed_on: fechaClinica(-180),
      notes: "Formulario archivado en recepción",
    });
    await doctora.subirImagen(`${base}/images`, "ejemplo-frontal.png", await imagenDeEjemplo(browser, "#0f766e", "Vista frontal"), {
      origin: "intraoral_camera",
      view: "frontal",
      taken_on: fechaClinica(-180),
    });
    await doctora.subirImagen(`${base}/images`, "ejemplo-detalle.png", await imagenDeEjemplo(browser, "#1d4ed8", "Detalle de pieza 36"), {
      origin: "phone",
      view: "detail",
      taken_on: fechaClinica(-30),
      tooth: "36",
    });

    const examen = async (dias: number, etapa: "inicial" | "control" | "borrador", finalizar: boolean) => {
      const creado = await doctora.post<{ id: number; revision: number }>(`${base}/periodontal-exams`, {
        exam_date: fechaClinica(dias),
        clinical_visit_id: null,
        notes: null,
        teeth: dientesDemo(etapa),
      });
      if (finalizar) {
        await doctora.post(`${base}/periodontal-exams/${creado.id}/finalize`, { base_revision: creado.revision });
      }
    };
    await examen(-180, "inicial", true);
    await examen(-30, "control", true);
    await examen(0, "borrador", false);

    // Cita propia para el detalle: las del seed llevan una nota técnica en su historial.
    await admin.post("/appointments/", {
      patient_id: paciente.id,
      doctor_id: ana.id,
      starts_at: `${proximoLunes()}T${HORA_CITA_DETALLE}:00${DESPLAZAMIENTO_CLINICA}`,
      duration_minutes: 30,
      reason: "Control",
    });

    // El seed no agenda fines de semana: sin esto, «Agenda de hoy» saldría vacía.
    const hora = horaClinica();
    if ((diaDeSemanaClinica() === "Sat" || diaDeSemanaClinica() === "Sun") && hora <= 20) {
      const { items } = await admin.get<{ items: Paciente[] }>("/patients/?page_size=6");
      for (let i = 0; i < 3; i++) {
        await admin.post("/appointments/", {
          patient_id: items[i + 3].id,
          doctor_id: doctores[i % doctores.length].id,
          starts_at: `${fechaClinica()}T${String(hora + 1 + i).padStart(2, "0")}:00:00${DESPLAZAMIENTO_CLINICA}`,
          duration_minutes: 30,
          reason: "Control",
          allow_outside_schedule: true,
        });
      }
    }
  } finally {
    await doctora.cerrar();
    await admin.cerrar();
  }
}

/** Guarda la captura cuando la pantalla terminó de cargar. */
async function capturar(
  page: Page,
  nombre: string,
  opciones: { paginaCompleta?: boolean; elemento?: Locator } = {},
): Promise<void> {
  await page.mouse.move(0, 0);
  await page.waitForLoadState("networkidle");
  const destino = path.join(IMG_DIR, `${nombre}.png`);
  if (opciones.elemento) {
    await opciones.elemento.screenshot({ path: destino, animations: "disabled" });
  } else {
    await page.screenshot({ path: destino, animations: "disabled", fullPage: opciones.paginaCompleta ?? false });
  }
}

/** Inicia sesión y espera a que se vaya el saludo, que tapa la parte superior. */
async function entrar(page: Page, email: string): Promise<void> {
  await iniciarSesion(page, email);
  await expect(page.getByText(/^Bienvenido, /)).toBeHidden();
}

async function irAlMenu(page: Page, opcion: string, titulo = opcion): Promise<void> {
  await menu(page).getByRole("link", { name: opcion, exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: titulo })).toBeVisible();
}

function pestana(page: Page, nombre: string): Locator {
  return page.getByRole("tablist", { name: "Secciones del expediente" }).getByRole("tab", { name: nombre, exact: true });
}

async function abrirFicha(page: Page, pestanaInicial?: string): Promise<void> {
  await page.goto(`/patients/${paciente.id}${pestanaInicial ? `?tab=${pestanaInicial}` : ""}`);
  await expect(page.getByRole("heading", { level: 1, name: `${paciente.first_name} ${paciente.last_name}` })).toBeVisible();
}

function nombrePaciente(): string {
  return `${paciente.first_name} ${paciente.last_name}`;
}

/** Calendario en la semana siguiente, donde están las citas futuras del seed. */
async function agendaSemanaSiguiente(page: Page): Promise<void> {
  await irAlMenu(page, "Agenda");
  await page.getByRole("button", { name: "Semana siguiente" }).click();
  await expect(page.locator(".fc-event").first()).toBeVisible();
  // El manual explica el sombreado de las horas fuera de horario.
  await expect(page.locator(".fc-non-business").first()).toBeAttached();
}

async function esperarGraficos(page: Page): Promise<void> {
  await expect(page.locator(".recharts-surface").first()).toBeVisible();
  // Recharts anima las barras al aparecer.
  await page.waitForTimeout(1800);
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  mkdirSync(IMG_DIR, { recursive: true });
  await prepararDatos(browser);
});

test("primeros pasos", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Correo electrónico").fill(USUARIOS.recepcionNorte);
  await page.getByLabel("Contraseña", { exact: true }).fill(SEED_PASSWORD);
  await capturar(page, "login");

  await page.getByRole("link", { name: "¿Olvidaste tu contraseña?" }).click();
  await page.getByLabel("Correo electrónico").fill(USUARIOS.recepcionNorte);
  await page.getByRole("button", { name: "Enviar enlace" }).click();
  await expect(page.getByText("pide a administración que te asigne")).toBeVisible();
  await capturar(page, "olvido-contrasena");

  await entrar(page, USUARIOS.recepcionNorte);
  await page.getByRole("link", { name: "Cambiar contraseña" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Cambiar contraseña" })).toBeVisible();
  await capturar(page, "cambiar-contrasena");
});

test("recepción", async ({ page }) => {
  await entrar(page, USUARIOS.recepcionNorte);
  await expect(page.getByRole("list", { name: "Indicadores" })).toBeVisible();
  await capturar(page, "recepcion-inicio");

  await agendaSemanaSiguiente(page);
  await capturar(page, "recepcion-agenda", { paginaCompleta: true });

  await page.getByRole("button", { name: "Nueva cita" }).click();
  const nuevaCita = page.getByRole("dialog", { name: "Nueva cita" });
  await nuevaCita.getByLabel("Paciente *").fill(paciente.last_name);
  await nuevaCita
    .getByRole("list", { name: "Resultados de pacientes" })
    .getByRole("button", { name: new RegExp(nombrePaciente()) })
    .click();
  await nuevaCita.getByLabel("Doctor *").selectOption({ label: DOCTORA_NORTE });
  await nuevaCita.getByLabel("Fecha *").fill(proximoLunes());
  await nuevaCita.getByLabel("Hora *").fill("12:00");
  await nuevaCita.getByLabel("Duración").selectOption({ label: "30 min" });
  await nuevaCita.getByLabel("Motivo").fill("Control");
  await capturar(page, "recepcion-nueva-cita");
  await nuevaCita.getByRole("button", { name: "Cancelar" }).click();

  await page.locator(".fc-event").filter({ hasText: `${HORA_CITA_DETALLE} - ` }).first().click();
  const detalle = page.getByRole("dialog", { name: "Detalle de la cita" });
  await expect(detalle.getByRole("button", { name: "Reprogramar" })).toBeVisible();
  await capturar(page, "recepcion-detalle-cita");
  await detalle.getByRole("button", { name: "Cerrar" }).click();

  await page.getByRole("tab", { name: /Por confirmar/ }).click();
  await expect(page.getByRole("button", { name: /^Confirmar cita de/ }).first()).toBeVisible();
  await capturar(page, "recepcion-por-confirmar");

  await irAlMenu(page, "Pacientes");
  await capturar(page, "recepcion-pacientes");

  await page.getByRole("button", { name: "Nuevo paciente" }).click();
  const nuevoPaciente = page.getByRole("dialog", { name: "Nuevo paciente" });
  await nuevoPaciente.getByLabel("Nombres *").fill("Paciente");
  await nuevoPaciente.getByLabel("Apellidos *").fill("De Ejemplo");
  await nuevoPaciente.getByLabel("Teléfono").fill("55550000");
  await nuevoPaciente.getByLabel("Doctor asignado").selectOption({ label: DOCTORA_NORTE });
  await capturar(page, "recepcion-nuevo-paciente");
  await nuevoPaciente.getByRole("button", { name: "Cerrar" }).click();

  await abrirFicha(page);
  await expect(pestana(page, "Historia médica")).toBeVisible();
  await expect(pestana(page, "Consultas")).toHaveCount(0);
  await capturar(page, "recepcion-ficha");

  await pestana(page, "Historia médica").click();
  await expect(page.getByText("Solo lectura")).toBeVisible();
  await capturar(page, "recepcion-historia");

  await page.goto("/doctors");
  await expect(page.getByRole("heading", { level: 1, name: "Doctores" })).toBeVisible();
  await expect(page.getByRole("button", { name: `Horario de ${DOCTORA_NORTE}` })).toBeEnabled();
  await capturar(page, "recepcion-doctores");

  await page.getByRole("button", { name: `Horario de ${DOCTORA_NORTE}` }).click();
  await expect(page.getByRole("dialog", { name: `Horario de ${DOCTORA_NORTE}` })).toBeVisible();
  await capturar(page, "recepcion-horario");
  await page.getByRole("dialog", { name: `Horario de ${DOCTORA_NORTE}` }).getByRole("button", { name: "Cancelar" }).click();

  await irAlMenu(page, "Reportes");
  await esperarGraficos(page);
  await expect(page.getByRole("button", { name: "Exportar CSV" })).toHaveCount(0);
  await capturar(page, "recepcion-reportes", { paginaCompleta: true });

  await irAlMenu(page, "Clínica");
  await capturar(page, "recepcion-clinica");

  await page.goto("/audit");
  await expect(page.getByRole("heading", { level: 1, name: "Acceso denegado" })).toBeVisible();
  await capturar(page, "recepcion-acceso-denegado");
});

test("doctor", async ({ page }) => {
  await entrar(page, USUARIOS.doctorNorte);
  await expect(page.getByRole("list", { name: "Indicadores" })).toBeVisible();
  await capturar(page, "doctor-inicio");

  await agendaSemanaSiguiente(page);
  await capturar(page, "doctor-agenda", { paginaCompleta: true });

  await abrirFicha(page);
  await expect(pestana(page, "Periodontograma")).toBeVisible();
  await capturar(page, "doctor-ficha");

  await pestana(page, "Historia médica").click();
  await page.getByRole("button", { name: "Editar historia" }).click();
  await expect(page.getByRole("button", { name: "Guardar historia" })).toBeVisible();
  await capturar(page, "doctor-historia-edicion");
  await page.getByRole("button", { name: "Cancelar" }).click();

  await pestana(page, "Consultas").click();
  await expect(page.getByRole("list", { name: "Consultas" }).getByRole("listitem")).toHaveCount(2);
  await capturar(page, "doctor-consultas");

  await page.getByRole("button", { name: "Nueva consulta" }).click();
  const nuevaConsulta = page.getByRole("form", { name: "Nueva consulta" });
  await nuevaConsulta.getByLabel("Motivo de la consulta *").fill("Control de encías");
  await nuevaConsulta.getByLabel("Hallazgos / examen").fill("Encías sin sangrado al cepillado.");
  await capturar(page, "doctor-nueva-consulta");
  await nuevaConsulta.getByRole("button", { name: "Cancelar" }).click();

  await pestana(page, "Tratamientos").click();
  await expect(page.getByRole("list", { name: "Tratamientos pendientes" })).toBeVisible();
  await capturar(page, "doctor-tratamientos");

  await page.getByRole("button", { name: "Nuevo tratamiento" }).click();
  const nuevoTratamiento = page.getByRole("form", { name: "Nuevo tratamiento" });
  await nuevoTratamiento.getByLabel("Procedimiento *").fill("Resina compuesta");
  await nuevoTratamiento.getByLabel("Pieza dental (FDI)").fill("26");
  await capturar(page, "doctor-nuevo-tratamiento");
  await nuevoTratamiento.getByRole("button", { name: "Cancelar" }).click();

  await page.getByRole("button", { name: "Completar", exact: true }).first().click();
  const completar = page.getByRole("dialog", { name: "Completar tratamiento" });
  await expect(completar.getByLabel("Consulta en que se realizó *")).toBeVisible();
  await capturar(page, "doctor-completar-tratamiento");
  await completar.getByRole("button", { name: "Volver" }).click();

  await pestana(page, "Imágenes").click();
  await expect(page.getByRole("list", { name: "Fotografías del paciente" }).getByRole("listitem")).toHaveCount(2);
  await capturar(page, "doctor-imagenes", { paginaCompleta: true });

  await page.getByRole("button", { name: "Actualizar", exact: true }).click();
  const consentimiento = page.getByRole("dialog", { name: "Registrar consentimiento" });
  await expect(consentimiento.getByText("El paciente autoriza fotografías clínicas")).toBeVisible();
  await capturar(page, "doctor-consentimiento");
  await consentimiento.getByRole("button", { name: "Cancelar" }).click();

  await page.getByRole("list", { name: "Fotografías del paciente" }).getByRole("button").first().click();
  const visor = page.getByRole("dialog", { name: /^Fotografía 1 de 2/ });
  await expect(visor.getByRole("img")).toBeVisible();
  await visor.getByRole("button", { name: "Historial de cambios" }).scrollIntoViewIfNeeded();
  await capturar(page, "doctor-visor-imagen");
  await visor.getByRole("button", { name: "Cerrar" }).click();

  await pestana(page, "Periodontograma").click();
  const examenes = page.getByRole("list", { name: "Periodontogramas del paciente" });
  await expect(examenes.getByRole("listitem")).toHaveCount(3);
  await capturar(page, "doctor-periodontogramas");

  await page.getByRole("button", { name: "Nuevo periodontograma" }).click();
  const nuevoExamen = page.getByRole("dialog", { name: "Nuevo periodontograma" });
  await nuevoExamen.getByRole("radio", { name: /A partir del examen/ }).check();
  await capturar(page, "doctor-nuevo-periodontograma");
  await nuevoExamen.getByRole("button", { name: "Cancelar" }).click();

  await examenes.getByRole("button").first().click();
  await expect(page.getByRole("button", { name: "Guardar borrador" })).toBeVisible();
  await capturar(page, "doctor-periodontograma-borrador", { paginaCompleta: true });

  await page.getByRole("button", { name: "Llenar con valores de salud" }).click();
  const valoresSalud = page.getByRole("dialog", { name: "Llenar con valores de salud" });
  await expect(valoresSalud.getByRole("button", { name: "Llenar sitios vacíos" })).toBeVisible();
  await capturar(page, "doctor-valores-salud");
  await valoresSalud.getByRole("button", { name: "Cancelar" }).click();

  await page.getByRole("button", { name: "Finalizar", exact: true }).click();
  const finalizar = page.getByRole("dialog", { name: "Finalizar periodontograma" });
  await expect(finalizar).toBeVisible();
  await capturar(page, "doctor-finalizar-periodontograma");
  await finalizar.getByRole("button", { name: "Cancelar" }).click();

  await page.getByRole("button", { name: "Periodontogramas", exact: true }).click();
  await examenes.getByRole("button").nth(1).click();
  await expect(page.getByRole("button", { name: "Descargar PDF" })).toBeVisible();
  await capturar(page, "doctor-periodontograma-finalizado", { paginaCompleta: true });
  await page.getByRole("button", { name: "Periodontogramas", exact: true }).click();

  await page.getByRole("button", { name: "Comparar" }).click();
  await expect(page.getByRole("region", { name: "Resumen comparado" })).toBeVisible();
  await capturar(page, "doctor-comparar-periodontogramas", { paginaCompleta: true });
  await page.getByRole("button", { name: "Periodontogramas", exact: true }).click();

  await pestana(page, "Historial").click();
  await expect(page.getByRole("list", { name: "Historial cronológico" })).toBeVisible();
  await capturar(page, "doctor-historial");

  await irAlMenu(page, "Doctores");
  await expect(page.getByRole("button", { name: `Horario de ${DOCTORA_NORTE}` })).toBeEnabled();
  await page.getByRole("button", { name: `Horario de ${DOCTORA_NORTE}` }).click();
  await expect(page.getByRole("dialog", { name: `Horario de ${DOCTORA_NORTE}` }).getByRole("button", { name: "Guardar horario" })).toBeVisible();
  await page.getByRole("button", { name: "Guardar horario" }).scrollIntoViewIfNeeded();
  await capturar(page, "doctor-horario");
  await page.getByRole("dialog", { name: `Horario de ${DOCTORA_NORTE}` }).getByRole("button", { name: "Cancelar" }).click();

  await irAlMenu(page, "Reportes");
  await esperarGraficos(page);
  await capturar(page, "doctor-reportes");

  await irAlMenu(page, "Auditoría");
  await expect(page.getByRole("table", { name: "Eventos de auditoría" })).toBeVisible();
  await capturar(page, "doctor-auditoria");
});

test("administración", async ({ page }) => {
  await entrar(page, USUARIOS.adminNorte);
  await expect(page.getByRole("list", { name: "Indicadores" })).toBeVisible();
  await capturar(page, "admin-inicio");

  await irAlMenu(page, "Usuarios");
  await expect(page.getByRole("cell", { name: DOCTORA_NORTE, exact: true })).toBeVisible();
  await capturar(page, "admin-usuarios");

  await page.getByRole("button", { name: "Nuevo usuario" }).click();
  const nuevoUsuario = page.getByRole("dialog", { name: "Nuevo usuario" });
  await nuevoUsuario.getByLabel("Nombre completo *").fill("Personal De Ejemplo");
  await nuevoUsuario.getByLabel("Correo electrónico *").fill("personal.ejemplo@odontonet-demo.com");
  await nuevoUsuario.getByLabel("Rol *").selectOption({ label: "Recepción" });
  await capturar(page, "admin-nuevo-usuario");
  await nuevoUsuario.getByRole("button", { name: "Cerrar" }).click();

  await page.getByRole("button", { name: `Editar ${DOCTORA_NORTE}` }).click();
  const editarUsuario = page.getByRole("dialog", { name: "Editar usuario" });
  await expect(editarUsuario.getByLabel("Nueva contraseña")).toBeVisible();
  await capturar(page, "admin-editar-usuario");
  await editarUsuario.getByRole("button", { name: "Cerrar" }).click();

  await page.getByRole("button", { name: `Desactivar ${DOCTORA_NORTE}` }).click();
  const desactivar = page.getByRole("dialog", { name: "Desactivar usuario" });
  await expect(desactivar).toBeVisible();
  await capturar(page, "admin-desactivar-usuario");
  await desactivar.getByRole("button", { name: "Cancelar" }).click();

  await irAlMenu(page, "Doctores");
  await expect(page.getByRole("button", { name: `Horario de ${DOCTORA_NORTE}` })).toBeEnabled();
  await capturar(page, "admin-doctores");

  await page.getByRole("button", { name: "Nuevo perfil" }).click();
  const nuevoPerfil = page.getByRole("dialog", { name: "Nuevo perfil de doctor" });
  await expect(nuevoPerfil.getByLabel("Usuario *")).toBeVisible();
  await capturar(page, "admin-nuevo-perfil");
  await nuevoPerfil.getByRole("button", { name: "Cerrar" }).click();

  await irAlMenu(page, "Clínica");
  await page.getByRole("button", { name: "Editar datos" }).click();
  await expect(page.getByRole("button", { name: "Guardar cambios" })).toBeVisible();
  await capturar(page, "admin-clinica");
  await page.getByRole("button", { name: "Cancelar" }).click();

  await irAlMenu(page, "Reportes");
  await esperarGraficos(page);
  await capturar(page, "admin-reportes", { paginaCompleta: true });

  const descarga = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).first().click();
  expect((await descarga).suggestedFilename()).toMatch(/^reporte-citas-.*\.csv$/);

  await irAlMenu(page, "Auditoría");
  const auditoria = page.getByRole("table", { name: "Eventos de auditoría" });
  await expect(auditoria.getByText("Exportó un reporte (CSV)").first()).toBeVisible();
  await capturar(page, "admin-auditoria");

  await abrirFicha(page, "imagenes");
  await page.getByRole("list", { name: "Fotografías del paciente" }).getByRole("button").first().click();
  const visor = page.getByRole("dialog", { name: /^Fotografía 1 de 2/ });
  await visor.getByRole("button", { name: "Accesos" }).click();
  await expect(visor.getByRole("list", { name: "Accesos al original" })).toBeVisible();
  await capturar(page, "admin-accesos-imagen");
});
