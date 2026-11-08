/**
 * Preparación de la corrida E2E (ODON-214): base nueva en cada corrida.
 *
 * 1. Borra y recrea `odontonet_e2e_test` (docker exec en local; psql contra
 *    el servicio en CI con E2E_DB_MODE=service).
 * 2. Aplica las migraciones con `alembic upgrade head`.
 * 3. Carga el seed sintético con la contraseña ficticia de E2E.
 *
 * Una base nueva por corrida también reinicia el límite de intentos de login.
 * Nota: Playwright arranca los webServer antes de este paso; el backend no
 * abre conexiones hasta la primera petición con base de datos (su señal de
 * arranque es `/`, que no la usa), así que no estorba al recrearla.
 */
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";

import {
  BACKEND_DIR,
  DB_CONTAINER,
  DB_MODE,
  E2E_DB_NAME,
  IMAGE_STORAGE_DIR,
  SEED_PASSWORD,
  databaseUrlE2E,
  entornoBackend,
  pythonDelBackend,
} from "./support/entorno";

interface Paso {
  descripcion: string;
  comando: string;
  args: string[];
  cwd?: string;
  env?: Record<string, string>;
}

function ejecutar({ descripcion, comando, args, cwd, env }: Paso): void {
  const resultado = spawnSync(comando, args, {
    cwd,
    env: { ...process.env, ...env },
    encoding: "utf-8",
    timeout: 180_000,
  });

  if (resultado.error || resultado.status !== 0) {
    // Solo la salida del proceso: nunca la URL ni la contraseña de la base.
    const salida = [resultado.stdout, resultado.stderr]
      .filter(Boolean)
      .join("\n")
      .trim();
    const motivo = resultado.error
      ? resultado.error.message
      : `código de salida ${resultado.status}`;
    throw new Error(
      `E2E: falló «${descripcion}» (${motivo}).${salida ? `\n${salida}` : ""}`,
    );
  }
}

/** Defensa extra: jamás tocar una base que no sea la de E2E. */
// Comprobación redundante (la URL ya se arma con E2E_DB_NAME y dropdb/createdb usan
// esa constante): deja explícito que solo se recrea una base de pruebas.
function verificarNombre(url: URL): void {
  const nombre = url.pathname.replace(/^\//, "");
  if (nombre !== E2E_DB_NAME || !nombre.endsWith("_test") || url.searchParams.has("dbname")) {
    throw new Error(`E2E: base inesperada «${nombre}»; se esperaba ${E2E_DB_NAME}.`);
  }
}

function recrearBase(url: URL): void {
  const usuario = decodeURIComponent(url.username);

  if (DB_MODE === "service") {
    // CI: psql contra el servicio postgres del job (credenciales desechables).
    const comun = [
      "-h", url.hostname,
      "-p", url.port || "5432",
      "-U", usuario,
      "-d", "postgres",
      "-v", "ON_ERROR_STOP=1",
    ];
    const env = { PGPASSWORD: decodeURIComponent(url.password) };
    ejecutar({
      descripcion: "borrar la base E2E (psql)",
      comando: "psql",
      args: [...comun, "-c", `DROP DATABASE IF EXISTS "${E2E_DB_NAME}" WITH (FORCE)`],
      env,
    });
    ejecutar({
      descripcion: "crear la base E2E (psql)",
      comando: "psql",
      args: [...comun, "-c", `CREATE DATABASE "${E2E_DB_NAME}"`],
      env,
    });
    return;
  }

  // Local: dentro del contenedor de desarrollo, sin exponer la contraseña.
  ejecutar({
    descripcion: `borrar la base E2E (docker exec ${DB_CONTAINER})`,
    comando: "docker",
    args: ["exec", DB_CONTAINER, "dropdb", "-U", usuario, "--if-exists", "--force", E2E_DB_NAME],
  });
  ejecutar({
    descripcion: `crear la base E2E (docker exec ${DB_CONTAINER})`,
    comando: "docker",
    args: ["exec", DB_CONTAINER, "createdb", "-U", usuario, E2E_DB_NAME],
  });
}

export default function globalSetup(): void {
  const url = new URL(databaseUrlE2E());
  verificarNombre(url);

  recrearBase(url);

  const python = pythonDelBackend();
  const env = entornoBackend();

  ejecutar({
    descripcion: "alembic upgrade head",
    comando: python,
    args: ["-m", "alembic", "upgrade", "head"],
    cwd: BACKEND_DIR,
    env,
  });

  // El seed conserva sus comprobaciones: APP_ENV=development, base local
  // (127.0.0.1 o localhost) y SEED_PASSWORD con la política de contraseñas.
  ejecutar({
    descripcion: "seed de demostración (scripts.seed_dev)",
    comando: python,
    args: ["-m", "scripts.seed_dev"],
    cwd: BACKEND_DIR,
    env: { ...env, SEED_PASSWORD },
  });

  mkdirSync(IMAGE_STORAGE_DIR, { recursive: true });
}
