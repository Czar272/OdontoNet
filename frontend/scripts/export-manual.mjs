/**
 * Exporta el manual de usuario a PDF (ODON-242): convierte cada Markdown de
 * docs/manual/ con marked y lo imprime con el Chromium de Playwright en
 * docs/manual/pdf/. Las capturas se incrustan en el HTML; si falta alguna, falla.
 * Uso, desde frontend/: npm run manual:pdf
 */
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";
import { Marked } from "marked";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const MANUAL_DIR = path.resolve(AQUI, "..", "..", "docs", "manual");
const PDF_DIR = path.join(MANUAL_DIR, "pdf");

const ESTILOS = `
  @page { size: A4; margin: 18mm 16mm 20mm; }
  body { font-family: "Segoe UI", Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #111827; }
  h1 { font-size: 22pt; margin: 0 0 12pt; }
  h2 { font-size: 15pt; margin: 18pt 0 6pt; border-bottom: 1px solid #d1d5db; padding-bottom: 3pt; break-after: avoid; }
  h3 { font-size: 12pt; margin: 12pt 0 4pt; break-after: avoid; }
  ul, ol { padding-left: 18pt; }
  li { margin: 2pt 0; }
  code { font-family: Consolas, monospace; font-size: 10pt; }
  blockquote { margin: 8pt 0; padding: 6pt 10pt; background: #f3f4f6; border-left: 3pt solid #6b7280; }
  blockquote p { margin: 0; }
  table { border-collapse: collapse; width: 100%; font-size: 10pt; margin: 8pt 0; }
  th, td { border: 1px solid #d1d5db; padding: 4pt 6pt; text-align: left; }
  th { background: #f3f4f6; }
  img { display: block; max-width: 100%; max-height: 235mm; margin: 8pt auto; border: 1px solid #d1d5db; break-inside: avoid; }
  a { color: #1d4ed8; }
`;

function mimeDe(archivo) {
  const extension = path.extname(archivo).toLowerCase();
  if (extension === ".png") return "image/png";
  if (extension === ".jpg" || extension === ".jpeg") return "image/jpeg";
  throw new Error(`Formato de imagen no admitido en el manual: ${archivo}`);
}

function imagenComoDataUri(href, documento) {
  const archivo = path.resolve(MANUAL_DIR, href);
  if (!existsSync(archivo)) {
    throw new Error(`${documento}: no existe la captura ${href}. Corre primero npm run manual:capturas.`);
  }
  return `data:${mimeDe(archivo)};base64,${readFileSync(archivo).toString("base64")}`;
}

function esExterno(href) {
  return /^(https?:|mailto:)/i.test(href);
}

function aHtml(markdown, documento) {
  const parser = new Marked({
    walkTokens(token) {
      if (token.type === "image" && !token.href.startsWith("data:")) {
        token.href = imagenComoDataUri(token.href, documento);
      }
    },
    renderer: {
      link(token) {
        const texto = this.parser.parseInline(token.tokens);
        if (esExterno(token.href) || token.href.startsWith("#")) {
          return `<a href="${token.href}">${texto}</a>`;
        }
        const destino = path.resolve(MANUAL_DIR, token.href);
        // Dentro del manual, el enlace apunta al PDF hermano; lo demás queda como texto.
        return path.dirname(destino) === MANUAL_DIR && destino.endsWith(".md")
          ? `<a href="${path.basename(destino, ".md")}.pdf">${texto}</a>`
          : texto;
      },
    },
  });
  return parser.parse(markdown);
}

async function main() {
  const documentos = readdirSync(MANUAL_DIR)
    .filter((nombre) => nombre.toLowerCase().endsWith(".md"))
    .sort();
  if (documentos.length === 0) throw new Error(`No hay archivos Markdown en ${MANUAL_DIR}.`);

  mkdirSync(PDF_DIR, { recursive: true });
  const navegador = await chromium.launch();
  try {
    const pagina = await navegador.newPage();
    for (const documento of documentos) {
      const markdown = readFileSync(path.join(MANUAL_DIR, documento), "utf-8");
      const titulo = markdown.match(/^#\s+(.+)$/m)?.[1] ?? documento;
      const html = `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${titulo}</title><style>${ESTILOS}</style></head><body>${aHtml(markdown, documento)}</body></html>`;

      await pagina.setContent(html, { waitUntil: "load" });
      const destino = path.join(PDF_DIR, `${path.basename(documento, ".md")}.pdf`);
      await pagina.pdf({
        path: destino,
        format: "A4",
        printBackground: true,
        preferCSSPageSize: true,
        displayHeaderFooter: true,
        headerTemplate: "<span></span>",
        footerTemplate: `<div style="width:100%;font-size:8pt;color:#6b7280;padding:0 16mm;display:flex;justify-content:space-between;font-family:Arial,sans-serif;"><span>Manual de usuario de OdontoNet</span><span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>`,
      });
      console.log(`PDF generado: ${path.relative(MANUAL_DIR, destino)}`);
    }
  } finally {
    await navegador.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
