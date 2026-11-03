import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// Esperas de findBy*/waitFor: 1 s (el valor por defecto) no alcanza en equipos
// más lentos cuando hay debounce (300 ms) más el primer render de jsdom.
// Solo alarga el límite; una prueba que pasa no espera más de lo necesario.
configure({ asyncUtilTimeout: 5000 });

// Sin globals de Vitest, Testing Library no limpia el DOM automáticamente.
afterEach(() => {
  cleanup();
});
